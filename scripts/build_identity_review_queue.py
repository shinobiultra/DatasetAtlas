#!/usr/bin/env python3
"""Turn every unresolved catalogue identity into a decision for a person. Read-only over the registry.

An entry whose `coverage.identity` is `candidate` or `family_or_variant_candidate` is mentioned by a paper under a name, but
the exact release, variant or subset the paper used is not human-verified. Only a person changes that (SPEC 4.5): this script
never edits a registry entry, never writes `coverage.identity`, `release`, `preview` or any other field, and offers no
recommendation. It lists what the registry already records so that a person can decide.

What it reads
- `registry/datasets/*.yaml`: scope (identity), links, access, names, blockers and evidence (the papers that mention an entry).
- `reports/dataset_coverage.csv`: the current `access`, `adapter` and `preview` of each entry as the merged catalogue reports
  them (a prepared version overrides the tracked YAML for adapter and preview). An entry the CSV lacks falls back to its YAML.

What it writes (and only this)
- `reports/identity_review_queue.md`: the human-readable queue.
- `work/corpus/review_queue.jsonl`: one appended `kind: identity_decision` record per group, never duplicated, existing lines
  untouched. The file is git-ignored.
- `registry/identity-review-ids.json`: `{group key: "IR-NNN"}`, written only when a group is seen for the first time.

Groups (deterministic, never by name similarity)
- Entries the registry links with `same_source_family_as`, `derived_from`, `annotation_overlay_of` or `source_subset_of` to the
  SAME target belong together (union-find over targets, so an entry linked to two targets joins them). The target may be a resolved
  entry that is not in the queue. An entry with no such link is its own group, keyed by its own id; an unlinked in-queue entry that
  others link to therefore joins them through that shared id.
- The group key is the sorted link targets (or the entry's id), joined by `|`.
- IDs are `IR-001`, `IR-002`, ... Unseen keys, in sorted-key order, take the next free numbers; an existing assignment is never
  renumbered or reused even if the group's membership changed. A group that grows a new link target gets a new key, and so a new id.

    python scripts/build_identity_review_queue.py [--root PATH] [--dry-run]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CREATED_BY = "build_identity_review_queue.py"
REGISTRY_DIR = "registry/datasets"
COVERAGE_CSV = "reports/dataset_coverage.csv"
IDS_FILE = "registry/identity-review-ids.json"
REPORT_FILE = "reports/identity_review_queue.md"
QUEUE_FILE = "work/corpus/review_queue.jsonl"

IDENTITY_SCOPE = frozenset({"candidate", "family_or_variant_candidate"})
LINK_TYPES = frozenset({"same_source_family_as", "derived_from", "annotation_overlay_of", "source_subset_of"})
GATED_ACCESS = frozenset({"gated", "request_required", "author_request_required"})
HOST_DOWN = re.compile(r"_host_(?:unresponsive|unresolvable)$")
BLOCKER_TYPES = ("identity", "access", "unreleased", "source_availability", "adapter")
EXCERPT_LIMIT = 200
ID_PATTERN = re.compile(r"IR-(\d+)")

INTRO = ("These are decisions for a person. Nothing in this file changes any registry record: `coverage.identity`, `release`, "
         "`preview`, `adapter` and every other field stay exactly as they are until a person records a decision. "
         "Recommendations are not acceptance, and no option below is ranked or preferred.")

LEGEND = (
    "- An entry is here because the registry records its `coverage.identity` as `candidate` or `family_or_variant_candidate`: a paper "
    "mentions the name, but the exact release, variant or subset the paper used is not human-verified. Every such entry appears exactly once.",
    "- Entries the registry already links with `same_source_family_as`, `derived_from`, `annotation_overlay_of` or `source_subset_of` "
    "to the same target share a group. Nothing is grouped by name similarity. A group is a reading aid: each entry is decided on its own.",
    "- Options. `alias_of:<id>`: the paper's name is another name for that registry entry. `distinct_release`: the paper's dataset is a "
    "release of its own. `accept_unreleased_custom_record`: a paper-private dataset with no public release, kept as an unreleased "
    "custom record. `keep_candidate`: leave the identity open.",
    "- Preview and adapter states come from `reports/dataset_coverage.csv`, the merged catalogue view; identity, links, access and "
    "evidence come from `registry/datasets/*.yaml`. A link to a prepared family is a pointer, never coverage: an entry whose "
    "preview is `none` stays `none` until a person decides.",
    "- Blocker types. `identity`: the exact release, variant or subset is not human-verified (a family alias or variant of another "
    "entry, or a name with no link). `access`: the data is gated or needs a request, which is a user action and not an identity "
    "question. `unreleased`: the registry records a paper-private dataset with no public release. `source_availability`: the "
    "registry's latest access audit records the source host as unresponsive or unresolvable. `adapter`: identity is settled and only an "
    "adapter is missing; such entries are outside this queue, so no entry below has this type.",
    "- IDs. `IR-NNN` comes from `registry/identity-review-ids.json`. An assignment is never renumbered or reused; a group seen for the "
    "first time takes the next free number.",
    "- Quoted lines (`>`) are text exactly as the registry stores it; paper excerpts are shortened to 200 characters.",
    "- Each group is also appended once to `work/corpus/review_queue.jsonl` as a `kind: identity_decision` record with `status: open`.",
)


@dataclass
class Link:
    type: str
    target: str


@dataclass
class Target:
    id: str
    identity: str
    preview: str
    in_queue: bool
    link_types: list[str] = field(default_factory=list)

    @property
    def prepared(self) -> bool:
        return self.preview not in ("none", "unknown")


@dataclass
class Paper:
    paper_id: str
    page: object
    role: str
    excerpt: str


@dataclass
class Member:
    id: str
    name: str
    identity: str
    access: str
    adapter: str
    preview: str
    blocker_type: str
    blocker_basis: str
    options: list[str]
    links: list[Link]
    papers: list[Paper]
    registry_blockers: list[str]
    description: str
    identity_audit: str


@dataclass
class Group:
    key: str
    nodes: list[str]
    members: list[Member]
    targets: list[Target]
    options: list[str]
    decision: list[str]
    id: str = ""


@dataclass
class QueueModel:
    groups: list[Group]
    ids: dict
    new_ids: int
    blocker_counts: dict
    preview_counts: dict
    appended: int = 0

    @property
    def entry_count(self) -> int:
        return sum(len(group.members) for group in self.groups)


# --- reading the registry (read-only) ----------------------------------------------------------------------------------

def _clean(value) -> str:
    return " ".join(str(value if value is not None else "").split())


def _clip(value, limit: int = EXCERPT_LIMIT) -> str:
    text = _clean(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def load_entries(registry_dir: Path) -> dict:
    entries = {}
    for path in sorted(Path(registry_dir).glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ValueError(f"{path.name}: not a dataset entry")
        if entry["id"] in entries:
            raise ValueError(f"Duplicate dataset ID {entry['id']}")
        entries[entry["id"]] = entry
    return entries


def load_state(csv_path: Path) -> dict:
    """The coverage CSV by dataset id; empty when the file is absent."""
    if not csv_path.is_file():
        return {}
    with csv_path.open(newline="", encoding="utf-8") as stream:
        return {row["dataset_id"]: row for row in csv.DictReader(stream)}


def _state(entry: dict, rows: dict, column: str) -> str:
    row = rows.get(entry["id"])
    if row and row.get(column):
        return row[column]
    return _clean((entry.get("coverage") or {}).get(column)) or "unknown"


def entry_links(entry: dict) -> list[Link]:
    """The registry's own links of the four grouping types, as (type, target); both `target` and `target_id` spellings exist."""
    found = {}
    for relation in entry.get("relationships") or []:
        if not isinstance(relation, dict) or relation.get("type") not in LINK_TYPES:
            continue
        target = _clean(relation.get("target") or relation.get("target_id"))
        if target and target != entry["id"]:
            found[(target, relation["type"])] = Link(relation["type"], target)
    return [found[key] for key in sorted(found)]


def _latest(entry: dict, kind: str):
    """The most recently checked evidence item of one kind (ties: the later one in the list)."""
    items = [(_clean(item.get("checked_on")), position, item) for position, item in enumerate(entry.get("evidence") or [])
             if isinstance(item, dict) and item.get("kind") == kind]
    return max(items, key=lambda found: (found[0], found[1]))[2] if items else None


def entry_papers(entry: dict) -> list[Paper]:
    """One entry per paper that mentions the dataset, with the first stored excerpt (clipped), in the registry's order."""
    papers = {}
    for item in entry.get("evidence") or []:
        if isinstance(item, dict) and item.get("kind") == "corpus_mention" and item.get("paper_id") and item["paper_id"] not in papers:
            papers[item["paper_id"]] = Paper(item["paper_id"], item.get("page"), _clean(item.get("role")), _clip(item.get("excerpt")))
    for paper_id in entry.get("paper_ids") or []:
        papers.setdefault(paper_id, Paper(paper_id, None, "", ""))
    return list(papers.values())


# --- groups ------------------------------------------------------------------------------------------------------------

def _host_down(entry: dict):
    """(status, checked_on) when the latest access audit records the source host as unresponsive or unresolvable."""
    audit = _latest(entry, "source_audit_access")
    status = _clean(audit.get("source_identity_status")) if audit else ""
    return (status, _clean(audit.get("checked_on"))) if HOST_DOWN.search(status) else None


def classify(access: str, host_down) -> str:
    """Precedence: a paper-private dataset, then an access gate, then a recorded host outage; otherwise identity."""
    if access == "unreleased":
        return "unreleased"
    if access in GATED_ACCESS:
        return "access"
    if host_down:
        return "source_availability"
    return "identity"


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _target_text(target: Target, link_types: list[str] | None = None) -> str:
    kinds = f" via {_and([f'`{kind}`' for kind in link_types])}" if link_types else ""
    return f"`{target.id}` (identity `{target.identity}`, preview `{target.preview}`){kinds}"


def _basis(blocker_type: str, access: str, links: list[Link], targets: dict, host_down) -> str:
    if blocker_type == "unreleased":
        return "Access is `unreleased`: the registry records a paper-private dataset with no public release."
    if blocker_type == "access":
        return (f"Access is `{access}`: getting the data needs a request, terms or credentials, which is a user action. "
                "The identity decision is separate from it.")
    if blocker_type == "source_availability":
        status, checked_on = host_down
        return (f"The registry's latest access audit ({checked_on}) records `{status}`: the source host did not answer or did not "
                "resolve. This is source availability, not identity.")
    if not links:
        return "No registry link to another entry; the exact release, variant or subset the paper used is not human-verified."
    by_target = {}
    for link in links:
        by_target.setdefault(link.target, []).append(link.type)
    linked = "; ".join(_target_text(targets[target], kinds) for target, kinds in sorted(by_target.items()))
    return f"The registry links this entry to {linked}. The exact release, variant or subset the paper used is not human-verified."


def _member_options(blocker_type: str, links: list[Link]) -> list[str]:
    options = [f"alias_of:{target}" for target in sorted({link.target for link in links})]
    options.append("accept_unreleased_custom_record" if blocker_type == "unreleased" else "distinct_release")
    options.append("keep_candidate")
    return options


def _group_options(members: list[Member]) -> list[str]:
    options = {option for member in members for option in member.options}
    ordered = sorted(option for option in options if option.startswith("alias_of:"))
    ordered += [option for option in ("distinct_release", "accept_unreleased_custom_record") if option in options]
    return ordered + ["keep_candidate"]


def _codes(items: list[str]) -> list[str]:
    return [f"`{item}`" for item in items]


OPTION_GLOSS = {
    "alias_of": "the paper's name is another name for that entry",
    "distinct_release": "a release of its own",
    "accept_unreleased_custom_record": "a paper-private dataset with no public release, kept as an unreleased custom record",
    "keep_candidate": "leave the identity open"}


def _option_phrases(options: list[str]) -> list[str]:
    """One phrase per kind of option; several `alias_of:<id>` options share one gloss."""
    phrases, aliases = [], [option for option in options if option.startswith("alias_of:")]
    for option in options:
        if option.startswith("alias_of:"):
            if option == aliases[0]:
                phrases.append(f"{_and(_codes(aliases))} ({OPTION_GLOSS['alias_of']})")
        else:
            phrases.append(f"`{option}` ({OPTION_GLOSS[option]})")
    return phrases


def _decision(members: list[Member], targets: list[Target], options: list[str]) -> list[str]:
    """The decision in plain sentences, derived only from the group's structure."""
    many = len(members) > 1
    subject = "these entries" if many else "this entry"
    sentences = [f"A person decides, for {'each of the ' + str(len(members)) + ' entries' if many else 'the entry'} below, which option "
                 "applies; until then it stays a candidate."]
    if targets:
        sentences.append(f"The registry links {subject} to {_and(_codes([target.id for target in targets]))}.")
    else:
        sentences.append(f"There is no registry link from {subject} to another entry, so `alias_of` has no concrete target.")
    only = "; each entry offers only the alias options for the targets it links to" if many and targets else ""
    sentences.append(f"The options are {_and(_option_phrases(options))}{only}.")
    prepared = [target.id for target in targets if target.prepared]
    if prepared:
        sentences.append(f"A prepared preview exists for {_and(_codes(prepared))}; the paper's exact release is unresolved, so no entry here "
                         "inherits it, and an entry whose preview is `none` stays `none`.")
    own = [member.id for member in members if member.preview not in ("none", "unknown")]
    if own:
        sentences.append(f"{_and(_codes(own))} already {'have' if len(own) > 1 else 'has'} a prepared preview of "
                         f"{'their' if len(own) > 1 else 'its'} own, yet the identity is still a candidate: the preview does not settle "
                         "which release the paper used.")
    unreleased = [member.id for member in members if member.blocker_type == "unreleased"]
    if len(unreleased) == 1:
        sentences.append(f"`{unreleased[0]}` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.")
    elif unreleased:
        sentences.append(f"{_and(_codes(unreleased))} are unreleased paper-private records: accept each as an unreleased custom record, "
                         "or keep each as candidate.")
    gated = [member for member in members if member.blocker_type == "access"]
    if gated:
        sentences.append(f"For {_and([f'`{m.id}` (access `{m.access}`)' for m in gated])} the blocker is access, a user action such as "
                         "a request, terms or credentials, not identity; the identity decision can be taken independently.")
    down = [member.id for member in members if member.blocker_type == "source_availability"]
    if down:
        sentences.append(f"For {_and(_codes(down))} the source host did not answer or did not resolve at the registry's latest access audit; "
                         "that is source availability, not an identity decision.")
    return sentences


class _Components:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        self.parent[self.find(right)] = self.find(left)


def build_groups(entries: dict, rows: dict) -> list[Group]:
    scope = {entry_id: entry for entry_id, entry in sorted(entries.items())
             if (entry.get("coverage") or {}).get("identity") in IDENTITY_SCOPE}
    links = {entry_id: entry_links(entry) for entry_id, entry in scope.items()}
    nodes = {entry_id: ({link.target for link in links[entry_id]} or {entry_id}) for entry_id in scope}
    components = _Components()
    for entry_id, entry_nodes in nodes.items():
        ordered = sorted(entry_nodes)
        for other in ordered[1:]:
            components.union(ordered[0], other)
        components.find(ordered[0])
    buckets = {}
    for entry_id in scope:
        buckets.setdefault(components.find(min(nodes[entry_id])), []).append(entry_id)

    def target_info(target_id: str, link_types: list[str]) -> Target:
        entry = entries.get(target_id)
        if entry is None:
            return Target(target_id, "not_in_registry", "unknown", False, link_types)
        return Target(target_id, _clean((entry.get("coverage") or {}).get("identity")) or "unknown", _state(entry, rows, "preview"),
                      target_id in scope, link_types)

    groups = []
    for member_ids in buckets.values():
        group_nodes = sorted(set().union(*(nodes[entry_id] for entry_id in member_ids)))
        kinds_by_target = {}
        for entry_id in member_ids:
            for link in links[entry_id]:
                kinds_by_target.setdefault(link.target, set()).add(link.type)
        targets = [target_info(target, sorted(kinds)) for target, kinds in sorted(kinds_by_target.items())]
        by_id = {target.id: target for target in targets}
        members = []
        for entry_id in sorted(member_ids):
            entry = scope[entry_id]
            access = _state(entry, rows, "access")
            host_down = _host_down(entry)
            blocker_type = classify(access, host_down)
            audit = _latest(entry, "source_audit_identity")
            audit_text = (f"`{_clean(audit.get('source_identity_status')) or 'no status'}` ({_clean(audit.get('checked_on')) or 'undated'})"
                          if audit else "")
            members.append(Member(
                id=entry_id, name=_clean(entry.get("name")) or entry_id, identity=_clean(entry["coverage"].get("identity")),
                access=access, adapter=_state(entry, rows, "adapter"), preview=_state(entry, rows, "preview"),
                blocker_type=blocker_type, blocker_basis=_basis(blocker_type, access, links[entry_id], by_id, host_down),
                options=_member_options(blocker_type, links[entry_id]), links=links[entry_id], papers=entry_papers(entry),
                registry_blockers=[_clean(line) for line in (entry["coverage"].get("blockers") or [])],
                description=_clean(entry.get("description")), identity_audit=audit_text))
        options = _group_options(members)
        groups.append(Group(key="|".join(group_nodes), nodes=group_nodes, members=members, targets=targets,
                            options=options, decision=_decision(members, targets, options)))
    return sorted(groups, key=lambda group: group.key)


# --- stable IDs --------------------------------------------------------------------------------------------------------

def _number(identifier: str) -> int:
    found = ID_PATTERN.fullmatch(identifier)
    if found is None:
        raise ValueError(f"{identifier!r} is not an IR-NNN id")
    return int(found.group(1))


def load_ids(path: Path) -> dict:
    if not path.is_file():
        return {}
    mapping = json.loads(path.read_text(encoding="utf-8"))
    values = list(mapping.values())
    if not all(isinstance(value, str) and ID_PATTERN.fullmatch(value) for value in values) or len(set(values)) != len(values):
        raise ValueError(f"{path.name}: every group key needs its own IR-NNN id")
    return mapping


def assign_ids(keys: list[str], existing: dict) -> tuple[dict, int]:
    """Keep every existing assignment; give unseen keys, in sorted order, the numbers after the highest ever assigned."""
    ids = dict(existing)
    top = max((_number(value) for value in ids.values()), default=0)
    new = 0
    for key in sorted(keys):
        if key not in ids:
            top += 1
            new += 1
            ids[key] = f"IR-{top:03d}"
    return dict(sorted(ids.items())), new


def build_model(root: Path = ROOT) -> QueueModel:
    """Everything the queue says, computed without writing a byte."""
    root = Path(root)
    entries = load_entries(root / REGISTRY_DIR)
    rows = load_state(root / COVERAGE_CSV)
    groups = build_groups(entries, rows)
    ids, new = assign_ids([group.key for group in groups], load_ids(root / IDS_FILE))
    for group in groups:
        group.id = ids[group.key]
    groups.sort(key=lambda group: _number(group.id))
    members = [member for group in groups for member in group.members]
    blocker_counts = {kind: sum(member.blocker_type == kind for member in members) for kind in BLOCKER_TYPES}
    previews = Counter(member.preview for member in members)
    preview_counts = {state: previews[state] for state in sorted(previews, key=lambda state: (state != "none", state))}
    return QueueModel(groups=groups, ids=ids, new_ids=new, blocker_counts=blocker_counts, preview_counts=preview_counts)


# --- the markdown a person reads ---------------------------------------------------------------------------------------

def _code(text) -> str:
    return f"`{_clean(text)}`"


def _cell(text) -> str:
    return _clean(text).replace("|", "\\|")


def _counts(counts: dict) -> str:
    return ", ".join(f"`{key}` {value}" for key, value in counts.items())


def _label(group: Group) -> str:
    targets = ", ".join(_code(target.id) for target in group.targets)
    if len(group.members) > 1:
        return f"{len(group.members)} entries linked to {targets}"
    member = group.members[0]
    return f"{_cell(member.name)}, linked to {targets}" if targets else _cell(member.name)


def _prepared_cell(group: Group) -> str:
    if not group.targets:
        return "no link"
    prepared = [f"{_code(target.id)} ({target.preview}{'; also in this queue' if target.in_queue else ''})"
                for target in group.targets if target.prepared]
    return ", ".join(prepared) if prepared else "none prepared"


def _summary_row(group: Group) -> str:
    previews = Counter(member.preview for member in group.members)
    states = ", ".join(f"{state} {previews[state]}" for state in sorted(previews, key=lambda state: (state != "none", state)))
    target = _code(group.members[0].id) if len(group.members) == 1 else ", ".join(_code(t.id) for t in group.targets)
    label = target if len(group.members) == 1 else f"linked to {target}"
    return (f"| {group.id} | {label} | {len(group.members)} | {states} | {_prepared_cell(group)} | "
            f"{', '.join(_code(option) for option in group.options)} |")


def _public_unstarted(model: QueueModel) -> list[str]:
    lines = ["## Public sources whose adapter is not started", "",
             "These entries have access `public` and adapter `not_started`. For each, what blocks it, read from the registry's own state:", ""]
    rows = [(group, member) for group in model.groups for member in group.members
            if member.access == "public" and member.adapter == "not_started"]
    if not rows:
        return lines + ["No entry is in this state.", ""]
    for group, member in rows:
        linked = {link.target for link in member.links}
        prepared = [target for target in group.targets if target.id in linked and target.prepared]
        if member.blocker_type == "source_availability":
            reason = None
        elif prepared:
            reason = (f"a family alias or variant of {_and(_codes([t.id for t in prepared]))}, whose release is already prepared "
                      f"(preview {_and([_code(t.preview) for t in prepared])}); the paper's exact release for this entry is unresolved. "
                      "The adapter is not what blocks it.")
        elif linked:
            reason = (f"linked to {_and(_codes(sorted(linked)))}, none of which has a prepared preview; the paper's exact release is unresolved.")
        else:
            reason = "no registry link to a prepared release; the paper's exact release, variant or component is unresolved."
        head = f"- {_code(member.id)} (group {group.id}) — blocker type **{member.blocker_type}**"
        lines.append(f"{head}: {reason}" if reason else f"{head}. {member.blocker_basis}")
        if member.identity_audit:
            lines.append(f"  Registry identity audit: {member.identity_audit}.")
        if member.description and not linked:
            lines += ["  Registry description:", f"  > {member.description}"]
        lines.append("  Registry blockers:")
        lines += [f"  > {line}" for line in member.registry_blockers] or ["  > none recorded"]
    return lines + [""]


def _member_lines(member: Member) -> list[str]:
    lines = [f"### {_code(member.id)} — {_cell(member.name)}", "",
             f"- State: access {_code(member.access)}, adapter {_code(member.adapter)}, preview {_code(member.preview)}, "
             f"identity {_code(member.identity)}.",
             f"- Blocker type: **{member.blocker_type}**. {member.blocker_basis}",
             f"- Options: {', '.join(_code(option) for option in member.options)}"]
    if member.links:
        lines.append("- Registry links: " + "; ".join(f"{_code(link.type)} → {_code(link.target)}" for link in member.links))
    if member.identity_audit:
        lines.append(f"- Registry identity audit: {member.identity_audit}.")
    lines.append("- Registry blockers:")
    lines += [f"  > {line}" for line in member.registry_blockers] or ["  > none recorded"]
    if not member.papers:
        lines.append("- Papers: none recorded in the registry.")
        return lines + [""]
    lines.append(f"- Mentioned by {len(member.papers)} paper{'s' if len(member.papers) != 1 else ''}:")
    for paper in member.papers:
        detail = ", ".join(part for part in (f"page {paper.page}" if paper.page not in (None, "") else "",
                                             f"role: {paper.role}" if paper.role else "") if part)
        lines.append(f"  - {_code(paper.paper_id)}" + (f", {detail}" if detail else ""))
        lines.append(f"    > {paper.excerpt}" if paper.excerpt else "    > no excerpt stored in the registry")
    return lines + [""]


def _group_lines(group: Group) -> list[str]:
    kinds = Counter(member.blocker_type for member in group.members)
    lines = [f"## {group.id} · {_label(group)}", "",
             f"**Group key:** {_code(group.key)} · **Entries:** {len(group.members)} · "
             f"**Blocker types:** {_counts({kind: kinds[kind] for kind in BLOCKER_TYPES if kinds[kind]})}", ""]
    if group.targets:
        lines += ["**Linked to:**", ""]
        for target in group.targets:
            state = "prepared" if target.prepared else "no preview"
            also = "; also an entry in this queue" if target.in_queue else ""
            lines.append(f"- {_target_text(target, target.link_types)} — {state}{also}")
    else:
        lines.append("**Linked to:** nothing.")
    lines += ["", "**Decision needed.** " + " ".join(group.decision), "",
              "**Options:** " + ", ".join(_code(option) for option in group.options), ""]
    for member in group.members:
        lines += _member_lines(member)
    return lines


def render_markdown(model: QueueModel) -> str:
    families = [group for group in model.groups if len(group.members) > 1]
    lines = ["# Identity review queue", "", INTRO, "", "## How to read this", "", *LEGEND, "", "## Summary", "",
             f"{model.entry_count} entries in {len(model.groups)} groups; {len(families)} groups hold more than one entry.", "",
             f"Blocker types: {_counts(model.blocker_counts)}.", "",
             f"Preview states of the entries: {_counts(model.preview_counts)}.", "",
             "Groups with more than one entry: " + (", ".join(f"{group.id} ({len(group.members)})" for group in families) or "none") + ".", "",
             "### Groups", "", "| IR | Group | Entries | Preview states | Prepared target | Options |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [_summary_row(group) for group in model.groups]
    lines.append("")
    lines += _public_unstarted(model)
    for group in model.groups:
        lines += _group_lines(group)
    return "\n".join(lines).rstrip("\n") + "\n"


# --- the review queue --------------------------------------------------------------------------------------------------

def queue_record(group: Group) -> dict:
    return {"kind": "identity_decision", "id": group.id, "group_key": group.key, "members": sorted(m.id for m in group.members),
            "status": "open", "options": list(group.options), "created_by": CREATED_BY}


def queue_ids(path: Path) -> set:
    """Ids of the records the queue file already holds. A line that is not JSON stops the run before anything is written."""
    present = set()
    for line in (path.read_text(encoding="utf-8").splitlines() if path.exists() else []):
        if line.strip():
            item = json.loads(line)
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                present.add(item["id"])
    return present


def append_queue(path: Path, records: list[dict], present: set) -> int:
    """Append the records whose id the file does not hold; never rewrite, reorder or duplicate a line."""
    fresh = [record for record in records if record["id"] not in present]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    separator = b"\n" if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n") else b""
    body = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in fresh).encode("utf-8")
    with path.open("ab") as stream:
        stream.write(separator + body)
    return len(fresh)


# --- running -----------------------------------------------------------------------------------------------------------

def run(root: Path = ROOT, *, dry_run: bool = False) -> QueueModel:
    root = Path(root)
    model = build_model(root)
    if dry_run:
        return model
    registry = (root / REGISTRY_DIR).resolve()
    ids_path, report_path, queue_path = root / IDS_FILE, root / REPORT_FILE, root / QUEUE_FILE
    for output in (ids_path, report_path, queue_path):
        if registry in output.resolve().parents:
            raise ValueError(f"{output.name}: the queue never writes into the dataset registry")
    present = queue_ids(queue_path)
    if model.new_ids or not ids_path.exists():
        ids_path.write_text(json.dumps(model.ids, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    markdown = render_markdown(model)
    if not report_path.exists() or report_path.read_text(encoding="utf-8") != markdown:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8", newline="\n")
    model.appended = append_queue(queue_path, [queue_record(group) for group in model.groups], present)
    return model


def summary(model: QueueModel, *, dry_run: bool = False) -> dict:
    return {"groups": len(model.groups), "entries": model.entry_count, "blocker_types": model.blocker_counts,
            "preview_states": model.preview_counts, "ids_assigned": model.new_ids, "queue_records_appended": model.appended,
            "dry_run": dry_run}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this repository)")
    parser.add_argument("--dry-run", action="store_true", help="compute and print the summary; write nothing")
    args = parser.parse_args(argv)
    model = run(args.root, dry_run=args.dry_run)
    print(json.dumps(summary(model, dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

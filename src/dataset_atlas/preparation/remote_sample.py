"""Reproducible previews of remote Parquet releases too large to index locally.

The population is every row of the pinned shards whose footers were read. Row
counts come from those footers, so no record is downloaded to learn them. Rows
are drawn with a portable SHA-256 counter: draw ``i`` is the global position
``int(sha256(f"{seed}:{i}")) mod N``. A draw selects the row group containing
it (probability proportional to that group's row count) until the next group
would exceed the transfer budget; later draws are kept only when they land in
an already selected group, where they are uniform. When every draw fits the
budget this is a simple random sample of rows without replacement.
"""
from __future__ import annotations
import bisect
import hashlib
from dataclasses import dataclass, field

METHOD = 'sha256_counter_two_stage_row_groups'


def shard_rank(seed: int, source_name: str) -> str:
    """Equal-probability shard order for releases whose footers are too costly to read in full."""
    return hashlib.sha256(f'{seed}:{source_name}'.encode()).hexdigest()


@dataclass
class TwoStageSampler:
    """Draw row positions over ``groups``: (file index, group index, rows, transfer bytes)."""
    groups: list[tuple[int, int, int, int]]
    seed: int = 0
    byte_budget: int = 1_000_000_000
    max_draws: int = 20_000_000
    draws: int = 0
    selected_bytes: int = 0
    selected: dict[int, set[int]] = field(default_factory=dict)
    order: list[int] = field(default_factory=list)
    rejected_for_budget: int = 0

    def __post_init__(self):
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError('Sampling seed must be a non-negative integer')
        if type(self.byte_budget) is not int or self.byte_budget < 1:
            raise ValueError('Sampling transfer budget must be positive')
        self.starts = []
        total = 0
        for _, _, rows, size in self.groups:
            if type(rows) is not int or rows < 0 or type(size) is not int or size < 0:
                raise ValueError('Row-group rows and bytes must be non-negative integers')
            self.starts.append(total)
            total += rows
        self.total = total
        if total < 1:
            raise ValueError('Remote population has no rows')

    def _position(self, index: int) -> int:
        return int.from_bytes(hashlib.sha256(f'{self.seed}:{index}'.encode()).digest(), 'big') % self.total

    def capacity(self) -> int:
        return sum(self.groups[group][2] for group in self.selected)

    def next(self) -> tuple[int, int, int] | None:
        """Next distinct (file index, row-group index, row within group), or None when exhausted."""
        while self.draws < self.max_draws:
            if self.rejected_for_budget and (not self.selected and self.rejected_for_budget > 100_000
                                             or self.selected and sum(len(rows) for rows in self.selected.values()) >= self.capacity()):
                return None
            position = self._position(self.draws)
            self.draws += 1
            group = bisect.bisect_right(self.starts, position) - 1
            row = position - self.starts[group]
            if group not in self.selected:
                size = self.groups[group][3]
                if self.selected_bytes + size > self.byte_budget:
                    self.rejected_for_budget += 1
                    continue
                self.selected[group] = set()
                self.order.append(group)
                self.selected_bytes += size
            if row in self.selected[group]:
                continue
            self.selected[group].add(row)
            file_index, group_index, _, _ = self.groups[group]
            return file_index, group_index, row
        return None

    def description(self, drawn: int) -> dict:
        simple = sum(group[3] for group in self.groups) <= self.byte_budget
        return {'method': METHOD, 'seed': self.seed, 'population_count': self.total, 'row_groups_in_population': len(self.groups),
                'row_groups_selected': len(self.order), 'rows_drawn': drawn, 'draws': self.draws,
                'selected_row_group_transfer_bytes': self.selected_bytes, 'transfer_budget_bytes': self.byte_budget,
                'rejected_draws_for_transfer_budget': self.rejected_for_budget,
                'row_groups_exceeding_initial_budget': sum(group[3] > self.byte_budget for group in self.groups),
                'rows_in_groups_exceeding_initial_budget': sum(group[2] for group in self.groups if group[3] > self.byte_budget),
                'valid_for_population_prevalence': simple,
                'design': ('simple random sample of rows without replacement' if simple else
                           'Budget-conditioned row-group draws: initial positions are proportional to native row counts, '
                           'but groups rejected for transfer cost alter inclusion probabilities. Oversized groups have zero inclusion; '
                           'not valid for population prevalence estimation.'),
                'draw_rule': 'global position = int(SHA-256("<seed>:<draw index>")) mod population count'}


HF_HOSTS = ['huggingface.co', 'cdn-lfs.huggingface.co', 'cdn-lfs-us-1.huggingface.co', 'cdn-lfs-eu-1.huggingface.co',
            'cas-bridge.xethub.hf.co', 'us.aws.cdn.hf.co', 'eu.aws.cdn.hf.co']


def draw_native_subset(adapter, source, sampler, count, record_filter, check=lambda: None, max_candidates=100_000):
    """A budgeted preview must enforce the same native subset as its full index."""
    from .filtering import filter_record
    selected = []
    drawn = excluded = 0
    while len(selected) < count and drawn < max_candidates:
        check()
        targets = []
        while len(targets) < min(count - len(selected), max_candidates - drawn):
            target = sampler.next()
            if target is None:
                break
            targets.append(target)
        if not targets:
            break
        drawn += len(targets)
        for record in adapter.records_at(source, targets):
            if filter_record(record, record_filter):
                selected.append(record)
            else:
                excluded += 1
    if len(selected) != count:
        raise ValueError('Native row groups cannot supply the filtered preview within its candidate and transfer bounds')
    description = sampler.description(drawn)
    if record_filter:
        description.update(native_source_population_count=sampler.total, excluded_by_native_filter=excluded,
            subset_filter=record_filter,
            design=description['design'] + '; only rows satisfying the pinned native subset are retained')
    return selected, description


def prepare_sampled_preview(root, plan, identity, dataset, version, base, directory, update, check):
    """Write a prepared version holding only a sampled preview of a pinned remote Parquet release."""
    import json
    from pathlib import Path
    from dataset_atlas.adapters.remote_columnar import RemoteColumnarAdapter
    from dataset_atlas.models import FieldDescriptor, Pack
    from . import atomic, prepared_metadata, snapshot_for
    from .remote import pin_remote_files
    from io import BytesIO
    from PIL import Image
    options = plan['sample']
    seed, size = options['seed'], options['size']
    files = list(plan['files'])
    if options['footers'] == 'shard_rank':
        files = sorted(files, key=lambda entry: (shard_rank(seed, entry['source_name']), entry['source_name']))[:options['shards']]
        files.sort(key=lambda entry: entry['source_name'])
    fingerprint_path = directory / 'remote-shards.json'
    if fingerprint_path.is_file():
        remote_files = json.loads(fingerprint_path.read_text())
        if [{k: v for k, v in entry.items() if k != 'etag'} for entry in remote_files] != files:
            raise ValueError('Saved remote shard fingerprints differ from the approved plan')
    else:
        remote_files = pin_remote_files(files, HF_HOSTS, check, update,credential_profile=plan.get('credential_profile'))
        atomic(fingerprint_path, remote_files)
    dataset.release = plan['revision']
    dataset.snapshot_id = snapshot_for(dataset.id, plan, identity, root)
    dataset.adapter = 'remote_columnar'
    mapping = dataset.adapter_config.get('mapping', {})
    cache_bytes = dataset.adapter_config.get('remote_cache_bytes', 200_000_000)
    dataset.adapter_config = {'remote_files': remote_files, 'allowed_hosts': HF_HOSTS,
        'remote_cache_root': str(Path(root) / 'work/media-cache/remote-parquet'), 'remote_cache_bytes': cache_bytes,
        'metadata_transfer_bytes': plan['max_download_bytes'], 'population': plan['scope'], 'mapping': mapping,
        **{key: dataset.adapter_config[key] for key in ('fields', 'max_record_bytes', 'media_transfer_bytes', 'media_columns','credential_profile') if key in dataset.adapter_config}}
    adapter = RemoteColumnarAdapter(dataset)
    # Parallel preparations must not evict each other's large native chunks.
    # This disposable per-version cache uses the reserved acquisition space;
    # the immutable runtime configuration still uses the shared browsing cache.
    from dataset_atlas.storage import BoundedCache
    staging_cache=version/'staging-range-cache'
    adapter.cache=BoundedCache(staging_cache,min(cache_bytes,plan['max_download_bytes']))
    adapter.config['remote_cache_root']=str(staging_cache)
    adapter.config['aggregate_transfer_bytes']=plan['max_download_bytes']
    adapter.cancel = check
    update(stage='reading remote Parquet footers')
    adapter.warm_layouts(progress=lambda **values: update(**values))
    footer_bytes = adapter.bytes_fetched
    groups = []
    for index in range(len(remote_files)):
        rows = adapter._layout(index)[3]
        for group, (count, (annotation, media)) in enumerate(zip(rows, adapter.group_bytes(index), strict=True)):
            groups.append((index, group, count, annotation + media))
    remaining = plan['max_download_bytes'] - footer_bytes
    if remaining <= 0:
        raise ValueError('Footer reads exhausted the approved transfer budget')
    sampler = TwoStageSampler(groups, seed=seed, byte_budget=remaining)
    source = adapter.prepare(adapter.plan(1000, plan['max_output_bytes']))
    has_media = any(adapter._layout(index)[1] for index in range(len(remote_files)))
    chosen = []
    media_validation = None
    drawn = unavailable = checked_assets = 0
    from dataset_atlas.adapters.remote_columnar import MediaLimitError
    excluded_limits = {}
    preview_bytes=0
    retained_handles={}
    while len(chosen) < size:
        check()
        targets = []
        while len(targets) < size - len(chosen):
            target = sampler.next()
            if target is None:
                break
            targets.append(target)
        if not targets:
            break
        drawn += len(targets)
        update(stage='reading sampled rows', sampled_rows=drawn, selected_row_groups=len(sampler.order), downloaded_bytes=adapter.bytes_fetched+adapter.media_bytes_fetched)
        records = adapter.records_at(source, targets)
        if not has_media:
            chosen.extend(records[:size - len(chosen)])
            continue
        media_source = adapter.prepare(adapter.plan(100, plan['max_output_bytes']))
        available={}
        # Resolve by native source position, then restore draw order. This keeps
        # large column chunks hot in the bounded cache instead of repeatedly
        # transferring them as random draws alternate between source shards.
        for record in sorted(records,key=lambda item:(item.source['_atlas_origin']['file'],item.source['_atlas_origin']['row'])):
            check()
            update(stage='checking sampled original media',downloaded_bytes=adapter.bytes_fetched+adapter.media_bytes_fetched)
            try:
                opened = 0
                for asset in record.assets:
                    if asset.modality != 'image' or not asset.uri:
                        continue
                    handle = adapter.resolve_asset(media_source, asset.uri)
                    with Image.open(BytesIO(handle.data)) as image:
                        image.verify()
                    asset.sha256 = handle.sha256
                    media_path=version/'pack/media'/handle.sha256
                    if not media_path.is_file():
                        preview_bytes+=len(handle.data)
                        if preview_bytes>plan['max_output_bytes']:
                            raise ValueError('Original preview media exceeds approved output budget')
                        media_path.parent.mkdir(parents=True,exist_ok=True)
                        media_path.write_bytes(handle.data)
                    retained_handles[asset.id]=handle.sha256
                    opened += 1
            except FileNotFoundError:
                unavailable += 1
                continue
            except MediaLimitError as error:
                unavailable += 1
                excluded_limits[str(error)] = excluded_limits.get(str(error), 0) + 1
                continue
            available[record.id]=opened
        for record in records:
            if len(chosen)==size:break
            if record.id in available:
                checked_assets+=available[record.id]
                chosen.append(record)
        media_validation = {'verified_records': len(chosen), 'unavailable_candidate_records': unavailable,
                            'media_limit_exclusions': excluded_limits,
                            'verified_preview_assets': checked_assets, 'candidates_checked': drawn}
    if not chosen:
        raise ValueError('No sampled rows were readable within the approved transfer budget')
    description = sampler.description(drawn)
    population_rows = sampler.total
    description.update(unit=dataset.coverage.unit, source_revision=dataset.release, requested_count=size, returned_count=len(chosen),
        population=plan['scope'], shards_in_population=len(remote_files), shards_in_release=len(plan['files']),
        shard_selection=('all pinned shards' if options['footers'] == 'all' else
                         f'{len(remote_files)} of {len(plan["files"])} shards with the lowest SHA-256("<seed>:<source name>") ranks; equal shard probability, not weighted by rows'),
        footer_transfer_bytes=footer_bytes, total_transfer_bytes=adapter.bytes_fetched+adapter.media_bytes_fetched,
        selection_note=('Rows drawn from the complete pinned release; no complete local index exists.' if options['footers'] == 'all' else
                        'Rows drawn from the listed shard subset only; other shards are outside this preview population.'))
    if has_media:
        description['media_selection'] = 'Drawn rows kept in draw order only when every embedded image slot opened; unavailable slots are excluded, not substituted.'
        description['media_availability_exclusions'] = unavailable
        description['valid_for_population_prevalence'] = False
        description['selection_note'] += ' Media availability and decoding limits condition this preview; it cannot estimate prevalence in the full pinned population. An available-media population has not been enumerated, even when no sampled candidates were excluded.'
    declared = adapter.source_field_types()
    fields = []
    for name in sorted({key for record in chosen for key in record.source} | set(declared)):
        dtype = declared.get(name, 'object')
        fields.append(FieldDescriptor(id='source.' + name, name=name, dtype=dtype, provenance={'source_url': dataset.source_url},
            query_ops=['eq', 'ne', 'in', 'contains', 'is_null'] + (['gt', 'gte', 'lt', 'lte'] if dtype == 'number' else [])))
    dataset.coverage.preview_count = len(chosen)
    dataset.coverage.total_count = population_rows if options['footers'] == 'all' else None
    dataset.coverage.preview = 'complete_target' if len(chosen) == size else 'partial'
    dataset.coverage.adapter = 'tested'
    dataset.coverage.complete_data = 'exceeds_storage_budget'
    note = (f'Complete local index not built: the pinned release has {plan["source_total_bytes"]:,} bytes of remote Parquet. '
            'The preview is a seeded sample; complete-scope queries are unavailable here.')
    dataset.coverage.blockers = [note] + [b for b in dataset.coverage.blockers if b != note]
    dataset = prepared_metadata(dataset, plan['scope'])
    dataset.evidence.append({'kind': 'computed_measurement', 'measurement': 'row_count', 'value': population_rows,
        'unit': 'rows', 'scope': 'complete pinned release' if options['footers'] == 'all' else f'{len(remote_files)} sampled shards',
        'method': 'Sum of row counts in the Parquet footers of the pinned shards', 'computed_or_reported': 'computed',
        'snapshot_id': dataset.snapshot_id})
    pack = Pack(dataset=dataset.model_copy(update={'adapter_config': {}}), fields=fields, records=chosen, population_scope='preview', sampling=description)
    payload = pack.model_dump_json(indent=2).encode()
    selected_hashes={retained_handles[a.id] for r in chosen for a in r.assets if a.id in retained_handles}
    media_dir=version/'pack/media'
    if media_dir.exists():
        for path in media_dir.iterdir():
            if path.name not in selected_hashes:path.unlink()
    checksums={}
    for record in chosen:
        for asset in record.assets:
            if asset.id not in retained_handles:continue
            relative='media/'+retained_handles[asset.id]
            asset.metadata['source_ref']=asset.uri
            asset.uri=relative
            checksums[relative]=retained_handles[asset.id]
    pack.checksums=checksums
    payload=pack.model_dump_json(indent=2).encode()
    retained_bytes=sum((version/'pack'/name).stat().st_size for name in checksums)
    if len(payload)+retained_bytes > plan['max_output_bytes']:
        raise ValueError('Sampled preview exceeds approved output budget')
    (version / 'pack').mkdir(parents=True, exist_ok=True)
    atomic(version / 'pack/pack.json', pack.model_dump(mode='json'))
    atomic(version / 'dataset.json', dataset.model_dump(mode='json'))
    atomic(version / 'receipt.json', {'plan_id': identity, 'source_files': plan['files'], 'remote_files': remote_files,
        'record_count': None, 'population_rows': population_rows, 'snapshot_id': dataset.snapshot_id, 'scope': plan['scope'],
        'sampling': description, 'preview_media_validation': media_validation, 'remote_metadata_bytes': adapter.bytes_fetched,
        'remote_media_bytes':adapter.media_bytes_fetched, 'retained_preview_original_bytes':retained_bytes,
        'integrity': 'Strong ETag-bound ranges; upstream shard SHA-256 values are provenance and were not computed locally.'})
    import shutil
    shutil.rmtree(staging_cache)
    atomic(base / 'active.json', {'version': identity})
    update(status='completed', stage='ready', snapshot_id=dataset.snapshot_id, preview_count=len(chosen), downloaded_bytes=adapter.bytes_fetched+adapter.media_bytes_fetched)

"""Append to a list inside a registry YAML file without re-dumping the document.

`yaml.safe_dump` re-flows long scalars, so a whole-document rewrite changes lines nobody edited (20 of the 333 shipped
files do not round-trip byte-for-byte at any wrap width). Evidence maintenance only ever adds items, so the new lines
are inserted at the end of the list's block and every other byte stays as committed. The result is parsed and compared
with the expected data before it is returned; a layout this module does not understand raises instead of guessing.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import yaml


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _significant(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _block_end(lines: list[str], key_index: int, key_indent: int) -> int:
    """First line after the block of the key at `key_index` (children are deeper, or `- ` items at the key's own indent)."""
    for index in range(key_index + 1, len(lines)):
        line = lines[index]
        if not _significant(line):
            continue
        indent = _indent(line)
        if indent < key_indent or (indent == key_indent and not line.lstrip().startswith("- ")):
            return index
    return len(lines)


def _find_key(lines: list[str], path: Sequence[str]) -> tuple[int, int]:
    """Index and indent of the line holding the last key of `path`."""
    low, high, mapping_indent = 0, len(lines), 0
    key_index = key_indent = -1
    for depth, key in enumerate(path):
        prefix = " " * mapping_indent + key + ":"
        matches = [i for i in range(low, high) if lines[i].startswith(prefix) and _indent(lines[i]) == mapping_indent]
        if not matches:
            raise KeyError(".".join(path[:depth + 1]))
        key_index, key_indent = matches[0], mapping_indent
        if depth + 1 < len(path):
            low, high = key_index + 1, _block_end(lines, key_index, key_indent)
            children = [_indent(lines[i]) for i in range(low, high) if _significant(lines[i])]
            if not children or min(children) <= key_indent:
                raise KeyError(".".join(path[:depth + 2]))
            mapping_indent = min(children)
    return key_index, key_indent


def _expected(document: Any, path: Sequence[str], items: Sequence[Any]) -> Any:
    expected = yaml.safe_load(yaml.safe_dump(document))
    target = expected
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = [*target[path[-1]], *items]
    return expected


def append_list_items(text: str, path: Sequence[str], items: Sequence[Any], *, width: int = 100) -> str:
    """Return `text` with `items` appended to the block list at `path` (for example `("coverage", "blockers")`).

    Raises KeyError for a missing key and ValueError when the target is not a block list (or an empty `[]`) or the
    edited text does not parse to exactly the original data plus the new items.
    """
    if not items:
        return text
    lines = text.split("\n")
    key_index, key_indent = _find_key(lines, path)
    key = path[-1]
    rest = lines[key_index][key_indent + len(key) + 1:].strip()
    end = _block_end(lines, key_index, key_indent)
    if rest == "[]":
        lines[key_index] = " " * key_indent + key + ":"
        item_indent, last = key_indent, key_index
    elif rest == "":
        following = [i for i in range(key_index + 1, end) if _significant(lines[i])]
        if not following or not lines[following[0]].lstrip().startswith("- "):
            raise ValueError(f"{'.'.join(path)} is not a block list")
        item_indent, last = _indent(lines[following[0]]), following[-1]
    else:
        raise ValueError(f"{'.'.join(path)} is not a block list (found `{rest[:30]}`)")
    rendered = yaml.safe_dump(list(items), sort_keys=False, allow_unicode=True, width=width, default_flow_style=False)
    block = [" " * item_indent + line if line else line for line in rendered.rstrip("\n").split("\n")]
    edited = "\n".join([*lines[:last + 1], *block, *lines[last + 1:]])
    if yaml.safe_load(edited) != _expected(yaml.safe_load(text), path, items):
        raise ValueError(f"appending to {'.'.join(path)} did not produce the expected document")
    return edited

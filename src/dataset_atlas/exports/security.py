"""Checks shared by imported exchange data and public artifacts."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

MAX_EXCHANGE_BYTES = 200_000_000
MAX_JSON_BYTES = 40_000_000

_SECRET_KEY = re.compile(r"(?:^|_)(?:api_?key|access_?token|refresh_?token|password|secret|credential|private_?key)(?:$|_)", re.I)
_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+[A-Za-z0-9._~+/-]{12,}|(?:api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]{8,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")
_LOCAL_PATH = re.compile(r"(?i)(?:file://|(?:^|[\s='\"(])/(?:home|Users|root|tmp|var|mnt|media|etc|opt|srv|private|data|scratch|workspace|nfs|gpfs|lustre)(?:/|\b)|(?:^|[\s='\"(])[A-Z]:\\)")
_PDF_REF = re.compile(r"(?i)(?:\.pdf(?:\b|[?#])|application/pdf)")
_SIGNED_URL = re.compile(r"(?i)https?://[^\s\"<>?]+\?[^\s\"<>]+")


class ExchangeError(ValueError):
    """A pack or publication failed validation."""


def compact_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path, *, limit: int = MAX_JSON_BYTES) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ExchangeError(f"Missing or linked JSON file: {path.name}")
    if path.stat().st_size > limit:
        raise ExchangeError(f"JSON file exceeds {limit} bytes: {path.name}")
    try:
        return json.loads(path.read_bytes())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExchangeError(f"Invalid JSON: {path.name}") from exc


def safe_member(name: str) -> str:
    if not isinstance(name, str) or not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name:
        raise ExchangeError(f"Unsafe pack member: {name!r}")
    parts = Path(name).parts
    if any(part in ("", ".", "..") for part in parts) or Path(name).is_absolute():
        raise ExchangeError(f"Unsafe pack member: {name!r}")
    return name


def scan_public(value: Any, *, label: str = "payload") -> None:
    """Fail closed on common private content; callers first construct an allowlisted shape."""
    if isinstance(value, dict):
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)) or str(key).lower() in {"adapter_config", "evidence", "private_notes"}:
                raise ExchangeError(f"Forbidden key in {label}: {key}")
            scan_public(item, label=f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            scan_public(item, label=f"{label}[{index}]")
    elif isinstance(value, str):
        if _SECRET_VALUE.search(value) or _LOCAL_PATH.search(value) or _PDF_REF.search(value) or _SIGNED_URL.search(value) or "\x00" in value:
            raise ExchangeError(f"Private, local, or PDF content in {label}")


def validate_image(data: bytes, suffix: str) -> None:
    """Check actual image bytes so a renamed PDF or oversized image cannot pass."""
    from PIL import Image, UnidentifiedImageError

    formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".gif": "GIF"}
    if suffix.lower() not in formats:
        raise ExchangeError("Unsupported media format")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != formats[suffix.lower()] or image.width * image.height > 50_000_000:
                raise ExchangeError("Media format or dimensions are invalid")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ExchangeError("Invalid image bytes") from exc


def contained_file(root: Path, member: str) -> Path:
    safe_member(member)
    root_real = root.resolve()
    target = root / member
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root_real):
        raise ExchangeError(f"Pack member escapes source root: {member}")
    return target

"""Place named, checksum-pinned members of a verified zip into a directory an adapter reads."""
from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile

MAX_MEMBER_BYTES = 2_000_000_000


def extract_zip_members(archive: Path, directory: Path, members: list[dict], check=lambda: None) -> None:
    """Copy each pinned member to `directory/<file name>`, failing unless its SHA-256 matches. Nothing else in the zip is read."""
    with zipfile.ZipFile(archive) as zipped:
        for pinned in members:
            check()
            try:
                info = zipped.getinfo(pinned['member'])
            except KeyError as error:
                raise ValueError(f"Pinned member is missing from the archive: {pinned['member']}") from error
            if info.is_dir() or info.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Pinned member is not a reasonably sized file: {pinned['member']}")
            target = directory / pinned['member'].rsplit('/', 1)[-1]
            partial = target.with_name(target.name + '.partial')
            digest = hashlib.sha256()
            try:
                with zipped.open(info) as source, partial.open('wb') as out:
                    for block in iter(lambda: source.read(1 << 20), b''):
                        check()
                        digest.update(block)
                        out.write(block)
                if digest.hexdigest() != pinned['sha256']:
                    raise ValueError(f"Archive member differs from its pinned checksum: {pinned['member']}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)

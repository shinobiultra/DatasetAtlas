"""Author constraint CSVs joined to their native image directories."""

from collections import defaultdict
from pathlib import PurePosixPath
import unicodedata
import zipfile

from .core import _safe_relative
from .structured_collection import StructuredCollectionAdapter


def native_unicode_name(info):
    """Repair unflagged UTF-8 ZIP names, retaining the raw member for reads."""
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return unicodedata.normalize("NFC", name)


class VQAConstraintsAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, "_constraint_rows"):
            return self._constraint_rows
        rows = super()._rows()
        for row in rows:
            # The CSV's first column has an empty native header. Preserve its
            # exact spelling/value in a nested object, since a blank top-level
            # field cannot form a valid query namespace such as source.<name>.
            if "" in row:
                row["_atlas_native_columns"] = {"": row.pop("")}
        inventories = {}
        self._unused_directories = {}
        for split, spec in self.config["directory_sources"].items():
            key = spec["archive"]
            path = self.config[self.config["local_archives"][key]["path_key"]]
            directories = defaultdict(list)
            raw_directories = {}
            with zipfile.ZipFile(path) as archive:
                names = set()
                for info in archive.infolist():
                    raw = _safe_relative(info.filename.rstrip("/"))
                    if (
                        info.is_dir()
                        or raw.startswith("__MACOSX/")
                        or PurePosixPath(raw).name.startswith(".")
                    ):
                        continue
                    if raw in names:
                        raise ValueError("Duplicate native constraint image member")
                    names.add(raw)
                    decoded = native_unicode_name(info)
                    if not decoded.startswith(spec["prefix"] + "/"):
                        raise ValueError(
                            "Constraint archive member lies outside the native image root"
                        )
                    directory = str(PurePosixPath(decoded).parent)
                    raw_directory = str(PurePosixPath(raw).parent)
                    previous = raw_directories.setdefault(directory, raw_directory)
                    if previous != raw_directory:
                        raise ValueError(
                            "Unicode normalization makes native directories ambiguous"
                        )
                    directories[directory].append((raw, PurePosixPath(decoded).name))
            used = set()
            for row in rows:
                if row["_atlas_origin"]["split"] != split:
                    continue
                url = row["image_url"]
                if not url.startswith("./"):
                    raise ValueError(
                        "Constraint image directory lacks its native relative prefix"
                    )
                directory = (
                    spec["prefix"]
                    + "/"
                    + unicodedata.normalize("NFC", _safe_relative(url[2:]))
                )
                if directory not in directories:
                    raise ValueError("Constraint row has no native image directory")
                used.add(directory)
                members = sorted(directories[directory], key=lambda pair: pair[1])
                refs = [f"zip/{key}/{raw}" for raw, _ in members]
                row["_atlas_media_refs"] = refs
                row["_atlas_media_conditions"] = {
                    ref: {
                        "condition": name,
                        "source_role": "author-provided source image",
                    }
                    for ref, (_, name) in zip(refs, members)
                }
                row["_atlas_image_directory_join"] = directory
            self._unused_directories[split] = sorted(set(directories) - used)
            inventories[split] = len(names)
        self._native_image_counts = inventories
        self._constraint_rows = rows
        return rows

    def validate_media(self, budget, cancel=None):
        report = super().validate_media(budget, cancel)
        report["unannotated_native_image_directories"] = self._unused_directories
        report["native_directory_image_counts"] = self._native_image_counts
        report["directory_join"] = (
            "Exact relative directory after reversible UTF-8 decoding for unflagged ZIP names and Unicode NFC normalization; raw native members are retained."
        )
        return report

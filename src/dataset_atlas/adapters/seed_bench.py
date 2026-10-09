"""Native SEED-Bench questions with original images and released ordered frames."""

import json
from pathlib import Path

from .core import _safe_relative
from .structured_collection import StructuredCollectionAdapter


class SeedBenchAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, "_seed_rows"):
            return self._seed_rows
        rows = super()._rows()
        payload = json.loads(Path(self.config["annotations_path"]).read_text())
        types = {value: key for key, value in payload["question_type"].items()}
        if len(types) != len(payload["question_type"]):
            raise ValueError("Duplicate SEED question type identity")
        version = self.config["seed_version"]
        if version not in (1, 2):
            raise ValueError("Unknown SEED release mapping")
        for row in rows:
            task = row["question_type_id"]
            if task not in types:
                raise ValueError("Unknown native SEED question type")
            row["_atlas_question_type"] = types[task]
            paths = row["data_id"]
            if version == 1:
                if row["data_type"] == "image":
                    refs = ["zip/images/SEED-Bench-image/" + _safe_relative(paths)]
                elif row["data_type"] == "video" and task in (10, 11, 12):
                    folder = {
                        10: "ssv2_8_frame",
                        11: "kitchen_8_frame",
                        12: "breakfast_8_frame",
                    }[task]
                    identity = _safe_relative(row["question_id"])
                    refs = [
                        f"zip/video/v1_video/task{task}/{folder}/{identity}/{frame}.png"
                        for frame in range(1, 9)
                    ]
                else:
                    raise ValueError("Unsupported native SEED v1 media type")
            elif row["data_source"] == "cc3m":
                refs = ["zip/cc3m/cc3m-image/" + _safe_relative(paths)]
            elif row["data_source"] == "SEED-Bench v2":
                if isinstance(paths, str):
                    paths = [paths]
                if (
                    not isinstance(paths, list)
                    or not paths
                    or any(not isinstance(p, str) for p in paths)
                ):
                    raise ValueError(
                        "SEED media paths must be a nonempty ordered string list"
                    )
                refs = [
                    "zip/images/SEED-Bench-2-image/" + _safe_relative(path)
                    for path in paths
                ]
            else:
                raise ValueError("Unknown native SEED media source")
            row["_atlas_media_refs"] = refs
            row["_atlas_media_conditions"] = {}
            frame_media = row["data_type"].lower() == "video"
            if frame_media and len(refs) != 8:
                raise ValueError(
                    "SEED released video examples require eight native frames"
                )
            for index, ref in enumerate(refs):
                row["_atlas_media_conditions"][ref] = {
                    "source_role": "released video frame"
                    if frame_media
                    else "native image",
                    "condition": f"frame {index + 1}/8"
                    if frame_media
                    else f"image {index + 1}/{len(refs)}",
                    "order": index,
                }
            if frame_media:
                row["_atlas_media_scope"] = (
                    "Eight author-released ordered frames; original video is not provided by this Atlas recipe."
                )
        self._seed_rows = rows
        return rows

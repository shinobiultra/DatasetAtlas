"""Native PATA labels/captions, with every URL row retained and no media fetch."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlsplit
from . import converter, RowDigest, file_sha256


def native_rows(files: Path, captions: Path, check=lambda: None):
    if files.stat().st_size > 2_000_000 or captions.stat().st_size > 1_000_000:
        raise ValueError('PATA annotation inputs exceed their read limits')
    groups = json.loads(captions.read_text(encoding='utf-8'))
    if not isinstance(groups, list) or len(groups) > 100:
        raise ValueError('PATA captions must be a bounded list of scene objects')
    lookup = {}
    for group in groups:
        if (not isinstance(group, dict) or not isinstance(group.get('short'), str)
                or not isinstance(group.get('long'), str)
                or not isinstance(group.get('pos'), dict) or not isinstance(group.get('neg'), dict)):
            raise ValueError('Invalid native PATA caption object')
        scene = group['short']
        if scene in lookup:
            raise ValueError('Duplicate PATA caption scene')
        lookup[scene] = group
    used = set()
    with files.open(encoding='utf-8', newline='') as stream:
        for ordinal, native_line in enumerate(stream):
            check()
            if ordinal >= 100_000 or len(native_line.encode()) > 32_000:
                raise ValueError('PATA rows exceed their count or width limit')
            line = native_line.removesuffix('\n').removesuffix('\r')
            identifier, separator, url = line.partition('|')
            labels = identifier.rsplit('_', 3)
            parsed = urlsplit(url)
            if (not separator or len(labels) != 4 or any(not part for part in labels)
                    or parsed.scheme not in {'https', 'http'} or not parsed.hostname):
                raise ValueError('Invalid native PATA label/URL row')
            scene, race, gender, age = labels
            if scene not in lookup:
                raise ValueError('PATA row has no exact native caption scene')
            used.add(scene)
            yield {'native_line': native_line, 'source_identifier': identifier,
                   'source_row': ordinal, 'scene': scene, 'source_race': race,
                   'source_gender': gender, 'source_age': age, 'media_url': url,
                   'captions': lookup[scene], 'media_available': False,
                   'media_status': 'not_acquired; third-party URL preserved as metadata'}
    if used != set(lookup):
        raise ValueError('Native PATA captions contain an unjoined scene')


@converter('pata_metadata')
def convert_pata(params, inputs, output_dir, check=lambda: None):
    maximum = params.get('max_output_bytes', 20_000_000)
    if type(maximum) is not int or not 1 <= maximum <= 100_000_000:
        raise ValueError('Invalid PATA converted-output byte limit')
    output = output_dir / 'pata-metadata.jsonl'
    digest = RowDigest()
    size = 0
    # Exclusive creation refuses symlinks, existing files and input hard links.
    with output.open('xb') as stream:
        for row in native_rows(inputs['files'], inputs['captions'], check):
            data = (json.dumps(row, ensure_ascii=False) + '\n').encode()
            size += len(data)
            if size > maximum:
                raise ValueError('PATA converted rows exceed the output byte limit')
            stream.write(data)
            digest.add(row)
    return {'path': output, 'format': 'jsonl', 'count': digest.count,
            'rows_sha256': digest.hexdigest(), 'file_sha256': file_sha256(output), 'columns': None}

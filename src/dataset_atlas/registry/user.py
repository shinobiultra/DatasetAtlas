"""Add a researcher's own dataset: inspect a local folder, table or Hugging Face repository, then register it.

Inspection is bounded and read-only: it never copies, moves or modifies the source. Registration writes one
YAML file under `local-config/registry/datasets/`, which is outside version control, so a `git pull` never
touches a user's datasets and nothing here can enter the public catalogue. The registered entry is an
ordinary dataset; the same preparation pipeline builds its complete index and sampled preview.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
import yaml
from dataset_atlas.models import Coverage, Dataset
from . import USER_REGISTRY

IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
TABLE_FORMATS = {'.csv': 'csv', '.tsv': 'csv', '.jsonl': 'jsonl', '.ndjson': 'jsonl', '.json': 'json', '.parquet': 'parquet'}
ARCHIVE_SUFFIXES = ('.zip', '.tar', '.tar.gz', '.tgz')
MAX_SOURCE_BYTES = 2_000_000_000
MAX_CATEGORIES = 50
ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}$')
_NUMBER = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')


def slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:63].strip('-')
    return slug if len(slug) >= 2 else f'dataset-{hashlib.sha256(name.encode()).hexdigest()[:8]}'


def _sha256(path: Path) -> str:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f'{path.name} exceeds the {MAX_SOURCE_BYTES:,}-byte limit for a single local source; use Parquet shards or a folder of files')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _stub(config: dict, adapter: str) -> Dataset:
    return Dataset(id='inspection', name='inspection', adapter=adapter, snapshot_id='inspection', release='inspection', adapter_config=config)


def inspect_source(source: str, options: dict | None = None) -> dict:
    """Describe what Atlas would register, without registering or copying anything."""
    options = dict(options or {})
    if source.startswith('https://') or source.startswith('http://'):
        return _inspect_huggingface(source)
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise ValueError('Give an absolute path to the folder or file')
    if not path.exists():
        raise ValueError(f'No such file or folder: {path}')
    path = path.resolve()
    if path.is_dir() or path.name.lower().endswith(ARCHIVE_SUFFIXES):
        return _inspect_images(path)
    suffix = path.suffix.lower()
    if suffix in TABLE_FORMATS:
        return _inspect_table(path, options)
    raise ValueError(f'Unsupported source type {suffix or "(none)"}. Use a folder of images, a zip/tar archive of images, '
                     'or a .csv/.tsv/.jsonl/.json/.parquet table.')


def _inspect_images(path: Path) -> dict:
    from dataset_atlas.adapters import get_adapter
    config = {'path': str(path), 'suffixes': list(IMAGE_SUFFIXES)}
    if path.is_file():
        config['sha256'] = _sha256(path)
    names = get_adapter(_stub(config, 'directory'))._names()
    if not names:
        raise ValueError('No images found (looked for ' + ', '.join(IMAGE_SUFFIXES) + ').')
    labels = sorted({name.split('/', 1)[0] for name in names if '/' in name})
    warnings = []
    fields = {'path': {'dtype': 'string', 'description': 'Path of the image relative to the chosen folder'}}
    if all('/' in name for name in names) and 2 <= len(labels) <= 1000:
        config['path_regex'] = r'(?P<label>[^/]+)/.+'
        fields['label'] = {'dtype': 'category', 'values': labels, 'description': 'Name of the top-level folder containing the image'}
        # The regex filters names, so recount with it to keep the registered total exact.
        names = get_adapter(_stub(config, 'directory'))._names()
    elif any('/' in name for name in names):
        warnings.append('Images sit at different folder depths, so folder names are not used as labels.')
    config['fields'] = fields
    if path.is_dir():
        size = sum((path / name).lstat().st_size for name in names)
        fingerprint = hashlib.sha256('\n'.join(f'{name}\t{(path / name).lstat().st_size}' for name in names).encode()).hexdigest()
        tables = sorted(p.name for p in path.iterdir() if p.suffix.lower() in TABLE_FORMATS)[:5]
        if tables:
            warnings.append(f'Found metadata table(s) {", ".join(tables)}. To browse their columns beside the images, add that table '
                            'and set its media root to this folder.')
    else:
        size = path.stat().st_size
        fingerprint = config['sha256']
    config['population'] = f'{len(names):,} images from a local {"folder" if path.is_dir() else "archive"}'
    return {'kind': 'images', 'adapter': 'directory', 'adapter_config': config, 'count': len(names), 'unit': 'images', 'bytes': size,
            'fingerprint': fingerprint[:16], 'labels': ['label'] if 'label' in fields else [], 'modalities': ['image'],
            'columns': [{'name': name, 'dtype': spec['dtype'], 'role': 'label' if name == 'label' else None} for name, spec in fields.items()],
            'suggested': {'name': path.stem if path.is_file() else path.name}, 'warnings': warnings}


def _profile_rows(rows):
    """One streaming pass: exact count plus per-column evidence for types and roles."""
    profile, count = {}, 0
    for row in rows:
        count += 1
        for key, value in row.items():
            column = profile.setdefault(key, {'nonnull': 0, 'numeric': True, 'boolean': True, 'strings': 0, 'length': 0, 'image_like': 0,
                                              'distinct': set(), 'types': set(), 'sample': []})
            if value is None or value == '':
                continue
            column['nonnull'] += 1
            column['types'].add(type(value).__name__)
            text = value if isinstance(value, str) else json.dumps(value, default=str) if isinstance(value, (list, dict)) else str(value)
            if isinstance(value, str):
                column['strings'] += 1
                column['length'] += len(value)
                column['numeric'] &= bool(_NUMBER.match(value.strip()))
                column['boolean'] &= value.strip().lower() in {'true', 'false'}
                column['image_like'] += value.lower().endswith(IMAGE_SUFFIXES)
            else:
                column['numeric'] &= isinstance(value, (int, float)) and not isinstance(value, bool)
                column['boolean'] &= isinstance(value, bool)
            if len(column['distinct']) <= 1000 and not isinstance(value, (list, dict)):
                column['distinct'].add(text)
            if len(column['sample']) < 3:
                column['sample'].append(text[:80])
    return count, profile


def _inspect_table(path: Path, options: dict) -> dict:
    from dataset_atlas.adapters import get_adapter
    suffix = path.suffix.lower()
    fmt = TABLE_FORMATS[suffix]
    config = {'path': str(path), 'format': fmt, 'sha256': _sha256(path)}
    if suffix == '.tsv':
        config['delimiter'] = '\t'
    if fmt == 'parquet':
        embedded = _embedded_image_columns(path)
        if embedded:
            return _inspect_embedded_parquet(path, config, embedded)
    adapter = get_adapter(_stub(config, 'structured'))
    count, profile = _profile_rows(adapter._rows())
    if count == 0:
        raise ValueError('The table has no rows.')
    csv_types = {}
    for name, column in profile.items():
        if fmt == 'csv' and column['nonnull'] and column['numeric'] and column['strings'] == column['nonnull']:
            csv_types[name] = 'number'
        elif fmt == 'csv' and column['nonnull'] and column['boolean'] and column['strings'] == column['nonnull']:
            csv_types[name] = 'boolean'
    if csv_types:
        config['csv_types'] = csv_types
    config['sequential_index'] = True
    return _describe_table(path, config, count, profile, csv_types, options, 'structured')


def _describe_table(path, config, count, profile, csv_types, options, adapter):
    total = max(count, 1)
    media = options.get('media_column')
    if media is None:
        media = next((name for name, c in profile.items() if c['nonnull'] and c['image_like'] >= 0.9 * c['nonnull']), None)
    text = options.get('text_column')
    if text is None:
        text = next((name for name, c in profile.items() if name != media and c['strings'] and c['strings'] == c['nonnull']
                     and c['length'] / c['strings'] >= 40), None)
    question = options.get('question_column')
    ident = options.get('id_column')
    if ident is not None and ident not in profile:
        raise ValueError(f'The table has no column named {ident!r}')
    if ident is not None and len(profile[ident]['distinct']) < count:
        raise ValueError(f'Column {ident!r} is not unique, so it cannot identify records. Choose a unique column or none.')
    fields, labels, columns, warnings = {}, [], [], []
    for name, c in profile.items():
        dtype = csv_types.get(name) or ('boolean' if c['boolean'] and c['nonnull'] else 'number' if c['numeric'] and c['nonnull'] else 'string')
        categorical = (dtype == 'string' and name not in {media, text, question, ident} and 0 < len(c['distinct']) <= MAX_CATEGORIES
                       and len(c['distinct']) < c['nonnull'] and len(c['distinct']) <= max(10, 0.2 * total) and c['strings'] == c['nonnull'])
        if categorical:
            fields[name] = {'dtype': 'category', 'values': sorted(c['distinct'])}
            labels.append(name)
        role = 'media' if name == media else 'text' if name == text else 'question' if name == question else 'id' if name == ident else 'label' if categorical else None
        columns.append({'name': name, 'dtype': 'category' if categorical else dtype, 'distinct': len(c['distinct']) if len(c['distinct']) <= 1000 else None,
                        'missing': count - c['nonnull'], 'sample': c['sample'], 'role': role})
    mapping = {key: value for key, value in (('id', ident), ('media', media), ('text', text), ('question', question)) if value}
    if mapping:
        config['mapping'] = mapping
    if fields:
        config['fields'] = fields
    if media:
        root = Path(options.get('media_root') or path.parent).expanduser().resolve()
        config['media_root'] = str(root)
        values = list(_media_values(config, media, 50))
        found = sum(1 for value in values if value and (root / value).is_file())
        if values and found == 0:
            warnings.append(f'None of the first {len(values)} values of {media!r} exist under {root}. Set the media root to the folder holding the images.')
        elif found < len(values):
            warnings.append(f'Only {found} of the first {len(values)} images named in {media!r} exist under {root}; missing images show as placeholders.')
    config['population'] = f'{count:,} rows from a local {config["format"]} table'
    return {'kind': 'table', 'adapter': adapter, 'adapter_config': config, 'count': count, 'unit': 'rows', 'bytes': path.stat().st_size,
            'fingerprint': config['sha256'][:16], 'labels': labels, 'columns': columns, 'warnings': warnings,
            'modalities': (['image'] if media else []) + (['text'] if text or question or not media else []),
            'suggested': {'name': path.stem, 'media_column': media, 'text_column': text, 'id_column': ident, 'media_root': config.get('media_root')}}


def _media_values(config, column, limit):
    from dataset_atlas.adapters import get_adapter
    adapter = get_adapter(_stub({k: v for k, v in config.items() if k != 'mapping'}, 'structured'))
    for index, row in enumerate(adapter._rows()):
        if index >= limit:
            return
        value = row.get(column)
        yield value if isinstance(value, str) else None


def _embedded_image_columns(path: Path) -> list[str]:
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = pq.ParquetFile(path).schema_arrow
    return [field.name for field in schema if pa.types.is_struct(field.type) and 'bytes' in {child.name for child in field.type}]


def _inspect_embedded_parquet(path: Path, config: dict, columns: list[str]) -> dict:
    import pyarrow.parquet as pq
    count = pq.ParquetFile(path).metadata.num_rows
    schema = pq.ParquetFile(path).schema_arrow
    config.update(media_columns=columns, mapping={'media': columns[0]}, sequential_index=True,
                  population=f'{count:,} rows from a local Parquet file with embedded images')
    return {'kind': 'embedded_parquet', 'adapter': 'embedded_parquet', 'adapter_config': config, 'count': count, 'unit': 'rows',
            'bytes': path.stat().st_size, 'fingerprint': config['sha256'][:16], 'labels': [], 'modalities': ['image'],
            'columns': [{'name': f.name, 'dtype': 'image' if f.name in columns else str(f.type), 'role': 'media' if f.name in columns else None} for f in schema],
            'suggested': {'name': path.stem, 'media_column': columns[0]}, 'warnings': []}


def _inspect_huggingface(url: str) -> dict:
    from dataset_atlas.preparation import read_metadata
    parts = urlsplit(url)
    match = re.match(r'^/datasets/([^/]+/[^/]+)(?:/tree/([^/]+)(/.*)?)?/?$', parts.path)
    if parts.hostname != 'huggingface.co' or not match:
        raise ValueError('Only Hugging Face dataset URLs (https://huggingface.co/datasets/<owner>/<name>) or local paths can be added.')
    repo, revision, prefix = match.group(1), match.group(2), (match.group(3) or '').strip('/')
    info = read_metadata(f'https://huggingface.co/api/datasets/{repo}' + (f'/revision/{quote(revision, safe="")}' if revision else '') + '?blobs=true')
    sha = info.get('sha', '')
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError('Hugging Face did not return an immutable revision for this dataset.')
    shards = [s for s in info.get('siblings', []) if s['rfilename'].endswith('.parquet') and (not prefix or s['rfilename'].startswith(prefix + '/'))]
    warnings = []
    if info.get('gated'):
        warnings.append('This repository is gated. Atlas does not bypass gates; configure access on Hugging Face before fetching a preview.')
    if not shards:
        warnings.append('No native Parquet files were found, so Atlas cannot sample it directly. It can still be registered, but a preview needs a source recipe.')
    pinned = f'https://huggingface.co/datasets/{repo}/tree/{sha}' + (f'/{prefix}' if prefix else '')
    name = repo.split('/')[1]
    return {'kind': 'huggingface', 'adapter': 'structured', 'adapter_config': {'population': f'Hugging Face repository {repo} at revision {sha[:12]}'},
            'count': None, 'unit': 'rows', 'bytes': sum(s.get('size') or 0 for s in shards), 'fingerprint': sha[:16], 'labels': [], 'columns': [],
            'modalities': [], 'source_url': pinned, 'revision': sha, 'parquet_shards': len(shards), 'gated': bool(info.get('gated')),
            'suggested': {'name': name}, 'warnings': warnings}


def user_directory(root: Path) -> Path:
    return Path(root) / USER_REGISTRY


def register(root: Path, inspection: dict, *, name: str, dataset_id: str | None = None, description: str = '', replace: bool = False) -> Dataset:
    """Write the entry for an inspected source. The caller's files are never touched."""
    from dataset_atlas.registry import Registry
    root = Path(root).resolve()
    dataset_id = dataset_id or slugify(name)
    if not ID_PATTERN.fullmatch(dataset_id):
        raise ValueError('The dataset ID must be 2-63 characters: lowercase letters, digits and hyphens, starting with a letter or digit.')
    registry = Registry(root)
    existing = registry.resolve(dataset_id)
    if registry.has(existing):
        if registry.baseline_dataset(existing).origin != 'user':
            raise ValueError(f'{dataset_id!r} is part of the shipped catalogue; choose a different ID.')
        if not replace:
            raise ValueError(f'You already added {dataset_id!r}. Choose another ID, or replace it to re-register the source.')
    elif existing != dataset_id:
        raise ValueError(f'{dataset_id!r} is a retired catalogue ID; choose a different ID.')
    remote = inspection['kind'] == 'huggingface'
    local_text = '' if remote else ' Added from local storage; publication rights are not reviewed, so it stays local.'
    entry = Dataset(
        id=dataset_id, name=name.strip() or dataset_id, origin='user',
        description=(description.strip() or inspection['adapter_config'].get('population', '')) + local_text,
        modalities=inspection['modalities'], labels=inspection['labels'], source_url=inspection.get('source_url'),
        release=f"user-{inspection['fingerprint']}", snapshot_id=f"{dataset_id}-user-{inspection['fingerprint']}",
        adapter=inspection['adapter'], adapter_config=inspection['adapter_config'],
        coverage=Coverage(identity='user_supplied', source='verified' if remote else 'local', access='public' if remote else 'locally_supplied',
                          adapter='implemented', preview='none', complete_data='requires_preparation', publication='not_reviewed',
                          preview_count=0, total_count=inspection['count'], unit='example'),
        evidence=[{'kind': 'user_registration', 'registered_at': datetime.now(timezone.utc).isoformat(), 'fingerprint': inspection['fingerprint'],
                   'population': inspection['adapter_config'].get('population', ''), 'record_count': inspection['count']}])
    directory = user_directory(root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{dataset_id}.yaml'
    temporary = target.with_name(target.name + '.tmp')
    temporary.write_text(yaml.safe_dump(entry.model_dump(mode='json'), sort_keys=False, allow_unicode=True))
    temporary.replace(target)
    registry.refresh()
    return entry


def unregister(root: Path, dataset_id: str, *, purge: bool = False) -> dict:
    """Remove a user dataset's registration. The source files are never touched; prepared data only with `purge`."""
    import shutil
    from dataset_atlas.registry import Registry
    root = Path(root).resolve()
    registry = Registry(root)
    if not registry.has(dataset_id) or registry.baseline_dataset(dataset_id).origin != 'user':
        raise KeyError(f'{dataset_id!r} is not a dataset you added.')
    (user_directory(root) / f'{dataset_id}.yaml').unlink()
    removed = []
    if purge:
        for sub in ('work/prepared', 'work/packs', 'work/snapshots'):
            target = root / sub / dataset_id
            if target.exists():
                shutil.rmtree(target)
                removed.append(sub + '/' + dataset_id)
    registry.refresh()
    return {'dataset_id': dataset_id, 'source_files_touched': False, 'purged': removed}

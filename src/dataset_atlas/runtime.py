"""Local runtime policy, loaded by trusted server/CLI rather than model inputs."""
from pathlib import Path
import json

def roots_for(root: Path, kind: str) -> list[Path]:
    defaults={'data_roots':[root/'work/packs',root/'work/media-cache'], 'model_roots':[root/'work/models',root/'local-config/models']}
    path=root/'local-config/settings.json'
    settings=json.loads(path.read_text()) if path.exists() else {}
    if kind not in settings:
        for directory in defaults[kind]:directory.mkdir(parents=True,exist_ok=True)
    values=settings.get(kind,defaults[kind])
    if not isinstance(values,list) or not values:raise ValueError(f'{kind} must be a nonempty array of configured roots')
    return [(root/Path(p)).resolve() if not Path(p).is_absolute() else Path(p).resolve() for p in values]

def analysis_config(root: Path, config: dict, data_roots: list[Path]|None=None) -> dict:
    result=dict(config)
    result['asset_roots']=[str(p) for p in (data_roots or roots_for(root,'data_roots'))]
    models=roots_for(root,'model_roots')
    result['model_roots']=[str(p) for p in models]
    for key in ('model_path','weights_path'):
        if key in result:
            path=Path(result[key]).expanduser().resolve()
            if not any(path.is_relative_to(r) for r in models):raise ValueError(f'{key} must be inside configured model_roots in local-config/settings.json')
            if not path.exists():raise ValueError(f'{key} does not exist')
            result[key]=str(path)
    return result

def resolve_record_media(record,root: Path,data_roots: list[Path]|None=None):
    copy=record.model_copy(deep=True)
    roots=data_roots or roots_for(root,'data_roots')
    for asset in copy.assets:
        if not asset.uri or '://' in asset.uri or asset.uri.startswith('data:'):continue
        path=Path(asset.uri)
        if not path.is_absolute():path=root/'work/packs'/asset.dataset_id/path
        path=path.resolve()
        if not any(path.is_relative_to(r) for r in roots):raise ValueError('Asset outside configured data_roots')
        asset.uri=str(path)
    return copy

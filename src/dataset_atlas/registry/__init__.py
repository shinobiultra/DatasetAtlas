"""Read-only registry and immutable pack loading."""
from pathlib import Path
import json
import yaml
from dataset_atlas.models import Dataset, Pack

class Registry:
    def __init__(self, root: Path):
        self.root=Path(root).resolve()
        self._signature=None
        self._datasets=[]
        self._packs={}
    def datasets(self) -> list[Dataset]:
        files=sorted((self.root/'registry/datasets').glob('*.yaml'))
        signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files)
        if signature!=self._signature:
            self._datasets=[Dataset.model_validate(yaml.safe_load(p.read_text())) for p in files]
            if len({d.id for d in self._datasets})!=len(self._datasets):raise ValueError('Duplicate dataset IDs')
            self._signature=signature
        return list(self._datasets)
    def dataset(self, dataset_id: str) -> Dataset:
        for dataset in self.datasets():
            if dataset.id==dataset_id:
                copy=dataset.model_copy(deep=True)
                for key in ('root','path','archive','prepared_root','images_archive','videos_archive','annotations_archive','media_archive','media_root'):
                    value=copy.adapter_config.get(key)
                    if isinstance(value,str) and '://' not in value and not Path(value).is_absolute():copy.adapter_config[key]=str(self.root/value)
                return copy
        raise KeyError(dataset_id)
    def pack(self, dataset_id: str) -> Pack:
        self.dataset(dataset_id)
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'}:raise ValueError('Invalid dataset ID')
        path=self.root/'work/packs'/dataset_id/'pack.json'
        if not path.is_file():raise FileNotFoundError('No prepared preview. Inspect dataset coverage and run atlas datasets prepare.')
        if path.stat().st_size>100_000_000:raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
        signature=(path.stat().st_mtime_ns,path.stat().st_size)
        cached=self._packs.get(dataset_id)
        if cached is None or cached[0]!=signature:
            cached=(signature,Pack.model_validate_json(path.read_text()))
            self._packs[dataset_id]=cached
        return cached[1]

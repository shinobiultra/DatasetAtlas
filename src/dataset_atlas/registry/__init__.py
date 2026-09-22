"""Read-only registry and immutable pack loading."""
from pathlib import Path
import json
import time
import yaml
from dataset_atlas.models import Dataset, Pack

# Registry YAML changes are rare and human-paced; stat-ing every file on every
# lookup is not. Resolving a 100-record selection used to sweep 33,600 files.
BASELINE_RECHECK_SECONDS = 0.5

class Registry:
    def __init__(self, root: Path):
        self.root=Path(root).resolve()
        self._signature=None
        self._datasets=[]
        self._packs={}
        self._active_datasets={}
        self._by_id={}
        self._baseline_checked=0.0
        self._versions={}
    def refresh(self):
        """Force the next lookup to re-read registry files regardless of the recheck window."""
        self._baseline_checked=0.0
    def has(self, dataset_id) -> bool:
        self._refresh_baseline()
        return dataset_id in self._by_id
    def ids(self) -> list[str]:
        """Catalogue IDs without resolving any prepared version; cheap enough to call per lookup."""
        self._refresh_baseline()
        return list(self._by_id)
    def _refresh_baseline(self):
        now=time.monotonic()
        if self._signature is not None and now-self._baseline_checked<BASELINE_RECHECK_SECONDS:return
        self._baseline_checked=now
        files=sorted((self.root/'registry/datasets').glob('*.yaml'))
        signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files)
        if signature!=self._signature:
            self._datasets=[Dataset.model_validate(yaml.safe_load(p.read_text())) for p in files]
            if len({d.id for d in self._datasets})!=len(self._datasets):raise ValueError('Duplicate dataset IDs')
            self._by_id={d.id:d for d in self._datasets}
            self._signature=signature
    def _active_dataset(self, baseline):
        active=self.active_directory(baseline.id)
        if not active:return baseline
        path=active/'dataset.json'
        stat=path.stat()
        signature=(str(path),stat.st_mtime_ns,stat.st_size)
        cached=self._active_datasets.get(baseline.id)
        if cached is None or cached[0]!=signature:
            dataset=Dataset.model_validate_json(path.read_text())
            if dataset.id!=baseline.id:raise ValueError('Prepared dataset identity mismatch')
            cached=(signature,dataset)
            self._active_datasets[baseline.id]=cached
        return cached[1]
    def datasets(self) -> list[Dataset]:
        self._refresh_baseline()
        return [self._active_dataset(dataset) for dataset in self._datasets]
    def active_directory(self, dataset_id):
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'}:raise ValueError('Invalid dataset ID')
        base=self.root/'work/prepared'/dataset_id
        pointer=base/'active.json'
        if not pointer.is_file():return None
        name=json.loads(pointer.read_text())['version']
        path=(base/name).resolve()
        if path.parent!=base.resolve():raise ValueError('Invalid prepared version')
        return path
    def snapshot_path(self, dataset_id):
        active=self.active_directory(dataset_id)
        return active/'snapshot' if active else self.root/'work/snapshots'/dataset_id

    def versions(self, dataset_id):
        self._refresh_baseline()
        baseline=self._by_id.get(dataset_id)
        if baseline is None:raise KeyError(dataset_id)
        active=self.active_directory(dataset_id)
        directories=sorted((self.root/'work/prepared'/dataset_id).glob('*/dataset.json'))
        if active:directories.sort(key=lambda p:p.parent!=active)
        # Re-read only when a version document or the baseline actually changed.
        signature=(self._signature and id(self._datasets),str(active),tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in directories))
        cached=self._versions.get(dataset_id)
        if cached is not None and cached[0]==signature:return list(cached[1])
        versions=[]
        for path in directories:
            dataset=Dataset.model_validate_json(path.read_text())
            versions.append((self._resolved(dataset),path.parent/'pack/pack.json',path.parent/'snapshot'))
        versions.append((self._resolved(baseline),self.root/'work/packs'/dataset_id/'pack.json',self.root/'work/snapshots'/dataset_id))
        self._versions[dataset_id]=(signature,versions)
        return list(versions)
    def dataset_version(self, dataset_id, release_id):
        for dataset,_,_ in self.versions(dataset_id):
            if dataset.release==release_id:return dataset
        raise KeyError('Dataset release is not prepared')
    def _resolved(self, dataset):
        copy=dataset.model_copy(deep=True)
        for key in copy.adapter_config:
            if key not in {'root','path','archive'} and not key.endswith(('_root','_path','_archive')):continue
            value=copy.adapter_config.get(key)
            if isinstance(value,str) and '://' not in value and not Path(value).is_absolute():copy.adapter_config[key]=str(self.root/value)
        return copy
    def dataset(self, dataset_id: str) -> Dataset:
        self._refresh_baseline()
        if dataset_id not in self._by_id:raise KeyError(dataset_id)
        return self._resolved(self._active_dataset(self._by_id[dataset_id]))
    def pack(self, dataset_id: str) -> Pack:
        self.dataset(dataset_id)
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'}:raise ValueError('Invalid dataset ID')
        active=self.active_directory(dataset_id)
        path=active/'pack/pack.json' if active else self.root/'work/packs'/dataset_id/'pack.json'
        if not path.is_file():raise FileNotFoundError('No prepared preview. Inspect dataset coverage and run atlas datasets prepare.')
        if path.stat().st_size>100_000_000:raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
        signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
        cached=self._packs.get(dataset_id)
        if cached is None or cached[0]!=signature:
            cached=(signature,Pack.model_validate_json(path.read_text()))
            self._packs[dataset_id]=cached
        return cached[1]

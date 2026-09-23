"""Read-only registry and immutable pack loading."""
from pathlib import Path
import json
import time
import yaml
from dataset_atlas.models import Dataset, Pack

# Registry YAML changes are rare and human-paced; stat-ing every file on every
# lookup is not. Resolving a 100-record selection used to sweep 33,600 files.
BASELINE_RECHECK_SECONDS = 0.5


def merge_prepared(baseline: Dataset, prepared: Dataset, recipe_present: bool, recipe_fields: set[str] | None = None) -> Dataset:
    """Combine the tracked registry record with what a preparation determined.

    Preparation legitimately fixes the release, snapshot, adapter and coverage,
    and may append its own evidence. Everything descriptive — name, aliases,
    paper links, rights, relationships and the source audits — stays owned by the
    registry YAML, so a later review edit is visible while the version is active
    instead of being frozen at plan time. A recipe may override the description
    and source URL for the population it prepares; those follow the prepared copy
    only when a recipe exists to have set them.
    """
    merged=baseline.model_copy(deep=True)
    merged.release=prepared.release
    merged.snapshot_id=prepared.snapshot_id
    merged.adapter=prepared.adapter
    merged.adapter_config=dict(prepared.adapter_config)
    merged.coverage=prepared.coverage.model_copy(deep=True)
    # Source audits and rights decisions remain registry-owned after preparation.
    for field in ('identity','source','access','publication'):
        setattr(merged.coverage,field,getattr(baseline.coverage,field))
    if recipe_present:
        if (recipe_fields is None or 'description' in recipe_fields) and prepared.description!=baseline.description:merged.description=prepared.description
        if (recipe_fields is None or 'source_url' in recipe_fields) and prepared.source_url!=baseline.source_url:merged.source_url=prepared.source_url
    local=[item for item in prepared.evidence if item.get('kind')=='local_preparation']
    merged.evidence=[item for item in baseline.evidence if item.get('kind')!='local_preparation']+local
    return merged

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
        self._aliases={}
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
        dispositions=self.root/'registry/candidate_dispositions.yaml'
        signature=tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files+([dispositions] if dispositions.is_file() else []))
        if signature!=self._signature:
            self._datasets=[Dataset.model_validate(yaml.safe_load(p.read_text())) for p in files]
            if len({d.id for d in self._datasets})!=len(self._datasets):raise ValueError('Duplicate dataset IDs')
            self._by_id={d.id:d for d in self._datasets}
            self._aliases=self._retired_aliases(dispositions)
            self._signature=signature
    def _retired_aliases(self, dispositions):
        """Retired IDs -> canonical ID, from confirmed alias redirects and `alias_resolved_from` relationships.

        A retired ID never shadows a live catalogue entry, and a redirect to an unknown canonical ID is ignored
        rather than inventing a dataset."""
        aliases={}
        rules=yaml.safe_load(dispositions.read_text()) if dispositions.is_file() else {}
        for rule in (rules or {}).get('alias_redirects',[]) or []:
            aliases[str(rule.get('alias_id'))]=str(rule.get('canonical_id'))
        for dataset in self._datasets:
            for relationship in dataset.relationships:
                if isinstance(relationship,dict) and relationship.get('type')=='alias_resolved_from' and relationship.get('target_id'):
                    aliases[str(relationship['target_id'])]=dataset.id
        return {alias:canonical for alias,canonical in aliases.items() if alias not in self._by_id and canonical in self._by_id}
    def resolve(self, dataset_id: str) -> str:
        """Canonical ID for a live or retired dataset ID; unknown IDs are returned unchanged."""
        self._refresh_baseline()
        if dataset_id in self._by_id:return dataset_id
        return self._aliases.get(dataset_id,dataset_id)
    def _active_dataset(self, baseline):
        active=self.active_directory(baseline.id)
        if not active:return baseline
        path=active/'dataset.json'
        stat=path.stat()
        # The merge depends on both documents, so the cache key covers both.
        recipe_path=self.root/'registry/recipes'/f'{baseline.id}.yaml'
        recipe_stat=recipe_path.stat() if recipe_path.is_file() else None
        signature=(str(path),stat.st_mtime_ns,stat.st_size,id(self._datasets),recipe_stat.st_mtime_ns if recipe_stat else None)
        cached=self._active_datasets.get(baseline.id)
        if cached is None or cached[0]!=signature:
            prepared=Dataset.model_validate_json(path.read_text())
            if prepared.id!=baseline.id:raise ValueError('Prepared dataset identity mismatch')
            recipe_fields=set(yaml.safe_load(recipe_path.read_text()) or {}) if recipe_stat else set()
            cached=(signature,merge_prepared(baseline,prepared,bool(recipe_stat),recipe_fields))
            self._active_datasets[baseline.id]=cached
        return cached[1]
    def datasets(self) -> list[Dataset]:
        self._refresh_baseline()
        return [self._active_dataset(dataset) for dataset in self._datasets]
    def active_directory(self, dataset_id):
        dataset_id=self.resolve(dataset_id)
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'}:raise ValueError('Invalid dataset ID')
        base=self.root/'work/prepared'/dataset_id
        pointer=base/'active.json'
        if not pointer.is_file():return None
        name=json.loads(pointer.read_text())['version']
        path=(base/name).resolve()
        if path.parent!=base.resolve():raise ValueError('Invalid prepared version')
        return path
    def snapshot_path(self, dataset_id):
        dataset_id=self.resolve(dataset_id)
        active=self.active_directory(dataset_id)
        return active/'snapshot' if active else self.root/'work/snapshots'/dataset_id

    def versions(self, dataset_id):
        self._refresh_baseline()
        dataset_id=self.resolve(dataset_id)
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
        dataset_id=self.resolve(dataset_id)
        if dataset_id not in self._by_id:raise KeyError(dataset_id)
        return self._resolved(self._active_dataset(self._by_id[dataset_id]))
    def baseline_dataset(self, dataset_id: str) -> Dataset:
        """Tracked source configuration, without inheriting an active version's paths."""
        dataset_id=self.resolve(dataset_id)
        if dataset_id not in self._by_id:raise KeyError(dataset_id)
        return self._resolved(self._by_id[dataset_id])
    def pack(self, dataset_id: str) -> Pack:
        dataset_id=self.resolve(dataset_id)
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

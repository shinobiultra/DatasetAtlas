"""Read-only registry and immutable pack loading."""
from pathlib import Path
import json
import time
import yaml
from dataset_atlas.models import Dataset, Pack

# Registry YAML changes are rare and human-paced; stat-ing every file on every
# lookup is not. Resolving a 100-record selection used to sweep 33,600 files.
BASELINE_RECHECK_SECONDS = 0.5
USER_REGISTRY = 'local-config/registry/datasets'


def _revision(stat):
    return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns


def _pack_dataset(path: Path) -> Dataset:
    """Decode a frozen pack's Dataset header without constructing its record models.

    Atlas writes this header before records. Other JSON field orders are still
    accepted under the same pack byte bound.
    """
    if path.stat().st_size>100_000_000:raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
    with path.open(encoding='utf-8') as stream:
        buffer=stream.read(65_536)
        position=0
        decoder=json.JSONDecoder()
        def character():
            nonlocal buffer
            while position>=len(buffer):
                chunk=stream.read(65_536)
                if not chunk:return ''
                buffer+=chunk
            return buffer[position]
        def whitespace():
            nonlocal position
            while character().isspace():position+=1
        def decode():
            nonlocal buffer,position
            whitespace()
            while True:
                try:
                    value,position=decoder.raw_decode(buffer,position)
                    return value
                except json.JSONDecodeError as error:
                    chunk=stream.read(65_536)
                    if not chunk:raise ValueError('Invalid frozen pack metadata') from error
                    buffer+=chunk
        whitespace()
        if character()!='{':raise ValueError('Invalid frozen pack metadata')
        position+=1
        while True:
            key=decode()
            whitespace()
            if character()!=':':raise ValueError('Invalid frozen pack metadata')
            position+=1
            value=decode()
            if key=='dataset':return Dataset.model_validate(value)
            whitespace()
            if character()!=',':raise ValueError('Pack dataset metadata is missing')
            position+=1


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
    # Adapter verification describes the current software, independently of the
    # older preparation's frozen record/coverage metadata.
    if baseline.coverage.adapter=='tested':merged.coverage.adapter='tested'
    # Blocker wording is reviewed in the registry after a version is prepared.
    # Apply the same removal of disproven acquisition blockers used by the worker,
    # without freezing the plan-time blocker list in an active snapshot.
    from dataset_atlas.preparation import prepared_metadata
    blocker_view=merged.model_copy(deep=True)
    blocker_view.coverage.blockers=list(baseline.coverage.blockers)
    merged.coverage.blockers=prepared_metadata(blocker_view, '').coverage.blockers
    if recipe_present:
        resolved=any(item.get('kind')=='source_release_resolution' for item in baseline.evidence)
        if not resolved and (recipe_fields is None or 'description' in recipe_fields) and prepared.description!=baseline.description:merged.description=prepared.description
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
        self._snapshot_checked=0.0
        self._snapshot_registry=None
        self._snapshot_sources={}
        self._snapshot_index={}
        self._snapshot_headers={}
        self._snapshot_locations={}
    def refresh(self):
        """Force the next lookup to re-read registry files regardless of the recheck window."""
        self._baseline_checked=0.0
        self._snapshot_checked=0.0
    def has(self, dataset_id) -> bool:
        self._refresh_baseline()
        return dataset_id in self._by_id
    def ids(self) -> list[str]:
        """Catalogue IDs without resolving any prepared version; cheap enough to call per lookup."""
        self._refresh_baseline()
        return list(self._by_id)
    def ids_for_snapshots(self, snapshot_ids) -> list[str]:
        """Discover literal local IDs for explicit snapshots, without listing archived cards.

        Snapshot strings are compared only as metadata values. They never form
        filesystem paths. Empty input keeps ordinary current-catalogue discovery.
        """
        if isinstance(snapshot_ids,str):raise ValueError('Snapshot IDs must be a collection')
        requested=set(snapshot_ids or ())
        if not requested:return self.ids()
        if any(not isinstance(item,str) for item in requested):raise ValueError('Snapshot IDs must be strings')
        self._refresh_snapshot_metadata()
        return sorted({dataset_id for snapshot in requested for dataset_id in self._snapshot_index.get(snapshot,())})
    def _refresh_snapshot_metadata(self):
        self._refresh_baseline()
        now=time.monotonic()
        if now-self._snapshot_checked>=BASELINE_RECHECK_SECONDS or self._snapshot_registry is not self._datasets:
            prepared=list((self.root/'work/prepared').glob('*/*/dataset.json'))
            manifests=list((self.root/'work/snapshots').glob('*/manifest.json'))
            packs=list((self.root/'work/packs').glob('*/pack.json'))
            if len(prepared)+len(manifests)+len(packs)>10_000:raise ValueError('Snapshot metadata inventory exceeds lookup budget')
            index={}
            sources={}
            headers={}
            locations={}
            def add(dataset_id,snapshot):
                if snapshot:index.setdefault(snapshot,set()).add(dataset_id)
            for dataset in self._datasets:add(dataset.id,dataset.snapshot_id)
            for kind,paths in (('prepared',prepared),('manifest',manifests),('pack',packs)):
                for path in paths:
                    stat=path.stat()
                    signature=_revision(stat)
                    previous=self._snapshot_sources.get(str(path))
                    if previous and previous[0]==signature:
                        _,dataset_id,snapshot=previous
                        if kind=='pack':headers[str(path)]=self._snapshot_headers[str(path)]
                    else:
                        expected=path.parents[1].name if kind=='prepared' else path.parent.name
                        if kind=='pack':
                            dataset=_pack_dataset(path)
                            dataset_id,snapshot=dataset.id,dataset.snapshot_id
                            headers[str(path)]=dataset
                        else:
                            if stat.st_size>20_000_000:raise ValueError('Snapshot metadata document exceeds lookup budget')
                            document=json.loads(path.read_text())
                            dataset_id=document['id' if kind=='prepared' else 'dataset_id']
                            snapshot=document['snapshot_id']
                        if kind=='prepared' and dataset_id!=expected:raise ValueError('Snapshot dataset identity mismatch')
                        if not isinstance(dataset_id,str) or not dataset_id or '/' in dataset_id or '\\' in dataset_id or '\0' in dataset_id or dataset_id in {'.','..'}:
                            raise ValueError('Invalid snapshot dataset identity')
                        if not isinstance(snapshot,str):raise ValueError('Invalid snapshot identity')
                    sources[str(path)]=(signature,dataset_id,snapshot)
                    locations.setdefault((dataset_id,snapshot),[]).append((kind,path))
                    add(dataset_id,snapshot)
            self._snapshot_sources=sources
            self._snapshot_index=index
            self._snapshot_headers=headers
            self._snapshot_locations=locations
            self._snapshot_registry=self._datasets
            self._snapshot_checked=time.monotonic()
    def _refresh_baseline(self):
        now=time.monotonic()
        if self._signature is not None and now-self._baseline_checked<BASELINE_RECHECK_SECONDS:return
        self._baseline_checked=now
        files=sorted((self.root/'registry/datasets').glob('*.yaml'))
        # A researcher's own datasets sit beside the shipped catalogue, outside version control.
        user_files=sorted((self.root/USER_REGISTRY).glob('*.yaml'))
        signature=tuple((str(p),_revision(p.stat())) for p in files+user_files)
        if signature!=self._signature:
            self._datasets=[Dataset.model_validate(yaml.safe_load(p.read_text())) for p in files]
            for path in user_files:
                entry=Dataset.model_validate(yaml.safe_load(path.read_text()))
                if entry.origin!='user':raise ValueError(f'{path.name}: datasets added from local storage must declare origin: user')
                self._datasets.append(entry)
            if len({d.id for d in self._datasets})!=len(self._datasets):raise ValueError('Duplicate dataset IDs')
            self._by_id={d.id:d for d in self._datasets}
            self._aliases=self._declared_aliases()
            self._signature=signature
    def _declared_aliases(self):
        """Resolve explicit names of live datasets; ambiguous aliases never choose an entry."""
        aliases={}
        for dataset in self._datasets:
            for alias in dataset.aliases:
                if alias and alias not in self._by_id:
                    aliases.setdefault(alias,set()).add(dataset.id)
        return {alias:next(iter(ids)) for alias,ids in aliases.items() if len(ids)==1}
    def resolve(self, dataset_id: str) -> str:
        """Canonical ID for a live entry or its declared alias; unknown IDs stay unchanged."""
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
        signature=(str(path),_revision(stat),id(self._datasets),_revision(recipe_stat) if recipe_stat else None)
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
    def local_state(self, dataset_id):
        """(has preview pack, has complete index) as actually present in this workspace; stat calls only."""
        dataset_id=self.resolve(dataset_id)
        active=self.active_directory(dataset_id)
        pack=active/'pack/pack.json' if active else self.root/'work/packs'/dataset_id/'pack.json'
        return pack.is_file(),(self.snapshot_path(dataset_id)/'manifest.json').is_file()
    def snapshot_path(self, dataset_id):
        dataset_id=self.resolve(dataset_id)
        active=self.active_directory(dataset_id)
        return active/'snapshot' if active else self.root/'work/snapshots'/dataset_id

    def versions(self, dataset_id, *, release_id=None, snapshot_id=None):
        """Read retained versions, allowing absent catalogue IDs only with an explicit binding.

        A release or snapshot selects the literal frozen dataset ID, never a
        current alias. Baseline preview packs retain their own Dataset metadata
        after a card changes or leaves the catalogue.
        """
        self._refresh_baseline()
        explicit=release_id is not None or snapshot_id is not None
        if not explicit:dataset_id=self.resolve(dataset_id)
        if not dataset_id or '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'} or '\0' in dataset_id:
            raise ValueError('Invalid dataset ID')
        baseline=self._by_id.get(dataset_id)
        if baseline is None and not explicit:raise KeyError(dataset_id)
        active=self.active_directory(dataset_id) if not explicit else None
        directories=sorted((self.root/'work/prepared'/dataset_id).glob('*/dataset.json'))
        if active:directories.sort(key=lambda p:p.parent!=active)
        pack_path=self.root/'work/packs'/dataset_id/'pack.json'
        pack_stat=pack_path.stat() if explicit and pack_path.is_file() else None
        # Parsing frozen pack metadata is bounded and cached per file revision.
        signature=(id(self._datasets),str(active),tuple((str(p),_revision(p.stat())) for p in directories),
                   _revision(pack_stat) if pack_stat else None)
        cache_key=(dataset_id,explicit)
        cached=self._versions.get(cache_key)
        if cached is not None and cached[0]==signature:
            versions=cached[1]
        else:
            versions=[]
            for path in directories:
                dataset=Dataset.model_validate_json(path.read_text())
                if dataset.id!=dataset_id:raise ValueError('Prepared dataset identity mismatch')
                versions.append((self._resolved(dataset),path.parent/'pack/pack.json',path.parent/'snapshot'))
            if pack_stat:
                if pack_stat.st_size>100_000_000:raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
                frozen=_pack_dataset(pack_path)
                if frozen.id!=dataset_id:raise ValueError('Frozen baseline dataset identity mismatch')
                versions.append((self._baseline_version(frozen),pack_path,self.root/'work/snapshots'/dataset_id))
            elif baseline is not None:
                versions.append((self._resolved(baseline),pack_path,self.root/'work/snapshots'/dataset_id))
            self._versions[cache_key]=(signature,versions)
        matches=[item for item in versions if (release_id is None or item[0].release==release_id)
                 and (snapshot_id is None or item[0].snapshot_id==snapshot_id)]
        if explicit and (not matches or snapshot_id is None):
            self._refresh_snapshot_metadata()
            known={str(path) for _,path,_ in matches}
            for (identity,snapshot),locations in self._snapshot_locations.items():
                if identity!=dataset_id or (snapshot_id is not None and snapshot!=snapshot_id):continue
                for kind,path in locations:
                    if kind!='pack' or str(path) in known:continue
                    frozen=self._snapshot_headers[str(path)]
                    if release_id is not None and frozen.release!=release_id:continue
                    matches.append((self._baseline_version(frozen),path,self.root/'work/snapshots'/path.parent.name))
                    known.add(str(path))
        return matches
    def dataset_version(self, dataset_id, release_id, snapshot_id=None):
        matches=self.versions(dataset_id,release_id=release_id,snapshot_id=snapshot_id)
        if snapshot_id is None and len({dataset.snapshot_id for dataset,_,_ in matches if dataset.snapshot_id})>1:
            raise KeyError('Dataset release has multiple retained snapshots; specify a snapshot ID')
        if matches:return matches[0][0]
        raise KeyError('Dataset release is not prepared')
    def _baseline_version(self,frozen):
        """Restore private source routing only for the exact current frozen identity.

        Preview packs may omit adapter configuration. Their content, rights and
        descriptive metadata remain frozen; a different or retired identity can
        never inherit the current catalogue's source route.
        """
        baseline=self._by_id.get(frozen.id)
        if baseline is not None and (baseline.id,baseline.release,baseline.snapshot_id)==(frozen.id,frozen.release,frozen.snapshot_id):
            frozen=frozen.model_copy(update={'adapter':baseline.adapter,'adapter_config':baseline.adapter_config})
        return self._resolved(frozen)
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
        # Existence only: dataset() deep-copies adapter configuration, which for
        # sharded releases is large and made every pack lookup cost milliseconds.
        if dataset_id not in self._by_id:raise KeyError(dataset_id)
        if '/' in dataset_id or '\\' in dataset_id or dataset_id in {'.','..'}:raise ValueError('Invalid dataset ID')
        active=self.active_directory(dataset_id)
        path=active/'pack/pack.json' if active else self.root/'work/packs'/dataset_id/'pack.json'
        if not path.is_file():raise FileNotFoundError('No prepared preview. Inspect dataset coverage and run atlas datasets prepare.')
        if path.stat().st_size>100_000_000:raise ValueError('Pack exceeds interactive size budget; prepare a bounded preview')
        signature=(str(path),_revision(path.stat()))
        cached=self._packs.get(dataset_id)
        if cached is None or cached[0]!=signature:
            cached=(signature,Pack.model_validate_json(path.read_text()))
            self._packs[dataset_id]=cached
        return cached[1]

"""Native aligned sentences and complete original article audio, never synthetic clips."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3

from .core import DatasetAdapter,StructuredAdapter,SourceDescription,MediaHandle,_safe_relative
from .remote_columnar import MediaLimitError
from dataset_atlas.storage import BoundedCache
from dataset_atlas.storage.indexed_tar import read_tar_member

_MIME={'.ogg':'audio/ogg','.wav':'audio/wav','.mp3':'audio/mpeg','.flac':'audio/flac'}


class SpokenWikipediaAdapter(StructuredAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        self.indices={key:Path(path) for key,path in self.config.get('native_audio_archives',{}).items()}
        self.bytes_fetched=0;self.preparation_transfer_limit: int | None=None
        self._indices_checked=False

    def probe(self):
        source=super().probe()
        present=source.exists and all((index/'receipt.json').is_file() for index in self.indices.values())
        return SourceDescription('native SWC sentences and article audio',source.location,present,self.revision,
            source.size_bytes,True,True,True,True,True,('Audio assets are complete released article recordings. Sentence alignment XML is preserved; no sentence clips are fabricated.',))

    def _verify_indices(self):
        if self._indices_checked:return
        from dataset_atlas.preparation.zip_tar import verified_index
        sources=self.config.get('native_audio_sources',{})
        if not self.indices or set(self.indices)!=set(sources):raise ValueError('Native audio archives require exact pinned source identities')
        for language,index in self.indices.items():
            if verified_index(index,sources[language]) is None:raise ValueError('Native audio index is unavailable')
        self._indices_checked=True

    def prepare(self,approved_plan):
        source=super().prepare(approved_plan);self._verify_indices();return source

    def prepare_media(self,approved_plan):
        source=DatasetAdapter.prepare(self,approved_plan);self._verify_indices();return source

    def _record(self,row,ordinal):
        record=super()._record(row,ordinal)
        native=json.loads(row.get('native_audio_json','[]'))
        if not isinstance(native,list) or len(native)>64:raise ValueError('Native article audio inventory exceeds its bound')
        by_ref={item['ref']:item for item in native}
        if len(by_ref)!=len(native) or set(by_ref)!={asset.uri for asset in record.assets}:
            raise ValueError('Native audio inventory and asset references differ')
        for asset in record.assets:
            item=by_ref[asset.uri];asset.sha256=item['sha256']
            asset.metadata.update(original_bytes=item['bytes'],source_member=item['member'],language=row['language'],
                representation='original',audio_extent='complete native article recording part; native sentence timing is preserved separately',
                original_media_type=_MIME[Path(item['member']).suffix.lower()],native_audio_tar_sha256=item['source_tar_sha256'])
        return record

    def resolve_asset(self,source,asset_ref):
        prefix,language,member=asset_ref.split('/',2)
        if prefix!='audio' or language not in self.indices:raise ValueError('Unknown native audio archive')
        _safe_relative(member);suffix=Path(member).suffix.lower()
        if suffix not in _MIME:raise ValueError('Unsupported native audio member encoding')
        index=self.indices[language]
        maximum=min(self.config.get('max_audio_bytes',100_000_000),source.max_bytes-source.bytes_read)
        with sqlite3.connect((index/'members.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
            row=db.execute('SELECT bytes FROM members WHERE name=?',(member,)).fetchone()
        if row is None:raise FileNotFoundError('Native article audio is absent')
        if row[0]>maximum:raise MediaLimitError('Native audio exceeds the original-byte preview limit')
        remaining=self.config.get('media_transfer_bytes',150_000_000)
        if self.preparation_transfer_limit is not None:remaining=min(remaining,self.preparation_transfer_limit-self.bytes_fetched)
        if remaining<1:raise ValueError('Native audio aggregate transfer budget exhausted')
        cache=BoundedCache(self.config['remote_cache_root'],self.config.get('remote_cache_bytes',200_000_000))
        data,proof=read_tar_member(index,member,max_bytes=maximum,transfer_bytes=remaining,cache=cache)
        self.bytes_fetched+=proof['transferred_bytes'];source.charge(len(data))
        return MediaHandle(data,_MIME[suffix],proof['sha256'],asset_ref)

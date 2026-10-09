"""Official Oxford Pets and DTD archive annotations, with original split membership."""
from __future__ import annotations
import json
from pathlib import Path
import tarfile
from .core import DirectoryArchiveAdapter, DatasetAdapter, RecordBatch


class OxfordArchiveAdapter(DirectoryArchiveAdapter):
    def _rows(self):
        if hasattr(self, '_metadata_rows'):return self._metadata_rows
        kind=self.config['dataset_kind']
        path=Path(self.config.get('annotations_archive',self.config['path']))
        with tarfile.open(path) as archive:
            def lines(name):
                member=archive.getmember(name)
                if not member.isfile() or member.size>2_000_000:raise ValueError('Annotation member exceeds bound')
                return archive.extractfile(member).read().decode().splitlines()
            rows={}
            if kind=='pets':
                for split in ('trainval','test'):
                    for line in lines(f'annotations/{split}.txt'):
                        if not line.strip() or line.startswith('#'):continue
                        name,class_id,species,breed_id=line.split()
                        if name in rows:raise ValueError('Pet appears in multiple original splits')
                        rows[name]={'image':f'images/{name}.jpg','image_id':name,'class_id':int(class_id),
                            'species_id':int(species),'breed_id':int(breed_id),'breed':name.rsplit('_',1)[0],
                            'split':split,'trimap':f'annotations/trimaps/{name}.png'}
            elif kind=='dtd':
                for partition in range(1,11):
                    for split in ('train','val','test'):
                        for name in lines(f'dtd/labels/{split}{partition}.txt'):
                            if not name:continue
                            row=rows.setdefault(name,{'image':f'dtd/images/{name}','image_id':name,'label':name.split('/')[0]})
                            key=f'split_{partition}'
                            if key in row:raise ValueError('DTD image duplicated within a partition')
                            row[key]=split
                if any(any(f'split_{i}' not in row for i in range(1,11)) for row in rows.values()):
                    raise ValueError('DTD partition membership is incomplete')
            else:raise ValueError('Unknown Oxford release format')
        with tarfile.open(self._path()) as archive:
            names={m.name for m in archive if m.isfile()}
        if any(row['image'] not in names for row in rows.values()):raise ValueError('Annotation references missing image')
        self._metadata_rows=[rows[key] for key in sorted(rows)]
        return self._metadata_rows

    @property
    def count(self):return len(self._rows())

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        rows=self._rows();size=min(limit or source.limit,source.limit)
        self.config['mapping']={'id':'image_id','media':'image'}
        records=[DatasetAdapter._record(self,row,i) for i,row in enumerate(rows[start:start+size],start)]
        source.charge(sum(len(r.model_dump_json().encode()) for r in records))
        end=start+len(records)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

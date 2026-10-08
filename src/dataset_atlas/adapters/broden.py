"""Native Broden CSV/PNG joins, without running the historical SciPy loader."""
import csv
import hashlib
import io
from pathlib import Path
import re
import stat
import zipfile

from PIL import Image

from .core import DatasetAdapter,SourceDescription,RecordBatch,MediaHandle,_safe_relative
from dataset_atlas.storage import read_rooted_file


class BrodenAdapter(DatasetAdapter):
    def _path(self):
        value=self.config.get('path')
        if not value:raise ValueError('Broden requires a native directory or official ZIP path')
        return Path(value)

    def _read(self,name,budget):
        name=_safe_relative(name);path=self._path()
        if path.is_dir():return read_rooted_file(path/name,[path],budget)
        with zipfile.ZipFile(path) as archive:
            if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Duplicate native Broden ZIP names')
            prefix=self.config.get('archive_prefix','')
            if prefix:prefix=_safe_relative(prefix.rstrip('/'))+'/'
            info=archive.getinfo(prefix+name)
            if info.is_dir() or stat.S_ISLNK(info.external_attr>>16) or info.file_size>budget:
                raise ValueError('Broden member is not a bounded regular file')
            return archive.read(info)

    def probe(self):
        path=self._path();present=path.is_file() or (path/'index.csv').is_file()
        return SourceDescription('native Broden',str(path),present,self.revision,path.stat().st_size if path.is_file() else None,
            True,False,True,True,True,('Native image, category, label and segmentation references remain distinct.',))

    def _rows(self):
        if hasattr(self,'rows'):return self.rows
        limit=self.config.get('max_annotation_bytes',100_000_000)
        tables={}
        def table(name):
            data=self._read(name,limit)
            tables[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
            return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        categories=table('category.csv');labels=table('label.csv')
        numbers={int(row['number']):row for row in labels}
        if len(numbers)!=len(labels):raise ValueError('Duplicate native Broden label number')
        names=[row['name'] for row in categories]
        if len(names)!=len(set(names)) or any(not re.fullmatch('[a-z_]+',name) for name in names):
            raise ValueError('Duplicate or unsafe native Broden category')
        for name in names:
            category_labels=table('c_'+name+'.csv')
            codes=[int(row['code']) for row in category_labels]
            if len(codes)!=len(set(codes)) or any(int(row['number']) not in numbers for row in category_labels):
                raise ValueError('Broden category labels disagree with the global label table')
        rows=[];seen=set()
        payload=self._read('index.csv',limit)
        index_digest=hashlib.sha256(payload).hexdigest()
        for ordinal,raw in enumerate(csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))):
            image=_safe_relative(raw['image'])
            if image in seen:raise ValueError('Duplicate native Broden image')
            seen.add(image);channels={};constants={};media=['images/'+image];mask_categories={}
            for category in names:
                values=[int(value) if re.fullmatch('[0-9]+',value) else _safe_relative(value)
                        for value in raw[category].split(';') if value]
                channels[category]=values
                constants[category]=[numbers[value] for value in values if isinstance(value,int) and value in numbers]
                if any(isinstance(value,int) and value not in numbers and value!=0 for value in values):
                    raise ValueError('Broden constant label absent from native label table')
                for value in values:
                    if isinstance(value,str):
                        ref='images/'+value
                        if ref not in mask_categories:mask_categories[ref]=[];media.append(ref)
                        if category not in mask_categories[ref]:mask_categories[ref].append(category)
            row={'source_id':image,'source_row':ordinal,'native_index':raw,'native_channels':channels,
                 'native_constant_labels':constants,'split':raw['split'],'media_refs':media,'mask_categories':mask_categories,
                 'image_width':int(raw['iw']),'image_height':int(raw['ih']),
                 'mask_width':int(raw['sw']),'mask_height':int(raw['sh']),
                 'index_csv_sha256':index_digest,'native_label_tables':tables}
            rows.append(row)
        self.rows=rows;return rows

    @property
    def count(self):return len(self._rows())

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        rows=self._rows();end=min(len(rows),start+min(limit or source.limit,source.limit));records=[]
        self.config['mapping']={'id':'source_id','media':'media_refs'}
        for ordinal,row in enumerate(rows[start:end],start):
            record=self._record(row,ordinal)
            for asset in record.assets:
                category=row['mask_categories'].get(asset.uri)
                if category:asset.metadata.update(purpose='native segmentation mask',categories=category,
                    native_label_encoding='label_id = red + 256 * green',width=row['mask_width'],height=row['mask_height'])
            source.charge(len(record.model_dump_json().encode()));records.append(record)
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

    def resolve_asset(self,source,asset_ref):
        ref=_safe_relative(asset_ref)
        if not ref.startswith('images/'):raise ValueError('Invalid native Broden image reference')
        data=self._read(ref,min(50_000_000,source.max_bytes-source.bytes_read))
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>50_000_000:raise ValueError('Broden image exceeds pixel budget')
            mime=Image.MIME.get(image.format,'application/octet-stream');image.verify()
        source.charge(len(data))
        return MediaHandle(data,mime,hashlib.sha256(data).hexdigest(),asset_ref)

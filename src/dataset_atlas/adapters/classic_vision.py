"""Original bird, flower, and aircraft releases with native annotation joins."""
from __future__ import annotations
import io
from pathlib import Path
import tarfile
import zipfile
from .core import DatasetAdapter,DirectoryArchiveAdapter,RecordBatch


class ClassicVisionAdapter(DirectoryArchiveAdapter):
    def __init__(self,dataset):
        super().__init__(dataset)
        import copy
        self.config=copy.deepcopy(dataset.adapter_config)

    def _rows(self):
        if hasattr(self,'_metadata_rows'):return self._metadata_rows
        path=self._path();is_zip=zipfile.is_zipfile(path)
        archive=zipfile.ZipFile(path) if is_zip else tarfile.open(path)
        maximum=self.config.get('max_annotation_bytes',256_000_000);consumed=0
        with archive:
            members={m.filename if is_zip else m.name:m for m in (archive.infolist() if is_zip else archive.getmembers()) if not m.is_dir()} if is_zip else {m.name:m for m in archive.getmembers() if m.isfile()}
            def lines(name):
                nonlocal consumed
                member=members[name];size=member.file_size if is_zip else member.size
                consumed+=size
                if consumed>maximum:raise ValueError('Native annotations exceed byte budget')
                with (archive.open(member) if is_zip else archive.extractfile(member)) as stream:
                    for line in io.TextIOWrapper(stream,encoding='utf-8-sig'):
                        if line.strip():yield line.rstrip('\n\r')
            def pairs(name):
                result={}
                for line in lines(name):
                    key,value=line.split(maxsplit=1)
                    if key in result:raise ValueError('Duplicate annotation identity')
                    result[key]=value
                return result
            kind=self.config['dataset_kind'];rows={}
            if kind=='cub_200_2011':
                prefix='CUB_200_2011/'
                images=pairs(prefix+'images.txt');classes=pairs(prefix+'classes.txt')
                labels=pairs(prefix+'image_class_labels.txt');splits=pairs(prefix+'train_test_split.txt');boxes=pairs(prefix+'bounding_boxes.txt')
                if any(set(table)!=set(images) for table in (labels,splits,boxes)):raise ValueError('CUB annotation joins do not cover every image')
                for id,name in images.items():
                    if splits[id] not in {'0','1'}:raise ValueError('Invalid CUB split')
                    rows[id]={'image_id':int(id),'image':prefix+'images/'+name,'class_id':int(labels[id]),'class_name':classes[labels[id]],
                              'split':'train' if splits[id]=='1' else 'test','bounding_box_xywh':[float(x) for x in boxes[id].split()],
                              'parts':[],'attributes':[]}
                part_names=pairs(prefix+'parts/parts.txt')
                for line in lines(prefix+'parts/part_locs.txt'):
                    id,part,x,y,visible=line.split()
                    rows[id]['parts'].append({'part_id':int(part),'name':part_names[part],'x':float(x),'y':float(y),'visible':bool(int(visible))})
                attribute_names=pairs('attributes.txt' if 'attributes.txt' in members else prefix+'attributes/attributes.txt')
                for line in lines(prefix+'attributes/image_attribute_labels.txt'):
                    id,attribute,present,certainty,*elapsed=line.split()
                    rows[id]['attributes'].append({'attribute_id':int(attribute),'name':attribute_names[attribute],'present':bool(int(present)),
                        'certainty_id':int(certainty),'annotation_time':float(elapsed[0]) if elapsed else None})
                expected_parts=self.config.get('parts_per_image',15);expected_attrs=self.config.get('attributes_per_image',312)
                if any(len(r['parts'])!=expected_parts or len(r['attributes'])!=expected_attrs or len({p['part_id'] for p in r['parts']})!=expected_parts or len({a['attribute_id'] for a in r['attributes']})!=expected_attrs for r in rows.values()):raise ValueError('CUB per-image annotation population differs from release')
            elif kind=='aircraft':
                prefix=self.config.get('archive_prefix','fgvc-aircraft-2013b/data/')
                boxes=pairs(prefix+'images_box.txt');sizes=pairs(prefix+'images_size.txt')
                for split in ('train','val','test'):
                    tables={level:pairs(prefix+f'images_{level}_{split}.txt') for level in ('variant','family','manufacturer')}
                    ids=list(lines(prefix+f'images_{split}.txt'))
                    if any(set(table)!=set(ids) for table in tables.values()):raise ValueError('Aircraft hierarchical labels disagree with split')
                    for id in ids:
                        if id in rows:raise ValueError('Aircraft appears in multiple source splits')
                        rows[id]={'image_id':id,'image':prefix+'images/'+id+'.jpg','split':split,**{level:table[id] for level,table in tables.items()},
                                  'bounding_box_xyxy_1based':[int(x) for x in boxes[id].split()],
                                  'source_size':[int(x) for x in sizes[id].split()], 'copyright_banner_height':20}
            elif kind=='food101':
                prefix='food-101/'
                classes=list(lines(prefix+'meta/classes.txt'));labels=list(lines(prefix+'meta/labels.txt'))
                if len(classes)!=len(labels) or len(set(classes))!=len(classes):raise ValueError('Food taxonomy is inconsistent')
                names=dict(zip(classes,labels))
                for split in ('train','test'):
                    for image_id in lines(prefix+f'meta/{split}.txt'):
                        category=image_id.split('/')[0]
                        if image_id in rows or category not in names:raise ValueError('Food split overlaps or uses unknown class')
                        rows[image_id]={'image_id':image_id,'image':prefix+'images/'+image_id+'.jpg',
                                        'class_name':category,'display_label':names[category],'split':split,
                                        'annotation_note':'Original training labels intentionally retain noise.' if split=='train' else 'Original manually reviewed test labels.'}
            elif kind=='flowers102':
                from scipy.io import loadmat
                labels=loadmat(self.config['labels_path'])['labels'].reshape(-1)
                splits=loadmat(self.config['splits_path'])
                for key,split in [('trnid','train'),('valid','val'),('tstid','test')]:
                    for value in splits[key].reshape(-1):
                        id=int(value)
                        if id in rows or not 1<=id<=len(labels):raise ValueError('Flower splits overlap or refer outside label array')
                        rows[id]={'image_id':id,'image':f'jpg/image_{id:05d}.jpg','class_id':int(labels[id-1]),'split':split}
                if len(rows)!=len(labels):raise ValueError('Flower splits do not cover label population')
            else:raise ValueError('Unsupported native vision release')
            missing=[r['image'] for r in rows.values() if r['image'] not in members]
            if missing:raise ValueError(f'Native annotations reference {len(missing)} missing images')
        self._metadata_rows=[rows[key] for key in sorted(rows,key=lambda x:int(x) if str(x).isdigit() else str(x))]
        return self._metadata_rows

    @property
    def count(self):return len(self._rows())

    def iter_records(self,source,cursor=None,limit=None):
        start=int(cursor or 0)
        if start<0:raise ValueError('Negative cursor')
        rows=self._rows();end=min(start+min(limit or source.limit,source.limit),len(rows))
        self.config['mapping']={'id':'image_id','media':'image'}
        records=[DatasetAdapter._record(self,row,index) for index,row in enumerate(rows[start:end],start)]
        source.charge(sum(len(r.model_dump_json().encode()) for r in records))
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

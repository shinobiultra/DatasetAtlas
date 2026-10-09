"""Original bird, flower, and aircraft releases with native annotation joins."""
from __future__ import annotations
import io
import hashlib
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
        path=self._path();is_zip=bool(self.config.get('original_access_index')) or zipfile.is_zipfile(path)
        if self.config.get('original_access_index'):
            from dataset_atlas.storage.indexed_tar import IndexedTarArchive
            archive=IndexedTarArchive(self.config['original_access_index'], self.config.get('original_archive_path'), self.config.get('max_annotation_bytes',256_000_000))
        else:
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
            if kind=='hod':
                import csv
                import xml.etree.ElementTree as ET
                from .core import _safe_relative
                prefix=self.config['archive_prefix']
                class_names=['alcohol','insulting_gesture','blood','cigarette','gun','knife']
                seen_annotations=set()
                for item in csv.DictReader(lines(prefix+'dataset/metadata.csv')):
                    image_name=_safe_relative(item['Image Name'])
                    image=prefix+'dataset/all/jpg/'+image_name
                    yolo_name=_safe_relative(item['Annotation Name (YOLOv5)'])
                    xml_name=_safe_relative(item['Annotation Name (Faster R-CNN)'])
                    if image_name in rows:raise ValueError('Duplicate HOD metadata image')
                    if item['Category'] not in class_names or item['Case Type'] not in {'Normal','Hard'}:
                        raise ValueError('Unknown HOD category or difficulty')
                    if Path(image_name).stem!=Path(yolo_name).stem or Path(image_name).stem!=Path(xml_name).stem:
                        raise ValueError('HOD annotation filename does not match image')
                    native_yolo='\n'.join(lines(prefix+'dataset/all/txt/'+yolo_name))
                    native_xml='\n'.join(lines(prefix+'dataset/all/xml/'+xml_name))
                    if '<!DOCTYPE' in native_xml.upper() or '<!ENTITY' in native_xml.upper():
                        raise ValueError('HOD XML must not declare entities')
                    xml=ET.fromstring(native_xml)
                    if xml.findtext('filename')!=image_name:raise ValueError('HOD XML image identity differs')
                    width,height=int(xml.findtext('size/width')),int(xml.findtext('size/height'))
                    if min(width,height)<1:raise ValueError('Invalid HOD image dimensions')
                    objects=[]
                    for obj in xml.findall('object'):
                        label=obj.findtext('name')
                        if label not in class_names:raise ValueError('Unknown HOD XML class')
                        objects.append({'name':label,'box_xyxy':[float(obj.findtext('bndbox/'+key)) for key in ('xmin','ymin','xmax','ymax')],
                                        'pose':obj.findtext('pose'),'truncated':obj.findtext('truncated'),'difficult':obj.findtext('difficult')})
                    yolo=[]
                    for line in native_yolo.splitlines():
                        values=line.split()
                        if len(values)!=5:raise ValueError('Invalid HOD YOLO annotation width')
                        label=int(values[0])
                        if not 0<=label<len(class_names):raise ValueError('Unknown HOD YOLO class')
                        yolo.append({'class_id':label,'class_name':class_names[label],'box_cxcywh_normalized':[float(v) for v in values[1:]]})
                    if len(objects)!=len(yolo):raise ValueError('HOD native annotation object counts disagree')
                    folder=f"{prefix}dataset/class/{item['Category']}/{item['Case Type'].lower()}_cases/"
                    copies={}
                    for kind_dir,filename in [('jpg',image_name),('txt',yolo_name),('xml',xml_name)]:
                        original=prefix+'dataset/all/'+kind_dir+'/'+filename
                        copy=folder+kind_dir+'/'+filename
                        if original not in members or copy not in members:raise ValueError('Missing HOD class/all counterpart')
                        if is_zip and (members[original].CRC,members[original].file_size)!=(members[copy].CRC,members[copy].file_size):
                            raise ValueError('HOD class/all counterparts differ')
                        copies[kind_dir]=copy
                    seen_annotations.update([prefix+'dataset/all/txt/'+yolo_name,prefix+'dataset/all/xml/'+xml_name])
                    rows[image_name]={'image_id':image_name,'image':image,'class_name':item['Category'],'difficulty':item['Case Type'],
                        'source_size':[width,height],'native_metadata':item,'native_yolo':native_yolo,'native_xml':native_xml,
                        'yolo_objects':yolo,'xml_objects':objects,'class_copy_members':copies,
                        'coordinate_provenance':'YOLO: source normalized centre/size. XML: source pixel xyxy, retained without coordinate reinterpretation.'}
                if {row['image'] for row in rows.values()}!={name for name in members if name.startswith(prefix+'dataset/all/jpg/')}:
                    raise ValueError('HOD image population differs from metadata')
                annotations={name for name in members if name.startswith((prefix+'dataset/all/txt/',prefix+'dataset/all/xml/'))}
                if annotations!=seen_annotations:raise ValueError('HOD has unmatched native annotation files')
            elif kind=='cub_200_2011':
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
                boxes=pairs(prefix+'images_box.txt');sizes=pairs(prefix+'images_size.txt') if prefix+'images_size.txt' in members else {}
                for split in ('train','val','test'):
                    tables={level:pairs(prefix+f'images_{level}_{split}.txt') for level in ('variant','family','manufacturer')}
                    ids=list(lines(prefix+f'images_{split}.txt'))
                    if any(set(table)!=set(ids) for table in tables.values()):raise ValueError('Aircraft hierarchical labels disagree with split')
                    for id in ids:
                        if id in rows:raise ValueError('Aircraft appears in multiple source splits')
                        rows[id]={'image_id':id,'image':prefix+'images/'+id+'.jpg','split':split,**{level:table[id] for level,table in tables.items()},
                                  'bounding_box_xyxy_1based':[int(x) for x in boxes[id].split()],
                                  'source_size':[int(x) for x in sizes[id].split()] if id in sizes else None, 'copyright_banner_height':20}
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
            elif kind=='dreambooth':
                import csv,re
                prefix=self.config['archive_prefix']+'dataset/'
                definitions='\n'.join(lines(prefix+'prompts_and_classes.txt'))
                references='\n'.join(lines(prefix+'references_and_licenses.txt'))
                class_text=definitions.split('subject_name,class\n',1)[1].split('\nPrompts',1)[0]
                classes={row[0]:row[1] for row in csv.reader(io.StringIO(class_text)) if row}
                prompts=definitions.split('\nPrompts',1)[1]
                sections={match.group(1):match.group(2).strip() for match in re.finditer(
                    r'^('+'|'.join(re.escape(c) for c in classes)+r'):\s*(.*?)(?=^(?:'+'|'.join(re.escape(c) for c in classes)+r'):\s*|\Z)',references,re.M|re.S)}
                seen=set()
                for name in sorted(members):
                    if not name.startswith(prefix) or not name.lower().endswith(('.jpg','.jpeg','.png')):continue
                    relative=name[len(prefix):];subject=relative.split('/')[0]
                    if subject not in classes or subject not in sections:raise ValueError('DreamBooth subject has no class or source attribution')
                    seen.add(subject)
                    rows[relative]={'image_id':relative,'image':name,'subject':subject,'class_name':classes[subject],
                        'source_references':sections[subject], 'native_prompt_templates':prompts,
                        'annotation_note':'Source prompt template text retained verbatim; no generated evaluation images.'}
                if seen!=set(classes):raise ValueError('DreamBooth class inventory has missing subject images')
            elif kind=='gvil':
                import json
                prefix='dataset/'
                def document(name):return json.loads('\n'.join(lines(prefix+name)))
                tasks={'vqa':document('vqa_annotation.json'),'vg':document('vg_annotation.json')}
                for task,table in tasks.items():
                    for key,value in table.items():
                        identity=task+':'+key
                        rows[identity]={**value,'image_id':identity,'native_id':key,'task':task,'image':prefix+'images/'+value['img'],'paired_source_ids':[]}
                        if task=='vg':rows[identity]['question']=value['query']
                for type,pairs in document('pair_info.json').items():
                    task='vg' if type=='localization' else 'vqa'
                    for pair in pairs:
                        if len(pair)!=2 or pair[0]==pair[1]:raise ValueError('Invalid GVIL native pair')
                        left,right=[task+':'+key for key in pair]
                        if left not in rows or right not in rows:raise ValueError('GVIL pair references missing question')
                        if rows[left]['type']!=type or rows[right]['type']!=type:raise ValueError('GVIL pair task disagrees with annotation')
                        rows[left]['paired_source_ids'].append(right);rows[right]['paired_source_ids'].append(left)
                for ordinal,value in enumerate(document('raw_annotations.json')):
                    key='raw:'+value['img_file']
                    if key in rows:raise ValueError('Duplicate GVIL raw image annotation')
                    rows[key]={**value,'image_id':key,'native_id':value['img_file'],'task':'raw_annotation','image':prefix+'images/'+value['img_file']}
            elif kind=='caltech101':
                from scipy.io import loadmat
                annotations_path=Path(self.config['annotations_path'])
                expected=self.config.get('derived_archive_checksums',{}).get('annotations_path')
                if expected:
                    with annotations_path.open('rb') as stream:
                        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Caltech annotation archive checksum changed')
                name_map={'Faces':'Faces_2','Faces_easy':'Faces_3','Motorbikes':'Motorbikes_16','airplanes':'Airplanes_Side_2'}
                with zipfile.ZipFile(annotations_path) as annotation_archive:
                    available={i.filename:i for i in annotation_archive.infolist() if not i.is_dir()}
                    # These three release-level files are not per-image outlines. Keep
                    # the source files intact; attach quality values by native image ordinal.
                    administrative={'Annotations/check_progress.mat','Annotations/progress.mat','Annotations/FeatureDetectionQuality.mat'}
                    quality={}
                    quality_name='Annotations/FeatureDetectionQuality.mat'
                    if quality_name in available:
                        consumed+=available[quality_name].file_size
                        if consumed>maximum:raise ValueError('Caltech annotations exceed byte budget')
                        with annotation_archive.open(quality_name) as stream:features=loadmat(stream,simplify_cells=True)['Features']
                        if isinstance(features,dict):features=[features]
                        import numpy as np
                        for feature in features:
                            category=feature['name']
                            good=np.atleast_1d(feature['Good_Pts']);total=np.atleast_1d(feature['Total_Pts'])
                            if category in quality or len(good)!=len(total):raise ValueError('Caltech quality annotation lengths or categories disagree')
                            ids=sorted(int(n.rsplit('_',1)[1].removesuffix('.mat')) for n in available if n.startswith(f'Annotations/{category}/annotation_'))
                            if ids!=list(range(1,len(good)+1)):raise ValueError('Caltech quality annotation ordinals disagree with outlines')
                            quality[category]=(good,total)
                    used=set()
                    for name in sorted(members):
                        if not name.startswith('101_ObjectCategories/') or not name.endswith('.jpg'):continue
                        _,category,filename=name.split('/')
                        image_id=filename.removeprefix('image_').removesuffix('.jpg')
                        row={'image_id':category+'/'+image_id,'image':name,'class_name':category,'is_background':category=='BACKGROUND_Google'}
                        annotation=f'Annotations/{name_map.get(category,category)}/annotation_{image_id}.mat'
                        if category!='BACKGROUND_Google':
                            if annotation not in available:raise ValueError('Caltech image has no matching annotation')
                            consumed+=available[annotation].file_size
                            if consumed>maximum:raise ValueError('Caltech annotations exceed byte budget')
                            with annotation_archive.open(annotation) as stream:values=loadmat(stream)
                            row['native_annotation']={key:value.tolist() for key,value in values.items() if not key.startswith('__')}
                            row['annotation_status']='released';used.add(annotation)
                            quality_category=name_map.get(category,category)
                            if quality_category in quality:
                                good,total=quality[quality_category];ordinal=int(image_id)-1
                                row['native_feature_quality']={'Good_Pts':good[ordinal].item(),'Total_Pts':total[ordinal].item(),
                                    'source_member':quality_name,'source_category':quality_category,'source_ordinal_1based':int(image_id)}
                        else:row['annotation_status']='not_released_for_background'
                        rows[row['image_id']]=row
                    if used!={name for name in available if name.endswith('.mat') and name not in administrative and not name.startswith('__MACOSX/')}:
                        raise ValueError('Caltech annotation inventory has unmatched images')
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
        self.config['mapping']={**self.config.get('mapping',{}),'id':'image_id','media':'image'}
        records=[DatasetAdapter._record(self,row,index) for index,row in enumerate(rows[start:end],start)]
        if self.config['dataset_kind']=='gvil':
            from dataset_atlas.models import Relation
            from .core import stable_id
            for record in records:
                record.relations=[Relation(subject_id=record.id,object_id=stable_id(self.dataset.id,self.revision,'example',key),
                    type='native_illusion_control_pair',provenance={'source_member':'dataset/pair_info.json'}) for key in record.source.get('paired_source_ids',[])]
        source.charge(sum(len(r.model_dump_json().encode()) for r in records))
        return RecordBatch(records,str(end) if end<len(rows) else None,len(records))

"""Native COCO image populations with complete published annotation joins."""
from __future__ import annotations
from collections import defaultdict
import json
import zipfile
from .structured_collection import StructuredCollectionAdapter
from .core import _safe_relative
from dataset_atlas.models import Annotation,stable_id


class CocoImagesAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self,'_annotation_rows'):return self._annotation_rows
        rows=[];consumed=0;self._annotation_bytes_fetched=0
        for entry in self.config['annotations']:
            with zipfile.ZipFile(self.config[entry['path_key']]) as archive:
                def read(member):
                    nonlocal consumed
                    info=archive.getinfo(_safe_relative(member));consumed+=info.file_size
                    if consumed>self.config.get('max_annotation_bytes',2_000_000_000):raise ValueError('COCO annotations exceed read budget')
                    return json.loads(archive.read(info))
                population=read(entry['images_member'])
                images={}
                for image in population['images']:
                    if image['id'] in images:raise ValueError('Duplicate COCO source image ID')
                    images[image['id']]=image
                joins={};categories={};licenses={x['id']:x for x in population.get('licenses',[])}
                for kind in ('captions','instances','keypoints'):
                    if not entry.get(kind+'_member'):continue
                    data=population if entry[kind+'_member']==entry['images_member'] else read(entry[kind+'_member'])
                    if {x['id'] for x in data['images']}!=set(images):raise ValueError('COCO annotation image populations disagree')
                    category_by_id={x['id']:x for x in data.get('categories',[])}
                    categories[kind]=category_by_id
                    grouped=defaultdict(list);seen=set()
                    for annotation in data['annotations']:
                        if annotation['id'] in seen or annotation['image_id'] not in images:raise ValueError('Duplicate or orphan COCO annotation')
                        if 'category_id' in annotation and annotation['category_id'] not in category_by_id:raise ValueError('Unknown COCO category')
                        seen.add(annotation['id']);grouped[annotation['image_id']].append(annotation)
                    joins[kind]=grouped
                for ordinal,(image_id,image) in enumerate(images.items()):
                    row={'image_id':image_id,'image':image,'image_license':licenses.get(image.get('license')),
                         'annotation_status':'published' if joins else 'not_released',
                         '_atlas_origin':{'split':entry['split'],'row':ordinal,'identity':f'{entry["split"]}:{image_id}','annotation_members':{k:entry[k+'_member'] for k in joins}},
                         '_atlas_media_refs':[f'zip/{entry["media_archive"]}/{_safe_relative(entry["media_prefix"]+"/"+image["file_name"])}']}
                    for kind,group in joins.items():row[kind]=group[image_id]
                    if 'captions' in row:row['caption_text']='\n'.join(x['caption'] for x in row['captions'])
                    if 'instances' in row:
                        used={x['category_id'] for x in row['instances']}
                        row['categories']=[categories['instances'][key] for key in sorted(used)]
                        row['category_names']=[x['name'] for x in row['categories']]
                        row['instance_count']=len(row['instances'])
                        row['person_count']=sum(categories['instances'][x['category_id']]['name']=='person' for x in row['instances'])
                    if 'keypoints' in row:row['keypoint_categories']=list(categories['keypoints'].values())
                    rows.append(row)
        self._annotation_rows=rows
        return rows

    def iter_records(self,source,cursor=None,limit=None):
        result=super().iter_records(source,cursor,limit)
        for record in result.records:
            asset=record.assets[0];image=record.source['image']
            asset.metadata.update(width=image['width'],height=image['height'],source_image_id=image['id'])
            for annotation in record.source.get('instances',[]):
                record.annotations.append(Annotation(id=stable_id(self.dataset.id,self.revision,'annotation',str(annotation['id'])),
                    subject_id=asset.id,subject_unit='asset',field_id='source.instance',value=annotation,
                    provenance={'coordinate_system':'original_pixels_xywh','source_member':record.source['_atlas_origin']['annotation_members']['instances']}))
            source.charge(sum(len(a.model_dump_json().encode()) for a in record.annotations))
        return result

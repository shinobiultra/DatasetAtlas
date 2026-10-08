"""Exact native VOC XML, split and classification tables, with original media refs."""
from collections import defaultdict
import hashlib
from pathlib import PurePosixPath
import re
import tarfile
import xml.etree.ElementTree as ET

from . import converter, file_sha256, write_rows
from dataset_atlas.adapters.core import _safe_relative

VOC_CLASSES = ('aeroplane','bicycle','bird','boat','bottle','bus','car','cat','chair','cow',
               'diningtable','dog','horse','motorbike','person','pottedplant','sheep','sofa','train','tvmonitor')


def _xml_value(node):
    if not list(node) and not node.attrib:return node.text
    result={}
    if node.attrib:result['@attributes']=dict(node.attrib)
    if node.text and node.text.strip():result['@text']=node.text
    for child in node:
        value=_xml_value(child)
        if child.tag in result:
            if not isinstance(result[child.tag],list):result[child.tag]=[result[child.tag]]
            result[child.tag].append(value)
        else:result[child.tag]=value
    return result


@converter('pascal_voc_native')
def pascal_voc_native(params,inputs,output_dir,check):
    source=inputs['archive_path']
    if source.stat().st_size>params.get('max_source_bytes',2_000_000_000):raise ValueError('Native VOC archive exceeds input bound')
    prefix=params.get('prefix','TrainVal/VOCdevkit/VOC2011/')
    if _safe_relative(prefix.rstrip('/'))+'/'!=prefix:raise ValueError('Unsafe native VOC release prefix')
    classes=tuple(params.get('classes',VOC_CLASSES))
    if not classes or len(set(classes))!=len(classes):raise ValueError('Native VOC class inventory is invalid')
    annotations={};images={};masks=defaultdict(dict);tables={};seen=set();annotation_bytes=0
    with tarfile.open(source,'r:') as archive:
        for member in archive:
            check();name=_safe_relative(member.name.rstrip('/'))
            if name in seen:raise ValueError('Duplicate native VOC archive member')
            seen.add(name)
            if len(seen)>100_000:raise ValueError('Native VOC member inventory exceeds its bound')
            if member.isdir():continue
            if not member.isfile():raise ValueError('Native VOC archive requires regular files and directories')
            if not name.startswith(prefix):continue
            relative=name[len(prefix):];section,_,leaf=relative.partition('/')
            stem=PurePosixPath(leaf).stem
            if section=='JPEGImages' and '/' not in leaf and leaf.endswith('.jpg'):
                if stem in images:raise ValueError('Duplicate native VOC image identity')
                images[stem]=name
            elif section in {'SegmentationClass','SegmentationObject'} and '/' not in leaf and leaf.endswith('.png'):
                if section in masks[stem]:raise ValueError('Duplicate native VOC segmentation identity')
                masks[stem][section]=name
            elif (section=='Annotations' and '/' not in leaf and leaf.endswith('.xml')) or (section=='ImageSets' and leaf.endswith('.txt')):
                annotation_bytes+=member.size
                if member.size>1_000_000 or annotation_bytes>128_000_000:raise ValueError('Native VOC annotations exceed their byte bounds')
                stream=archive.extractfile(member)
                if stream is None:raise ValueError('Native VOC annotation is unreadable')
                with stream:payload=stream.read(member.size+1)
                if len(payload)!=member.size:raise ValueError('Native VOC annotation length changed')
                if section=='Annotations':
                    if stem in annotations:raise ValueError('Duplicate native VOC XML identity')
                    if b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():raise ValueError('Native VOC XML must not declare external entities')
                    text=payload.decode('utf-8');node=ET.fromstring(text)
                    if node.tag!='annotation' or node.findtext('filename')!=stem+'.jpg':raise ValueError('Native VOC XML and image filenames differ')
                    annotations[stem]=(text,hashlib.sha256(payload).hexdigest(),node)
                else:tables[relative]=(payload.decode('utf-8').splitlines(),hashlib.sha256(payload).hexdigest())
    if not images or set(images)!=set(annotations) or not set(masks).issubset(images):
        raise ValueError('Native VOC XML/image/mask memberships differ')
    memberships=defaultdict(list);labels=defaultdict(dict);trainval_ids=None
    for name,(lines,table_sha) in sorted(tables.items()):
        used=set()
        for ordinal,line in enumerate(lines):
            if not line.strip():continue
            cells=line.split();identity=cells[0]
            if identity not in images or (name.startswith('ImageSets/Main/') and identity in used):raise ValueError('Native VOC image-set membership is duplicate or unjoined')
            used.add(identity);memberships[identity].append({'file':prefix+name,'row':ordinal,'line':line,'fields':cells[1:],'file_sha256':table_sha})
            match=re.fullmatch(r'ImageSets/Main/([a-z]+)_trainval\.txt',name)
            if match:
                label=match[1]
                if label not in classes or len(cells)!=2 or cells[1] not in {'-1','0','1'}:raise ValueError('Native VOC signed class label changed')
                labels[identity][label]=int(cells[1])
        if name=='ImageSets/Main/trainval.txt':trainval_ids=used
    if trainval_ids is None or any(set(labels[identity])!=set(classes) for identity in trainval_ids) or any(labels[identity] for identity in set(images)-trainval_ids):
        raise ValueError('Native VOC classification inventories are incomplete')
    archive_sha=file_sha256(source)
    def rows():
        for ordinal,(identity,image) in enumerate(images.items()):
            check();text,xml_sha,node=annotations[identity]
            yield {'image_id':identity,'native_image_member':image,'native_image_order':ordinal,
                   'native_xml':text,'native_xml_sha256':xml_sha,'native_archive_sha256':archive_sha,
                   'native_annotation':_xml_value(node),'objects':[_xml_value(element) for element in node.findall('object')],
                   'class_labels':labels[identity],'native_image_sets':memberships[identity],
                   **{'class_'+name:labels[identity].get(name) for name in classes},
                   'main_classification_population':'trainval' if identity in trainval_ids else 'outside_main_trainval',
                   'native_segmentation_members':dict(masks.get(identity,{})),
                   'media_refs':[image,*[masks[identity][key] for key in sorted(masks.get(identity,{}))]],
                   'bbox_coordinate_reference':'Native VOC XML coordinates; preserved without clipping or reindexing.',
                   'classification_code_reference':'Native signed classification values -1,0,1; no binary coercion.'}
    result=write_rows(rows,output_dir/'voc-native.jsonl','jsonl',check)
    result['adapter_config']={'mapping':{'id':'image_id','media':'media_refs'},'sequential_index':True,'native_archive_sha256':archive_sha}
    result['native_scope_counts']={'images':len(images),'xml_annotations':len(annotations),'classes':len(classes),
                                 'classification_trainval_images':len(trainval_ids),'native_images_outside_main_trainval':len(images)-len(trainval_ids),
                                 'image_set_files':len(tables),'segmentation_class_masks':sum('SegmentationClass' in value for value in masks.values()),
                                 'segmentation_object_masks':sum('SegmentationObject' in value for value in masks.values())}
    return result

"""Native TextVQA-X explanations, question joins and lossless mask inspection."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import numpy as np
from PIL import Image

from dataset_atlas.models import Asset, stable_id
from dataset_atlas.storage.zip_members import LOCAL_ZIP_MEMBERS
from .core import MediaHandle
from .structured_collection import StructuredCollectionAdapter


class TextVQAXAdapter(StructuredCollectionAdapter):
    def _rows(self):
        if hasattr(self, '_annotation_rows'):
            return self._annotation_rows
        keys=['explanations_path','train_ids_path','val_ids_path','questions_train_path','questions_val_path']
        if sum(Path(self.config[k]).stat().st_size for k in keys)>self.config.get('max_annotation_bytes',64_000_000):
            raise ValueError('TextVQA-X annotations exceed read budget')
        explanations=json.loads(Path(self.config['explanations_path']).read_text())
        questions={}
        for key in ['questions_train_path','questions_val_path']:
            for question in json.loads(Path(self.config[key]).read_text())['data']:
                identity=str(question['question_id'])
                if identity in questions:raise ValueError('Duplicate native question identity')
                questions[identity]=question
        rows=[];seen=set()
        for split,key in [('train','train_ids_path'),('val','val_ids_path')]:
            for identity in Path(self.config[key]).read_text().splitlines():
                if not re.fullmatch(r'\d+',identity) or identity in seen:
                    raise ValueError('Invalid or repeated TextVQA-X split identity')
                seen.add(identity)
                if identity not in explanations or identity not in questions:
                    raise ValueError('TextVQA-X split has an unmatched explanation or question')
                explanation=explanations[identity];question=questions[identity]
                if explanation['image']!=question['image_id']+'.jpg':
                    raise ValueError('TextVQA-X question and explanation images differ')
                rows.append({'native_question_id':identity,'explanation_annotation':explanation,'question_annotation':question,
                    '_atlas_question':question['question'],
                    '_atlas_origin':{'identity':f'{split}:{identity}','split':split,'group':split,'row':len(rows)},
                    '_atlas_visual_explanation':{'member':f'seg/{identity}.npy','encoding':'native NumPy boolean mask; PNG is a lossless visualization'},
                    '_atlas_media_refs':[f'zip/trainval/train_images/{question["image_id"]}.jpg']})
        if seen!=set(explanations):raise ValueError('TextVQA-X explanations are absent from declared splits')
        self._mask_ids=seen
        self._annotation_rows=rows
        return rows

    def validate_media(self,budget,cancel=None):
        proof=super().validate_media(budget,cancel)
        with zipfile.ZipFile(self.config['masks_path']) as archive:
            members=[entry.filename for entry in archive.infolist() if not entry.is_dir()]
        expected={f'seg/{row["native_question_id"]}.npy' for row in self._rows()}
        if len(members)!=len(set(members)) or set(members)!=expected:
            raise ValueError('Native mask members do not exactly match TextVQA-X questions')
        return {**proof,'native_masks':len(members)}

    def iter_records(self,source,cursor=None,limit=None):
        batch=super().iter_records(source,cursor,limit)
        for record in batch.records:
            original_size=len(record.model_dump_json().encode())
            identity=record.source['native_question_id'];native_ref=f'zip/masks/seg/{identity}.npy'
            array_id=stable_id(self.dataset.id,self.revision,'asset',native_ref)
            record.assets.extend([
                Asset(id=stable_id(self.dataset.id,self.revision,'asset',f'mask/{identity}.png'),dataset_id=self.dataset.id,
                      release_id=self.revision,modality='image',uri=f'mask/{identity}.png',representation='lossless_mask_render',
                      metadata={'role':'visual explanation mask','native_array_asset_id':array_id,'pixel_encoding':'False=0, True=255; original dimensions'}),
                Asset(id=array_id,dataset_id=self.dataset.id,release_id=self.revision,modality='array',uri=native_ref,
                      metadata={'role':'native visual explanation array','encoding':'NumPy bool; no pickle'})])
            record.asset_ids=[asset.id for asset in record.assets]
            source.charge(len(record.model_dump_json().encode())-original_size)
        return batch

    def resolve_asset(self,source,asset_ref):
        match=re.fullmatch(r'mask/(\d+)\.png',asset_ref)
        original=re.fullmatch(r'zip/masks/seg/(\d+)\.npy',asset_ref)
        selected=match or original
        if selected is None:return super().resolve_asset(source,asset_ref)
        identity=selected[1]
        self._rows()
        if identity not in self._mask_ids:
            raise ValueError('Mask is outside the prepared population')
        key='masks_path';path=Path(self.config[key]);expected=self.config['derived_archive_checksums'][key]
        data=LOCAL_ZIP_MEMBERS.read(path,f'seg/{identity}.npy',min(32_000_000,source.max_bytes-source.bytes_read),expected)
        source.charge(len(data))
        if original:return MediaHandle(data,'application/octet-stream',hashlib.sha256(data).hexdigest(),asset_ref)
        stream=io.BytesIO(data);version=np.lib.format.read_magic(stream)
        if version==(1,0):shape,order,dtype=np.lib.format.read_array_header_1_0(stream)
        elif version==(2,0):shape,order,dtype=np.lib.format.read_array_header_2_0(stream)
        else:raise ValueError('Unsupported native mask header')
        if dtype!=np.dtype(bool) or len(shape)!=2 or any(type(n) is not int or n<1 for n in shape) or shape[0]*shape[1]>32_000_000:
            raise ValueError('Native mask must be a bounded two-dimensional boolean array')
        if len(data)-stream.tell()!=shape[0]*shape[1]:raise ValueError('Native mask payload length mismatch')
        array=np.load(io.BytesIO(data),allow_pickle=False)
        output=io.BytesIO();Image.fromarray(array).save(output,format='PNG')
        rendered=output.getvalue()
        return MediaHandle(rendered,'image/png',hashlib.sha256(rendered).hexdigest(),asset_ref)

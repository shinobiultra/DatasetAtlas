"""Explicit, bounded reconstruction using the author's released Shapes generator."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
import PIL
from dataset_atlas.models import Relation, stable_id
from .core import StructuredAdapter, SourceDescription
from . import _pathways_shapes as author

REVISION = '470944b3f6b44901a9055cf8d91aef18cee21671'
FUNCTIONS = {'relations':author.generate_center_paired_dataset,
             'localization':author.generate_single_position_pairs,
             'recognition':author.generate_single_recognition_pairs}


def parameters(config):
    task = config.get('shape_task')
    if task not in FUNCTIONS: raise ValueError('Unknown author Shapes task')
    pairs,size,shape,seed = [config.get(k) for k in ('n_pairs','image_size','shape_size','seed')]
    if any(type(v) is not int for v in (pairs,size,shape,seed)):
        raise ValueError('Shapes generation parameters must be integers')
    if not 1 <= pairs <= 1000 or not 64 <= size <= 1024 or not 2 <= shape < size//3 or not 0 <= seed <= 2**32-1:
        raise ValueError('Shapes generation parameter exceeds supported bounds')
    if pairs*2*size*size*3 > 1_500_000_000:
        raise ValueError('Shapes generation exceeds 1.5 GB decoded pixel bound')
    if config.get('python_version') != '.'.join(map(str,sys.version_info[:2])):
        raise ValueError('Install the pinned Python minor version to reproduce the author random sequence')
    if config.get('renderer_version') != PIL.__version__:
        raise ValueError('Install the pinned Pillow renderer version to reproduce these generated pixels')
    if config.get('generator_revision') != REVISION:
        raise ValueError('Unknown author generator revision')
    return task,{'n_pairs':pairs,'image_size':size,'grid_spec':(3,3),'shape_size':shape,'seed':seed}


def materialize(dataset, output, max_bytes, cancel):
    task,args = parameters(dataset.adapter_config); output = Path(output)
    fingerprint = {'revision':REVISION,'task':task,'arguments':{**args,'grid_spec':list(args['grid_spec'])},
                   'renderer_version':PIL.__version__,'python_version':dataset.adapter_config['python_version'],
                   'bundled_functions_sha256':hashlib.sha256(Path(author.__file__).read_bytes()).hexdigest()}
    receipt: dict[str, Any]
    if output.exists():
        receipt = json.loads((output/'receipt.json').read_text())
        if receipt['generator'] != fingerprint: raise ValueError('Existing Shapes generation differs from pinned inputs')
        if receipt['bytes'] > max_bytes: raise ValueError('Generated Shapes exceed output budget')
        for name,sha in receipt['checksums'].items():
            cancel()
            if hashlib.sha256((output/name).read_bytes()).hexdigest() != sha:
                raise ValueError('Generated Shapes output checksum changed')
    else:
        stage = output.with_name(output.name+'.partial')
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir(parents=True); checksums = {}; rows = []; total = 0
        try:
            cancel(); samples = FUNCTIONS[task](**args)
            for ordinal,sample in enumerate(samples):
                cancel(); image = sample.pop('image'); name = f'{ordinal:06d}.png'
                try: image.save(stage/name,'PNG')
                finally: image.close()
                payload = (stage/name).read_bytes(); total += len(payload)
                if total > max_bytes: raise ValueError('Generated Shapes exceed output budget')
                sha = hashlib.sha256(payload).hexdigest(); checksums[name] = sha
                rows.append({**sample,'generator_ordinal':ordinal,'generated_image':name,
                             'generated_image_sha256':sha,'generator':fingerprint,
                             'representation_note':'Author recipe reconstruction; historical experiment pixels are not available.'})
            payload = json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode(); total += len(payload)
            if total > max_bytes: raise ValueError('Generated Shapes exceed output budget')
            (stage/'records.json').write_bytes(payload); checksums['records.json'] = hashlib.sha256(payload).hexdigest()
            receipt = {'generator':fingerprint,'records':len(rows),'checksums':checksums,'bytes':total,'format':'author-generated-png-json'}
            while True:
                payload = (json.dumps(receipt,indent=2)+'\n').encode()
                actual = total + len(payload)
                if receipt['bytes'] == actual: break
                receipt['bytes'] = actual
            if actual > max_bytes: raise ValueError('Generated Shapes exceed output budget')
            (stage/'receipt.json').write_bytes(payload);stage.rename(output)
        except BaseException:
            shutil.rmtree(stage,ignore_errors=True)
            raise
    dataset.adapter_config.update(path=str(output/'records.json'),media_root=str(output),
                                  sha256=receipt['checksums']['records.json'],mapping={'id':'generator_ordinal','media':'generated_image'})
    return {**receipt,'path':str(output)}


class PathwaysShapesAdapter(StructuredAdapter):
    def probe(self):
        if self.config.get('path') and Path(self.config['path']).is_file():return super().probe()
        parameters(self.config)
        return SourceDescription('author_generator','bundled vlm-pathways Shapes recipe',True,self.revision,
                                 None,False,True,True,False,False,('Author-generated reconstruction; no historical pixel identity claim.',))

    def _record(self,row,ordinal):
        record = super()._record(row,ordinal)
        record.assets[0].sha256 = row['generated_image_sha256']
        record.assets[0].metadata['generation'] = row['generator']
        peer = int(row['generator_ordinal']) ^ 1
        record.relations.append(Relation(subject_id=record.id,object_id=stable_id(self.dataset.id,self.revision,'example',str(peer)),
            type='author_counterfactual_pair',provenance={'pair_id':row['pair_id'],'generator_revision':REVISION}))
        return record

    def resolve_asset(self,source,asset_ref):
        handle = super().resolve_asset(source,asset_ref)
        inventory = json.loads((Path(self.config['media_root'])/'receipt.json').read_text())['checksums']
        if inventory.get(asset_ref) != handle.sha256:raise ValueError('Generated Shapes image checksum changed')
        return handle

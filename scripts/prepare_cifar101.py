"""Build local CIFAR-10.1 v6 browsing from pinned numeric NPY arrays, never pickle."""
from pathlib import Path
import collections,hashlib,json
import numpy as np
from PIL import Image
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dataset_atlas.adapters import build_preview,get_adapter
from dataset_atlas.registry import Registry
from dataset_atlas.queries.parquet import build_parquet_snapshot
ROOT=Path(__file__).resolve().parents[1]
PIN='d9982abb0bfc4846b8d13a11e66b887d946205d0'
EXPECTED={'cifar10.1_v6_data.npy':'2997188e5816f5bd545dc77771b6227828c28146049fcecf3fa10775474cacc6','cifar10.1_v6_labels.npy':'ae40beda001693674edc94d925ee8268cfe68905f8f9aff800c8dcdfcd6c9448'}
NAMES=['airplane','automobile','bird','cat','deer','dog','frog','horse','ship','truck']
def main():
 directory=ROOT/'work/sources/cifar-10-1';media=directory/'images';media.mkdir(exist_ok=True)
 for name,digest in EXPECTED.items():
  if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:raise ValueError('Pinned original bytes changed')
 images=np.load(directory/'cifar10.1_v6_data.npy',allow_pickle=False);labels=np.load(directory/'cifar10.1_v6_labels.npy',allow_pickle=False)
 if images.shape!=(2000,32,32,3) or images.dtype!=np.uint8 or labels.shape!=(2000,) or labels.dtype!=np.int32:raise ValueError('Source shape/dtype differs from release')
 if collections.Counter(labels.tolist())!={label:200 for label in range(10)}:raise ValueError('Source class counts differ from release')
 rows=[]
 for ordinal,(pixels,label) in enumerate(zip(images,labels,strict=True)):
  filename=f'{ordinal:04d}.png';Image.fromarray(pixels).save(media/filename)
  if not np.array_equal(np.asarray(Image.open(media/filename)),pixels):raise ValueError('PNG conversion changed source pixels')
  rows.append({'source_id':str(ordinal),'source_index':ordinal,'label':int(label),'class_name':NAMES[label],'image':filename,'release_variant':'v6','pixel_representation':'Lossless RGB PNG encoding of original NPY row; no resize or normalization'})
 # Order the prepared view by a documented deterministic class round-robin,
 # retaining original source_index as the identity so sorting cannot rename samples.
 groups={label:[row for row in rows if row['label']==label] for label in range(10)}
 ordered=[groups[label][index] for index in range(200) for label in range(10)]
 path=directory/'records.parquet';pq.write_table(pa.Table.from_pylist(ordered),path,compression='zstd')
 digest=hashlib.sha256(path.read_bytes()).hexdigest();manifest_path=ROOT/'registry/datasets/cifar-10-1.yaml';manifest=yaml.safe_load(manifest_path.read_text())
 manifest.update(name='CIFAR-10.1 v6',release='v6-'+PIN[:12],snapshot_id='cifar101-v6-'+digest,source_url=f'https://github.com/modestyachts/CIFAR-10.1/tree/{PIN}',description='Author v6 release: 2,000 original 32×32 RGB images, 200 per CIFAR-10 class. Distinct from the 2,021-image v4 release. Original NPY pixels are losslessly encoded as PNG for local browsing; source row indices are preserved.',adapter='structured',modalities=['image'],tasks=['image classification','distribution shift evaluation'],labels=NAMES)
 manifest['adapter_config']={'path':str(path.relative_to(ROOT)),'format':'parquet','sha256':digest,'media_root':str(media.relative_to(ROOT)),'mapping':{'id':'source_id','media':'image'},'fields':{'source_index':{'dtype':'number','description':'Original v6 NPY row index'},'label':{'dtype':'category','values':list(range(10)),'description':'Original CIFAR-10 numeric label'},'class_name':{'dtype':'category','values':NAMES,'description':'CIFAR-10 class name'},'release_variant':{'dtype':'category','values':['v6']},'pixel_representation':{'dtype':'string'}},'source_files_sha256':EXPECTED}
 manifest['coverage'].update(identity='resolved',source='verified',access='public',adapter='tested',preview='complete_target',complete_data='supported',publication='metadata_only',preview_count=100,total_count=2000,blockers=['Author MIT code license excludes dataset images; public media redistribution is not approved.','CIFAR-10.1 v4 is a separate release and is not substituted.'])
 manifest['rights']={'records':'not_reviewed','annotations':'not_reviewed','images':'not_reviewed','external_provider':'local_only','source':manifest['source_url'],'basis':'Author repository distributes NPY data; MIT repository license applies to code and explicitly excludes image/label data from Tiny Images.'}
 receipt={'kind':'verified_source_acquisition','source_url':manifest['source_url'],'checked_at':'2026-09-22','sha256':EXPECTED,'count':2000,'counts_by_label':{name:200 for name in NAMES},'pixel_validation':'All 2,000 saved PNG arrays exactly equal original NPY rows; no transformations'}
 if receipt not in manifest.setdefault('evidence',[]):manifest['evidence'].append(receipt)
 manifest_path.write_text(yaml.safe_dump(manifest,sort_keys=False))
 dataset=Registry(ROOT).dataset('cifar-10-1');pack=build_preview(dataset,ROOT/'work/packs/cifar-10-1',limit=100,max_bytes=20_000_000,include_media=True)
 adapter=get_adapter(dataset);snapshots=ROOT/'work/snapshots'
 build_parquet_snapshot((adapter._record(row,index) for index,row in enumerate(adapter._rows())),pack.fields,snapshots/'cifar-10-1',root=snapshots,dataset_id=dataset.id,release_id=dataset.release,snapshot_id=dataset.snapshot_id,expected_count=2000,population_scope='complete',max_bytes=100_000_000)
 receipt.update(preview_count=len(pack.records),preview_class_counts=dict(collections.Counter(row.source['class_name'] for row in pack.records)),prepared_parquet_sha256=digest)
 (ROOT/'reports/cifar-10-1-source.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()

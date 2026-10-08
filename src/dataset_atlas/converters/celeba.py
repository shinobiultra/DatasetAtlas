"""Filename-exact joins of the public author CelebA tables and aligned images."""
import json
import re
import stat
import zipfile

from . import converter, file_sha256, write_rows


def _table(path, *, header=True):
    if path.stat().st_size > 40_000_000: raise ValueError('Native CelebA table exceeds input budget')
    with path.open(encoding='utf-8', newline='') as stream:
        declared = int(next(stream).strip()) if header else None
        names = next(stream).split() if header else ['partition']
        if len(names) != len(set(names)): raise ValueError('Duplicate native CelebA field name')
        if names and names[0] == 'image_id': names = names[1:]
        rows = {}; raw_rows = {}
        for line in stream:
            cells = line.split()
            if len(cells) != len(names)+1 or not re.fullmatch(r'[0-9]{6}\.jpg', cells[0]):
                raise ValueError('Native CelebA table row shape changed')
            if cells[0] in rows: raise ValueError('Duplicate native CelebA filename')
            rows[cells[0]] = [int(value) for value in cells[1:]]
            raw_rows[cells[0]] = line.rstrip('\r\n')
    if declared is not None and len(rows) != declared: raise ValueError('Native CelebA declared table count differs')
    return names, rows, raw_rows


@converter('celeba_native')
def celeba_native(params, inputs, output_dir, check):
    """Identity annotations are never inferred or silently substituted."""
    import pyarrow as pa
    tables = {key:_table(inputs[key],header=key!='partitions')
              for key in ('attributes','bbox','landmarks_align','partitions')}
    names, attributes, _ = tables['attributes']
    expected_attributes = params.get('attribute_count',40)
    if len(names) != expected_attributes or any(not re.fullmatch('[A-Za-z0-9_]+',name) for name in names):
        raise ValueError('Native CelebA attribute header changed')
    if any(set(rows) != set(attributes) for _,rows,_ in tables.values()):
        raise ValueError('Native CelebA filename joins differ')
    if len(tables['bbox'][0]) != 4 or len(tables['landmarks_align'][0]) != 10:
        raise ValueError('Native CelebA geometry table header changed')
    prefix = params.get('archive_prefix','img_align_celeba/')
    if not re.fullmatch('[A-Za-z0-9_-]+/',prefix): raise ValueError('Invalid native CelebA archive prefix')
    with zipfile.ZipFile(inputs['media_archive']) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        filenames = set()
        for info in members:
            check()
            if (not info.filename.startswith(prefix) or not re.fullmatch(r'[0-9]{6}\.jpg',info.filename[len(prefix):])
                    or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1 or not 1<=info.file_size<=10_000_000):
                raise ValueError('Unsupported or unsafe native CelebA image member')
            filename = info.filename[len(prefix):]
            if filename in filenames: raise ValueError('Duplicate native CelebA image member')
            filenames.add(filename)
    if filenames != set(attributes): raise ValueError('Native CelebA image and annotation memberships differ')
    original_shas = {key:file_sha256(inputs[key]) for key in tables}
    original_headers = {}
    for key in tables:
        with inputs[key].open(encoding='utf-8', newline='') as stream:
            original_headers[key] = [next(stream).rstrip('\r\n'),next(stream).rstrip('\r\n')] if key!='partitions' else []
    def rows():
        for ordinal,(filename,labels) in enumerate(attributes.items()):
            check()
            if any(value not in {-1,1} for value in labels): raise ValueError('Native signed attribute label changed')
            partition = tables['partitions'][1][filename][0]
            if partition not in {0,1,2}: raise ValueError('Native CelebA partition code changed')
            yield {'source_id':filename,'filename':filename,'media_ref':prefix+filename,'source_row':ordinal,
                   'native_partition':partition,'split':{0:'train',1:'validation',2:'test'}[partition],
                   'native_attribute_names':names,'native_bbox_names':tables['bbox'][0],
                   'native_bbox':tables['bbox'][1][filename],'native_landmark_names':tables['landmarks_align'][0],
                   'native_aligned_landmarks':tables['landmarks_align'][1][filename],
                   'native_table_rows_json':json.dumps({key:table[2][filename] for key,table in tables.items()},ensure_ascii=False),
                   'native_table_sha256_json':json.dumps(original_shas,sort_keys=True),
                   'native_table_headers_json':json.dumps(original_headers,sort_keys=True),
                   'bbox_coordinate_reference':'Original in-the-wild photograph; not the aligned crop displayed here.',
                   'identity_availability':'Publisher request required; identity labels were not acquired.',
                   **{'attr_'+name:value for name,value in zip(names,labels,strict=True)}}
    strings = ['source_id','filename','media_ref','split','native_table_rows_json','native_table_sha256_json','native_table_headers_json',
               'bbox_coordinate_reference','identity_availability']
    schema = pa.schema([(key,pa.string()) for key in strings]+[
        ('source_row',pa.int32()),('native_partition',pa.int8()),
        *[(key,pa.list_(pa.string())) for key in ['native_attribute_names','native_bbox_names','native_landmark_names']],
        ('native_bbox',pa.list_(pa.int32())),('native_aligned_landmarks',pa.list_(pa.int32())),
        *[('attr_'+name,pa.int8()) for name in names]])
    result = write_rows(rows,output_dir/'faces.parquet','parquet',check,schema=schema)
    result['adapter_config'] = {'mapping':{'id':'source_id','media':'media_ref'},'sequential_index':True,
                                'media_archive_sha256':file_sha256(inputs['media_archive'])}
    return result

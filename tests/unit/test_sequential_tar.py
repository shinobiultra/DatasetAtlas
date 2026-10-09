"""Synthetic sequential native annotations exercise full archive/hash retrieval."""
import hashlib
import io
import tarfile

import pytest

from dataset_atlas.preparation.sequential_tar import prepare_tar_sources


def test_native_json_archive_checks_all_bytes_and_probes_declared_suffix(tmp_path,monkeypatch):
    native=tmp_path/'native.tar.gz'
    with tarfile.open(native,'w:gz') as archive:
        body=b'{"native_annotation":true}'
        info=tarfile.TarInfo('val.json');info.size=len(body);archive.addfile(info,io.BytesIO(body))
    raw=native.read_bytes()
    entry={'source_name':'val.json.tar.gz','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
        'url':'https://example.invalid/native.tar.gz','probe_member_suffix':'.json'}
    version=tmp_path/'version';version.mkdir()
    plan={'files':[entry],'prepared_dataset':{'release':'pinned'},'allowed_hosts':['example.invalid'],
        'max_download_bytes':1000000,'max_output_bytes':1000000}
    monkeypatch.setattr('dataset_atlas.storage.parallel_fetch.fetch_checksum_ranges',lambda *a,**k:(native,{'network_bytes':len(raw)}))
    monkeypatch.setattr('dataset_atlas.storage.hash_ranges.HashPinnedRangeReader._fetch',lambda self,start,end:raw[start:end+1])
    result=prepare_tar_sources(tmp_path,plan,version,lambda **k:None,lambda:None)
    proof=result['acquisition_proofs'][0]
    assert proof['source_sha256']==entry['sha256'] and proof['probe_member_suffix']=='.json'
    assert proof['probe_member_count']==1 and proof['publisher_md5_verified'] is None
    assert len(proof['cold_retrieval'])==1 and proof['cold_retrieval'][0]['sha256']==hashlib.sha256(body).hexdigest()
    # Reusing the checkpoint checks its index hashes and does not fetch again.
    monkeypatch.setattr('dataset_atlas.storage.parallel_fetch.fetch_checksum_ranges',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Completed native archive must not download again')))
    assert prepare_tar_sources(tmp_path,plan,version,lambda **k:None,lambda:None)['indices']==result['indices']
    entry['probe_member_suffix']=".jpg%'"
    with pytest.raises(ValueError,match='suffix'):prepare_tar_sources(tmp_path,plan,version,lambda **k:None,lambda:None)

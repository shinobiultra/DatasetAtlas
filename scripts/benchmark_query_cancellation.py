import json,time,threading,platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dataset_atlas.queries.parquet import ParquetSnapshot
from dataset_atlas.models import Query
root=Path.cwd()
snapshot=ParquetSnapshot(root/'work/snapshots',root/'work/snapshots/clevr-v1-full')
query=Query(snapshot_id=snapshot.snapshot_id,population_scope='complete',sample={'method':'stratified','field_id':snapshot.fields[0].id,'size':100})
started=time.perf_counter()
with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(snapshot.query,query)
    time.sleep(.1)
    requested=time.perf_counter()
    while not future.done():
        snapshot.interrupt()
        time.sleep(.01)
    try:
        future.result()
        outcome='completed before cancellation'
    except ValueError as exc:outcome=str(exc)
    finished=time.perf_counter()
result=snapshot.query(Query(snapshot_id=snapshot.snapshot_id,population_scope='complete',limit=1))
receipt={'dataset_id':snapshot.dataset_id,'records':snapshot.record_count,'query':query.model_dump(),'outcome':outcome,'seconds_before_request':requested-started,'seconds_after_request':finished-requested,'reader_usable_after_interrupt':result.matched_count==snapshot.record_count,'duckdb_memory_limit_mb':snapshot.memory_mb,'default_query_timeout_seconds':snapshot.timeout_seconds,'scope':'Real full CLEVR query cancellation; repeated interrupt every 10ms until future exits; not a process RSS bound or browser disconnect test.','platform':platform.platform()}
(root/'reports/query-cancellation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))

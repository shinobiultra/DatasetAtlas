"""Small command line for reproducible data preparation and local work."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

def emit(value):
    if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
    elif hasattr(value,'__dict__'):value=vars(value)
    print(json.dumps(value,indent=2,default=str))

def main(argv=None):
    parser=argparse.ArgumentParser(prog='atlas',description='Dataset Atlas local workbench')
    parser.add_argument('--root',type=Path,default=Path(os.environ.get('ATLAS_ROOT','.')),help='Workspace containing registry/ and work/')
    sub=parser.add_subparsers(dest='command',required=True)
    corpus=sub.add_parser('corpus').add_subparsers(dest='action',required=True)
    scan=corpus.add_parser('scan');scan.add_argument('--papers-dir',type=Path,required=True);scan.add_argument('--output',type=Path,default=Path('work/corpus'))
    extract=corpus.add_parser('extract');extract.add_argument('--manifest',type=Path,required=True)
    resolve=corpus.add_parser('resolve');resolve.add_argument('--mentions',type=Path,required=True);resolve.add_argument('--registry',type=Path,default=Path('registry'))
    datasets=sub.add_parser('datasets').add_subparsers(dest='action',required=True)
    validate=datasets.add_parser('validate');validate.add_argument('--all',action='store_true')
    prepare=datasets.add_parser('prepare');prepare.add_argument('--dataset',required=True);prepare.add_argument('--preview-size',type=int,default=100);prepare.add_argument('--max-bytes',type=int,default=20_000_000);prepare.add_argument('--dry-run',action='store_true')
    acquire=datasets.add_parser('acquire');acquire.add_argument('--dataset',required=True);acquire.add_argument('--max-download-bytes',type=int,required=True);acquire.add_argument('--max-output-bytes',type=int,required=True);acquire.add_argument('--execute',action='store_true')
    preparation=datasets.add_parser('preparation');preparation.add_argument('--id',required=True);preparation.add_argument('--cancel',action='store_true');preparation.add_argument('--retry',action='store_true')
    index=datasets.add_parser('index');index.add_argument('--dataset',required=True);index.add_argument('--expected-count',type=int,required=True);index.add_argument('--max-bytes',type=int,default=30_000_000_000)
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8765)
    analyze=sub.add_parser('analyze');analyze.add_argument('--selection',required=True);analyze.add_argument('--processor',required=True);analyze.add_argument('--config',type=Path)
    export=sub.add_parser('export').add_subparsers(dest='action',required=True)
    selection=export.add_parser('selection');selection.add_argument('selection_id');selection.add_argument('--output',type=Path,required=True)
    publish=sub.add_parser('publish').add_subparsers(dest='action',required=True)
    for action in ['validate','build']:
        p=publish.add_parser(action);p.add_argument('--profile',default='public');p.add_argument('--output',type=Path,default=Path('apps/web/public'));p.add_argument('--packs-dir',type=Path)
    sub.add_parser('doctor')
    args=parser.parse_args(argv);root=args.root.resolve()
    try:
        if args.command=='corpus':
            from dataset_atlas.corpus import pipeline
            if args.action=='scan':emit(pipeline.scan(args.papers_dir,args.output))
            elif args.action=='extract':emit(pipeline.extract(args.manifest))
            else:emit(pipeline.resolve(args.mentions,args.registry))
        elif args.command=='datasets':
            from dataset_atlas.registry import Registry
            registry=Registry(root)
            if args.action=='acquire':
                from dataset_atlas.preparation import PreparationManager
                manager=PreparationManager(root);plan=manager.plan(args.dataset,args.max_download_bytes,args.max_output_bytes);emit(plan)
                if args.execute:emit(manager.start(plan['id']))
            elif args.action=='preparation':
                from dataset_atlas.preparation import PreparationManager
                manager=PreparationManager(root);emit(manager.cancel(args.id) if args.cancel else manager.start(args.id) if args.retry else manager.status(args.id))
            elif args.action=='validate':
                errors=[];count=0
                for dataset in registry.datasets():
                    count+=1
                    try:
                        pack=registry.pack(dataset.id)
                        if len({r.id for r in pack.records})!=len(pack.records):raise ValueError('Duplicate IDs')
                        for record in pack.records:
                            if record.snapshot_id!=dataset.snapshot_id:raise ValueError('Snapshot mismatch')
                    except FileNotFoundError:pass
                    except ValueError as exc:errors.append({'dataset':dataset.id,'error':str(exc)})
                emit({'datasets':count,'errors':errors})
                if errors:return 1
            elif args.action=='index':
                from dataset_atlas.adapters import get_adapter
                from dataset_atlas.queries.parquet import build_parquet_snapshot
                dataset=registry.dataset(args.dataset);adapter=get_adapter(dataset)
                plan=adapter.plan(min(args.expected_count,1000),args.max_bytes);emit(plan)
                source=adapter.prepare(plan)
                def records():
                    cursor=None
                    while True:
                        batch=adapter.iter_records(source,cursor,1000)
                        yield from batch.records
                        cursor=batch.next_cursor
                        if not cursor:break
                directory=root/'work/snapshots';directory.mkdir(parents=True,exist_ok=True)
                fields=registry.pack(dataset.id).fields
                output=build_parquet_snapshot(records(),fields,directory/dataset.id,root=directory,dataset_id=dataset.id,release_id=dataset.release,snapshot_id=dataset.snapshot_id,expected_count=args.expected_count,population_scope='complete',max_bytes=args.max_bytes)
                emit({'snapshot':str(output)})
            else:
                from dataset_atlas.adapters import get_adapter,build_preview
                dataset=registry.dataset(args.dataset)
                if args.dry_run:emit(get_adapter(dataset).plan(args.preview_size,args.max_bytes))
                else:emit(build_preview(dataset,root/'work/packs'/dataset.id,limit=args.preview_size,max_bytes=args.max_bytes))
        elif args.command=='serve':
            import uvicorn
            from dataset_atlas.api import create_app
            if args.host not in {'127.0.0.1','::1','localhost'}:raise ValueError('Use loopback binding and an SSH tunnel; remote binding is disabled by default')
            uvicorn.run(create_app(root),host=args.host,port=args.port)
        elif args.command=='doctor':
            checks={name:importlib.util.find_spec(name) is not None for name in ['fastapi','duckdb','pyarrow','nudenet','torchvision','transformers','sentence_transformers','lancedb','umap']}
            from dataset_atlas.registry import Registry
            emit({'workspace':str(root),'writable':os.access(root,os.W_OK),'datasets':len(Registry(root).datasets()),'dependencies':checks,'frontend_built':(root/'apps/web/dist/index.html').exists() or (Path(__file__).resolve().parents[1]/'web/index.html').exists(),'providers':'Not probed; no network requests performed','downloads':0})
        elif args.command=='publish':
            from dataset_atlas.exports import build_publication,validate_publication
            if args.profile!='public':raise ValueError('Only explicitly configured public profile is available')
            call=build_publication if args.action=='build' else validate_publication
            result=call(registry_dir=root/'registry',packs_dir=(args.packs_dir or (root/'examples/approved-packs' if (root/'examples/approved-packs').is_dir() else root/'work/packs')),output_dir=root/args.output,profile_path=root/'registry/publication.json')
            emit(result)
            if hasattr(result,'errors') and result.errors:return 1
        elif args.command in {'analyze','export'}:
            from dataset_atlas.api.app import State,create_app
            app=create_app(root)
            manager=app.state.jobs
            try:
                state=State(root/'work/atlas.sqlite')
                selection=state.get(args.selection if args.command=='analyze' else args.selection_id)
                records=app.state.selection_records(selection,prepare_media=args.command=='analyze')
                if args.command=='export':
                    from dataset_atlas.exports import export_selection
                    emit({'path':str(export_selection(selection,records,args.output))})
                else:
                    if manager is None:raise ValueError('Job coordinator unavailable')
                    supplied=json.loads(args.config.read_text()) if args.config else {}
                    with_config=app.state.run_config(args.processor,supplied)
                    emit(manager.estimate(selection,records,args.processor,with_config))
                    run=manager.create(selection,records,args.processor,with_config)
                    emit(run)
                    import time
                    while manager.get_run(run.id).status in {'queued','running','cancelling'}:time.sleep(.25)
                    final=manager.get_run(run.id);emit(final)
                    if final.status!='completed':return 1
            finally:
                if manager is not None:manager.close()
        return 0
    except (ValueError,FileNotFoundError,KeyError,ImportError) as exc:
        print(f'Atlas: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())

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
    storage=sub.add_parser('storage').add_subparsers(dest='action',required=True)
    usage=storage.add_parser('status',help='Measure local storage including sources, previews, models, caches and staging')
    usage.add_argument('--target-bytes',type=int)
    usage.add_argument('--ceiling-bytes',type=int)
    clean=storage.add_parser('clean',help='Evict unpinned caches and test environments; hard-link checksum-identical acquired sources')
    clean.add_argument('--execute',action='store_true')
    clean.add_argument('--idle-media-caches',action='store_true',help='Evict only unpinned media caches outside active preparation namespaces')
    clean.add_argument('--include-model-test-env',action='store_true',help='Also remove the reproducible isolated vLLM demonstration environment; retain model weights and evidence')
    configure=storage.add_parser('configure',help='Enable full-resolution on-demand compression and shared preparation admission limits')
    configure.add_argument('--target-bytes',type=int,default=100_000_000_000)
    configure.add_argument('--ceiling-bytes',type=int,default=150_000_000_000)
    configure.add_argument('--optimized-cache-bytes',type=int,default=5_000_000_000)
    configure.add_argument('--external-root',type=Path,action='append',default=[])
    compact=storage.add_parser('compact',help='Prepare full-dimension AVIF browsing copies while protecting preview originals')
    compact.add_argument('--dataset',required=True)
    compact.add_argument('--max-input-bytes',type=int,required=True)
    compact.add_argument('--max-output-bytes',type=int,required=True)
    compact.add_argument('--quality',type=int,default=60)
    compact.add_argument('--speed',type=int,default=6)
    pin=storage.add_parser('pin-preview',help='Retain every original image in a verified local preview')
    pin.add_argument('--dataset',required=True)
    pin.add_argument('--max-input-bytes',type=int,required=True)
    pin.add_argument('--max-output-bytes',type=int,required=True)
    index=storage.add_parser('index-original',help='Build a verified native archive member index for bounded original retrieval')
    index.add_argument('--source',type=Path,required=True)
    index.add_argument('--sha256',required=True)
    index.add_argument('--url',required=True)
    index.add_argument('--allow-host',action='append',required=True)
    index.add_argument('--format',choices=['zip','gzip-tar','tar'],required=True)
    index.add_argument('--name',required=True)
    index.add_argument('--max-input-bytes',type=int,required=True)
    index.add_argument('--max-index-bytes',type=int,default=500_000_000)
    retire=storage.add_parser('retire-original',help='Verify original retrieval and preview retention before removing acquired archive copies')
    retire.add_argument('--dataset',required=True)
    retire.add_argument('--also-dataset',action='append',default=[])
    retire.add_argument('--source',type=Path,required=True)
    retire.add_argument('--index',required=True)
    retire.add_argument('--asset-prefix',default='')
    retire.add_argument('--member-prefix',default='')
    retire.add_argument('--extracted-root',type=Path)
    retire.add_argument('--max-preview-bytes',type=int,default=500_000_000)
    retire.add_argument('--max-transfer-bytes',type=int,default=150_000_000)
    retire.add_argument('--modality',action='append',choices=['image','audio'],default=[])
    retire.add_argument('--execute',action='store_true')
    cifar=storage.add_parser('retire-cifar-c',help='Preserve native RGB rows and protected previews before retiring acquired CIFAR-C TAR copies')
    cifar.add_argument('--dataset',required=True,choices=['cifar-10-c','cifar-100-c'])
    cifar.add_argument('--max-transfer-bytes',type=int,default=20_000_000)
    cifar.add_argument('--execute',action='store_true')
    repacked=storage.add_parser('retire-repacked',help='Remove a redundant ZIP after exact native-member and retained-route verification')
    repacked.add_argument('--source',type=Path,required=True)
    repacked.add_argument('--sha256',required=True)
    repacked.add_argument('--index',required=True)
    repacked.add_argument('--max-decoded-bytes',type=int,required=True)
    repacked.add_argument('--max-transfer-bytes',type=int,default=150_000_000)
    repacked.add_argument('--execute',action='store_true')
    columnar=storage.add_parser('retire-columnar',help='Retain original previews and verified remote routes before removing acquired Parquet bodies')
    columnar.add_argument('--dataset',required=True)
    columnar.add_argument('--max-source-bytes',type=int,required=True)
    columnar.add_argument('--max-preview-bytes',type=int,required=True)
    columnar.add_argument('--max-transfer-bytes',type=int,required=True)
    columnar.add_argument('--max-index-bytes',type=int,default=250_000_000)
    columnar.add_argument('--execute',action='store_true')
    verified=storage.add_parser('verify-retired-preview',help='Decode and re-derive a native preview after source-body retirement')
    verified.add_argument('--dataset',required=True)
    verified.add_argument('--max-preview-bytes',type=int,required=True)
    verified.add_argument('--max-transfer-bytes',type=int,required=True)
    verified.add_argument('--execute',action='store_true')
    corpus=sub.add_parser('corpus').add_subparsers(dest='action',required=True)
    scan=corpus.add_parser('scan');scan.add_argument('--papers-dir',type=Path,required=True);scan.add_argument('--output',type=Path,default=Path('work/corpus'))
    extract=corpus.add_parser('extract');extract.add_argument('--manifest',type=Path,required=True)
    resolve=corpus.add_parser('resolve');resolve.add_argument('--mentions',type=Path,required=True);resolve.add_argument('--registry',type=Path,default=Path('registry'))
    datasets=sub.add_parser('datasets').add_subparsers(dest='action',required=True)
    cached=datasets.add_parser('cache-source',help='Register a verified local archive for reuse across preparation jobs');cached.add_argument('--path',type=Path,required=True);cached.add_argument('--sha256',required=True);cached.add_argument('--max-bytes',type=int,required=True)
    def source_options(parser):
        parser.add_argument('source',help='Absolute path to a folder/archive of images or a .csv/.tsv/.jsonl/.json/.parquet table, or a Hugging Face dataset URL')
        for flag in ('media-column','text-column','question-column','id-column','media-root'):parser.add_argument('--'+flag)
    inspect=datasets.add_parser('inspect',help='Show what would be registered for your own data, without registering anything');source_options(inspect)
    add=datasets.add_parser('add',help='Register your own folder, table or Hugging Face dataset and build its preview');source_options(add)
    add.add_argument('--name');add.add_argument('--id',dest='dataset_id');add.add_argument('--description',default='');add.add_argument('--replace',action='store_true',help='Re-register an existing dataset of yours, e.g. after its folder changed')
    add.add_argument('--no-prepare',action='store_true',help='Register only; build the preview later from the workbench or atlas previews fetch')
    add.add_argument('--max-download-bytes',type=int,default=2_000_000_000,help='Budget for Hugging Face sources; local sources download nothing')
    remove=datasets.add_parser('remove',help='Unregister a dataset you added; your files are never touched');remove.add_argument('dataset_id');remove.add_argument('--purge',action='store_true',help='Also delete its prepared index and preview')
    validate=datasets.add_parser('validate');validate.add_argument('--all',action='store_true')
    prepare=datasets.add_parser('prepare');prepare.add_argument('--dataset',required=True);prepare.add_argument('--preview-size',type=int,default=100);prepare.add_argument('--max-bytes',type=int,default=20_000_000);prepare.add_argument('--dry-run',action='store_true')
    acquire=datasets.add_parser('acquire');acquire.add_argument('--dataset',required=True);acquire.add_argument('--max-download-bytes',type=int,required=True);acquire.add_argument('--max-output-bytes',type=int,required=True);acquire.add_argument('--execute',action='store_true');acquire.add_argument('--source-mode',choices=['download','selective','sample'],default='download')
    preparation=datasets.add_parser('preparation');preparation.add_argument('--id',required=True);preparation.add_argument('--cancel',action='store_true');preparation.add_argument('--retry',action='store_true')
    preparation.add_argument('--refresh-metadata',metavar='DATASET_ID',help='Re-derive a completed version\'s coverage/evidence from its receipt');preparation.add_argument('--activate',action='store_true',help='With --refresh-metadata: make that version active')
    preparation.add_argument('--verify-remote-preview',metavar='DATASET_ID',help='Check a completed remote index and derive a preview with verified original images')
    preparation.add_argument('--verify-full-media',metavar='DATASET_ID',help='Prove every indexed image has a protected original and update media coverage')
    prune=datasets.add_parser('prune',help='List or remove failed, duplicate and unreferenced prepared versions');prune.add_argument('--execute',action='store_true')
    metadata=datasets.add_parser('prepare-metadata',help='Index the pinned PATA author labels/URLs without fetching third-party images')
    metadata.add_argument('--dataset',required=True,choices=['pata']);metadata.add_argument('--execute',action='store_true')
    metadata.add_argument('--max-download-bytes',type=int,default=1_000_000);metadata.add_argument('--max-output-bytes',type=int,default=20_000_000)
    index=datasets.add_parser('index');index.add_argument('--dataset',required=True);index.add_argument('--expected-count',type=int,required=True);index.add_argument('--max-bytes',type=int,default=30_000_000_000)
    previews=sub.add_parser('previews',help='Fetch inspectable previews into a workspace that holds none yet').add_subparsers(dest='action',required=True)
    pstatus=previews.add_parser('status',help='List datasets by what this workspace holds; --plan also checks cost and readiness over the network');pstatus.add_argument('--plan',action='store_true');pstatus.add_argument('--dataset',action='append',default=[])
    pstatus.add_argument('--max-download-bytes',type=int,default=2_000_000_000)
    pfetch=previews.add_parser('fetch',help='Plan, and with --execute fetch, previews cheapest first within a total download budget');pfetch.add_argument('--dataset',action='append',default=[],help='Repeat to name datasets; default is every dataset with an upstream preview')
    pfetch.add_argument('--per-dataset-download-bytes',type=int,default=2_000_000_000);pfetch.add_argument('--per-dataset-output-bytes',type=int,default=4_000_000_000,help='Cap on one dataset\'s prepared index and preview; a complete index can be several times its source size');pfetch.add_argument('--total-download-bytes',type=int,default=20_000_000_000);pfetch.add_argument('--execute',action='store_true')
    init=sub.add_parser('init',help='Create a workspace from the catalogue shipped in this installation (or refresh its catalogue with --update)');init.add_argument('directory',nargs='?',type=Path,default=Path('.'));init.add_argument('--update',action='store_true')
    models=sub.add_parser('models',help='Install the pinned public model weights the analysis tools need').add_subparsers(dest='action',required=True)
    mstatus=models.add_parser('status',help='Which analysis models are installed and configured; --verify re-hashes every file');mstatus.add_argument('--verify',action='store_true')
    mfetch=models.add_parser('fetch',help='Plan, and with --execute download, pinned model weights into work/models and configure the processors')
    mfetch.add_argument('--model',action='append',default=[],help='Repeat to name models (see `atlas models status`); default is all');mfetch.add_argument('--execute',action='store_true')
    mfetch.add_argument('--max-download-bytes',type=int,default=3_000_000_000);mfetch.add_argument('--reconfigure',action='store_true',help='Overwrite existing processor settings in local-config/recipes.json')
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8765)
    analyze=sub.add_parser('analyze');analyze.add_argument('--selection',required=True);analyze.add_argument('--processor',required=True);analyze.add_argument('--config',type=Path)
    export=sub.add_parser('export').add_subparsers(dest='action',required=True)
    selection=export.add_parser('selection');selection.add_argument('selection_id');selection.add_argument('--output',type=Path,required=True)
    publish=sub.add_parser('publish').add_subparsers(dest='action',required=True)
    for action in ['validate','build']:
        p=publish.add_parser(action);p.add_argument('--profile',default='public');p.add_argument('--output',type=Path,default=Path('apps/web/public'));p.add_argument('--packs-dir',type=Path)
    schemas=publish.add_parser('schemas',help='Write the preview field schemas and the merged coverage snapshot the public build needs (a maintainers\' step; commit the result)')
    schemas.add_argument('--output',type=Path,default=Path('examples/public-schema'))
    doctor=sub.add_parser('doctor')
    doctor.add_argument('--probe-provider',action='append',default=[],metavar='ID',help='Check a selected configured endpoint with a generated benign text probe; sends no dataset contents and downloads no files')
    args=parser.parse_args(argv);root=args.root.resolve()
    try:
        if args.command=='init':
            from dataset_atlas.workspace import init_workspace
            result=init_workspace(args.directory,update=args.update);emit(result)
            print(f"Next: cd {result['workspace']} && atlas serve   (then open http://127.0.0.1:8765/)",file=sys.stderr)
            return 0
        if args.command in {'serve','previews','datasets','models'} and not (root/'registry/datasets').is_dir():
            raise ValueError(f'No catalogue in {root}. Run `atlas init {root}` to create a workspace, or pass --root for an existing one.')
        if args.command=='storage':
            if args.action=='clean':
                from dataset_atlas.storage.maintenance import clean_workspace,evict_idle_media_caches
                if args.idle_media_caches:
                    if args.include_model_test_env:raise ValueError('Idle media-cache cleanup cannot remove model environments')
                    emit(evict_idle_media_caches(root,execute=args.execute))
                else:emit(clean_workspace(root,execute=args.execute,include_model_test_env=args.include_model_test_env))
                return 0
            if args.action=='status':
                from dataset_atlas.storage.usage import workspace_usage
                from dataset_atlas.storage.optimized import storage_policy
                policy = storage_policy(root) or {}
                emit(workspace_usage(root,args.target_bytes if args.target_bytes is not None else policy.get('target_bytes',100_000_000_000),args.ceiling_bytes if args.ceiling_bytes is not None else policy.get('ceiling_bytes',150_000_000_000),policy.get('external_roots',[])))
            elif args.action=='configure':
                from dataset_atlas.storage.optimized import configure_storage
                emit(configure_storage(root,target_bytes=args.target_bytes,ceiling_bytes=args.ceiling_bytes,optimized_cache_bytes=args.optimized_cache_bytes,external_roots=args.external_root))
            elif args.action=='index-original':
                from dataset_atlas.storage.ranges import range_fingerprint
                source=args.source if args.source.is_absolute() else root/args.source
                base=(root/'work/original-access').resolve();output=(base/args.name).resolve()
                if not output.is_relative_to(base) or output==base:raise ValueError('Original index name must stay inside work/original-access')
                if source.stat().st_size>args.max_input_bytes:raise ValueError('Source exceeds input byte budget')
                remote={'url':args.url,'bytes':source.stat().st_size,'allowed_hosts':args.allow_host}
                remote['etag']=range_fingerprint(args.url,expected_size=remote['bytes'],allowed_hosts=args.allow_host)
                if args.format=='zip':
                    from dataset_atlas.storage.indexed_zip import build_zip_index as build
                    bounds={'max_input_bytes':args.max_input_bytes}
                else:
                    from dataset_atlas.storage.indexed_tar import build_tar_index as build
                    bounds={'max_uncompressed_bytes':args.max_input_bytes}
                emit(build(source,output,source_sha256=args.sha256,remote=remote,max_index_bytes=args.max_index_bytes,**bounds))
            elif args.action=='retire-cifar-c':
                from dataset_atlas.storage.cifar_ranges import retire_cifar_archive
                emit(retire_cifar_archive(root,args.dataset,max_transfer_bytes=args.max_transfer_bytes,execute=args.execute))
            elif args.action=='retire-repacked':
                from dataset_atlas.storage.retention import retire_repacked_archive
                emit(retire_repacked_archive(root,args.index,args.source,source_sha256=args.sha256,max_decoded_bytes=args.max_decoded_bytes,max_transfer_bytes=args.max_transfer_bytes,execute=args.execute))
            elif args.action=='retire-columnar':
                from dataset_atlas.storage.columnar_retention import retire_columnar_sources
                emit(retire_columnar_sources(root,args.dataset,max_source_bytes=args.max_source_bytes,max_preview_bytes=args.max_preview_bytes,
                    max_transfer_bytes=args.max_transfer_bytes,max_index_bytes=args.max_index_bytes,execute=args.execute))
            elif args.action=='verify-retired-preview':
                from dataset_atlas.storage.columnar_retention import verify_retired_preview
                emit(verify_retired_preview(root,args.dataset,max_preview_bytes=args.max_preview_bytes,
                    max_transfer_bytes=args.max_transfer_bytes,execute=args.execute))
            elif args.action=='retire-original':
                from dataset_atlas.storage.retention import retire_image_archive
                emit(retire_image_archive(root,args.dataset,args.index,args.source,mappings=[{'asset_prefix':args.asset_prefix,'member_prefix':args.member_prefix},{'asset_prefix':'media/'+args.asset_prefix,'member_prefix':args.member_prefix}],max_preview_bytes=args.max_preview_bytes,max_transfer_bytes=args.max_transfer_bytes,extracted_root=args.extracted_root,linked_datasets=args.also_dataset,modalities=args.modality or ('image',),execute=args.execute))
            elif args.action=='pin-preview':
                from dataset_atlas.storage.compact import pin_preview_originals
                emit(pin_preview_originals(root,args.dataset,max_input_bytes=args.max_input_bytes,max_output_bytes=args.max_output_bytes))
            else:
                from dataset_atlas.storage.compact import compact_dataset
                emit(compact_dataset(root,args.dataset,max_input_bytes=args.max_input_bytes,max_output_bytes=args.max_output_bytes,quality=args.quality,speed=args.speed,
                    progress=lambda value: print(json.dumps(value),file=sys.stderr,flush=True)))
        elif args.command=='corpus':
            from dataset_atlas.corpus import pipeline
            if args.action=='scan':emit(pipeline.scan(args.papers_dir,args.output))
            elif args.action=='extract':emit(pipeline.extract(args.manifest))
            else:emit(pipeline.resolve(args.mentions,args.registry))
        elif args.command=='datasets':
            from dataset_atlas.registry import Registry
            registry=Registry(root)
            if args.action=='cache-source':
                from dataset_atlas.storage.sources import register_source
                emit(register_source(root,args.path,args.sha256,args.max_bytes))
            elif args.action=='acquire':
                from dataset_atlas.preparation import PreparationManager
                manager=PreparationManager(root);plan=manager.plan(args.dataset,args.max_download_bytes,args.max_output_bytes,args.source_mode);emit(plan)
                if args.execute:emit(manager.start(plan['id']))
            elif args.action=='preparation':
                from dataset_atlas.preparation import PreparationManager
                manager=PreparationManager(root)
                if args.verify_full_media:emit(manager.verify_full_media(args.verify_full_media,args.id))
                elif args.verify_remote_preview:emit(manager.verify_remote_preview(args.verify_remote_preview,args.id))
                elif args.refresh_metadata:emit(manager.refresh_metadata(args.refresh_metadata,args.id,activate=args.activate))
                else:emit(manager.cancel(args.id) if args.cancel else manager.start(args.id) if args.retry else manager.status(args.id))
            elif args.action=='prune':
                from dataset_atlas.preparation import PreparationManager
                emit(PreparationManager(root).prune(execute=args.execute))
            elif args.action=='prepare-metadata':
                from dataset_atlas.preparation.pata import prepare_metadata
                emit(prepare_metadata(root,execute=args.execute,max_download_bytes=args.max_download_bytes,max_output_bytes=args.max_output_bytes))
            elif args.action in {'inspect','add'}:
                from dataset_atlas.registry.user import inspect_source,register
                options={key:getattr(args,key) for key in ('media_column','text_column','question_column','id_column','media_root') if getattr(args,key)}
                inspection=inspect_source(args.source,options)
                shown={key:value for key,value in inspection.items() if key!='adapter_config'}
                if args.action=='inspect':emit(shown)
                else:
                    entry=register(root,inspection,name=args.name or inspection['suggested']['name'],dataset_id=args.dataset_id,description=args.description,replace=args.replace)
                    emit({'registered':entry.id,'name':entry.name,'records':inspection['count'],'warnings':inspection['warnings'],'source_files_touched':False})
                    if not args.no_prepare:
                        from dataset_atlas.preparation.previews import fetch_previews
                        report=fetch_previews(root,[entry.id],per_dataset_download_bytes=args.max_download_bytes,total_download_bytes=args.max_download_bytes,execute=True,log=lambda message:print(message,file=sys.stderr,flush=True))
                        emit(report)
                        if report['outcomes'].get('failed') or report['outcomes'].get('skipped_not_ready'):return 1
            elif args.action=='remove':
                from dataset_atlas.registry.user import unregister
                emit(unregister(root,args.dataset_id,purge=args.purge))
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
        elif args.command=='previews':
            from dataset_atlas.preparation import PreparationManager
            from dataset_atlas.preparation.previews import fetch_previews,plan_all,targets
            if args.action=='status':
                manager=PreparationManager(root);registry=manager.registry
                local=[d.id for d in registry.datasets() if registry.local_state(d.id)[0]]
                missing=targets(manager,args.dataset or None)
                result={'catalogue':len(registry.datasets()),'local_previews':len(local),'on_request':len(missing),'dataset_ids_on_request':[d.id for d in missing]}
                if args.plan:
                    rows=plan_all(manager,missing,args.max_download_bytes,args.max_download_bytes,lambda message:print(message,file=sys.stderr,flush=True))
                    result['readiness']={'ready':sum(r['ready'] for r in rows),'not_ready':sum(not r['ready'] for r in rows),'datasets':rows}
                emit(result)
            else:
                report=fetch_previews(root,args.dataset or None,per_dataset_download_bytes=args.per_dataset_download_bytes,per_dataset_output_bytes=args.per_dataset_output_bytes,total_download_bytes=args.total_download_bytes,execute=args.execute,log=lambda message:print(message,file=sys.stderr,flush=True))
                emit(report)
                if not args.execute:print('Dry run: nothing was downloaded. Re-run with --execute to fetch the planned previews.',file=sys.stderr)
                if report['outcomes'].get('failed') or report.get('interrupted'):return 1
        elif args.command=='models':
            from dataset_atlas import models_install
            if args.action=='status':emit(models_install.status(root,verify=args.verify))
            else:
                report=models_install.install(root,args.model or None,execute=args.execute,max_download_bytes=args.max_download_bytes,reconfigure=args.reconfigure,log=lambda message:print(message,file=sys.stderr,flush=True))
                emit(report)
                if not args.execute:print('Dry run: nothing was downloaded. Re-run with --execute to install these models.',file=sys.stderr)
        elif args.command=='serve':
            import uvicorn
            from dataset_atlas.api import create_app
            if args.host not in {'127.0.0.1','::1','localhost'}:raise ValueError('Use loopback binding and an SSH tunnel; remote binding is disabled by default')
            from dataset_atlas.jobs.coordinator_lock import acquire_coordinator_lock
            coordinator_lock=acquire_coordinator_lock(root/'work')  # held until the process exits
            uvicorn.run(create_app(root),host=args.host,port=args.port)
        elif args.command=='doctor':
            checks={name:importlib.util.find_spec(name) is not None for name in ['fastapi','duckdb','pyarrow','nudenet','torchvision','transformers','sentence_transformers','lancedb','umap']}
            from dataset_atlas.registry import Registry
            import shutil
            issues=[]
            catalogue=(root/'registry/datasets').is_dir()
            if not catalogue:issues.append(f'No catalogue in {root}: run `atlas init {root}` to create a workspace.')
            frontend=(root/'apps/web/dist/index.html').exists() or (Path(__file__).resolve().parents[1]/'web/index.html').exists()
            if not frontend:issues.append('The interface is not built: install a release wheel, or run `npm --prefix apps/web ci && npm --prefix apps/web run build`.')
            free=shutil.disk_usage(root).free
            if free<5_000_000_000:issues.append(f'Only {free/1e9:.1f} GB free on the workspace disk; previews and indexes need room.')
            from dataset_atlas.storage.optimized import storage_policy
            policy=storage_policy(root) or {}
            for external in policy.get('external_roots',[]):
                if not Path(external).is_dir():issues.append(f'Configured storage root does not exist: {external}. Preparations are refused until it is fixed: re-run `atlas storage configure` with --external-root for each root that still exists.')
            datasets=Registry(root).datasets() if catalogue else []
            user=[d.id for d in datasets if d.origin=='user']
            provider_checks='Not probed; no network requests performed'
            if args.probe_provider:
                if len(args.probe_provider)>8 or len(set(args.probe_provider))!=len(args.probe_provider):raise ValueError('Select at most eight unique provider IDs')
                from dataset_atlas.providers import ProviderService
                service=ProviderService(root/'local-config/providers.json',lambda identity:None)
                provider_checks=[]
                for identity in args.probe_provider:
                    try:
                        view=service.probe(identity,['text_generation'])
                        capability=view.capabilities['text_generation']
                        provider_checks.append({'provider_id':identity,'model':view.config.model,'capability':capability.model_dump(mode='json'),'probe_input':'generated benign text only'})
                        if capability.status!='supported':issues.append(f'Provider {identity} did not pass its text-generation connection check: {capability.detail}')
                    except ValueError as exc:
                        provider_checks.append({'provider_id':identity,'error':str(exc)})
                        issues.append(f'Provider {identity} connection check failed: {exc}')
            emit({'workspace':str(root),'writable':os.access(root,os.W_OK),'datasets':len(datasets),'your_datasets':user,'free_bytes':free,'dependencies':checks,'frontend_built':frontend,'issues':issues,'providers':provider_checks,'downloads':0})
            if issues:return 1
        elif args.command=='publish' and args.action=='schemas':
            from dataset_atlas.exports.guide import write_coverage,write_schemas
            from dataset_atlas.registry import Registry
            registry=Registry(root)
            written=write_schemas(registry,root/args.output)
            emit({'schemas_written':len(written),'coverage_entries':write_coverage(registry,root/args.output),'output':str(args.output)})
        elif args.command=='publish':
            from dataset_atlas.exports import build_publication,validate_publication
            if args.profile!='public':raise ValueError('Only explicitly configured public profile is available')
            call=build_publication if args.action=='build' else validate_publication
            result=call(registry_dir=root/'registry',packs_dir=(args.packs_dir or (root/'examples/approved-packs' if (root/'examples/approved-packs').is_dir() else root/'work/packs')),output_dir=root/args.output,profile_path=root/'registry/publication.json')
            emit(result)
            if hasattr(result,'errors') and result.errors:return 1
        elif args.command in {'analyze','export'}:
            from dataset_atlas.api.app import State,create_app
            # Both commands construct the app's recovering job manager, so
            # acquire ownership before either can recover pending runs.
            from dataset_atlas.jobs.coordinator_lock import acquire_coordinator_lock
            coordinator_lock=acquire_coordinator_lock(root/'work')
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

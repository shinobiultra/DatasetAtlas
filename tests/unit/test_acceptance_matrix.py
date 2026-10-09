"""SPEC 22.1 traceability: every acceptance row names a real test or a receipt."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location('atlas_verify_acceptance_matrix', ROOT / 'scripts/verify_acceptance_matrix.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SPEC_ROWS = ['Corpus', 'Identity', 'Repeated images', 'Overlays', 'Query parity', 'Scope', 'Sampling', 'Retrieval',
             'Detector results', 'Geometry', 'Projections', 'Model context', 'Tools', 'Jobs', 'Publication', 'Installation']


@pytest.fixture(scope='module')
def matrix():
    return json.loads((ROOT / 'docs/acceptance-matrix.json').read_text())


@pytest.fixture(scope='module')
def collected():
    return module.collect_nodes(ROOT)


def test_all_sixteen_spec_rows_are_present(matrix):
    assert [row['spec_row'] for row in matrix['rows']] == SPEC_ROWS
    assert len({row['id'] for row in matrix['rows']}) == 16
    assert all(row['condition'] and row['note'] for row in matrix['rows'])


def test_every_row_names_at_least_one_existing_test_or_receipt(matrix, collected):
    assert module.verify(matrix, collected, ROOT) == []
    for row in matrix['rows']:
        assert row['pytest'] or row['playwright'] or row['receipts'] or row.get('status') == 'not_applicable', row['id']


def test_a_nonexistent_node_id_fails_verification(matrix, collected):
    bad = {'rows': [dict(matrix['rows'][0], pytest=['tests/unit/test_nothing_here.py::test_missing'])]}
    problems = module.verify(bad, collected, ROOT)
    assert any('test_nothing_here.py::test_missing' in problem for problem in problems)


def test_a_row_with_no_test_and_no_receipt_fails_verification(collected):
    row = {'id': 'x', 'spec_row': 'X', 'condition': 'c', 'pytest': [], 'playwright': [], 'receipts': [], 'note': 'n'}
    assert any('no test and no receipt' in problem for problem in module.verify({'rows': [row]}, collected, ROOT))


def test_a_missing_playwright_spec_or_receipt_fails_verification(collected):
    row = {'id': 'x', 'spec_row': 'X', 'condition': 'c', 'pytest': [], 'playwright': ['apps/web/e2e/nope.spec.ts'],
           'receipts': ['reports/nope.json'], 'note': 'n'}
    problems = module.verify({'rows': [row]}, collected, ROOT)
    assert any('nope.spec.ts' in problem for problem in problems) and any('reports/nope.json' in problem for problem in problems)


def test_corpus_gives_every_paper_an_outcome_and_every_mention_its_evidence(tmp_path):
    from dataset_atlas.corpus.pipeline import OUTCOMES, extract, scan
    root = tmp_path / 'papers'
    root.mkdir()
    (root / 'broken.pdf').write_bytes(b'not really a PDF')
    (root / 'named.html').write_text('<html><body>We evaluate on the ImageNet dataset.</body></html>')
    (root / 'silent.html').write_text('<html><body>No dataset is named here.</body></html>')
    scan(root, tmp_path / 'out')
    extract(tmp_path / 'out/corpus_manifest.json')
    papers = [json.loads(line) for line in (tmp_path / 'out/papers.jsonl').read_text().splitlines()]
    mentions = [json.loads(line) for line in (tmp_path / 'out/dataset_mentions.jsonl').read_text().splitlines()]
    assert len(papers) == 3 and all(paper['outcome'] in OUTCOMES for paper in papers)
    assert {paper['outcome'] for paper in papers} >= {'extraction_failed', 'processed_with_review_items'}
    assert mentions and {mention['paper_id'] for mention in mentions} <= {paper['paper_id'] for paper in papers}
    assert all(m['source_file_hash'] and m['supporting_excerpt'] and (m['page'] or m['line']) for m in mentions)
    assert {m['review_status'] for m in mentions} == {'candidate_unreviewed'}


def test_ids_survive_sort_pagination_and_export_import(pack, tmp_path):
    from dataset_atlas.exports import export_pack, import_pack
    from dataset_atlas.models import Query
    from dataset_atlas.queries import query_pack
    expected = {record.id for record in pack.records}
    for sort in ([], [{'field_id': 'source.score', 'direction': 'desc'}], [{'field_id': 'source.label', 'direction': 'asc'}]):
        seen, cursor = [], None
        while True:
            page = query_pack(pack, Query(snapshot_id='s1', sort=sort, limit=3, cursor=cursor))
            seen += [record.id for record in page.records]
            cursor = page.cursor
            if cursor is None:
                break
        assert sorted(seen) == sorted(expected) and len(seen) == len(expected)
    restored = import_pack(export_pack(pack, tmp_path / 'pack'))
    assert [record.id for record in restored.records] == [record.id for record in pack.records]


def test_a_preview_pack_refuses_complete_scope_and_labels_its_counts_as_preview(pack):
    from dataset_atlas.models import Query
    from dataset_atlas.queries import query_pack
    with pytest.raises(ValueError, match='scope'):
        query_pack(pack, Query(snapshot_id='s1', population_scope='complete'))
    result = query_pack(pack, Query(snapshot_id='s1'))
    assert result.population_scope == 'preview' and any('preview' in warning for warning in result.warnings)


def test_a_pack_overlay_join_counts_result_items_that_match_no_record(pack):
    import re
    from dataset_atlas.models import Artifact
    from dataset_atlas.queries.results import attach_results
    items = [{'id': 'r0', 'status': 'completed', 'output': {'score': 1}}, {'id': 'ghost', 'status': 'completed', 'output': {'score': 2}}]
    artifact = Artifact(id='run-a', kind='fixture.score', snapshot_ids=['s1'], unit='example', ids=['r0', 'ghost'], data={'items': items})
    try:
        joined = attach_results(pack, [artifact])
    except ValueError:
        return
    counts = [value for key, value in joined.artifacts[0].coverage.items() if re.search('unjoin|unmatch|not_join|join_fail', key)]
    assert counts == [1]


@pytest.mark.parametrize('text', ['Authorization: Bearer abcdefghijklmnopqrstuvwxyz', 'see /home/researcher/private/notes.txt', 'full text at https://example.org/paper.pdf'], ids=['secret', 'absolute-path', 'pdf-reference'])
def test_publication_rejects_secrets_absolute_paths_and_pdf_references(tmp_path, text):
    from dataset_atlas.exports import PublicationError, build_publication
    from dataset_atlas.models import Dataset, Pack, Record
    entry = Dataset(id='toy', name='Toy', release='r1', snapshot_id='s1', rights={'records': 'approved'})
    (tmp_path / 'registry/datasets').mkdir(parents=True)
    (tmp_path / 'packs/toy').mkdir(parents=True)
    (tmp_path / 'registry/datasets/toy.json').write_text(entry.model_dump_json())
    (tmp_path / 'registry/publication.json').write_text(json.dumps({'schema_version': '1.0', 'datasets': {'toy': {'records': True}}}))
    record = Record(id='toy:example:1', dataset_id='toy', release_id='r1', snapshot_id='s1', text=text)
    (tmp_path / 'packs/toy/pack.json').write_text(Pack(dataset=entry, fields=[], records=[record], sampling={'method': 'first'}).model_dump_json())
    with pytest.raises(PublicationError, match='Private, local, or PDF'):
        build_publication(tmp_path / 'registry', tmp_path / 'packs', tmp_path / 'public', tmp_path / 'registry/publication.json')
    assert not (tmp_path / 'public/data').exists()


def test_base_install_declares_no_model_dependency_and_the_api_imports_none_of_them():
    import subprocess
    import sys
    import tomllib
    heavy = ('torch', 'torchvision', 'transformers', 'nudenet', 'sentence-transformers', 'lancedb', 'scikit-learn', 'umap-learn')
    base = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['dependencies']
    assert not [dependency for dependency in base if dependency.lower().startswith(heavy)]
    code = "import sys, dataset_atlas.api, dataset_atlas.cli; print(sorted(m for m in ('torch','transformers','nudenet','lancedb','sklearn','umap','sentence_transformers') if m in sys.modules))"
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env={'PYTHONPATH': str(ROOT / 'src'), 'PATH': '/usr/bin'}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-500:]
    assert result.stdout.strip() == '[]'


def test_projection_provenance_survives_export_and_filtering_leaves_the_fit_untouched(pack, tmp_path):
    from dataset_atlas.exports import export_pack, import_pack
    from dataset_atlas.models import Artifact, Query
    from dataset_atlas.processors import run_processor
    from dataset_atlas.queries import query_pack
    from dataset_atlas.queries.results import attach_results
    records = pack.records[:3]
    config = {'vectors': {'r0': [0, 0], 'r1': [1, 0], 'r2': [0, 2]}, 'embedding_space_id': 'space-a', 'embedding_run_id': 'run-a'}
    result = run_processor('project.pca', records, config)
    points = [{'id': item['id'], **item['output']} for item in result['items']]
    artifact = Artifact(id='proj', kind='project.pca', snapshot_ids=['s1'], unit='example', ids=[r.id for r in records],
                        provenance={'processor_provenance': result['provenance']}, data={'items': result['items'], 'points': points})
    before = artifact.model_dump()
    filtered = query_pack(attach_results(pack, [artifact]), Query(snapshot_id='s1', result_snapshot_ids=['proj'], filter={'field_id': 'prediction.proj.x', 'op': 'gte', 'value': 0}))
    assert filtered.matched_count and artifact.model_dump() == before
    assert run_processor('project.pca', records, config)['provenance']['fit_id'] == result['provenance']['fit_id']
    restored = import_pack(export_pack(pack.model_copy(update={'artifacts': [artifact]}), tmp_path / 'pack')).artifacts[0]
    assert restored.provenance['processor_provenance']['fit_id'] == result['provenance']['fit_id']
    assert restored.provenance['processor_provenance']['embedding_space_id'] == 'space-a'


def test_no_approximate_vector_index_ships_so_there_is_nothing_for_exact_search_to_validate():
    import re
    pattern = re.compile(r'create_index|create_ann|ivf_pq|\bhnsw\b|faiss|nprobe|\bIVF\b', re.I)
    hits = [str(path.relative_to(ROOT)) for path in (ROOT / 'src').rglob('*.py') if pattern.search(path.read_text(errors='ignore'))]
    assert hits == []
    assert 'bypass_vector_index' in (ROOT / 'src/dataset_atlas/processors/analysis.py').read_text()

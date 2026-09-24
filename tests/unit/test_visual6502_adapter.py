import hashlib

import pytest


def test_visual6502_literal_table_is_bounded_and_never_executed(pack, tmp_path):
    from dataset_atlas.adapters.visual6502 import Visual6502Adapter

    rows = [f"['t{i}', 1, 2, 3, [1, 2, 3, 4], [1, 2, 3, 4, 5]]"
            for i in range(3510)]
    path = tmp_path / 'transdefs.js'
    path.write_text('var transdefs = [\n' + ',\n'.join(rows) + '\n]')
    data = path.read_bytes()
    dataset = pack.dataset
    dataset.id = 'visual6502-fixture'
    dataset.release = 'test-pinned'
    dataset.snapshot_id = 'fixture'
    dataset.adapter = 'visual6502'
    dataset.adapter_config = {'transdefs': str(path), 'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(), 'commit': 'fixture'}
    adapter = Visual6502Adapter(dataset)
    assert adapter.count == 3510
    source = adapter.prepare(adapter.plan(10, 100_000))
    page = adapter.iter_records(source, cursor='3509', limit=10)
    assert len(page.records) == 1
    assert page.records[0].source['transistor_id'] == 't3509'

    # Even if a changed source is checksum-pinned, it must remain a literal
    # table; a JavaScript/Python expression is never evaluated.
    path.write_text(path.read_text().replace("['t0', 1", "[__import__('os').system('false'), 1", 1))
    changed = path.read_bytes()
    dataset.adapter_config['bytes'] = len(changed)
    dataset.adapter_config['sha256'] = hashlib.sha256(changed).hexdigest()
    with pytest.raises((ValueError, SyntaxError), match='malformed|Visual6502|literal'):
        Visual6502Adapter(dataset).count

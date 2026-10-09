"""Ring-A-Bell nudity InvPrompt converter on synthetic CSVs: variant scoping, parsed parameters and refusal of malformed files."""
import csv
import json
from pathlib import Path

import pytest

from dataset_atlas.converters import CONVERTERS
from dataset_atlas.converters import text  # noqa: F401  (registers the converter)

VARIANTS = {'k16': 'Nudity_eta_3_K_16', 'k38': 'Nudity_eta_3_K_38'}


def write(path: Path, rows, header=('prompt', 'case_number', 'evaluation_seed')):
    with path.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def run(inputs, tmp_path):
    return CONVERTERS['ring_a_bell_nudity']({'variants': VARIANTS}, inputs, tmp_path / 'out', lambda: None)


def test_case_numbers_repeat_across_variants_but_source_ids_do_not(tmp_path):
    inputs = {'k16': write(tmp_path / 'a.csv', [('synthetic prompt one', 0, 11), ('synthetic prompt two', 1, 12)]),
              'k38': write(tmp_path / 'b.csv', [('synthetic prompt three', 0, 13)])}
    result = run(inputs, tmp_path)
    rows = [json.loads(line) for line in Path(result['path']).read_text().splitlines()]
    assert result['count'] == 3
    assert [r['source_id'] for r in rows] == ['Nudity_eta_3_K_16:0', 'Nudity_eta_3_K_16:1', 'Nudity_eta_3_K_38:0']
    assert rows[0]['k'] == 16 and rows[0]['eta'] == 3 and rows[2]['k'] == 38
    assert rows[0]['evaluation_seed'] == 11 and rows[0]['prompt'] == 'synthetic prompt one'


def test_a_repeated_case_number_inside_one_file_is_refused(tmp_path):
    inputs = {'k16': write(tmp_path / 'a.csv', [('p', 0, 1), ('q', 0, 2)]), 'k38': write(tmp_path / 'b.csv', [('r', 0, 3)])}
    with pytest.raises(ValueError, match='repeats case number'):
        run(inputs, tmp_path)


def test_unexpected_columns_or_stems_are_refused_not_guessed(tmp_path):
    inputs = {'k16': write(tmp_path / 'a.csv', [('p', 0, 1)], header=('prompt', 'case_number', 'seed')), 'k38': write(tmp_path / 'b.csv', [('r', 0, 3)])}
    with pytest.raises(ValueError, match='Unexpected Ring-A-Bell columns'):
        run(inputs, tmp_path)
    good = {'k16': write(tmp_path / 'c.csv', [('p', 0, 1)])}
    with pytest.raises(ValueError, match='Unexpected Ring-A-Bell file stem'):
        CONVERTERS['ring_a_bell_nudity']({'variants': {'k16': 'Violence_K_16'}}, good, tmp_path / 'out2', lambda: None)

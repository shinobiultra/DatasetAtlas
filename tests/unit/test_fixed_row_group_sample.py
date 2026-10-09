"""A seeded two-stage preview selection that never looks at the transfer budget.

Stage one ranks every row group of the pinned population by SHA-256("<seed>:row_group:<source name>:<group>") and keeps
the lowest `row_groups`; stage two ranks the rows of each kept group by SHA-256("<seed>:row:<source name>:<group>:<row>")
and keeps the lowest few, so exactly `count` rows result and no group contributes more than `max_rows_per_group`.
Same population, seed and parameters give the same rows in every workspace. The byte budget only gates admission: a
selection that does not fit is refused, never altered.
"""
import hashlib

import pytest

from dataset_atlas.preparation.remote_sample import FixedRowGroupSampler

NAMES = ['data/real-00000-of-00002.parquet', 'data/real-00001-of-00002.parquet', 'data/test-00000-of-00001.parquet']
# (file index, row group, rows, transfer bytes), in the fixed population order of the pinned shards.
GROUPS = [(f, g, 40 + (f * 7 + g * 3) % 30, 1_000_000 + 10_000 * (f * 17 + g)) for f in range(3) for g in range(12)]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def drain(sampler):
    rows = []
    while (row := sampler.next()) is not None:
        rows.append(row)
    return rows


def make(**kwargs):
    options = dict(groups=GROUPS, names=NAMES, seed=0, row_groups=14, count=100, max_rows_per_group=8, byte_budget=10**12)
    options.update(kwargs)
    return FixedRowGroupSampler(**options)


def test_selection_is_the_documented_ranking_and_nothing_else():
    rows = drain(make())
    ranked = sorted(GROUPS, key=lambda g: sha(f'0:row_group:{NAMES[g[0]]}:{g[1]}'))[:14]
    assert [(f, g) for f, g in dict.fromkeys((f, g) for f, g, _ in rows)] == [(f, g) for f, g, _, _ in ranked]
    assert len(rows) == len(set(rows)) == 100
    per_group = {}
    for f, g, row in rows:
        per_group.setdefault((f, g), []).append(row)
    sizes = sorted(len(v) for v in per_group.values())
    assert sizes == [7] * 12 + [8] * 2  # 100 = 14 * 7 + 2: the two best-ranked groups give one more row
    for (f, g), picked in per_group.items():
        expected = sorted(range(next(r for ff, gg, r, _ in GROUPS if (ff, gg) == (f, g))), key=lambda r: sha(f'0:row:{NAMES[f]}:{g}:{r}'))
        assert picked == expected[:len(picked)]


def test_the_budget_never_changes_which_records_are_chosen():
    needed = make().selected_bytes
    baseline = drain(make(byte_budget=needed))
    assert drain(make(byte_budget=needed * 1000)) == baseline
    assert make(byte_budget=needed).description(100)['admission_budget_bytes'] == needed


def test_a_selection_that_does_not_fit_is_refused_instead_of_shrunk():
    needed = make().selected_bytes
    with pytest.raises(ValueError, match=r'needs .* bytes.*budget.*does not change'):
        make(byte_budget=needed - 1)


def test_seed_and_names_define_the_selection_and_the_listing_order_does_not():
    assert drain(make()) == drain(make())
    assert drain(make(seed=1)) != drain(make())
    assert drain(make(groups=list(reversed(GROUPS)))) == drain(make())  # only names and numbers matter, never list order


def test_groups_are_chosen_uniformly_not_in_proportion_to_their_row_counts():
    def kept(row_counts):
        groups = [(f, g, row_counts(f, g), 1_000_000) for f in range(3) for g in range(12)]
        return {(f, g) for f, g, _ in drain(make(groups=groups))}
    assert kept(lambda f, g: 40) == kept(lambda f, g: 40 + (f * 31 + g * 11) % 60) == kept(lambda f, g: 100 if g < 6 else 40)


def test_description_records_seed_grouping_population_and_that_it_is_not_a_prevalence_estimate():
    sampler = make()
    description = sampler.description(len(drain(sampler)))
    assert description['method'] == 'sha256_ranked_row_groups_then_rows' and description['seed'] == 0
    assert description['grouping'] == 'row group, then row within group'
    assert description['population_count'] == sum(g[2] for g in GROUPS) and description['row_groups_in_population'] == len(GROUPS)
    assert description['row_groups_selected'] == 14 and description['rows_drawn'] == 100 and description['max_rows_per_group'] == 8
    assert description['valid_for_population_prevalence'] is False and 'prevalence' in description['design']
    assert description['selected_row_group_transfer_bytes'] == sampler.selected_bytes
    assert 'rank' in description['draw_rule'] and 'SHA-256' in description['draw_rule']


@pytest.mark.parametrize('bad', [dict(row_groups=0), dict(row_groups=99), dict(count=0), dict(max_rows_per_group=0),
                                 dict(row_groups=2, count=100, max_rows_per_group=3), dict(seed=-1), dict(seed=True)])
def test_impossible_or_unclear_parameters_are_refused(bad):
    with pytest.raises(ValueError):
        make(**bad)


def test_a_group_too_small_for_its_allocation_is_refused():
    small = [(0, g, 2, 100) for g in range(12)]
    with pytest.raises(ValueError, match='fewer rows'):
        FixedRowGroupSampler(groups=small, names=NAMES, seed=0, row_groups=6, count=18, max_rows_per_group=3, byte_budget=10**9)


def test_from_spec_reads_the_recipe_block():
    spec = {'method': 'sha256_ranked_row_groups_then_rows', 'seed': 0, 'row_groups': 14, 'count': 100, 'max_rows_per_group': 8}
    assert drain(FixedRowGroupSampler.from_spec(GROUPS, NAMES, spec, byte_budget=10**12)) == drain(make())
    with pytest.raises(ValueError, match='method'):
        FixedRowGroupSampler.from_spec(GROUPS, NAMES, {**spec, 'method': 'something_else'}, byte_budget=10**12)

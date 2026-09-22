"""Source conversion preserves task structure and withheld labels."""
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('prepare_text_sources',Path(__file__).parents[2]/'scripts/prepare_text_sources.py')
source=importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)

def test_cola_headerless_rows_are_not_lost_and_original_copies_not_counted(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'SOURCE',tmp_path)
    with zipfile.ZipFile(tmp_path/'CoLA.zip','w') as z:
        z.writestr('CoLA/train.tsv','paper\t1\t\tFirst sentence.\n')
        z.writestr('CoLA/dev.tsv','paper\t0\t*\tBad sentence.\n')
        z.writestr('CoLA/test.tsv','index\tsentence\n0\tHidden label.\n')
        z.writestr('CoLA/original/raw/in_domain_train.tsv','paper\t1\t\tFirst sentence.\n')
    records=list(source.glue_rows('glue-cola'))
    assert len(records)==3
    assert records[0]['sentence']=='First sentence.'
    assert records[0]['source_id']=='train:0'
    assert records[-1]['label'] is None
    assert records[-1]['label_status']=='withheld_by_glue'

def test_paired_questions_and_original_ids_preserved(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'SOURCE',tmp_path)
    with zipfile.ZipFile(tmp_path/'QQP-clean.zip','w') as z:
        for split in ('train','dev','test'):
            z.writestr(f'QQP/{split}.tsv','id\tquestion1\tquestion2\n7\tFirst?\tSecond?\n')
    records=list(source.glue_rows('qqp'))
    assert records[0]['display_text']=='First?\n\nSecond?'
    assert records[0]['id']=='7'
    assert len({row['source_id'] for row in records})==3

def test_cebab_overlapping_alternatives_retain_same_original_id(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'SOURCE',tmp_path)
    with zipfile.ZipFile(tmp_path/'CEBaB-v1.1.zip','w') as z:
        for split in ('train_inclusive','train_exclusive','train_observational','dev','test'):
            z.writestr(f'CEBaB-v1.1/{split}.json',json.dumps([{'id':'same','original_id':'review','description':'Source text','review_majority':'no majority'}]))
    records=list(source.cebab_rows())
    assert len(records)==5 and len({row['source_id'] for row in records})==5
    assert {row['id'] for row in records}=={'same'}
    assert all(row['review_majority']=='no majority' for row in records)

def test_malformed_source_rows_fail_instead_of_silent_drop():
    with pytest.raises(ValueError,match='Malformed source row'):
        list(source.tsv_rows('a\tb\n1\n'))

from dataset_atlas.preparation.slots import try_writer_slot, transfer_slot
import pytest


def test_two_datasets_can_prepare_but_same_dataset_and_third_writer_wait(tmp_path):
    first = try_writer_slot(tmp_path, 'one')
    assert first is not None
    try:
        assert try_writer_slot(tmp_path, 'one') is None
        second = try_writer_slot(tmp_path, 'two')
        assert second is not None
        try:
            assert try_writer_slot(tmp_path, 'three') is None
            assert try_writer_slot(tmp_path, 'two') is None
        finally:
            second.close()
        third = try_writer_slot(tmp_path, 'three')
        assert third is not None
        third.close()
    finally:
        first.close()
    again = try_writer_slot(tmp_path, 'one')
    assert again is not None
    again.close()


def test_waiting_for_download_cache_is_cancellable_and_releases_lock(tmp_path):
    with transfer_slot(tmp_path, lambda: None):
        def cancel():raise InterruptedError('cancelled')
        with pytest.raises(InterruptedError):
            with transfer_slot(tmp_path, cancel):
                raise AssertionError('Cancelled reader entered')
    with transfer_slot(tmp_path, lambda: None):
        pass

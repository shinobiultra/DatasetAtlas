"""A workspace has one run coordinator: a second process is refused with the holder named, and the lock dies with its holder."""
import json
import subprocess
import sys

import pytest

from dataset_atlas.jobs.coordinator_lock import CoordinatorBusy, acquire_coordinator_lock


def test_a_second_coordinator_is_refused_naming_the_holder_and_released_on_close(tmp_path):
    work = tmp_path / 'work'
    first = acquire_coordinator_lock(work)
    with pytest.raises(CoordinatorBusy, match='already coordinating'):
        acquire_coordinator_lock(work)
    assert (work / '.coordinator.lock').read_text().strip().isdigit()
    first.close()
    again = acquire_coordinator_lock(work)  # released with the handle
    again.close()


def test_the_lock_is_released_when_the_holding_process_exits_without_cleanup(tmp_path):
    work = tmp_path / 'work'
    holder = subprocess.Popen([sys.executable, '-c',
        'import sys,time\nfrom dataset_atlas.jobs.coordinator_lock import acquire_coordinator_lock\n'
        'lock=acquire_coordinator_lock(sys.argv[1]);print("held",flush=True);time.sleep(60)', str(work)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'held'
        with pytest.raises(CoordinatorBusy, match=str(holder.pid)):
            acquire_coordinator_lock(work)
    finally:
        holder.kill()
        holder.wait()
    acquire_coordinator_lock(work).close()


@pytest.mark.parametrize('command', [
    ['analyze', '--selection', 'none', '--processor', 'quality.basic'],
    ['export', 'selection', 'none', '--output', 'unused.json'],
])
def test_cli_refuses_before_recovery_while_another_process_coordinates(tmp_path, capsys, monkeypatch, command):
    from dataset_atlas.cli import main
    from dataset_atlas.jobs.manager import JobManager
    (tmp_path / 'registry/datasets').mkdir(parents=True)
    def unexpected_recovery(self):
        pytest.fail('A second coordinator must not recover pending runs')
    monkeypatch.setattr(JobManager, 'recover', unexpected_recovery)
    held = acquire_coordinator_lock(tmp_path / 'work')
    try:
        code = main(['--root', str(tmp_path), *command])
    finally:
        held.close()
    assert code != 0
    assert 'already coordinating' in capsys.readouterr().err

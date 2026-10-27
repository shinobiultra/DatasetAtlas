"""Fresh-source verification cannot borrow generated or private checkout state."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


def startup_script():
    scripts = Path(__file__).resolve().parents[2] / 'scripts'
    spec = importlib.util.spec_from_file_location('atlas_sample_startup', scripts / 'verify_sample_startup.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_source_copy_keeps_tracked_build_inputs_and_excludes_all_generated_state(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    inputs = {'start.sh', 'pyproject.toml', 'uv.lock', 'LICENSE', 'README.md',
              'scripts/build_release.py', 'scripts/build_sample_bundle.py',
              'src/dataset_atlas/__init__.py', 'apps/web/src/main.tsx', 'apps/web/package.json',
              'apps/web/package-lock.json', 'apps/web/tsconfig.json', 'apps/web/vite.config.ts',
              'apps/web/index.html', 'apps/web/public/licenses/eurosat-MIT.txt',
              'examples/approved-packs/clevr/pack.json', 'examples/public-schema/coverage.json',
              'registry/datasets/clevr.yaml', 'registry/publication.json', 'registry/live-previews.yaml'}
    excluded = {'work/private.json', 'dist/old.whl', '.venv/bin/python', 'local-config/credentials.json',
                'apps/web/node_modules/existing.js', 'apps/web/dist/index.html',
                'apps/web/public/data/stale.json', 'src/dataset_atlas/web/index.html',
                'src/dataset_atlas/catalogue_seed/registry/private.json',
                'src/dataset_atlas/__pycache__/old.pyc', 'reports/private.json', 'registry/media/local.png'}
    for name in inputs | excluded:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic input: ' + name)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    # Force tracked generated files too: an ignore rule alone must not be the gate.
    subprocess.run(['git', '-C', str(root), 'add', '--all', '--force'], check=True)
    untracked = root / 'src/dataset_atlas/untracked.py'
    untracked.write_text('synthetic untracked source must not be borrowed')
    destination = tmp_path / 'clean'
    receipt = startup_script().copy_source_inputs(root, destination)
    copied = {path.relative_to(destination).as_posix() for path in destination.rglob('*') if path.is_file()}
    assert copied == inputs
    assert receipt['source_input_files'] == len(inputs)
    assert receipt['source_input_bytes'] == sum((root / name).stat().st_size for name in inputs)
    assert len(receipt['source_input_sha256']) == 64
    assert not (destination / '.git').exists()
    assert untracked.exists() and all((root / name).exists() for name in excluded)

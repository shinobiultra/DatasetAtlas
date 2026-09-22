"""Build the frontend once and include it in the installable Python wheel."""
from pathlib import Path
import shutil
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
subprocess.run(['npm','ci'],cwd=root/'apps/web',check=True)
subprocess.run(['npm','run','build'],cwd=root/'apps/web',check=True)
target=root/'src/dataset_atlas/web'
if target.exists():shutil.rmtree(target)
shutil.copytree(root/'apps/web/dist',target)
subprocess.run([sys.executable,'-m','build'],cwd=root,check=True)

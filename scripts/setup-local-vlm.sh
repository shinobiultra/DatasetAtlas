#!/usr/bin/env bash
set -euo pipefail

atlas_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uv venv "${atlas_root}/work/model-server/.venv" --python 3.12
uv pip install --python "${atlas_root}/work/model-server/.venv/bin/python" 'vllm==0.29.0' --torch-backend=auto
"${atlas_root}/work/model-server/.venv/bin/python" -c 'import torch,vllm; print("vLLM",vllm.__version__,"PyTorch",torch.__version__,"CUDA",torch.version.cuda)'

#!/usr/bin/env bash
set -euo pipefail

atlas_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
snapshot="${HOME}/.cache/huggingface/hub/models--Qwen--Qwen2.5-VL-3B-Instruct/snapshots/66285546d2b821cf421d4f5eb2576359d3770cd3"
server="${atlas_root}/work/model-server/.venv/bin/vllm"
if [[ ! -x "${server}" || ! -f "${snapshot}/config.json" ]]; then
  echo 'Pinned local model or isolated vLLM environment is unavailable. Recreate the environment with scripts/setup-local-vlm.sh.' >&2
  exit 1
fi
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES="${ATLAS_VLM_GPU:-0}"
exec "${server}" serve "${snapshot}" \
  --served-model-name qwen2.5-vl-3b-local \
  --host 127.0.0.1 --port 8001 \
  --dtype bfloat16 --gpu-memory-utilization 0.56 \
  --max-model-len 4096 --max-num-seqs 1 \
  --limit-mm-per-prompt '{"image":2,"video":0}' \
  --enable-auto-tool-choice --tool-call-parser hermes

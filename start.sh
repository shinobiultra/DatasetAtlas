#!/usr/bin/env bash
# A fresh clone needs only uv and Node/npm; no maintainer workspace or GPU.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ./start.sh [--no-open] [--port PORT]"
    echo "       ./start.sh --workbench"
    echo "Opens approved samples at http://127.0.0.1:8767/ (workbench: port 8765)."
    exit 0
fi
for tool in uv npm; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing $tool. Install uv and Node.js 26 (or 22.12+), then run ./start.sh again." >&2
        exit 1
    fi
done
# Retain optional analysis libraries already installed by the workspace owner.
uv sync --frozen --inexact
if [[ "${1:-}" == "--workbench" ]]; then
    shift
    exec uv run --no-sync python scripts/build_sample_bundle.py --workbench "$@"
fi
exec uv run --no-sync python scripts/build_sample_bundle.py --serve "$@"

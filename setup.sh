#!/usr/bin/env bash
# Linux/macOS setup for chrono-rag: conda env + install + prebuilt index.
# Re-running is safe: an existing env is reused, an existing index is kept.
set -e

ENV="${CHRONO_RAG_ENV:-chrono-rag}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found. Install Miniforge first: https://conda-forge.org/download/" >&2
  exit 1
fi

echo "==> [1/3] Creating conda env '$ENV' (python 3.12)..."
conda create -n "$ENV" python=3.12 -y >/dev/null || true

echo "==> [2/3] Installing chrono-rag into '$ENV'..."
conda run -n "$ENV" pip install -q -e ".[llm,web,mcp,dev]"

echo "==> [3/3] Downloading the prebuilt search index (~50 MB)..."
if ! conda run -n "$ENV" chrono-rag get-index; then
  echo '    (download failed or an index is already present; chrono-rag get-index --force retries)'
fi

cat <<EOF

============================================
  chrono-rag is ready. Next:

    conda activate $ENV
    chrono-rag search "how do I attach a lidar in pychrono"

  Using the conda PyChrono 10.0.0 release? Match the index to it:
    chrono-rag get-index --channel 10.0.0 --force

  Anything wrong? chrono-rag doctor
  Editor (MCP) and web app: see README.md
============================================
EOF

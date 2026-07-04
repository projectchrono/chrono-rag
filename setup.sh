#!/usr/bin/env bash
# Linux/macOS setup for chrono-rag: conda env + editable install.
set -e

ENV="${CHRONO_RAG_ENV:-chrono-rag}"

echo "==> Creating conda env '$ENV' (python 3.12)..."
conda create -n "$ENV" python=3.12 -y || true

echo "==> Installing chrono-rag (editable, with all extras)..."
conda run -n "$ENV" pip install -e ".[llm,web,mcp,dev]"

cat <<EOF

============================================
  chrono-rag env '$ENV' is ready.

  Next steps:
  1. Get the search index (downloads the prebuilt one):
       conda run -n $ENV chrono-rag get-index

  2. Search from the CLI (no API key needed):
       conda run -n $ENV chrono-rag search "attach a lidar in pychrono"

  3. Check your setup anytime:
       conda run -n $ENV chrono-rag doctor

  For editor (MCP) and web-app usage, see README.md.
============================================
EOF

#!/usr/bin/env bash
# Cross-platform (Linux/macOS) setup for chrono-rag v2. No Docker, no MongoDB.
set -e

ENV="${CHRONO_RAG_ENV:-chrono-rag}"

echo "==> Creating conda env '$ENV' (python 3.12)..."
conda create -n "$ENV" python=3.12 -y || true

echo "==> Installing dependencies..."
conda run -n "$ENV" pip install -r requirements.txt

cat <<EOF

============================================
  chrono-rag env '$ENV' is ready.

  Next steps:
  1. Get an index. Point at an existing one:
       export CHRONO_RAG_INDEX=/path/to/index
     or build from a Chrono checkout:
       CHRONO_RAG_REPO=/path/to/chrono conda run -n $ENV \\
         python src/preprocess/build_index.py

  2. Search from the CLI (no API key needed for the default fastembed index):
       conda run -n $ENV python src/surfaces/cli.py search "attach a lidar in pychrono"

  3. (Optional) Use the OpenAI-backed index converted from a MongoDB dump:
       pip install pymongo
       python scripts/convert_mongo_index.py --zip chrono_embeddings.zip --out index-mongo/
       CHRONO_RAG_INDEX=\$(pwd)/index-mongo conda run -n $ENV \\
         python src/surfaces/cli.py search "ChBodyEasyBox"
       # OPENAI_API_KEY must be set in the environment for query embedding.

  4. Use it in your editor: add src/surfaces/mcp_server.py as an MCP
     server (see README.md for the config snippet).
============================================
EOF

#!/bin/bash
set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$PROJECT_ROOT/.env" 2>/dev/null || true; set +a
python3 "$PROJECT_ROOT/scripts/rag_search.py" "$@"

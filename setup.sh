#!/usr/bin/env bash
# Linux/macOS setup; the shared helper preserves environments and checks failures.
set -euo pipefail
CONDA="${CONDA_EXE:-$(command -v conda || true)}"
if [[ -z "$CONDA" ]]; then
  echo 'conda not found. Install Miniforge first: https://conda-forge.org/download/' >&2
  exit 1
fi
BASE=$("$CONDA" info --base)
PYTHON="$BASE/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$BASE/python.exe"  # Git Bash on Windows
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$PYTHON" "$ROOT/scripts/setup_env.py" --conda "$CONDA" "$@"

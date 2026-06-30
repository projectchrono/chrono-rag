# Windows setup for chrono-rag v2. No Docker, no MongoDB.
$ErrorActionPreference = "Stop"

$EnvName = if ($env:CHRONO_RAG_ENV) { $env:CHRONO_RAG_ENV } else { "chrono-rag" }

Write-Host "==> Creating conda env '$EnvName' (python 3.12)..."
conda create -n $EnvName python=3.12 -y

Write-Host "==> Installing dependencies..."
conda run -n $EnvName pip install -r requirements.txt

Write-Host @"

============================================
  chrono-rag env '$EnvName' is ready.

  Next steps:
  1. Get an index. Point at an existing one:
       `$env:CHRONO_RAG_INDEX = "C:\path\to\index"
     or build from a Chrono checkout:
       `$env:CHRONO_RAG_REPO = "C:\path\to\chrono"
       conda run -n $EnvName python src/preprocess/build_index.py

  2. Search from the CLI (no API key needed):
       conda run -n $EnvName python src/surfaces/cli.py search "attach a lidar in pychrono"

  3. Use it in your editor: add src/surfaces/mcp_server.py as an MCP
     server (see README.md for the config snippet).
============================================
"@

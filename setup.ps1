# Windows setup for chrono-rag: conda env + editable install.
$ErrorActionPreference = "Stop"

$EnvName = if ($env:CHRONO_RAG_ENV) { $env:CHRONO_RAG_ENV } else { "chrono-rag" }

Write-Host "==> Creating conda env '$EnvName' (python 3.12)..."
conda create -n $EnvName python=3.12 -y

Write-Host "==> Installing chrono-rag (editable, with all extras)..."
conda run -n $EnvName pip install -e ".[llm,web,mcp,dev]"

Write-Host @"

============================================
  chrono-rag env '$EnvName' is ready.

  Next steps:
  1. Get the search index (downloads the prebuilt one):
       conda run -n $EnvName chrono-rag get-index

  2. Search from the CLI (no API key needed):
       conda run -n $EnvName chrono-rag search "attach a lidar in pychrono"

  3. Check your setup anytime:
       conda run -n $EnvName chrono-rag doctor

  For editor (MCP) and web-app usage, see README.md.
============================================
"@

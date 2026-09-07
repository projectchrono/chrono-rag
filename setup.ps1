# Windows setup for chrono-rag: conda env + install + prebuilt index.
# Re-running is safe: an existing env is reused, an existing index is kept.
$ErrorActionPreference = "Stop"

$EnvName = if ($env:CHRONO_RAG_ENV) { $env:CHRONO_RAG_ENV } else { "chrono-rag" }

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Error "conda not found. Install Miniforge first: https://conda-forge.org/download/"
}

Write-Host "==> [1/3] Creating conda env '$EnvName' (python 3.12)..."
conda create -n $EnvName python=3.12 -y | Out-Null

Write-Host "==> [2/3] Installing chrono-rag into '$EnvName'..."
conda run -n $EnvName pip install -q -e ".[llm,web,mcp,dev]"

Write-Host "==> [3/3] Downloading the prebuilt search index (~50 MB)..."
$ErrorActionPreference = "Continue"
conda run -n $EnvName chrono-rag get-index
if ($LASTEXITCODE -ne 0) {
    Write-Host "    (download failed or an index is already present; 'chrono-rag get-index --force' retries)"
}
$ErrorActionPreference = "Stop"

Write-Host @"

============================================
  chrono-rag is ready. Next:

    conda activate $EnvName
    chrono-rag search "how do I attach a lidar in pychrono"

  Using the conda PyChrono 10.0.0 release? Match the index to it:
    chrono-rag get-index --channel 10.0.0 --force

  Anything wrong? chrono-rag doctor
  Editor (MCP) and web app: see README.md
============================================
"@

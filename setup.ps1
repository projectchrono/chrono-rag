# Windows setup. Use native conda so shell aliases cannot hide failures.
param([string]$Channel = $(if ($env:CHRONO_RAG_CHANNEL) { $env:CHRONO_RAG_CHANNEL } else { 'main' }))
$ErrorActionPreference = 'Stop'
$Conda = $env:CONDA_EXE
if (-not $Conda) {
    $Conda = (Get-Command conda.exe -CommandType Application -ErrorAction Stop).Source
}
$CondaBase = & $Conda info --base
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate conda. Install Miniforge and retry.' }
$Python = Join-Path ($CondaBase | Select-Object -Last 1).Trim() 'python.exe'
& $Python (Join-Path $PSScriptRoot 'scripts/setup_env.py') --conda $Conda --channel $Channel
if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Resolve the error above and retry.' }

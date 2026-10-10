# Start Jarvis with the keys from .env loaded into the process environment.
# The server does not read .env by itself. Keys are never printed.
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envFile)) {
    Write-Host 'Missing .env - copy .env.example to .env and add your keys.' -ForegroundColor Red
    exit 1
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), 'Process')
    }
}

if (-not $env:GEMINI_API_KEY) {
    Write-Host 'GEMINI_API_KEY is empty in .env' -ForegroundColor Yellow
}

# --- Bootstrap (native tools print progress to stderr; that must not be fatal here) ---
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

# The package version comes from git, so every new commit makes `uv run` want to reinstall the
# editable package, which fails if jarvis.exe is running. Do it here, before it starts.
# --frozen leaves uv.lock alone, --inexact keeps our extra packages.
uv sync --frozen --extra desktop --inexact 2>&1 | Out-Null

# Optional runtime packages that are not in pyproject (changing pyproject would make `uv run`
# try to replace jarvis.exe while it is running). Install them once if missing.
$venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
foreach ($pkg in @(@{ mod = 'google.genai'; pip = 'google-genai' }, @{ mod = 'edge_tts'; pip = 'edge-tts' }, @{ mod = 'webview'; pip = 'pywebview' })) {
    & $venvPy -c "import $($pkg.mod)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $($pkg.pip)..."
        uv pip install $pkg.pip 2>&1 | Out-Null
    }
}
$ErrorActionPreference = $prevEap
# --- End bootstrap ---

$jarvisArgs = @('gui')
if ($NoBrowser) { $jarvisArgs += '--no-browser' }
& (Join-Path $PSScriptRoot '.venv\Scripts\jarvis.exe') @jarvisArgs
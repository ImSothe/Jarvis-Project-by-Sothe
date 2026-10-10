# One-click Jarvis: starts the server if needed (hidden), waits until it is ready,
# then opens Jarvis in its own app window (no tabs, no address bar).
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$url = 'http://localhost:5173'

function Test-Port([int]$port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect('127.0.0.1', $port); return $true } catch { return $false } finally { $c.Close() }
}

if (-not ((Test-Port 5173) -and (Test-Port 8000))) {
    # The server may be half up (e.g. it is still booting): only start it when nothing answers.
    if (-not ((Test-Port 5173) -or (Test-Port 8000))) {
        Start-Process powershell -WindowStyle Hidden -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
            '-File', (Join-Path $PSScriptRoot 'start-jarvis.ps1'), '-NoBrowser')
    }
    $deadline = (Get-Date).AddSeconds(150)
    while (-not ((Test-Port 5173) -and (Test-Port 8000))) {
        if ((Get-Date) -gt $deadline) {
            (New-Object -ComObject WScript.Shell).Popup('Jarvis no arrancó en 150 s. Abre jarvis-terminal.cmd para ver el error.', 0, 'Jarvis', 48) | Out-Null
            exit 1
        }
        Start-Sleep -Milliseconds 700
    }
    Start-Sleep -Seconds 2   # let the frontend finish its first compile
}

$candidates = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
)
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($browser) {
    Start-Process $browser -ArgumentList "--app=$url", '--window-size=1100,800'
} else {
    Start-Process $url
}

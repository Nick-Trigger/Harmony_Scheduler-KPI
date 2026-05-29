# dev.ps1 — boot the full planner stack for local development
#
# Usage:
#   .\dev.ps1            # start everything
#   .\dev.ps1 -Stop      # stop Postgres AND close opened terminals
#   .\dev.ps1 -DbOnly    # only start Postgres
#
# First time? You may need:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

param(
    [switch]$Stop,
    [switch]$DbOnly
)

$Root = Join-Path $PSScriptRoot ".."
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$StateFile = Join-Path $Root ".dev-state.json"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "!!! $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Cleanup helper — kills shells and closes WT windows launched in this session
# ---------------------------------------------------------------------------
function Stop-DevProcesses {
    if (-not (Test-Path $StateFile)) { return }

    try {
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    } catch {
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
        return
    }

    $marker = $state.SessionId
    if (-not $marker) {
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
        return
    }

    # 1. Kill the powershell.exe shells running our session's temp scripts.
    #    We match on the command line, which contains the session-tagged script path.
    $shells = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
              Where-Object { $_.CommandLine -like "*$marker*" }
    foreach ($s in $shells) {
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Ok "Closed shell PID $($s.ProcessId)"
    }

    # 2. Best-effort: close WT windows whose active tab title contains our marker.
    #    Tab titles were set via wt --title and also via $Host.UI.RawUI.WindowTitle.
    if (-not ('Native.WinAPI' -as [type])) {
        try {
            Add-Type -Namespace Native -Name WinAPI -MemberDefinition @"
[DllImport("user32.dll")]
public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
"@ -ErrorAction Stop
        } catch {}
    }
    if ('Native.WinAPI' -as [type]) {
        Get-Process WindowsTerminal -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -like "*$marker*" } |
            ForEach-Object {
                [Native.WinAPI]::PostMessage($_.MainWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
                Write-Ok "Closed Windows Terminal window (PID $($_.Id))"
            }
    }

    # 3. Clean up the temp scripts we generated for this session.
    Get-ChildItem $env:TEMP -Filter "dev-*-$marker.ps1" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue

    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Stop mode
# ---------------------------------------------------------------------------
if ($Stop) {
    Write-Step "Closing dev terminals..."
    Stop-DevProcesses

    Write-Step "Stopping Postgres..."
    docker compose -f (Join-Path $Root "docker-compose.yml") down
    Write-Ok "Done."
    exit 0
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
Write-Step "Checking prerequisites..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker not found on PATH. Install Docker Desktop and restart your terminal."
    exit 1
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker is installed but not running. Start Docker Desktop and try again."
    exit 1
}
Write-Ok "Docker is running."

if (-not (Test-Path $Backend)) { Write-Err "backend/ folder not found at $Backend"; exit 1 }
if (-not (Test-Path $Frontend) -and -not $DbOnly) { Write-Err "frontend/ folder not found at $Frontend"; exit 1 }

# Clean up any leftover processes from a previous run (e.g. crashed without -Stop)
if (Test-Path $StateFile) {
    Write-Step "Cleaning up previous dev session..."
    Stop-DevProcesses
}

# ---------------------------------------------------------------------------
# Postgres (detached)
# ---------------------------------------------------------------------------
Write-Step "Starting Postgres..."
docker compose -f (Join-Path $Root "docker-compose.yml") up -d
if ($LASTEXITCODE -ne 0) { Write-Err "Postgres failed to start."; exit 1 }

Write-Step "Waiting for Postgres to be ready..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    docker compose -f (Join-Path $Root "docker-compose.yml") exec -T db pg_isready -U planner 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { Write-Err "Postgres did not become ready in 15s. Check 'docker compose logs db'."; exit 1 }
Write-Ok "Postgres is accepting connections on localhost:5432"

if ($DbOnly) {
    Write-Host ""
    Write-Ok "Postgres is up. Run '.\.dev\dev.ps1 -Stop' when you're done."
    exit 0
}

# ---------------------------------------------------------------------------
# Backend + Frontend launch with session tracking
# ---------------------------------------------------------------------------
# Generate a unique session ID. We embed it in:
#   - the temp script paths (visible in each shell's command line for -Stop matching)
#   - wt tab titles AND the inner shell's window title (for WM_CLOSE on -Stop)
$SessionId = "WebPlanner-" + ([guid]::NewGuid().ToString("N").Substring(0, 8))

# Write the actual commands to temp script files. Passing them through wt as
# inline -Command strings is fragile because wt eats semicolons. -File is safer.
$bScript = Join-Path $env:TEMP "dev-backend-$SessionId.ps1"
$fScript = Join-Path $env:TEMP "dev-frontend-$SessionId.ps1"

@"
`$Host.UI.RawUI.WindowTitle = '$SessionId-Backend'
uv run uvicorn app.main:app --reload
"@ | Set-Content $bScript

@"
`$Host.UI.RawUI.WindowTitle = '$SessionId-Frontend'
npm run dev
"@ | Set-Content $fScript

Write-Step "Launching backend and frontend... (session: $SessionId)"

$wtAvailable = Get-Command wt -ErrorAction SilentlyContinue
if ($wtAvailable) {
    & wt `
        new-tab --title "$SessionId-Backend"  -d $Backend  powershell -NoExit -File $bScript `
        `; new-tab --title "$SessionId-Frontend" -d $Frontend powershell -NoExit -File $fScript
    Write-Ok "Opened Windows Terminal with backend + frontend tabs."
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-File", $bScript -WorkingDirectory $Backend
    Start-Process powershell -ArgumentList "-NoExit", "-File", $fScript -WorkingDirectory $Frontend
    Write-Ok "Opened two PowerShell windows (install Windows Terminal for tabbed UI)."
}

# Save session info so -Stop knows what to clean up
@{
    SessionId = $SessionId
    Started   = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content $StateFile

Write-Host ""
Write-Host "Stack is up:" -ForegroundColor Green
Write-Host "  Postgres:  localhost:5432"
Write-Host "  Backend:   http://localhost:8000  (docs: http://localhost:8000/docs)"
Write-Host "  Frontend:  http://localhost:5173"
Write-Host ""
Write-Host "To stop everything (Postgres + terminals): .\.dev\dev.ps1 -Stop"
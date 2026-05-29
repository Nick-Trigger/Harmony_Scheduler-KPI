# reset_db.ps1 — wipe and re-initialize the local database
#
# Usage:
#   .\reset_db.ps1           # reset DB, leave stack stopped
#   .\reset_db.ps1 -Restart  # reset DB and immediately bring the stack back up

param([switch]$Restart)

$Root = Join-Path $PSScriptRoot ".."
$DevScript = Join-Path $Root "./.dev/dev.ps1"
$Compose = Join-Path $Root "docker-compose.yml"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "!!! $msg" -ForegroundColor Red }

if (-not (Test-Path $DevScript)) {
    Write-Err "dev.ps1 not found at $DevScript"
    exit 1
}

# 1. Stop the running stack (closes terminals + stops Postgres container)
Write-Step "Stopping dev environment..."
& $DevScript -Stop
if ($LASTEXITCODE -ne 0) {
    Write-Err "dev.ps1 -Stop failed"
    exit 1
}

# 2. Nuke the Postgres data volume
Write-Step "Removing Postgres volume..."
docker compose -f $Compose down -v
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to remove volume"; exit 1 }
Write-Ok "Volume removed."

# 3. Bring Postgres back up (fresh, empty)
Write-Step "Starting fresh Postgres..."
& $DevScript -DbOnly
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to start Postgres"; exit 1 }

# 4. Apply migrations
Write-Step "Applying migrations..."
Push-Location (Join-Path $Root "backend")
try {
    uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Write-Err "Migration failed"; exit 1 }
    Write-Ok "Migrations applied."
} finally {
    Pop-Location
}

# 5. Optionally restart the full stack
if ($Restart) {
    Write-Host ""
    Write-Step "Restarting full stack..."
    & $DevScript
} else {
    Write-Host ""
    Write-Host "Database reset complete." -ForegroundColor Green
    Write-Host "Run '.\dev.ps1' to start the stack, or re-run with -Restart to do it automatically."
}
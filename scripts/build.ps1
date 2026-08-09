$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repo "frontend"
$backend = Join-Path $repo "backend"
$static = Join-Path $backend "app/static"

Push-Location $frontend
try {
    npm.cmd ci
    npm.cmd run api:check
    npm.cmd run test:coverage
    npm.cmd run build
}
finally {
    Pop-Location
}

Push-Location $backend
try {
    uv sync --frozen
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .
    uv run ty check
    uv build --wheel
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $static "index.html"))) {
    throw "The packaged SPA was not produced."
}

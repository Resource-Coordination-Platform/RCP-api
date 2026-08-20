param (
    [string]$service = "iam"
)

# Pytest ස්ථානය
$pytest = ".\venv\Scripts\pytest.exe"

# අදාළ සේවාවේ ෆෝල්ඩරය
$serviceDir = ".\services\$service"

if (-Not (Test-Path $serviceDir)) {
    Write-Host "Error: Service '$service' not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Running tests for '$service' service..." -ForegroundColor Cyan

# Tests ධාවනය කිරීම
Push-Location $serviceDir
& "..\..\venv\Scripts\pytest.exe" -v "tests\"
Pop-Location

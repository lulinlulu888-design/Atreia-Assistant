param(
    [string]$BackendPath = '',
    [switch]$SkipBackendBuild
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This development bundle targets Windows only.' }
$taskRoot = $PSScriptRoot
$taskVenv = Join-Path $taskRoot '.venv-build'
$taskPython = Join-Path $taskVenv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv $taskVenv
    if ($LASTEXITCODE -ne 0) { throw 'Build virtual environment creation failed.' }
}
& $taskPython -m pip install -r (Join-Path $taskRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Pinned packaging dependencies could not be installed.' }
if (-not $SkipBackendBuild) {
    cargo build --release --locked --manifest-path (Join-Path $taskRoot 'backend/Cargo.toml')
    if ($LASTEXITCODE -ne 0) { throw 'Rust backend build failed.' }
}
if (-not $BackendPath) {
    if ($env:CARGO_TARGET_DIR) { $taskTarget = $env:CARGO_TARGET_DIR }
    else { $taskTarget = Join-Path $taskRoot 'backend/target' }
    $BackendPath = Join-Path $taskTarget 'release/atreia-combat-backend.exe'
}
$taskBackend = (Resolve-Path -LiteralPath $BackendPath).Path
# Each build uses new directories. No cleaning, recursive delete or overwrite.
$taskStamp = 'dev-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 6)
$taskDist = Join-Path $taskRoot "dist/$taskStamp"
$taskWork = Join-Path $taskRoot "build/$taskStamp"
& $taskPython -m PyInstaller --onedir --windowed --name Atreia-Assistant-dev `
    --distpath $taskDist --workpath $taskWork --specpath $taskWork `
    --add-binary "${taskBackend}:bin" `
    --add-data "${taskRoot}/LICENSE:." `
    --add-data "${taskRoot}/THIRD_PARTY_NOTICES.md:." `
    (Join-Path $taskRoot 'app.py')
if ($LASTEXITCODE -ne 0) { throw 'Windows development bundle build failed.' }
$taskExe = Join-Path $taskDist 'Atreia-Assistant-dev/Atreia-Assistant-dev.exe'
$taskReport = Join-Path $taskDist 'synthetic-self-test.json'
$taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--self-test-report', ('"' + $taskReport + '"')) -WindowStyle Hidden -PassThru
if (-not $taskProcess.WaitForExit(60000)) {
    Stop-Process -Id $taskProcess.Id
    throw 'Synthetic bundle smoke test timed out; only this build test process was stopped.'
}
if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'Bundle smoke test failed.' }
$taskResult = Get-Content -Raw -LiteralPath $taskReport | ConvertFrom-Json
if ($taskResult.status -ne 'passed' -or $taskResult.real_game_tested -ne $false) { throw 'Unexpected smoke-test result.' }
Write-Output "Local development bundle: $taskExe"
Write-Output "Synthetic smoke test: $taskReport"
Write-Output 'Not a verified game release. Do not distribute before compatibility and corresponding-source/license audits.'

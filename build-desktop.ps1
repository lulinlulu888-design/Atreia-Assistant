param([string]$LocalizationEnginePath, [switch]$DebugBuild)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskDesktop = Join-Path $taskRoot 'desktop'
if ($LocalizationEnginePath) {
    $taskStage = Join-Path $taskRoot ('dist/desktop-localization-' + [guid]::NewGuid().ToString('N'))
    & (Join-Path $taskRoot 'prepare-localization.ps1') -Engine $LocalizationEnginePath -Destination $taskStage
    if ($LASTEXITCODE -ne 0) { throw 'Localization component preparation failed.' }
    $taskVendor = Join-Path $taskDesktop 'src-tauri/vendor/localization'
    foreach ($taskName in @('Atreia-Localization-Bridge.exe', 'Aion2-Steam-CN-v2.4.0.exe')) {
        Copy-Item -LiteralPath (Join-Path $taskStage $taskName) -Destination (Join-Path $taskVendor $taskName)
    }
}
Push-Location $taskDesktop
try {
    npm ci --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
    node --test tests/*.test.cjs tests/*.test.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Launcher tests failed.' }
    if ($DebugBuild) { npm run tauri build -- --no-bundle --debug }
    else { npm run tauri build -- --no-bundle }
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    Write-Output 'Local desktop build complete; no application, driver or game operation was started.'
} finally { Pop-Location }

param([string]$LocalizationEnginePath, [string]$LocalizationDecoderPath, [string]$LocalizationAdditionsPath, [switch]$DebugBuild)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskDesktop = Join-Path $taskRoot 'desktop'
if ($LocalizationEnginePath) {
    $taskStage = Join-Path $taskRoot ('dist/desktop-localization-' + [guid]::NewGuid().ToString('N'))
    & (Join-Path $taskRoot 'prepare-localization.ps1') -Engine $LocalizationEnginePath -Destination $taskStage -DecoderPath $LocalizationDecoderPath -AdditionsPath $LocalizationAdditionsPath
    if ($LASTEXITCODE -ne 0) { throw 'Localization component preparation failed.' }
    $taskVendor = Join-Path $taskDesktop 'src-tauri/vendor/localization'
    foreach ($taskName in @('Atreia-Localization-Bridge.exe', 'Aion2-Steam-CN-v2.4.0.exe')) {
        Copy-Item -LiteralPath (Join-Path $taskStage $taskName) -Destination (Join-Path $taskVendor $taskName)
    }
    if (Test-Path -LiteralPath (Join-Path $taskStage 'dependencies')) {
        $taskVendorDependencies = Join-Path $taskVendor 'dependencies'
        New-Item -ItemType Directory -Force -Path $taskVendorDependencies | Out-Null
        Copy-Item -LiteralPath (Join-Path $taskStage 'dependencies/oo2core_9_win64.dll') -Destination (Join-Path $taskVendorDependencies 'oo2core_9_win64.dll')
    }
}
& (Join-Path $taskRoot 'test-localization-safety.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Translation safety checks failed.' }
Push-Location $taskDesktop
try {
    npm ci --ignore-scripts --no-audit --no-fund --fetch-retries=0 --fetch-timeout=20000
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend resource generation failed.' }
    node --test tests/*.test.cjs tests/*.test.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Launcher tests failed.' }
    if ($DebugBuild) { npm run tauri build -- --no-bundle --debug }
    else { npm run tauri build -- --no-bundle }
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
    Write-Output 'Local desktop build complete; no application, driver or game operation was started.'
} finally { Pop-Location }

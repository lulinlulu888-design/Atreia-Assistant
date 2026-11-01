param([string]$LocalizationEnginePath, [string]$LocalizationDecoderPath, [string]$LocalizationAdditionsPath,
      [string]$JapaneseBundles, [string]$Python,
      [ValidateSet('steam','purple')][string[]]$LocalizationClients = @('steam','purple'), [switch]$DebugBuild)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskDesktop = Join-Path $taskRoot 'desktop'
if ($LocalizationEnginePath -or $LocalizationDecoderPath -or $LocalizationAdditionsPath) {
    throw 'The old English localization preparation is no longer supported. Use JapaneseBundles and Python with reviewed Japanese bundles.'
}
if ($JapaneseBundles) {
    if (-not $Python) { throw 'Python is required to prepare the Japanese helper.' }
    $taskStage = Join-Path $taskRoot ('dist/desktop-localization-' + [guid]::NewGuid().ToString('N'))
    & (Join-Path $taskRoot 'prepare-japanese-localization.ps1') -Bundles $JapaneseBundles -Python $Python -Clients $LocalizationClients -Destination $taskStage
    if ($LASTEXITCODE -ne 0) { throw 'Localization component preparation failed.' }
    $taskVendor = Join-Path $taskDesktop 'src-tauri/vendor/localization'
    foreach ($taskName in @('Atreia-Localization-Bridge.exe', 'helper.sha256', 'build.json')) {
        Copy-Item -LiteralPath (Join-Path $taskStage $taskName) -Destination (Join-Path $taskVendor $taskName)
    }
}
$taskVendor = Join-Path $taskDesktop 'src-tauri/vendor/localization'
if (-not (Test-Path -LiteralPath (Join-Path $taskVendor 'helper.sha256'))) { throw 'Prepare the reviewed Japanese helper before building the desktop app.' }
if (Test-Path -LiteralPath (Join-Path $taskVendor 'Aion2-Steam-CN-v2.4.0.exe')) { throw 'Legacy engine remains in localization resources; archive it before packaging.' }
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

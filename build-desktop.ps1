param([string]$LocalizationEnginePath, [string]$LocalizationDecoderPath, [string]$LocalizationAdditionsPath,
      [string]$JapaneseBundles, [string]$Python,
      [ValidateSet('steam')][string[]]$LocalizationClients = @('steam'), [switch]$DebugBuild)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskDesktop = Join-Path $taskRoot 'desktop'
$taskVendor = Join-Path $taskDesktop 'src-tauri/vendor/localization'
if ($LocalizationEnginePath) {
    if (-not $LocalizationDecoderPath -or -not $LocalizationAdditionsPath) { throw 'PURPLE preparation requires the reviewed decoder and additions.' }
    $taskPurpleStage = Join-Path $taskRoot ('dist/purple-localization-' + [guid]::NewGuid().ToString('N'))
    & (Join-Path $taskRoot 'prepare-localization.ps1') -Engine $LocalizationEnginePath -DecoderPath $LocalizationDecoderPath -AdditionsPath $LocalizationAdditionsPath -Destination $taskPurpleStage -PurpleOnly
    if ($LASTEXITCODE -ne 0) { throw 'PURPLE component preparation failed.' }
    $taskPurpleVendor = Join-Path $taskVendor 'purple'
    New-Item -ItemType Directory -Force -Path $taskPurpleVendor | Out-Null
    Copy-Item -Path (Join-Path $taskPurpleStage '*') -Destination $taskPurpleVendor -Recurse -Force
} elseif ($LocalizationDecoderPath -or $LocalizationAdditionsPath) {
    throw 'PURPLE preparation requires LocalizationEnginePath.'
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
if (-not (Test-Path -LiteralPath (Join-Path $taskVendor 'purple/helper.sha256'))) { throw 'Prepare the reviewed PURPLE English helper before building the desktop app.' }
if (Test-Path -LiteralPath (Join-Path $taskVendor 'Aion2-Steam-CN-v2.4.0.exe')) { throw 'Legacy engine remains in localization resources; archive it before packaging.' }
foreach ($taskClient in @('steam','purple')) {
    $taskComponent = if ($taskClient -eq 'steam') { $taskVendor } else { Join-Path $taskVendor 'purple' }
    $taskExecutable = Join-Path $taskComponent 'Atreia-Localization-Bridge.exe'
    $taskPin = (Get-Content -LiteralPath (Join-Path $taskComponent 'helper.sha256') -Raw).Trim()
    if ((Get-FileHash -LiteralPath $taskExecutable).Hash.ToLowerInvariant() -cne $taskPin) { throw "$taskClient helper digest mismatch." }
    $taskProtocol = & $taskExecutable --protocol | ConvertFrom-Json
    $taskEntry = if ($taskClient -eq 'steam') { 'ja-JP' } else { 'en-US' }
    if ($LASTEXITCODE -ne 0 -or $taskProtocol.protocol -ne 1 -or $taskProtocol.entry -ne $taskEntry) { throw "$taskClient helper protocol mismatch." }
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

param(
    [Parameter(Mandatory=$true)][string]$Inputs,
    [Parameter(Mandatory=$true)][string]$BaseComponent,
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Release staging directory must be new.' }
$taskInputs = (Resolve-Path -LiteralPath $Inputs).Path
$taskBase = (Resolve-Path -LiteralPath $BaseComponent).Path
$taskPython = (Resolve-Path -LiteralPath $Python).Path
New-Item -ItemType Directory -Path $Destination | Out-Null
$taskStage = (Resolve-Path -LiteralPath $Destination).Path
$taskSteam = Join-Path $taskInputs 'steam'
& $taskPython -X utf8 (Join-Path $PSScriptRoot 'localization/build_japanese_bundle.py') --client steam `
    --official-english (Join-Path $taskSteam 'official-en.dat') --official-japanese (Join-Path $taskSteam 'official-ja.dat') `
    --manifest (Join-Path $taskSteam 'manifest.dat') --previous-english (Join-Path $taskSteam 'previous-en.json') `
    --own-chinese (Join-Path $taskSteam 'own-chinese.json') --reviews (Join-Path $taskSteam 'reviews.json') `
    --packages (Join-Path $taskSteam 'ja-packages') --english-packages (Join-Path $taskSteam 'en-packages') `
    --destination (Join-Path $taskStage 'bundles/steam')
if ($LASTEXITCODE) { throw 'Steam Japanese-entry generation failed.' }
$taskMetadata = Get-Content -LiteralPath (Join-Path $taskStage 'bundles/steam/bundle.json') -Raw | ConvertFrom-Json
$taskExpected = Get-Content -LiteralPath (Join-Path $taskInputs 'expected.json') -Raw | ConvertFrom-Json
if ($taskMetadata.payload_sha256 -cne $taskExpected.steam_payload_sha256 -or $taskMetadata.keys -ne 153297 -or $taskMetadata.reference_keys -ne 153297) { throw 'Steam bundle differs from the game-tested payload.' }
if ((Get-FileHash -LiteralPath (Join-Path $taskInputs 'purple/additions.json.gz')).Hash.ToLowerInvariant() -cne $taskExpected.purple_additions_sha256) { throw 'PURPLE translations differ from the reviewed original scheme.' }
& (Join-Path $PSScriptRoot 'prepare-japanese-localization.ps1') -Bundles (Join-Path $taskStage 'bundles') -Python $taskPython -Destination (Join-Path $taskStage 'component')
if ($LASTEXITCODE) { throw 'Steam helper freeze failed.' }
& (Join-Path $PSScriptRoot 'prepare-localization.ps1') -Engine (Join-Path $taskBase 'Aion2-Steam-CN-v2.4.0.exe') `
    -DecoderPath (Join-Path $taskBase 'dependencies/oo2core_9_win64.dll') -AdditionsPath (Join-Path $taskInputs 'purple/additions.json.gz') `
    -PurpleOnly -Destination (Join-Path $taskStage 'component/purple')
if ($LASTEXITCODE) { throw 'PURPLE English-entry helper build failed.' }
foreach ($taskClient in @('steam','purple')) {
    $taskComponent = if ($taskClient -eq 'steam') { Join-Path $taskStage 'component' } else { Join-Path $taskStage 'component/purple' }
    $taskProtocol = & (Join-Path $taskComponent 'Atreia-Localization-Bridge.exe') --protocol | ConvertFrom-Json
    $taskEntry = if ($taskClient -eq 'steam') { 'ja-JP' } else { 'en-US' }
    if ($LASTEXITCODE -or $taskProtocol.protocol -ne 1 -or $taskProtocol.entry -ne $taskEntry) { throw "$taskClient protocol check failed." }
}
Write-Output 'Prepared Steam Japanese entry and PURPLE English entry; no game files were modified.'

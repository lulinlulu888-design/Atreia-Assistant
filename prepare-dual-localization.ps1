param(
    [Parameter(Mandatory=$true)][string]$Engine,
    [Parameter(Mandatory=$true)][string]$PurpleRoot,
    [Parameter(Mandatory=$true)][string]$SteamRoot,
    [Parameter(Mandatory=$true)][string]$DecoderPath,
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Destination must be new.' }
$taskEngine = (Resolve-Path -LiteralPath $Engine).Path
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskEngine).Hash -ne '1D01A3AB4C9604296DA6B2265FD0A5A1247D628D31FD4AB02EB8BAC539340E58') { throw 'Unreviewed localization engine.' }
$taskPurple = (Resolve-Path -LiteralPath $PurpleRoot).Path
$taskSteam = (Resolve-Path -LiteralPath $SteamRoot).Path
$taskDecoder = (Resolve-Path -LiteralPath $DecoderPath).Path
$taskPython = (Resolve-Path -LiteralPath $Python).Path
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
New-Item -ItemType Directory -Path $Destination | Out-Null
$taskStage = (Resolve-Path -LiteralPath $Destination).Path
$taskLocaleProbe = Join-Path $taskStage 'LocaleProbe.exe'
& $taskCompiler /nologo /target:exe /platform:x64 "/out:$taskLocaleProbe" (Join-Path $PSScriptRoot 'localization/LocaleProbe.cs')
if ($LASTEXITCODE -ne 0) { throw 'Extractor compilation failed.' }
$taskInputs = @(
    @{ Name='manifest'; Pak=(Join-Path $taskPurple 'Aion2/Content/Paks/pakchunk0-Windows.pak'); Locale='manifest' },
    @{ Name='purple-zh-TW'; Pak=(Join-Path $taskPurple 'Aion2/Content/Paks/L10N/Text/zh-TW/pakchunk504000-Windows_0_P.pak'); Locale='zh-TW' },
    @{ Name='purple-en-US'; Pak=(Join-Path $taskPurple 'Aion2/Content/Paks/L10N/Text/en-US/pakchunk502000-Windows_0_P.pak'); Locale='en-US' },
    @{ Name='steam-en-US'; Pak=(Join-Path $taskSteam 'Aion2/Content/Paks/L10N/Text/en-US/pakchunk502000-Windows_0_P.pak'); Locale='en-US' }
)
foreach ($taskInput in $taskInputs) {
    & $taskLocaleProbe $taskEngine $taskInput.Pak $taskInput.Locale $taskDecoder (Join-Path $taskStage $taskInput.Name)
    if ($LASTEXITCODE -ne 0) { throw 'Read-only extraction failed; use original current game resources, not localization marker packages.' }
}
foreach ($taskName in @('purple-zh-TW','purple-en-US','steam-en-US')) {
    $taskLocale = if ($taskName -eq 'purple-zh-TW') { 'zh-TW' } else { 'en-US' }
    & $taskPython (Join-Path $PSScriptRoot 'localization/locale_codec.py') (Join-Path $taskStage 'manifest/L10NString.dat') (Join-Path $taskStage "$taskName/L10NString.dat") $taskLocale (Join-Path $taskStage "$taskName.json")
    if ($LASTEXITCODE -ne 0) { throw 'Official table decoding failed.' }
}
$taskOfficial = Join-Path $taskStage 'official.json.gz'
& $taskPython (Join-Path $PSScriptRoot 'localization/build_official_additions.py') (Join-Path $taskStage 'purple-en-US.json') (Join-Path $taskStage 'purple-zh-TW.json') $taskOfficial (Join-Path $taskStage 'token-review.json')
if ($LASTEXITCODE -ne 0) { throw 'Official additions generation failed.' }
if (@(Get-Content -Raw (Join-Path $taskStage 'token-review.json') | ConvertFrom-Json).Count -ne 0) { throw 'Unreviewed official runtime parameter differences.' }
$taskProbe = Join-Path $taskStage 'CompatibilityProbe.exe'
& $taskCompiler /nologo /target:exe /platform:x64 /reference:System.Web.Extensions.dll "/out:$taskProbe" "/resource:$taskOfficial,Atreia.Localization.OfficialAdditions.gz" (Join-Path $PSScriptRoot 'localization/CompatibilityProbe.cs') (Join-Path $PSScriptRoot 'localization/EquivalentTranslations.cs') (Join-Path $PSScriptRoot 'localization/OfficialTranslations.cs')
if ($LASTEXITCODE -ne 0) { throw 'Compatibility probe compilation failed.' }
$taskDependencies = Join-Path $taskStage 'dependencies'
New-Item -ItemType Directory -Path $taskDependencies | Out-Null
Copy-Item -LiteralPath $taskDecoder -Destination (Join-Path $taskDependencies 'oo2core_9_win64.dll')
$taskDual = Join-Path $taskStage 'localization-additions.json.gz'
& $taskPython (Join-Path $PSScriptRoot 'localization/build_client_variants.py') $taskOfficial (Join-Path $taskStage 'purple-en-US.json') (Join-Path $taskStage 'steam-en-US.json') $taskProbe $taskEngine $taskSteam $taskDual
if ($LASTEXITCODE -ne 0) { throw 'Steam variant review failed; unsupported snapshots are not accepted silently.' }
& (Join-Path $PSScriptRoot 'prepare-localization.ps1') -Engine $taskEngine -DecoderPath $taskDecoder -AdditionsPath $taskDual -Destination (Join-Path $taskStage 'component')
if ($LASTEXITCODE -ne 0) { throw 'Dual-client component preparation failed.' }
Write-Output 'Read-only dual-client preparation complete. No game files were modified.'

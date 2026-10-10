param(
    [Parameter(Mandatory=$true)][string]$TestEngine,
    [Parameter(Mandatory=$true)][string]$GameRoot,
    [Parameter(Mandatory=$true)][ValidateSet('steam','purple')][string]$Client,
    [Parameter(Mandatory=$true)][string]$AdditionsPath,
    [Parameter(Mandatory=$true)][string]$DecoderPath
)
$ErrorActionPreference = 'Stop'
# The engine must have its DEBUG test interface. It is never used against the
# real game directory: only one original PAK is copied into our new fixture.
$taskEngine = (Resolve-Path -LiteralPath $TestEngine).Path
$taskAdditions = (Resolve-Path -LiteralPath $AdditionsPath).Path
$taskDecoder = (Resolve-Path -LiteralPath $DecoderPath).Path
if ((Get-FileHash -LiteralPath $taskDecoder -Algorithm SHA256).Hash -ne '6F5D41A7892EA6B2DB420F2458DAD2F84A63901C9A93CE9497337B16C195F457') {
    throw 'Unreviewed test decoder.'
}
$taskSource = Join-Path (Resolve-Path -LiteralPath $GameRoot).Path 'Aion2/Content/Paks/L10N/Text/en-US/pakchunk502000-Windows_0_P.pak'
$taskBefore = (Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash
# Keep generated backup/archive paths below the legacy .NET MAX_PATH limit.
$taskStage = Join-Path ([System.IO.Path]::GetTempPath()) ('Atreia-rt-' + $Client + '-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$taskPakDirectory = Join-Path $taskStage 'fixture/Aion2/Content/Paks/L10N/Text/en-US'
$taskFixture = Join-Path $taskStage 'fixture'
New-Item -ItemType Directory -Path $taskPakDirectory | Out-Null
New-Item -ItemType File -Path (Join-Path $taskFixture 'isolated-test.marker') | Out-Null
Copy-Item -LiteralPath $taskSource -Destination (Join-Path $taskPakDirectory 'pakchunk502000-Windows_0_P.pak')
$taskDependencies = Join-Path $taskStage 'dependencies'
New-Item -ItemType Directory -Path $taskDependencies | Out-Null
Copy-Item -LiteralPath $taskDecoder -Destination (Join-Path $taskDependencies 'oo2core_9_win64.dll')
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$taskRunner = Join-Path $taskStage 'LocalizationRoundtrip.exe'
$taskSources = @('tests/LocalizationRoundtrip.cs', 'localization/SupplementInstaller.cs', 'localization/EquivalentTranslations.cs', 'localization/OfficialTranslations.cs') | ForEach-Object { Join-Path $PSScriptRoot $_ }
& $taskCompiler /nologo /target:exe /platform:x64 /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll "/out:$taskRunner" "/resource:$taskAdditions,Atreia.Localization.OfficialAdditions.gz" @taskSources
if ($LASTEXITCODE -ne 0) { throw 'Roundtrip test compilation failed.' }
& $taskRunner $taskEngine $taskFixture
$taskExit = $LASTEXITCODE
if ((Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash -ne $taskBefore) {
    throw 'Game source changed during test; fixture result is not current.'
}
if ($taskExit -ne 0) { throw 'Isolated native transaction tests failed.' }
Write-Output "PASS: $Client current PAK isolated transactions; original game PAK unchanged."
Write-Output "Independent decoder audit fixture: $taskFixture"

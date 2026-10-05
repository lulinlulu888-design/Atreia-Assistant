param(
    [Parameter(Mandatory=$true)][string]$Engine,
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$DecoderPath,
    [string]$AdditionsPath
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Localization staging directory must be new.' }
$taskEngine = (Resolve-Path -LiteralPath $Engine).Path
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskEngine).Hash -ne '1D01A3AB4C9604296DA6B2265FD0A5A1247D628D31FD4AB02EB8BAC539340E58') {
    throw 'Only the reviewed official v2.4.0 localization engine is accepted.'
}
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $taskCompiler)) { throw '.NET Framework compiler is unavailable.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
$taskHelper = Join-Path $Destination 'Atreia-Localization-Bridge.exe'
$taskResources = @()
if ($AdditionsPath) {
    $taskAdditions = (Resolve-Path -LiteralPath $AdditionsPath).Path
    $taskResources += "/resource:$taskAdditions,Atreia.Localization.OfficialAdditions.gz"
}
& $taskCompiler /nologo /target:exe /platform:x64 /optimize+ /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll "/out:$taskHelper" @taskResources (Join-Path $PSScriptRoot 'localization/EngineBridge.cs') (Join-Path $PSScriptRoot 'localization/EquivalentTranslations.cs') (Join-Path $PSScriptRoot 'localization/OfficialTranslations.cs') (Join-Path $PSScriptRoot 'localization/SupplementInstaller.cs')
if ($LASTEXITCODE -ne 0) { throw 'Localization bridge compilation failed.' }
Copy-Item -LiteralPath $taskEngine -Destination (Join-Path $Destination 'Aion2-Steam-CN-v2.4.0.exe')
if ($DecoderPath) {
    $taskDecoder = (Resolve-Path -LiteralPath $DecoderPath).Path
    $taskDecoderHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $taskDecoder).Hash
    if ($taskDecoderHash -notin @('6F5D41A7892EA6B2DB420F2458DAD2F84A63901C9A93CE9497337B16C195F457','8595A4795F1E0C7F548598F3E2AA528B6BE5456C6D934C665182EAECB04156C0')) {
        throw 'Localization decoder hash mismatch.'
    }
    $taskDependencies = Join-Path $Destination 'dependencies'
    New-Item -ItemType Directory -Path $taskDependencies | Out-Null
    Copy-Item -LiteralPath $taskDecoder -Destination (Join-Path $taskDependencies 'oo2core_9_win64.dll')
}
Write-Output (Resolve-Path -LiteralPath $Destination).Path

param(
    [Parameter(Mandatory=$true)][string]$Engine,
    [Parameter(Mandatory=$true)][string]$Destination
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
& $taskCompiler /nologo /target:exe /platform:x64 /optimize+ /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll "/out:$taskHelper" (Join-Path $PSScriptRoot 'localization/EngineBridge.cs')
if ($LASTEXITCODE -ne 0) { throw 'Localization bridge compilation failed.' }
Copy-Item -LiteralPath $taskEngine -Destination (Join-Path $Destination 'Aion2-Steam-CN-v2.4.0.exe')
Write-Output (Resolve-Path -LiteralPath $Destination).Path

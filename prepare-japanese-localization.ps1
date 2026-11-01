param(
    [Parameter(Mandatory=$true)][string]$Bundles,
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Destination,
    [ValidateSet('steam','purple')][string[]]$Clients = @('steam','purple')
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'Localization staging directory must be new.' }
$taskBundles = (Resolve-Path -LiteralPath $Bundles).Path
$taskPython = (Resolve-Path -LiteralPath $Python).Path
& $taskPython -X utf8 (Join-Path $PSScriptRoot 'localization/freeze_entry_host.py') $taskBundles $Destination --clients @Clients
if ($LASTEXITCODE -ne 0) { throw 'Japanese localization helper preparation failed.' }
$taskStage = (Resolve-Path -LiteralPath $Destination).Path
$taskHelper = Join-Path $taskStage 'Atreia-Localization-Bridge.exe'
$taskBuild = Get-Content -LiteralPath (Join-Path $taskStage 'build.json') -Raw | ConvertFrom-Json
$taskHash = (Get-FileHash -LiteralPath $taskHelper -Algorithm SHA256).Hash.ToLowerInvariant()
if ($taskHash -cne $taskBuild.executable_sha256) { throw 'Prepared helper hash mismatch.' }
[IO.File]::WriteAllText((Join-Path $taskStage 'helper.sha256'), $taskHash, [Text.UTF8Encoding]::new($false))
Write-Output $taskStage

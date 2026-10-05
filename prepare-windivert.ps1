param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Destination) { throw 'WinDivert staging directory must be new.' }
New-Item -ItemType Directory -Path $Destination | Out-Null
$taskArchive = Join-Path $Destination 'WinDivert-2.2.2-A.zip'
$taskUrl = 'https://github.com/basil00/WinDivert/releases/download/v2.2.2/WinDivert-2.2.2-A.zip'
Invoke-WebRequest -Uri $taskUrl -OutFile $taskArchive
# Recorded from the official release asset during review; not an upstream
# published digest. Pinning prevents later silent asset changes in builds.
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskArchive).Hash -ne '63CB41763BB4B20F600B6DE04E991A9C2BE73279E317D4D82F237B150C5F3F15') {
    throw 'WinDivert release asset changed; review it before rebuilding.'
}
Expand-Archive -LiteralPath $taskArchive -DestinationPath (Join-Path $Destination 'source-package')
$taskRoot = Join-Path $Destination 'source-package/WinDivert-2.2.2-A'
$taskDriver = Join-Path $taskRoot 'x64/WinDivert64.sys'
if ((Get-AuthenticodeSignature -LiteralPath $taskDriver).Status -ne 'Valid') {
    throw 'WinDivert driver signature could not be validated; no driver was loaded.'
}
$taskBundle = Join-Path $Destination 'bundle'
New-Item -ItemType Directory -Path $taskBundle | Out-Null
foreach ($taskName in @('WinDivert.dll','WinDivert64.sys')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot ('x64/' + $taskName)) -Destination $taskBundle
}
foreach ($taskName in @('LICENSE','README','VERSION')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot $taskName) -Destination $taskBundle
}
Write-Output $taskBundle

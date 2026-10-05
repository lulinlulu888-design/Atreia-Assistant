param(
    [Parameter(Mandatory=$true)][string]$Component,
    [Parameter(Mandatory=$true)][string]$GameRoot,
    [Parameter(Mandatory=$true)][ValidateSet('steam','purple')][string]$Client,
    [Parameter(Mandatory=$true)][int]$ExpectedKeys,
    [Parameter(Mandatory=$true)][int]$ExpectedSupplemented
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$taskComponent = (Resolve-Path -LiteralPath $Component).Path
function Get-LanguageSnapshot {
    $taskRecords = foreach ($taskRelative in @('Aion2/Content/Paks/L10N/Text/en-US','Aion2/Content/L10N/Text/en-US')) {
        $taskDirectory = Join-Path $taskRoot $taskRelative
        if (Test-Path -LiteralPath $taskDirectory) {
            Get-ChildItem -LiteralPath $taskDirectory -File -Recurse | ForEach-Object {
                [pscustomobject]@{ Path=$_.FullName; Hash=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
            }
        }
    }
    return ($taskRecords | Sort-Object Path | ConvertTo-Json -Compress)
}
$taskBefore = Get-LanguageSnapshot
$taskRaw = & (Join-Path $taskComponent 'Atreia-Localization-Bridge.exe') (Join-Path $taskComponent 'Aion2-Steam-CN-v2.4.0.exe') inspect $taskRoot $Client
$taskExit = $LASTEXITCODE
$taskAfter = Get-LanguageSnapshot
if ($taskBefore -cne $taskAfter) { throw 'Inspection changed game language files.' }
if ($taskExit -ne 0) { throw "Inspection failed: $taskRaw" }
$taskResult = $taskRaw | ConvertFrom-Json
if (-not $taskResult.ok -or $taskResult.operation -ne 'inspect') { throw 'Unexpected inspection result.' }
if ($taskResult.supplemented -ne $ExpectedSupplemented) { throw 'Structured supplemental count is incorrect.' }
if ($taskResult.message -notmatch ([regex]::Escape("$ExpectedKeys 个键，额外补译 $ExpectedSupplemented 条"))) {
    throw 'Inspection message does not match expected current-source coverage.'
}
Write-Output $taskRaw
Write-Output "PASS: $Client real-source coverage, structured supplemental count, and byte-exact read-only inspection."

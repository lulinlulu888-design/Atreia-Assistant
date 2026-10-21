param(
    [Parameter(Mandatory=$true)][string]$Component,
    [Parameter(Mandatory=$true)][string]$SourcePak,
    [ValidateSet('steam','purple')][string]$Client = 'steam',
    [int]$ExpectedSupplemented = -1
)
$ErrorActionPreference = 'Stop'
$componentPath = (Resolve-Path -LiteralPath $Component).Path
$source = (Resolve-Path -LiteralPath $SourcePak).Path
$before = (Get-FileHash -LiteralPath $source).Hash
$fixture = Join-Path $env:TEMP ('Atreia-completion-' + [guid]::NewGuid().ToString('N'))
$pakDirectory = Join-Path $fixture 'Aion2/Content/Paks/L10N/Text/en-US'
New-Item -ItemType Directory -Path $pakDirectory | Out-Null
New-Item -ItemType File -Path (Join-Path $fixture 'isolated-test.marker') | Out-Null
$pak = Join-Path $pakDirectory 'pakchunk502000-Windows_0_P.pak'
Copy-Item -LiteralPath $source -Destination $pak
foreach ($operation in @('install','install','restore')) {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $componentPath 'Atreia-Localization-Bridge.exe'
    $psi.WorkingDirectory = $componentPath
    $psi.Arguments = '"' + (Join-Path $componentPath 'Aion2-Steam-CN-v2.4.0.exe') + '" ' + $operation + ' "' + $fixture + '" ' + $Client
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $process = [Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(45000)) {
        # Only this newly created, marked fixture process may be terminated.
        $process.Kill()
        $process.WaitForExit()
        throw "Isolated $operation did not return; fixture retained: $fixture; $($stderr.Result)"
    }
    $result = $stdout.Result | ConvertFrom-Json
    if ($process.ExitCode -ne 0 -or -not $result.ok -or $result.operation -ne $operation -or
        $result.client -ne $Client -or $result.game_root -ne $fixture) {
        throw "Isolated $operation failed: $($stdout.Result) $($stderr.Result)"
    }
    if ($operation -eq 'install') {
        if ($ExpectedSupplemented -ge 0 -and $result.supplemented -ne $ExpectedSupplemented) { throw 'Unexpected supplemental count.' }
        $dat = Join-Path $fixture 'Aion2/Content/L10N/Text/en-US/L10NString.dat'
        Copy-Item -LiteralPath $dat -Destination (Join-Path $fixture 'installed-payload.audit.dat') -Force
    }
    Write-Output "PASS: $Client production bridge $operation returned without a completion click."
    $process.Dispose()
}
if ((Get-FileHash -LiteralPath $pak).Hash -ne $before) { throw 'Isolated restore differs from original.' }
if ((Get-FileHash -LiteralPath $source).Hash -ne $before) { throw 'Original source changed.' }
Write-Output "PASS: byte-exact restoration; original source unchanged. Fixture: $fixture"

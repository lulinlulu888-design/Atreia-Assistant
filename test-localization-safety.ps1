$ErrorActionPreference = 'Stop'
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$taskStage = Join-Path $PSScriptRoot ('build/translation-safety-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskStage | Out-Null
$taskRunner = Join-Path $taskStage 'TranslationSafety.exe'
$taskFixture = Join-Path $taskStage 'fixture.json.gz'
$taskSources = @('tests/TranslationSafety.cs', 'localization/OfficialTranslations.cs', 'localization/EquivalentTranslations.cs') | ForEach-Object { Join-Path $PSScriptRoot $_ }
& $taskCompiler /nologo /target:exe /platform:x64 /reference:System.Web.Extensions.dll "/out:$taskRunner" @taskSources
if ($LASTEXITCODE -ne 0) { throw 'Safety test compilation failed.' }
& $taskRunner $taskFixture
if ($LASTEXITCODE -ne 0) { throw 'Synthetic fixture generation failed.' }
& $taskCompiler /nologo /target:exe /platform:x64 /reference:System.Web.Extensions.dll "/out:$taskRunner" "/resource:$taskFixture,Atreia.Localization.OfficialAdditions.gz" @taskSources
if ($LASTEXITCODE -ne 0) { throw 'Embedded safety test compilation failed.' }
& $taskRunner
if ($LASTEXITCODE -ne 0) { throw 'Translation safety tests failed.' }

param([string]$SshHost = 'atreia-aws')
$ErrorActionPreference = 'Stop'
$site = Split-Path $PSScriptRoot -Parent
$public = Join-Path $site '.output/public'
if (-not (Test-Path (Join-Path $public 'index.html'))) { throw 'Generate the Nuxt site first.' }
Copy-Item -LiteralPath (Join-Path $site 'release.json') -Destination (Join-Path $public 'download-release.json')
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
$archive = Join-Path ([IO.Path]::GetTempPath()) "atreia-site-$stamp.tar.gz"
tar -czf $archive -C $public .
if ($LASTEXITCODE) { throw 'Website archive failed.' }
scp -o BatchMode=yes $archive "${SshHost}:/tmp/atreia-site-$stamp.tar.gz"
if ($LASTEXITCODE) { throw 'Website transfer failed.' }
# A new release directory and atomic symlink switch leave hczs untouched.
ssh -o BatchMode=yes $SshHost "set -eu; sudo install -d -o ec2-user -g ec2-user /srv/atreia/www/releases/$stamp; tar -xzf /tmp/atreia-site-$stamp.tar.gz -C /srv/atreia/www/releases/$stamp; test -f /srv/atreia/www/releases/$stamp/index.html; ln -s /srv/atreia/www/releases/$stamp /srv/atreia/www/current-next; mv -Tf /srv/atreia/www/current-next /srv/atreia/www/current; sudo restorecon -RF /srv/atreia/www 2>/dev/null || true"
if ($LASTEXITCODE) { throw 'Website activation failed.' }
Write-Output "Published website revision $stamp"

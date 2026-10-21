param([Parameter(Mandatory = $true)][string]$MsiPath)
$ErrorActionPreference = 'Stop'

# Read the MSI database only; never install, launch, or create real shortcuts.
$installer = New-Object -ComObject WindowsInstaller.Installer
$database = $null
function Read-MsiRows([string]$Query, [int]$Columns) {
    $view = $database.OpenView($Query)
    try {
        [void]$view.Execute()
        while ($record = $view.Fetch()) {
            try {
                $values = @()
                for ($column = 1; $column -le $Columns; $column++) {
                    $values += $record.StringData($column)
                }
                ,$values
            } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($record) }
        }
    } finally {
        [void]$view.Close()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($view)
    }
}
try {
    $database = $installer.OpenDatabase((Resolve-Path -LiteralPath $MsiPath).Path, 0)
    $product = @(Read-MsiRows 'SELECT `Value` FROM `Property` WHERE `Property` = ''ProductName''' 1)
    if ($product.Count -ne 1 -or $product[0][0] -ne '亚特雷亚助手') { throw 'Expected the Chinese product display name.' }
    $upgrade = @(Read-MsiRows 'SELECT `Value` FROM `Property` WHERE `Property` = ''UpgradeCode''' 1)
    if ($upgrade.Count -ne 1 -or $upgrade[0][0].Trim('{}') -ine 'c743efbd-a4df-5791-be41-a1d39ebe3c98') { throw 'Existing MSI upgrade identity changed.' }
    $names = @(Read-MsiRows 'SELECT `Name` FROM `Shortcut` WHERE `Shortcut` = ''ApplicationDesktopShortcut''' 1)
    if ($names.Count -ne 1 -or $names[0][0].Split('|')[-1] -ne '亚特雷亚助手') { throw 'Desktop shortcut must use the Chinese software name.' }
    $menu = @(Read-MsiRows 'SELECT `Name` FROM `Shortcut` WHERE `Shortcut` = ''ApplicationStartMenuShortcut''' 1)
    if ($menu.Count -ne 1 -or $menu[0][0].Split('|')[-1] -ne '亚特雷亚助手') { throw 'Start menu shortcut must use the Chinese software name.' }
    $shortcuts = @(Read-MsiRows 'SELECT `Directory_`, `Component_`, `Target`, `WkDir` FROM `Shortcut` WHERE `Shortcut` = ''ApplicationDesktopShortcut''' 4)
    if ($shortcuts.Count -ne 1) { throw 'Expected exactly one built-in desktop shortcut.' }
    $shortcut = $shortcuts[0]
    if ($shortcut[0] -ne 'DesktopFolder' -or $shortcut[1] -ne 'ApplicationShortcutDesktop' -or
        $shortcut[2] -ne '[!Path]' -or $shortcut[3] -ne 'INSTALLDIR') {
        throw 'Desktop shortcut does not target the installed application.'
    }
    $files = @(Read-MsiRows 'SELECT `FileName` FROM `File` WHERE `File` = ''Path''' 1)
    if ($files.Count -ne 1 -or $files[0][0] -notlike '*.exe') { throw 'Shortcut executable is missing.' }
    $links = @(Read-MsiRows 'SELECT `Feature_` FROM `FeatureComponents` WHERE `Component_` = ''ApplicationShortcutDesktop''' 1)
    if ('External' -notin @($links | ForEach-Object { $_[0] })) { throw 'Desktop shortcut is not in the mandatory feature.' }
    $features = @(Read-MsiRows 'SELECT `Level`, `Attributes` FROM `Feature` WHERE `Feature` = ''External''' 2)
    if ($features.Count -ne 1 -or $features[0][0] -ne '1' -or (([int]$features[0][1] -band 16) -eq 0)) {
        throw 'Desktop shortcut feature must be enabled and disallow removal.'
    }
    $components = @(Read-MsiRows 'SELECT `Attributes` FROM `Component` WHERE `Component` = ''ApplicationShortcutDesktop''' 1)
    if ($components.Count -ne 1 -or (([int]$components[0][0] -band 16) -ne 0)) {
        throw 'Desktop shortcut must not be permanent after uninstall.'
    }
    $actions = @(Read-MsiRows 'SELECT `Action` FROM `InstallExecuteSequence` WHERE `Action` = ''RemoveShortcuts''' 1)
    if ($actions.Count -ne 1) { throw 'Installer is missing shortcut removal.' }
    Write-Output 'PASS: MSI desktop shortcut target, mandatory feature and uninstall cleanup.'
} finally {
    if ($database) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($database) }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
}

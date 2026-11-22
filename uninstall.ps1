# ARASAKA RELIC // desinstalador Windows
# powershell -ExecutionPolicy Bypass -File uninstall.ps1
$App  = 'arasaka-relic'
$Data = Join-Path $env:LOCALAPPDATA $App
$Bin  = Join-Path $Data 'bin'
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$Data*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
foreach ($l in @((Join-Path ([Environment]::GetFolderPath('Programs')) 'Arasaka Relic.lnk'),
                 (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Arasaka Relic.lnk'))) {
    if (Test-Path $l) { Remove-Item -Force $l }
}
Unregister-ScheduledTask -TaskName 'Arasaka Relic' -Confirm:$false -ErrorAction SilentlyContinue

$up = [Environment]::GetEnvironmentVariable('Path', 'User')
[Environment]::SetEnvironmentVariable('Path', (($up -split ';' | Where-Object { $_ -and $_ -ne $Bin }) -join ';'), 'User')
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Data
Write-Host " ■ ARASAKA RELIC REMOVIDO (os seus dados foram mantidos)" -ForegroundColor Red

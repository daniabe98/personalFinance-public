#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$WheelPath,

    [Parameter(Mandatory = $true)]
    [string]$ServerIp,

    [Parameter(Mandatory = $true)]
    [switch]$StablePrivateIPv4Confirmed,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$BootstrapUsername,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$SpaceName,

    [ValidateSet(8080)]
    [int]$Port = 8080,

    [ValidateRange(1, 365)]
    [int]$BackupRetention = 7,

    [ValidateNotNullOrEmpty()]
    [string]$DomesticTimezone = "Europe/Madrid",

    [string]$InstallRoot = (Join-Path $env:ProgramFiles "PersonalFinance"),
    [string]$DataRoot = (Join-Path $env:ProgramData "PersonalFinance")
)

$ErrorActionPreference = "Stop"
$firewallName = "Personal Finance LAN"

function Test-PrivateIPv4 {
    param([Parameter(Mandatory = $true)][string]$Address)

    $parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$parsed)) {
        return $false
    }
    if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        return $false
    }
    $bytes = $parsed.GetAddressBytes()
    return (
        $bytes[0] -eq 10 -or
        ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
        ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
    )
}

if (-not (Test-PrivateIPv4 -Address $ServerIp)) {
    throw "ServerIp must be a private IPv4 address (10/8, 172.16/12 or 192.168/16)."
}
if (-not $StablePrivateIPv4Confirmed) {
    throw "Confirm that the private IPv4 is static or reserved by DHCP."
}
if ($null -eq (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from the official Astral distribution first."
}

$WheelPath = (Resolve-Path -LiteralPath $WheelPath).Path
$configRoot = Join-Path $DataRoot "config"
$dataDirectory = Join-Path $DataRoot "data"
$backupDirectory = Join-Path $DataRoot "backups"
$logDirectory = Join-Path $DataRoot "logs"
$venv = Join-Path $InstallRoot "venv"
$pythonInstallRoot = Join-Path $InstallRoot "python"
$databasePath = (Join-Path $dataDirectory "personal-finance.db").Replace("\", "/")
$configPath = Join-Path $configRoot "appsettings.json"

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $DataRoot)) {
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
}

# Use well-known SIDs so the ACL is independent of the Windows display language.
& icacls.exe $DataRoot /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-19:(OI)(CI)M" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not apply the protected data ACL." }

foreach ($directory in @($configRoot, $dataDirectory, $backupDirectory, $logDirectory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

# Stop the scheduled actions and any exact runtime child before replacing the venv.
foreach ($taskName in @("PersonalFinance-App", "PersonalFinance-Backup")) {
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask -and $existingTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $taskName
    }
}
$taskStopDeadline = (Get-Date).AddSeconds(15)
do {
    $runningTasks = @(
        Get-ScheduledTask -TaskName "PersonalFinance-App", "PersonalFinance-Backup" -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq "Running" }
    )
    if ($runningTasks.Count -eq 0) { break }
    Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $taskStopDeadline)
if ($runningTasks.Count -ne 0) {
    throw "Scheduled Personal Finance tasks did not stop before the runtime update."
}

$runtimePrefix = $venv.TrimEnd("\") + "\"
$runtimeProcesses = @(
    Get-CimInstance Win32_Process | Where-Object {
        $null -ne $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)
    }
)
foreach ($runtimeProcess in $runtimeProcesses) {
    Invoke-CimMethod -InputObject $runtimeProcess -MethodName Terminate | Out-Null
}
Start-Sleep -Milliseconds 500

$env:UV_PYTHON_INSTALL_DIR = $pythonInstallRoot
uv python install 3.13 --install-dir $pythonInstallRoot --no-bin --no-registry
if ($LASTEXITCODE -ne 0) { throw "uv could not install Python 3.13." }
$previousVirtualEnv = $env:VIRTUAL_ENV
$previousCondaPrefix = $env:CONDA_PREFIX
$previousProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    [Environment]::SetEnvironmentVariable("VIRTUAL_ENV", $null, "Process")
    [Environment]::SetEnvironmentVariable("CONDA_PREFIX", $null, "Process")
    [Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $null, "Process")
    $managedPythonOutput = & uv python find --managed-python --no-project 3.13
    $uvFindExitCode = $LASTEXITCODE
    $managedPython = $managedPythonOutput | Select-Object -First 1
} finally {
    [Environment]::SetEnvironmentVariable("VIRTUAL_ENV", $previousVirtualEnv, "Process")
    [Environment]::SetEnvironmentVariable("CONDA_PREFIX", $previousCondaPrefix, "Process")
    [Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $previousProjectEnvironment, "Process")
}
if ($uvFindExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($managedPython)) {
    throw "uv could not resolve the application-owned Python 3.13 runtime."
}
$managedPython = $managedPython.Trim()
if (-not $managedPython.StartsWith($pythonInstallRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "uv resolved Python outside the protected application directory."
}
uv venv --clear --python $managedPython $venv
if ($LASTEXITCODE -ne 0) { throw "uv could not create the managed environment." }
$python = Join-Path $venv "Scripts\python.exe"
uv pip install --link-mode copy --python $python $WheelPath
if ($LASTEXITCODE -ne 0) { throw "The wheel could not be installed." }

foreach ($script in Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.ps1") {
    Copy-Item -LiteralPath $script.FullName -Destination $InstallRoot -Force
}

# LOCAL SERVICE executes the runtime but cannot modify application files.
& icacls.exe $InstallRoot /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-19:(OI)(CI)RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not apply the protected application ACL." }

$secretBytes = New-Object byte[] 48
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $generator.GetBytes($secretBytes)
} finally {
    $generator.Dispose()
}
$secret = [Convert]::ToBase64String($secretBytes)
$configuration = [ordered]@{
    PF_ALLOWED_ORIGIN = "http://${ServerIp}:${Port}"
    PF_BACKUP_DIRECTORY = $backupDirectory
    PF_BACKUP_RETENTION = [string]$BackupRetention
    PF_DATABASE_URL = "sqlite:///$databasePath"
    PF_DOMESTIC_TIMEZONE = $DomesticTimezone
    PF_SECRET_KEY = $secret
    PF_TRANSPORT_MODE = "http_lan"
}
$configuration | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8

foreach ($property in $configuration.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($property.Key, [string]$property.Value, "Process")
}
& "$venv\Scripts\personal-finance.exe" migrate
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
$ErrorActionPreference = "Continue"
& "$venv\Scripts\personal-finance.exe" bootstrap --username $BootstrapUsername --space-name $SpaceName
$bootstrapExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if (@(0, 2) -notcontains $bootstrapExitCode) { throw "Identity bootstrap failed." }

$powerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$principal = New-ScheduledTaskPrincipal -UserId "S-1-5-19" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365) -MultipleInstances IgnoreNew
$appArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$InstallRoot\Start-PersonalFinance.ps1`""
$backupArguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$InstallRoot\Backup-PersonalFinance.ps1`""
$appAction = New-ScheduledTaskAction -Execute $powerShell -Argument $appArguments
$backupAction = New-ScheduledTaskAction -Execute $powerShell -Argument $backupArguments
$appTrigger = New-ScheduledTaskTrigger -AtStartup
$backupTrigger = New-ScheduledTaskTrigger -Daily -At "03:00"

Register-ScheduledTask -TaskName "PersonalFinance-App" -Action $appAction -Trigger $appTrigger -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName "PersonalFinance-Backup" -Action $backupAction -Trigger $backupTrigger -Principal $principal -Settings $settings -Force | Out-Null

Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $firewallName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private -RemoteAddress LocalSubnet | Out-Null

Start-ScheduledTask -TaskName "PersonalFinance-Backup"
Start-ScheduledTask -TaskName "PersonalFinance-App"
Write-Host "Personal Finance installed. Data and backups are under $DataRoot."

[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:ProgramFiles "PersonalFinance"),
    [string]$DataRoot = (Join-Path $env:ProgramData "PersonalFinance")
)

$ErrorActionPreference = "Stop"
$configPath = Join-Path $DataRoot "config\appsettings.json"
$logPath = Join-Path $DataRoot "logs\backup.log"
$allowedKeys = @(
    "PF_ALLOWED_ORIGIN",
    "PF_BACKUP_DIRECTORY",
    "PF_BACKUP_RETENTION",
    "PF_DATABASE_URL",
    "PF_DOMESTIC_TIMEZONE",
    "PF_SECRET_KEY",
    "PF_TRANSPORT_MODE"
)

$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
foreach ($property in $config.PSObject.Properties) {
    if ($allowedKeys -notcontains $property.Name) {
        throw "Unsupported configuration key: $($property.Name)"
    }
    [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, "Process")
}
foreach ($key in $allowedKeys) {
    if ($null -eq $config.PSObject.Properties[$key]) {
        throw "Missing required configuration key: $key"
    }
}

$ErrorActionPreference = "Continue"
& "$InstallRoot\venv\Scripts\personal-finance.exe" backup --if-due *>> $logPath
$backupExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if (@(0, 5) -contains $backupExitCode) {
    return
}
throw "Daily backup failed with exit code $backupExitCode. Review the backup log."

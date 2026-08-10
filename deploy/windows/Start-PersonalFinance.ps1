[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:ProgramFiles "PersonalFinance"),
    [string]$DataRoot = (Join-Path $env:ProgramData "PersonalFinance"),
    [ValidateRange(1, 65535)]
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$configPath = Join-Path $DataRoot "config\appsettings.json"
$logPath = Join-Path $DataRoot "logs\application.log"
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
& "$InstallRoot\venv\Scripts\personal-finance.exe" migrate *>> $logPath
$migrationExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($migrationExitCode -ne 0) {
    throw "Database migration failed. Review the application log."
}

$ErrorActionPreference = "Continue"
& "$InstallRoot\venv\Scripts\personal-finance.exe" backup --if-due *>> $logPath
$backupExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if (@(0, 5) -contains $backupExitCode) {
    "Daily backup state verified." | Add-Content -LiteralPath $logPath
} else {
    throw "Backup catch-up failed. Review the application log."
}

$ErrorActionPreference = "Continue"
& "$InstallRoot\venv\Scripts\uvicorn.exe" app.main:create_app --factory --host 0.0.0.0 --port $Port *>> $logPath
exit $LASTEXITCODE

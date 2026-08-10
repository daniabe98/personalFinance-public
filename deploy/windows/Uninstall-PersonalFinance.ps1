#Requires -RunAsAdministrator
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [string]$InstallRoot = (Join-Path $env:ProgramFiles "PersonalFinance"),
    [string]$DataRoot = (Join-Path $env:ProgramData "PersonalFinance")
)

$ErrorActionPreference = "Stop"
foreach ($taskName in @("PersonalFinance-App", "PersonalFinance-Backup")) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($taskName, "Stop and unregister scheduled task")) {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }
    }
}

if (Get-NetFirewallRule -DisplayName "Personal Finance LAN" -ErrorAction SilentlyContinue) {
    if ($PSCmdlet.ShouldProcess("Personal Finance LAN", "Remove firewall rule")) {
        Remove-NetFirewallRule -DisplayName "Personal Finance LAN"
    }
}

if (Test-Path -LiteralPath $InstallRoot) {
    if ($PSCmdlet.ShouldProcess($InstallRoot, "Remove application runtime")) {
        Remove-Item -LiteralPath $InstallRoot -Recurse -Force
    }
}

Write-Host "Application runtime removed. Data, configuration, logs and backups are preserved at $DataRoot."

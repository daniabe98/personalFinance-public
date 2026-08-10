#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ServerIp,
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [string]$InstallRoot = (Join-Path $env:ProgramFiles "PersonalFinance"),
    [string]$DataRoot = (Join-Path $env:ProgramData "PersonalFinance")
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]

foreach ($taskName in @("PersonalFinance-App", "PersonalFinance-Backup")) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -eq $task -or $task.State -eq "Disabled") {
        $failures.Add("Scheduled task is absent or disabled: $taskName")
    }
}

$appTask = Get-ScheduledTask -TaskName "PersonalFinance-App" -ErrorAction SilentlyContinue
$backupTask = Get-ScheduledTask -TaskName "PersonalFinance-Backup" -ErrorAction SilentlyContinue
$firewall = Get-NetFirewallRule -DisplayName "Personal Finance LAN" -ErrorAction SilentlyContinue
if ($null -eq $firewall -or $firewall.Profile -notmatch "Private") {
    $failures.Add("The private-profile firewall rule is absent.")
} else {
    $portFilter = $firewall | Get-NetFirewallPortFilter
    $addressFilter = $firewall | Get-NetFirewallAddressFilter
    if ($portFilter.Protocol -ne "TCP" -or [int]$portFilter.LocalPort -ne $Port) {
        $failures.Add("The firewall port or protocol is incorrect.")
    }
    if ($addressFilter.RemoteAddress -notcontains "LocalSubnet") {
        $failures.Add("The firewall rule is not limited to LocalSubnet.")
    }
}

$acl = Get-Acl -LiteralPath $DataRoot
$aclSids = @(
    $acl.Access | ForEach-Object {
        try {
            $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        } catch {
            $_.IdentityReference.Value
        }
    }
)
foreach ($identitySid in @("S-1-5-18", "S-1-5-32-544", "S-1-5-19")) {
    if ($aclSids -notcontains $identitySid) {
        $failures.Add("Missing protected data ACL entry: $identitySid")
    }
}

try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri "http://${ServerIp}:${Port}/health/ready" -TimeoutSec 10
    if ($health.StatusCode -ne 200) {
        $failures.Add("Readiness did not return HTTP 200.")
    }
} catch {
    $failures.Add("Readiness request failed.")
}

try {
    & "$InstallRoot\Backup-PersonalFinance.ps1"
} catch {
    $failures.Add("Backup catch-up failed.")
}

if ($null -eq $appTask -or $null -eq $backupTask) {
    $failures.Add("Task inspection did not complete.")
}
if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "Personal Finance Windows diagnostics passed."

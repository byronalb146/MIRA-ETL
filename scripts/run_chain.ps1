param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d{6}$")]
    [string]$GuatemalaPeriod,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d{6}$")]
    [string]$CostaRicaPeriod,

    [ValidateRange(1, [int]::MaxValue)]
    [Nullable[int]]$Limit
)

$ErrorActionPreference = "Stop"
$CurrentPeriod = Get-Date -Format "yyyyMM"
$LimitArguments = @{}
if ($null -ne $Limit) { $LimitArguments["Limit"] = $Limit }

& "$PSScriptRoot\install.ps1"
& "$PSScriptRoot\run_tests.ps1"
& "$PSScriptRoot\init_db.ps1"
& "$PSScriptRoot\run_etl.ps1" -Source guatemala_guatecompras -Period $GuatemalaPeriod @LimitArguments
& "$PSScriptRoot\run_etl.ps1" -Source costa_rica_sicop -Period $CostaRicaPeriod @LimitArguments
& "$PSScriptRoot\run_etl.ps1" -Source nicaragua_siscae -Period $CurrentPeriod @LimitArguments

Write-Host "Installation, tests, database initialization and all three ETLs completed."

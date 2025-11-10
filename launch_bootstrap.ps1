# ----------------------------------------
# Launcher for bootstrap.ps1 with permission handling
# ----------------------------------------

# Check current execution policy
$currentPolicy = Get-ExecutionPolicy -Scope Process

if ($currentPolicy -eq "Restricted") {
    Write-Host "Execution policy is Restricted. Temporarily allowing script execution..."
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
}

# Run the actual bootstrap script
& "$PSScriptRoot\bootstrap.ps1"

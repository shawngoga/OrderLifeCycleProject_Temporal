# ----------------------------------------
# Setup script for OrderLifecycleProject_Temporal
# Run this from an Administrator PowerShell session
# ----------------------------------------

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

# Check for Chocolatey
$chocoPath = "C:\ProgramData\chocolatey\bin\choco.exe"
if (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "Chocolatey is available in PATH."
} elseif (Test-Path $chocoPath) {
    Write-Host "Chocolatey found but not in PATH. Adding temporarily..."
    $env:Path += ";C:\ProgramData\chocolatey\bin"
} else {
    Write-Host "Installing Chocolatey..."
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    try {
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        $env:Path += ";C:\ProgramData\chocolatey\bin"
    } catch {
        Write-Host "Chocolatey installation failed. Check your internet connection or permissions."
        exit 1
    }
}

# Check for make
$makePath = "$env:ChocolateyInstall\bin"
if (Get-Command make -ErrorAction SilentlyContinue) {
    Write-Host "make is available in PATH."
} elseif (Test-Path "$makePath\make.exe") {
    Write-Host "make found but not in PATH. Adding temporarily..."
    $env:Path += ";$makePath"
} else {
    Write-Host "Installing make..."
    try {
        choco install make -y
    } catch {
        Write-Host "make installation failed. Check Chocolatey setup or permissions."
        exit 1
    }
}

# Add make to system PATH if missing
$systemPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
if (-not ($systemPath -split ";" | Where-Object { $_ -eq $makePath })) {
    Write-Host "Adding make to system PATH permanently..."
    $newPath = "$systemPath;$makePath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "PATH updated. Restart PowerShell to apply changes."
} else {
    Write-Host "make already in system PATH."
}

# Create virtual environment
if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists."
} else {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

# Install dependencies
if (Test-Path "requirements.txt") {
    Write-Host "Installing Python dependencies..."
    pip install -r requirements.txt
} else {
    Write-Host "requirements.txt not found. Please create it before running this script."
    exit 1
}

# ----------------------------------------
# Temporal CLI Setup
# ----------------------------------------

$temporalInstallDir = "$env:USERPROFILE\.temporal"
$temporalExe = "$temporalInstallDir\temporal.exe"

if (Get-Command temporal -ErrorAction SilentlyContinue) {
    Write-Host "Temporal CLI is available in PATH."
} elseif (Test-Path $temporalExe) {
    Write-Host "Temporal CLI found at $temporalExe. Adding to PATH temporarily..."
    $env:Path += ";$temporalInstallDir"
} else {
    Write-Host "Temporal CLI not found. Downloading to $temporalInstallDir..."
    try {
        New-Item -ItemType Directory -Force -Path $temporalInstallDir | Out-Null
        Invoke-WebRequest -Uri "https://github.com/temporalio/cli/releases/latest/download/temporal_windows_amd64.exe" `
                          -OutFile $temporalExe
        if (Test-Path $temporalExe) {
            Write-Host "Temporal CLI downloaded successfully."
            $env:Path += ";$temporalInstallDir"
        } else {
            Write-Host "Download completed but executable not found. Please verify manually."
            exit 1
        }
    } catch {
        Write-Host "Failed to download Temporal CLI. Check your internet connection or permissions."
        exit 1
    }
}

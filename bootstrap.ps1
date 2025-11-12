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
# Temporal CLI Setup (fixed for ZIP asset)
# ----------------------------------------

$temporalInstallDir = "$env:USERPROFILE\.temporal"
$temporalExe        = Join-Path $temporalInstallDir "temporal.exe"
$temporalZip        = Join-Path $temporalInstallDir "temporal_windows_amd64.zip"
$downloadUri        = "https://github.com/temporalio/cli/releases/latest/download/temporal_windows_amd64.zip"

function Test-ExeHeader([string]$path) {
    if (-not (Test-Path $path)) { return $false }
    try {
        $fs = [System.IO.File]::OpenRead($path)
        try {
            $b0 = $fs.ReadByte(); $b1 = $fs.ReadByte()
            return ($b0 -eq 0x4D -and $b1 -eq 0x5A) # "MZ"
        } finally { $fs.Dispose() }
    } catch { return $false }
}

# If temporal.exe already valid, just use it
if (Test-ExeHeader $temporalExe) {
    Write-Host "Temporal CLI already present at $temporalExe"
    if ($env:Path -notmatch [regex]::Escape($temporalInstallDir)) {
        $env:Path += ";$temporalInstallDir"
    }
}
else {
    Write-Host "Temporal CLI not found or invalid. Installing to $temporalInstallDir ..."

    # Ensure folder exists and clean any bad leftovers
    New-Item -ItemType Directory -Force -Path $temporalInstallDir | Out-Null
    if (Test-Path $temporalExe) { Remove-Item $temporalExe -Force -ErrorAction SilentlyContinue }
    if (Test-Path $temporalZip) { Remove-Item $temporalZip -Force -ErrorAction SilentlyContinue }

    # Harden TLS just in case
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072

    try {
        Write-Host "Downloading: $downloadUri"
        Invoke-WebRequest -Uri $downloadUri -OutFile $temporalZip -UseBasicParsing -ErrorAction Stop

        if (-not (Test-Path $temporalZip)) {
            Write-Host "Download failed: $temporalZip not found."
            exit 1
        }

        Write-Host "Extracting to $temporalInstallDir ..."
        Expand-Archive -Path $temporalZip -DestinationPath $temporalInstallDir -Force

        # Some zips extract into a subfolder; try to locate the exe
        if (-not (Test-Path $temporalExe)) {
            $found = Get-ChildItem $temporalInstallDir -Recurse -Filter "temporal.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                Move-Item -Force $found.FullName $temporalExe
            }
        }

        # Cleanup zip
        Remove-Item $temporalZip -Force -ErrorAction SilentlyContinue

        if (-not (Test-ExeHeader $temporalExe)) {
            Write-Host "Install failed: temporal.exe missing or invalid after extraction."
            exit 1
        }

        Write-Host "Temporal CLI installed successfully at $temporalExe"
        if ($env:Path -notmatch [regex]::Escape($temporalInstallDir)) {
            $env:Path += ";$temporalInstallDir"
        }
    }
    catch {
        Write-Host "Failed to install Temporal CLI: $($_.Exception.Message)"
        exit 1
    }
}

# Optional: quick version check
try {
    & $temporalExe --version
} catch {
    Write-Host "Temporal CLI present but not runnable: $($_.Exception.Message)"
    exit 1
}
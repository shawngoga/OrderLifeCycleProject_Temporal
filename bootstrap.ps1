# ----------------------------------------
# Bootstrap: cross-machine Windows setup
# ----------------------------------------
# Safe to run multiple times. Designed for Admin PowerShell.
# Installs: Chocolatey (if missing), Python, make, Temporal CLI (or Docker fallback)
# Sets up .venv and installs requirements.txt
# ----------------------------------------

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'     # cleaner output
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13

# 0) Helpers
function Write-Step($msg){ Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function In-Path([string]$p){ (($env:Path -split ';') -contains $p) }
function Ensure-Path([string]$p){ if (-not (In-Path $p)) { $env:Path = "$env:Path;$p" } }
function Test-ExeHeader([string]$path){
  if (-not (Test-Path $path)) { return $false }
  try {
    $fs=[System.IO.File]::OpenRead($path); try {
      $b0=$fs.ReadByte(); $b1=$fs.ReadByte(); return ($b0 -eq 0x4D -and $b1 -eq 0x5A) # "MZ"
    } finally { $fs.Dispose() }
  } catch { return $false }
}
function Test-Admin(){
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
  Write-Host "⚠️  Please run this script in an **Administrator** PowerShell window." -ForegroundColor Yellow
  exit 1
}

# Allow script for this session only
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force | Out-Null

# 1) Chocolatey
Write-Step "Checking Chocolatey"
$chocoBin = "C:\ProgramData\chocolatey\bin"
$chocoExe = Join-Path $chocoBin "choco.exe"
if (Get-Command choco -ErrorAction SilentlyContinue) {
  Write-Host "Chocolatey is available in PATH."
} elseif (Test-Path $chocoExe) {
  Write-Host "Chocolatey exists but not in PATH. Adding for this session."
  Ensure-Path $chocoBin
} else {
  Write-Host "Installing Chocolatey..."
  try {
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    Ensure-Path $chocoBin
  } catch {
    Write-Host "❌ Chocolatey installation failed: $($_.Exception.Message)"
    throw
  }
}

# 2) Python (install if missing)
Write-Step "Checking Python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python not found. Installing via Chocolatey..."
  choco install python -y --no-progress
  $pyUser = "$env:LOCALAPPDATA\Programs\Python\Python*\"
  if (Test-Path $pyUser) {
    Get-ChildItem $pyUser -Directory | Sort-Object Name -Descending | Select-Object -First 1 | ForEach-Object {
      Ensure-Path $_.FullName
      Ensure-Path (Join-Path $_.FullName "Scripts")
    }
  }
} else {
  Write-Host "Python found: $(python --version)"
}

# 3) Make (install if missing)
Write-Step "Checking make"
if (-not (Get-Command make -ErrorAction SilentlyContinue)) {
  Write-Host "Installing make via Chocolatey..."
  choco install make -y --no-progress
  Ensure-Path "$env:ChocolateyInstall\bin"
} else {
  Write-Host "make found."
}

# 4) Project virtual environment
Write-Step "Setting up Python virtual env (.venv)"
if (-not (Test-Path ".venv")) {
  Write-Host "Creating .venv..."
  python -m venv .venv
} else {
  Write-Host ".venv already exists."
}

Write-Host "Activating .venv..."
& .\.venv\Scripts\Activate.ps1

# Upgrade pip (won't break lockfiles)
try { python -m pip install --upgrade pip wheel setuptools --quiet } catch { }

# 5) Python dependencies
Write-Step "Installing requirements"
if (Test-Path "requirements.txt") {
  pip install -r requirements.txt
} else {
  Write-Host "requirements.txt not found. Skipping Python deps." -ForegroundColor Yellow
}

# 6) Temporal CLI (preferred) with Docker fallback
Write-Step "Configuring Temporal (CLI preferred, Docker as fallback)"

$temporalDir = Join-Path $env:USERPROFILE ".temporal"
$temporalExe = Join-Path $temporalDir "temporal.exe"
$temporalZip = Join-Path $temporalDir "temporal_windows.zip"

# arch detect
$arch = if ($env:PROCESSOR_ARCHITECTURE -match 'ARM64') { 'arm64' } else { 'amd64' }
$cdn  = "https://temporal.download/cli/archive/latest?platform=windows&arch=$arch"

$cliReady = $false
try {
  if (Test-ExeHeader $temporalExe) {
    Write-Host "Temporal CLI already present at $temporalExe"
    Ensure-Path $temporalDir
    $cliReady = $true
  } else {
    Write-Host "Installing Temporal CLI to $temporalDir ..."
    New-Item -ItemType Directory -Force -Path $temporalDir | Out-Null
    Remove-Item $temporalZip -Force -ErrorAction SilentlyContinue
    Remove-Item $temporalExe -Force -ErrorAction SilentlyContinue

    $headers = @{ "User-Agent" = "PowerShellInvokeWebRequest" }
    Invoke-WebRequest -Uri $cdn -OutFile $temporalZip -Headers $headers -MaximumRedirection 10 -UseBasicParsing

    if (-not (Test-Path $temporalZip)) { throw "Download failed: $temporalZip not found." }

    Expand-Archive -Path $temporalZip -DestinationPath $temporalDir -Force

    # locate exe (zip may include a subfolder)
    $found = Get-ChildItem $temporalDir -Recurse -Filter "temporal.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found -and ($found.FullName -ne $temporalExe)) { Move-Item -Force $found.FullName $temporalExe }

    Remove-Item $temporalZip -Force -ErrorAction SilentlyContinue

    if (-not (Test-ExeHeader $temporalExe)) { throw "Temporal CLI missing or invalid after extraction." }

    Ensure-Path $temporalDir
    $cliReady = $true
  }
} catch {
  Write-Host "⚠️  Temporal CLI install failed: $($_.Exception.Message)" -ForegroundColor Yellow
  $cliReady = $false
}

# 7) Start Temporal (CLI or Docker)
$usingDocker = $false
if ($cliReady) {
  Write-Host "Starting Temporal dev server via CLI ..."
  try {
    # Start in background (dev server: UI 8233, gRPC 7233)
    Start-Process -FilePath $temporalExe -ArgumentList "server start-dev" -WindowStyle Hidden
    $env:TEMPORAL_ADDRESS = "localhost:7233"
  } catch {
    Write-Host "⚠️  Failed to start Temporal via CLI: $($_.Exception.Message)" -ForegroundColor Yellow
    $cliReady = $false
  }
}

if (-not $cliReady) {
  # Docker fallback
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Falling back to Docker: temporalio/auto-setup ..."
    try {
      docker rm -f temporal-dev 2>$null | Out-Null
      docker run -d --name temporal-dev -p 7233:7233 -p 8233:8233 temporalio/auto-setup:latest | Out-Null
      $env:TEMPORAL_ADDRESS = "localhost:7233"
      $usingDocker = $true
    } catch {
      Write-Host "❌ Docker fallback failed: $($_.Exception.Message)"
      Write-Host "Please ensure Docker Desktop is installed and running, or fix network access for CLI download." -ForegroundColor Yellow
      throw
    }
  } else {
    Write-Host "❌ Neither Temporal CLI installed nor Docker available. Please install Docker Desktop or allow CLI download."
    throw "Temporal dev environment not available."
  }
}

# 8) Smoke test (optional but helpful)
Write-Step "Temporal readiness check"
try {
  if ($cliReady) {
    & $temporalExe --version | Write-Host
  }
  # Quick port wait loop
  $deadline = (Get-Date).AddSeconds(25)
  $ready = $false
  while ((Get-Date) -lt $deadline -and -not $ready) {
    try {
      $client = New-Object System.Net.Sockets.TcpClient
      $iar = $client.BeginConnect('127.0.0.1', 7233, $null, $null)
      $ok = $iar.AsyncWaitHandle.WaitOne(2000, $false)
      if ($ok -and $client.Connected){ $ready=$true }
      $client.Close()
    } catch { Start-Sleep -Milliseconds 500 }
    if (-not $ready) { Start-Sleep -Milliseconds 500 }
  }
  if ($ready) { Write-Host "✅ Temporal listening on 7233. UI on http://localhost:8233 (if CLI or Docker UI enabled)." -ForegroundColor Green }
  else { Write-Host "⚠️ Temporal did not confirm by port check, but may still be starting. Continue if your app connects." -ForegroundColor Yellow }
} catch {
  Write-Host "⚠️ Temporal readiness check skipped: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Step "Done"
Write-Host "TEMPORAL_ADDRESS=$env:TEMPORAL_ADDRESS"
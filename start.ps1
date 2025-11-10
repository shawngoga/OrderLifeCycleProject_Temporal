# ----------------------------------------
# Start script for OrderLifecycleProject_Temporal
# Activates environment and launches FastAPI app
# ----------------------------------------

# Move to project root
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)

# Activate virtual environment
if (-Not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "Virtual environment not found. Run bootstrap.ps1 first."
    exit 1
}

Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

# Launch FastAPI app
Write-Host "Starting FastAPI app with uvicorn..."
uvicorn app.main:app --reload

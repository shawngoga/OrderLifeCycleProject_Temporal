# OrderLifecycleProject_Temporal

This project implements a reproducible, event-driven order lifecycle system using Temporal workflows, FastAPI, and SQLAlchemy. It is designed for local development on Windows using PowerShell and Python, with strict boundaries, audit-friendly logging, and manual environment setup (no Docker).

## Setup

### 1. Enable PowerShell Script Execution

Before running any setup scripts, you must allow PowerShell to execute local `.ps1` files. Open PowerShell as Administrator and run:

'Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser'

This enables script execution for your user account and is required to run `bootstrap.ps1`.

### 2. Run the Bootstrap Script

Once script execution is enabled, run the bootstrap script to install dependencies and set up the environment:

.\bootstrap.ps1

This will:

- Install Chocolatey and Make (if not already installed)
- Create and activate a Python virtual environment (`.venv`)
- Install all required Python packages from `requirements.txt`
- Download and configure the Temporal CLI (without starting the server)

## Requirements

The project uses the following core dependencies:

fastapi  
uvicorn  
sqlalchemy  
alembic  
psycopg2-binary  
temporalio  
httpx  
pytest  
pytest-asyncio  
python-dotenv

These are automatically installed via `bootstrap.ps1`.

## Running the Application

After setup, you can manually start the Temporal server and run the API:

### 1. Start Temporal Server

temporal server start-dev

This launches the Temporal dev server at:

- Temporal API: localhost:7233
- Temporal Web UI: http://localhost:8233

### 2. Run the FastAPI Server

uvicorn app.main:app --reload

### 3. Trigger Workers (manually via API or CLI)

Workers are not started by the bootstrap script. They are launched manually or triggered via API endpoints:

python app/core/worker_order.py  
python app/core/worker_shipping.py  
python app/core/worker_returns.py

## Testing

To verify Temporal connectivity:

pytest tests/test_temporal_connection.py

To run all tests:

pytest

## Project Structure

app/  
├── core/                 # Worker entrypoints  
├── workflows/            # Temporal workflow definitions  
├── activities/           # Activity implementations  
├── models.py             # SQLAlchemy models  
├── main.py               # FastAPI app  
tests/  
├── test_temporal_connection.py  
bootstrap.ps1            # Environment setup script  
launch_bootstrap.ps1     # Optional launcher with permission handling  
requirements.txt  
Makefile  
README.md

## Features

- Manual, reproducible setup with no Docker dependency  
- Temporal workflows for orders, shipping, and returns  
- Full event logging and auditability  
- API endpoints for workflow control and status queries  
- Strict separation of concerns and task queues  
- Unit and integration tests for all major components


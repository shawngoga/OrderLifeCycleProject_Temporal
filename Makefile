# ----------------------------------------
# Setup instructions (Windows):
# 1. Run from an Administrator PowerShell session.
# 2. Execute: .\bootstrap.ps1
#    This installs dependencies, sets up the virtual environment, and prepares the system.
# ----------------------------------------

.PHONY: init-db run-api run-worker test

init-db:
	python -m app.db.init_db


run-api:
	python app/main.py

run-worker:
	python app/core/worker.py

test:
	pytest tests/

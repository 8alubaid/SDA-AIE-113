.PHONY: install run-batch lint

# Override on Windows if needed:  make run-batch PYTHON=.venv/Scripts/python.exe
PYTHON ?= python

install:
	$(PYTHON) -m pip install -e ".[dev]"

run-batch:
	$(PYTHON) -m fraud_service.batch

lint:
	$(PYTHON) -m ruff check src

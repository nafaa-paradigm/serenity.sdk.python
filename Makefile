
PYTHON = python3

.PHONY = help setup test clean
.DEFAULT_GOAL = help

# basic virtual environment setup
venv:
	@echo "Setting up virtual environment..."
	rm -rf venv
	${PYTHON} -m venv venv
	. venv/bin/activate && pip install poetry bumpversion build twine cryptography==37.0.2 keyring keyrings.alt flake8 pytest
	. venv/bin/activate && poetry install

# static code analysis
lint: venv
	. venv/bin/activate && flake8 src tests

# Run unit tests
test: venv
	. venv/bin/activate && PYTHONPATH=src/python ${PYTHON} -m pytest

# publish to PyPi; requires an API token set in TWINE_PASSWORD
publish: lint test
	. venv/bin/activate && ${PYTHON} -m build
	. venv/bin/activate && ${PYTHON} -m twine upload -u __token__ dist/*

# Clear out build cruft
clean:
	rm -rf build dist venv

# Basic usage
help:
	@echo "---------------HELP-----------------"
	@echo "To setup the project type make setup"
	@echo "To test the project type make test"
	@echo "To publish the project type make publish"
	@echo "------------------------------------"


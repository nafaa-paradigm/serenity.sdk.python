
PYTHON = python3

.PHONY = help setup test clean
.DEFAULT_GOAL = help

# basic virtual environment setup
venv:
	@echo "Setting up virtual environment..."
	rm -rf venv
	${PYTHON} -m venv venv
	bash venv/bin/activate
	pip3 install poetry bumpversion build twine cryptography keyring keyrings.alt flake8 pytest
	poetry install

activate-venv:
	bash venv/bin/activate

# static code analysis
lint: activate-venv
	flake8 src tests

# Run unit tests
test: activate-venv
	${PYTHON} -m pytest

# publish to PyPi; requires an API token set in TWINE_PASSWORD
publish: venv lint test
	${PYTHON} -m build
	${PYTHON} -m twine upload -u __token__ dist/*

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



PYTHON = python3
SHELL := /bin/bash

.PHONY = help setup test clean
.DEFAULT_GOAL = help

# basic virtual environment setup
venv:
	@echo "Setting up virtual environment..."
	rm -rf venv
	python -m venv venv
	source venv/bin/activate
	pip install -U pip wheel build twine keyring keyrings.alt flake8 pytest
	pip install -e .

# static code analysis
lint:
	flake8 src tests

# Run unit tests
test: venv
	${PYTHON} -m pytest

# publish to PyPi; requires an API token set in TWINE_PASSWORD
install: venv lint test
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
	@echo "To publish the project type make install"
	@echo "------------------------------------"


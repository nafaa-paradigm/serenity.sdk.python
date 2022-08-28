#!/bin/bash

echo "Installing Poetry"
pip install poetry

echo "Installing dependencies"
poetry config "virtualenvs.in-project" true
poetry install

echo "Installing pre-commit hooks"
poetry run pre-commit install --hook-type pre-commit --hook-type pre-push
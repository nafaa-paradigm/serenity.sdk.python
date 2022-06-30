#!/bin/bash
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -U pip wheel build twine keyring keyrings.alt flake8
pip install -e .

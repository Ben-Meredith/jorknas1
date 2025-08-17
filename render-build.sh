#!/bin/bash
set -e

# Upgrade pip to latest
pip install --upgrade pip

# Install Python dependencies from requirements.txt
pip install --only-binary=:all: -r requirements.txt

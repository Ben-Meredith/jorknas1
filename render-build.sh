#!/bin/bash
set -e

# Upgrade pip
pip install --upgrade pip

# Install dependencies, forcing prebuilt wheels
pip install --only-binary=:all: -r requirements.txt

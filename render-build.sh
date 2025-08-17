#!/bin/bash
set -e

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

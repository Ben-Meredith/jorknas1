#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Update package lists
sudo apt-get update

# Install system dependencies required for Pillow (image processing)
sudo apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libtiff5-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk

# Install Python dependencies from requirements.txt
pip install --upgrade pip
pip install -r requirements.txt

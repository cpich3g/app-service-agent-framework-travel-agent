#!/bin/bash
# Startup script for Azure App Service

# Install dependencies if needed
pip install -r requirements.txt

# Run the application
python main.py

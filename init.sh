#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Check for .env.template
if [ ! -f .env.template ]; then
  echo ".env.template not found!"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.template .env
  echo ".env created at: $(readlink -f .env)"
else
  echo ".env already exists at: $(readlink -f .env)"
fi

# Install requirements
if [ -f requirements.txt ]; then
    echo "Installing requirements... ($(readlink -f requirements.txt))"
    pip install -r requirements.txt -q --no-color --disable-pip-version-check
    echo "Requirements installed."
fi

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

echo "Setup complete."
echo "---"
echo "An env file has been created at: $(readlink -f .env)"
echo "Remember to set your environment variables in the .env file."
echo "Once set, start the application with 'python src/main.py'"
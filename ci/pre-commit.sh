#!/usr/bin/env sh

# Check for syntax mistakes
# try to fix them

ROOTDIR="$(git rev-parse --show-toplevel)"

# Syntax check
echo "### RUFF ###"
ruff check --fix "$ROOTDIR"

# Format fix
echo "### RUFF FORMAT ###"
ruff format .

# Static typing check
echo -e "\n### MYPY ###"
mypy "$ROOTDIR"

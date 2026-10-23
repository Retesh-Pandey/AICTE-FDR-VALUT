#!/usr/bin/env bash
# AICTE Smart FDR Portal — Reset Demo Database
set -e

echo "=== Resetting AICTE FDR Demo Database ==="
cd "$(dirname "$0")/../backend"

if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
    ALEMBIC_BIN=".venv/bin/alembic"
elif [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
    ALEMBIC_BIN=".venv/Scripts/alembic.exe"
else
    PYTHON_BIN="python"
    ALEMBIC_BIN="alembic"
fi

echo "1. Applying database migrations to head..."
$ALEMBIC_BIN upgrade head

echo "2. Seeding clean demo dataset..."
$PYTHON_BIN -m app.db.seed

echo "=== Demo database successfully reset! ==="

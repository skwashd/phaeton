#!/usr/bin/env bash
set -euo pipefail

echo "=== Format check ==="
uv run ruff format --check src/ tests/

echo "=== Lint check ==="
uv run ruff check src/ tests/

echo "=== Type check ==="
uv run ty check

echo "=== Tests + coverage ==="
uv run coverage run -m pytest
uv run coverage report --show-missing --fail-under=90

echo "=== All checks passed ==="

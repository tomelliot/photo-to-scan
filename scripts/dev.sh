#!/usr/bin/env bash
# Run the dev server: Tailwind in watch mode alongside uvicorn --reload.
set -euo pipefail

cd "$(dirname "$0")/.."

scripts/build-css.sh --watch &
tailwind_pid=$!
trap 'kill "$tailwind_pid" 2>/dev/null' EXIT

uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

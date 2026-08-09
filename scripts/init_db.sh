#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -x .venv/bin/mira-etl ]]; then
    echo "Missing .venv. Run scripts/install.sh first." >&2
    exit 1
fi

.venv/bin/mira-etl init-db

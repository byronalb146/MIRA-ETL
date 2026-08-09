#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <source> <YYYYMM> [limit] [local_zip]" >&2
    echo "Sources: guatemala_guatecompras, costa_rica_sicop, nicaragua_siscae" >&2
}

if [[ $# -lt 2 || $# -gt 4 ]]; then
    usage
    exit 2
fi

source_name="$1"
period="$2"
limit="${3:-}"
local_zip="${4:-}"

case "$source_name" in
    guatemala_guatecompras|costa_rica_sicop|nicaragua_siscae) ;;
    *) usage; exit 2 ;;
esac

if [[ ! "$period" =~ ^[0-9]{6}$ ]]; then
    echo "Period must use YYYYMM format." >&2
    exit 2
fi
if [[ -n "$limit" && ! "$limit" =~ ^[1-9][0-9]*$ ]]; then
    echo "Limit must be a positive integer." >&2
    exit 2
fi
if [[ "$source_name" == "nicaragua_siscae" && -n "$local_zip" ]]; then
    echo "Nicaragua reads current HTML and does not accept a local ZIP." >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

command=(.venv/bin/mira-etl run --source "$source_name" --period "$period")
[[ -n "$limit" ]] && command+=(--limit "$limit")
[[ -n "$local_zip" ]] && command+=(--local-zip "$local_zip")
"${command[@]}"

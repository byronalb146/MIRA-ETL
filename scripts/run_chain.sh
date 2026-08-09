#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <guatemala_YYYYMM> <costa_rica_YYYYMM> [limit]" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage
    exit 2
fi

gt_period="$1"
cr_period="$2"
limit="${3:-}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! "$gt_period" =~ ^[0-9]{6}$ || ! "$cr_period" =~ ^[0-9]{6}$ ]]; then
    echo "Both periods must use YYYYMM format." >&2
    exit 2
fi
if [[ -n "$limit" && ! "$limit" =~ ^[1-9][0-9]*$ ]]; then
    echo "Limit must be a positive integer." >&2
    exit 2
fi

"$script_dir/install.sh"
"$script_dir/run_tests.sh"
"$script_dir/init_db.sh"
"$script_dir/run_etl.sh" guatemala_guatecompras "$gt_period" "$limit"
"$script_dir/run_etl.sh" costa_rica_sicop "$cr_period" "$limit"
"$script_dir/run_etl.sh" nicaragua_siscae "$limit"

echo "Installation, tests, database initialization and all three ETLs completed."

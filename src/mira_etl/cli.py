from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from mira_etl.config import SourceConfig
from mira_etl.db import Database
from mira_etl.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="mira-etl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run an ETL source for a period.")
    run.add_argument(
        "--source",
        required=True,
        help="Source configuration name.",
    )
    run.add_argument("--period", default=None, help="Period in AAAAMM format.")
    run.add_argument("--local-zip", type=Path, default=None)
    run.add_argument("--work-dir", type=Path, default=Path("data/work"))
    run.add_argument("--config-dir", type=Path, default=Path("config/sources"))
    run.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of records fetched/loaded (quick smoke tests against a real database).",
    )

    subparsers.add_parser("init-db", help="Create database schemas and tables.")

    args = parser.parse_args()

    if args.command == "init-db":
        with Database.from_env() as db:
            for sql_file in sorted(Path("sql").glob("*.sql")):
                db.execute_sql_file(sql_file)
            db.validate_schema()
        print("Database schema initialized and validated.")
        return

    if args.command == "run":
        period = resolve_period(
            source=args.source,
            period=args.period,
            config_dir=args.config_dir,
        )
        run_pipeline(
            source=args.source,
            period=period,
            config_dir=args.config_dir,
            work_dir=args.work_dir,
            local_zip=args.local_zip,
            limit=args.limit,
        )


def resolve_period(*, source: str, period: str | None, config_dir: Path) -> str:
    if period:
        return period

    config = SourceConfig.load(config_dir, source)
    if config.download.get("type") == "html_session_scrape":
        return datetime.now().strftime("%Y%m")

    raise SystemExit("--period is required for historical ZIP/JSON sources.")


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from mira_etl.config import SourceConfig
from mira_etl.csvio import read_csv_rows
from mira_etl.db import Database
from mira_etl.extract import extract_zip, obtain_zip, validate_required_files
from mira_etl.transform_cr import build_records
from mira_etl.validation import validate_records


def run_pipeline(
    *,
    source: str,
    period: str,
    config_dir: Path,
    work_dir: Path,
    local_zip: Path | None,
) -> None:
    config = SourceConfig.load(config_dir, source)
    connector_version = config.connector_version
    work_dir.mkdir(parents=True, exist_ok=True)

    with Database.from_env() as db:
        run_id = db.insert_run(source=source, period=period, connector_version=connector_version)
        try:
            zip_path = obtain_zip(config, period, work_dir, local_zip)
            extract_dir = extract_zip(zip_path, work_dir, source, period)
            validate_required_files(config, extract_dir)

            selected_files = config.files["required"] + config.files.get("optional", [])
            source_rows: dict[str, list[dict[str, str | None]]] = {}

            for filename in selected_files:
                csv_path = extract_dir / filename
                if not csv_path.exists():
                    continue

                delimiter = config.delimiter_for(filename)
                rows = list(read_csv_rows(csv_path, delimiter=delimiter, encoding=config.encoding))
                source_rows[filename] = rows

                source_file_id = db.insert_source_file(
                    run_id=run_id,
                    source=source,
                    period=period,
                    filename=filename,
                    file_hash=file_hash(csv_path),
                    row_count=len(rows),
                )
                db.insert_raw_rows(run_id=run_id, source_file_id=source_file_id, rows=rows)

            records = transform_source(
                config=config,
                period=period,
                connector_version=connector_version,
                source_rows=source_rows,
            )
            validation_results = validate_records(records)
            staged = db.insert_staging_candidates(run_id=run_id, source=source, period=period, records=records)
            db.execute(
                """
                insert into audit.etl_row_counts (run_id, layer_name, table_name, row_count)
                values (%s, 'staging', 'normalized_candidates', %s)
                """,
                (run_id, staged),
            )
            validations = db.insert_validation_results(
                run_id=run_id,
                source=source,
                period=period,
                results=validation_results,
            )
            db.execute(
                """
                insert into audit.etl_row_counts (run_id, layer_name, table_name, row_count)
                values (%s, 'audit', 'validation_results', %s)
                """,
                (run_id, validations),
            )
            inserted = db.upsert_mart_split_records(records)
            db.execute(
                """
                insert into audit.etl_row_counts (run_id, layer_name, table_name, row_count)
                values (%s, 'mart', 'procurement_record_core', %s)
                """,
                (run_id, inserted),
            )
            db.finish_run(run_id, "SUCCESS")
        except Exception as exc:
            db.finish_run(run_id, "ERROR", str(exc))
            raise


def transform_source(
    *,
    config: SourceConfig,
    period: str,
    connector_version: str,
    source_rows: dict[str, list[dict[str, str | None]]],
) -> list[dict[str, Any]]:
    if config.source == "costa_rica_sicop":
        return build_records(config=config, period=period, connector_version=connector_version, source_rows=source_rows)
    raise ValueError(f"Unsupported source: {config.source}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()

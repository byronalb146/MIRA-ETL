from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import ijson

from mira_etl.config import SourceConfig
from mira_etl.csvio import read_csv_rows
from mira_etl.db import Database
from mira_etl.extract import (
    extract_zip,
    obtain_zip,
    validate_required_files,
)
from mira_etl.transform_cr import build_records as build_cr_records
from mira_etl.transform_gt import build_record as build_gt_record
from mira_etl.validation import validate_records


# Limite temporal para las pruebas contra Supabase.
CONTRACT_LIMIT = 2


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
        run_id = db.insert_run(
            source=source,
            period=period,
            connector_version=connector_version,
        )

        try:
            zip_path = obtain_zip(
                config,
                period,
                work_dir,
                local_zip,
            )

            extract_dir = extract_zip(
                zip_path,
                work_dir,
                source,
                period,
            )

            if config.source == "costa_rica_sicop":
                records = process_costa_rica(
                    db=db,
                    run_id=run_id,
                    config=config,
                    period=period,
                    connector_version=connector_version,
                    extract_dir=extract_dir,
                )

            elif config.source == "guatemala_guatecompras":
                process_guatemala(
                    db=db,
                    run_id=run_id,
                    config=config,
                    period=period,
                    connector_version=connector_version,
                    extract_dir=extract_dir,
                )
                db.finish_run(run_id, "SUCCESS")
                return

            else:
                raise ValueError(
                    f"Unsupported source: {config.source}"
                )

            records = records[:CONTRACT_LIMIT]

            # Desde aquí el pipeline vuelve a ser común
            validation_results = validate_records(records)

            staged = db.insert_staging_candidates(
                run_id=run_id,
                source=source,
                period=period,
                records=records,
            )

            db.execute(
                """
                insert into audit.etl_row_counts
                    (run_id, layer_name, table_name, row_count)
                values
                    (%s, 'staging', 'normalized_candidates', %s)
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
                insert into audit.etl_row_counts
                    (run_id, layer_name, table_name, row_count)
                values
                    (%s, 'audit', 'validation_results', %s)
                """,
                (run_id, validations),
            )

            inserted = db.upsert_mart_split_records(records)

            db.execute(
                """
                insert into audit.etl_row_counts
                    (run_id, layer_name, table_name, row_count)
                values
                    (%s, 'mart', 'procurement_record_core', %s)
                """,
                (run_id, inserted),
            )

            db.finish_run(run_id, "SUCCESS")

        except BaseException as exc:
            error_message = str(exc) or type(exc).__name__
            db.finish_run_after_error(run_id, error_message)
            raise


def process_costa_rica(
    *,
    db: Database,
    run_id: int,
    config: SourceConfig,
    period: str,
    connector_version: str,
    extract_dir: Path,
) -> list[dict[str, Any]]:
    validate_required_files(config, extract_dir)

    selected_files = config.files["required"] + config.files.get(
        "optional",
        [],
    )
    source_rows: dict[str, list[dict[str, str | None]]] = {}

    for filename in selected_files:
        csv_path = extract_dir / filename
        if not csv_path.exists():
            continue

        delimiter = config.delimiter_for(filename)
        rows = list(
            read_csv_rows(
                csv_path,
                delimiter=delimiter,
                encoding=config.encoding,
            )
        )
        source_rows[filename] = rows
        raw_rows = rows[:CONTRACT_LIMIT]

        source_file_id = db.insert_source_file(
            run_id=run_id,
            source=config.source,
            period=period,
            filename=filename,
            file_hash=file_hash(csv_path),
            row_count=len(rows),
        )
        db.insert_raw_rows(
            run_id=run_id,
            source_file_id=source_file_id,
            rows=raw_rows,
        )

    return build_cr_records(
        config=config,
        period=period,
        connector_version=connector_version,
        source_rows=source_rows,
    )


def process_guatemala(
    *,
    db: Database,
    run_id: int,
    config: SourceConfig,
    period: str,
    connector_version: str,
    extract_dir: Path,
) -> None:
    json_path = find_json_file(extract_dir)
    print(
        f"JSON extracted: {json_path} "
        f"({json_path.stat().st_size:,} bytes)"
    )
    print("Hashing Guatemala JSON...")
    source_file_id = db.insert_source_file(
        run_id=run_id,
        source=config.source,
        period=period,
        filename=str(json_path.relative_to(extract_dir)),
        file_hash=file_hash(json_path),
        row_count=0,
    )
    batch_size = config.batch_size
    record_limit = config.record_limit
    raw_batch: list[dict[str, Any]] = []
    record_batch: list[dict[str, Any]] = []
    totals = {
        "raw": 0,
        "transformed": 0,
        "staging": 0,
        "validations": 0,
        "mart": 0,
    }

    print(
        "Processing Guatemala OCDS... "
        f"batch_size={batch_size}"
    )
    with json_path.open("rb") as fh:
        rows = ijson.items(fh, "records.item")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(
                    "Every Guatemala OCDS records item must be an object"
                )
            raw_batch.append(row)
            record_batch.append(
                build_gt_record(
                    config=config,
                    period=period,
                    connector_version=connector_version,
                    source_row=row,
                )
            )

            if len(raw_batch) >= batch_size:
                flush_guatemala_batch(
                    db=db,
                    run_id=run_id,
                    source_file_id=source_file_id,
                    source=config.source,
                    period=period,
                    raw_batch=raw_batch,
                    record_batch=record_batch,
                    batch_size=batch_size,
                    totals=totals,
                )

            if record_limit and totals["raw"] + len(raw_batch) >= record_limit:
                break

    if raw_batch:
        flush_guatemala_batch(
            db=db,
            run_id=run_id,
            source_file_id=source_file_id,
            source=config.source,
            period=period,
            raw_batch=raw_batch,
            record_batch=record_batch,
            batch_size=batch_size,
            totals=totals,
        )

    db.update_source_file_row_count(source_file_id, totals["raw"])
    insert_row_count(db, run_id, "raw", "source_rows", totals["raw"])
    insert_row_count(
        db,
        run_id,
        "staging",
        "normalized_candidates",
        totals["staging"],
    )
    insert_row_count(
        db,
        run_id,
        "audit",
        "validation_results",
        totals["validations"],
    )
    insert_row_count(
        db,
        run_id,
        "mart",
        "procurement_record_core",
        totals["mart"],
    )
    print(
        "Guatemala complete: "
        f"RAW={totals['raw']:,}, "
        f"STAGING={totals['staging']:,}, "
        f"MART={totals['mart']:,}"
    )


def flush_guatemala_batch(
    *,
    db: Database,
    run_id: int,
    source_file_id: int,
    source: str,
    period: str,
    raw_batch: list[dict[str, Any]],
    record_batch: list[dict[str, Any]],
    batch_size: int,
    totals: dict[str, int],
) -> None:
    batch_count = len(raw_batch)
    db.insert_raw_rows(
        run_id=run_id,
        source_file_id=source_file_id,
        rows=raw_batch,
        batch_size=batch_size,
        start_row_number=totals["raw"] + 1,
        progress_offset=totals["raw"],
    )
    totals["raw"] += batch_count
    totals["transformed"] += len(record_batch)
    print(f"Transformed: {totals['transformed']:,}")

    validation_results = validate_records(record_batch)
    staged = db.insert_staging_candidates(
        run_id=run_id,
        source=source,
        period=period,
        records=record_batch,
        batch_size=batch_size,
        progress_offset=totals["staging"],
    )
    totals["staging"] += staged
    totals["validations"] += db.insert_validation_results(
        run_id=run_id,
        source=source,
        period=period,
        results=validation_results,
        batch_size=batch_size,
    )
    inserted = db.upsert_mart_split_records(record_batch)
    totals["mart"] += inserted
    print(f"MART upserted: {totals['mart']:,}")
    raw_batch.clear()
    record_batch.clear()


def insert_row_count(
    db: Database,
    run_id: int,
    layer_name: str,
    table_name: str,
    row_count: int,
) -> None:
    db.execute(
        """
        insert into audit.etl_row_counts
            (run_id, layer_name, table_name, row_count)
        values (%s, %s, %s, %s)
        """,
        (run_id, layer_name, table_name, row_count),
    )


def find_json_file(extract_dir: Path) -> Path:
    json_files = sorted(extract_dir.rglob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON file found in {extract_dir}")
    if len(json_files) > 1:
        raise ValueError(
            f"Expected one JSON file, found {len(json_files)}"
        )
    return json_files[0]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()

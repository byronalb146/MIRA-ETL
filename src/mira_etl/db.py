from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from mira_etl.env import load_dotenv


class Database:
    def __init__(self, dsn: str) -> None:
        self.conn = psycopg.connect(ensure_sslmode(dsn), row_factory=dict_row, autocommit=True)

    @classmethod
    def from_env(cls) -> "Database":
        load_dotenv()
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            raise RuntimeError("SUPABASE_DB_URL is required.")
        return cls(dsn)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.conn.close()

    def execute_sql_file(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as fh:
            with self.conn.cursor() as cur:
                cur.execute(fh.read())

    def fetch_one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def insert_run(self, *, source: str, period: str, connector_version: str) -> int:
        row = self.fetch_one(
            """
            insert into audit.etl_runs (pipeline_name, source, period, connector_version, status)
            values (%s, %s, %s, %s, 'RUNNING')
            returning id
            """,
            (source, source, period, connector_version),
        )
        assert row is not None
        return int(row["id"])

    def finish_run(self, run_id: int, status: str, error_message: str | None = None) -> None:
        self.execute(
            """
            update audit.etl_runs
               set status = %s,
                   error_message = %s,
                   finished_at = now()
             where id = %s
            """,
            (status, error_message, run_id),
        )

    def insert_source_file(
        self,
        *,
        run_id: int,
        source: str,
        period: str,
        filename: str,
        file_hash: str,
        row_count: int,
    ) -> int:
        row = self.fetch_one(
            """
            insert into raw.source_files (run_id, source, period, filename, file_hash, row_count)
            values (%s, %s, %s, %s, %s, %s)
            returning source_file_id
            """,
            (run_id, source, period, filename, file_hash, row_count),
        )
        assert row is not None
        return int(row["source_file_id"])

    def insert_raw_rows(
        self,
        *,
        run_id: int,
        source_file_id: int,
        rows: Iterable[dict[str, Any]],
    ) -> None:
        records = [(run_id, source_file_id, index, json.dumps(row, ensure_ascii=False)) for index, row in enumerate(rows, 1)]
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                insert into raw.source_rows (run_id, source_file_id, row_number, payload)
                values (%s, %s, %s, %s::jsonb)
                """,
                records,
            )

    def insert_staging_candidates(
        self,
        *,
        run_id: int,
        source: str,
        period: str,
        records: Iterable[dict[str, Any]],
    ) -> int:
        rows = [
            (
                run_id,
                source,
                period,
                record["source_record_id"],
                record["raw_payload_hash"],
                json.dumps(record, ensure_ascii=False, default=str),
            )
            for record in records
        ]
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                insert into staging.normalized_candidates (
                    run_id, source, period, source_record_id, raw_payload_hash, payload
                )
                values (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                rows,
            )
        return len(rows)

    def upsert_mart_records(self, records: Iterable[dict[str, Any]]) -> int:
        sql = """
            insert into mart.procurement_records (
                process_id, process_number, title, description,
                buyer_name, buyer_id_source, buyer_tax_id,
                procurement_method, process_status, source_status,
                publication_date, closing_date, award_date,
                estimated_amount, awarded_amount, currency_code,
                supplier_name, supplier_id_source, supplier_tax_id, supplier_type,
                item_description, category_source, category_normalised,
                country_code, source_system, source_record_id, source_url,
                extracted_at, source_last_modified_at, connector_version,
                raw_payload, raw_payload_hash,
                normalisation_status, normalised_at, data_quality_status, missing_fields
            )
            values (
                %(process_id)s, %(process_number)s, %(title)s, %(description)s,
                %(buyer_name)s, %(buyer_id_source)s, %(buyer_tax_id)s,
                %(procurement_method)s, %(process_status)s, %(source_status)s,
                %(publication_date)s, %(closing_date)s, %(award_date)s,
                %(estimated_amount)s, %(awarded_amount)s, %(currency_code)s,
                %(supplier_name)s, %(supplier_id_source)s, %(supplier_tax_id)s, %(supplier_type)s,
                %(item_description)s, %(category_source)s, %(category_normalised)s,
                %(country_code)s, %(source_system)s, %(source_record_id)s, %(source_url)s,
                %(extracted_at)s, %(source_last_modified_at)s, %(connector_version)s,
                %(raw_payload)s::jsonb, %(raw_payload_hash)s,
                %(normalisation_status)s, %(normalised_at)s, %(data_quality_status)s, %(missing_fields)s::jsonb
            )
            on conflict (source_system, source_record_id, raw_payload_hash)
            do nothing
        """
        rows = []
        for record in records:
            payload = dict(record)
            payload["raw_payload"] = json.dumps(payload["raw_payload"], ensure_ascii=False)
            payload["missing_fields"] = json.dumps(payload["missing_fields"], ensure_ascii=False)
            rows.append(payload)

        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)
        return len(rows)


def ensure_sslmode(dsn: str) -> str:
    if "sslmode=" in dsn:
        return dsn
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}sslmode=require"

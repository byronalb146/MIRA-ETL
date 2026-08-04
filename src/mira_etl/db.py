from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from mira_etl.env import load_dotenv


CORE_SQL = """
    insert into mart.procurement_record_core (
        process_id, country_code, source_system, source_record_id, source_url,
        extracted_at, source_last_modified_at, connector_version,
        raw_payload, raw_payload_hash, normalisation_status, normalised_at,
        data_quality_status, missing_fields
    )
    values (
        %(process_id)s, %(country_code)s, %(source_system)s, %(source_record_id)s, %(source_url)s,
        %(extracted_at)s, %(source_last_modified_at)s, %(connector_version)s,
        %(raw_payload)s::jsonb, %(raw_payload_hash)s, %(normalisation_status)s, %(normalised_at)s,
        %(data_quality_status)s, %(missing_fields)s::jsonb
    )
    on conflict (process_id)
    do update set
        country_code = excluded.country_code,
        source_system = excluded.source_system,
        source_record_id = excluded.source_record_id,
        source_url = excluded.source_url,
        extracted_at = excluded.extracted_at,
        source_last_modified_at = excluded.source_last_modified_at,
        connector_version = excluded.connector_version,
        raw_payload = excluded.raw_payload,
        normalisation_status = excluded.normalisation_status,
        normalised_at = excluded.normalised_at,
        data_quality_status = excluded.data_quality_status,
        missing_fields = excluded.missing_fields
"""

PROCESS_DETAIL_SQL = """
    insert into mart.procurement_process_details (
        process_id, process_number, title, description, procurement_method,
        process_status, source_status, publication_date, closing_date,
        award_date, estimated_amount, awarded_amount, currency_code
    )
    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    on conflict (process_id) do update set
        process_number = excluded.process_number,
        title = excluded.title,
        description = excluded.description,
        procurement_method = excluded.procurement_method,
        process_status = excluded.process_status,
        source_status = excluded.source_status,
        publication_date = excluded.publication_date,
        closing_date = excluded.closing_date,
        award_date = excluded.award_date,
        estimated_amount = excluded.estimated_amount,
        awarded_amount = excluded.awarded_amount,
        currency_code = excluded.currency_code
"""

BUYER_DETAIL_SQL = """
    insert into mart.procurement_buyer_details (
        process_id, buyer_name, buyer_id_source, buyer_tax_id
    )
    values (%s, %s, %s, %s)
    on conflict (process_id) do update set
        buyer_name = excluded.buyer_name,
        buyer_id_source = excluded.buyer_id_source,
        buyer_tax_id = excluded.buyer_tax_id
"""

SUPPLIER_DETAIL_SQL = """
    insert into mart.procurement_supplier_details (
        process_id, supplier_name, supplier_id_source, supplier_tax_id, supplier_type
    )
    values (%s, %s, %s, %s, %s)
    on conflict (process_id) do update set
        supplier_name = excluded.supplier_name,
        supplier_id_source = excluded.supplier_id_source,
        supplier_tax_id = excluded.supplier_tax_id,
        supplier_type = excluded.supplier_type
"""

ITEM_DETAIL_SQL = """
    insert into mart.procurement_item_details (
        process_id, item_description, category_source, category_normalised
    )
    values (%s, %s, %s, %s)
    on conflict (process_id) do update set
        item_description = excluded.item_description,
        category_source = excluded.category_source,
        category_normalised = excluded.category_normalised
"""


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

    def insert_validation_results(
        self,
        *,
        run_id: int,
        source: str,
        period: str,
        results: Iterable[dict[str, Any]],
    ) -> int:
        rows = [
            (
                run_id,
                source,
                period,
                result.get("source_record_id"),
                result.get("raw_payload_hash"),
                result["rule_code"],
                result["severity"],
                result.get("field_name"),
                result.get("raw_value"),
                result.get("normalised_value"),
                result["message"],
                json.dumps(result.get("payload"), ensure_ascii=False, default=str),
            )
            for result in results
        ]
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                insert into audit.validation_results (
                    run_id, source, period, source_record_id, raw_payload_hash,
                    rule_code, severity, field_name, raw_value, normalised_value,
                    message, payload
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                rows,
            )
        return len(rows)

    def upsert_mart_split_records(self, records: Iterable[dict[str, Any]]) -> int:
        record_list = list(records)
        if not record_list:
            return 0

        self.upsert_record_core_batch(record_list)

        process_rows = []
        buyer_rows = []
        supplier_rows = []
        item_rows = []

        for record in record_list:
            process_id = record["process_id"]
            process_rows.append(
                (
                    process_id,
                    record.get("process_number"),
                    record.get("title"),
                    record.get("description"),
                    record.get("procurement_method"),
                    record.get("process_status"),
                    record.get("source_status"),
                    record.get("publication_date"),
                    record.get("closing_date"),
                    record.get("award_date"),
                    record.get("estimated_amount"),
                    record.get("awarded_amount"),
                    record.get("currency_code"),
                )
            )
            buyer_rows.append(
                (process_id, record.get("buyer_name"), record.get("buyer_id_source"), record.get("buyer_tax_id"))
            )
            supplier_rows.append(
                (
                    process_id,
                    record.get("supplier_name"),
                    record.get("supplier_id_source"),
                    record.get("supplier_tax_id"),
                    record.get("supplier_type"),
                )
            )
            item_rows.append(
                (
                    process_id,
                    record.get("item_description"),
                    record.get("category_source"),
                    record.get("category_normalised"),
                )
            )

        with self.conn.cursor() as cur:
            cur.executemany(PROCESS_DETAIL_SQL, process_rows)
            cur.executemany(BUYER_DETAIL_SQL, buyer_rows)
            cur.executemany(SUPPLIER_DETAIL_SQL, supplier_rows)
            cur.executemany(ITEM_DETAIL_SQL, item_rows)

        return len(record_list)

    def upsert_record_core_batch(self, records: list[dict[str, Any]]) -> None:
        rows = [
            {
                **record,
                "raw_payload": json.dumps(record["raw_payload"], ensure_ascii=False, default=str),
                "missing_fields": json.dumps(record["missing_fields"], ensure_ascii=False, default=str),
            }
            for record in records
        ]
        with self.conn.cursor() as cur:
            cur.executemany(CORE_SQL, rows)

def ensure_sslmode(dsn: str) -> str:
    if "sslmode=" in dsn:
        return dsn
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}sslmode=require"

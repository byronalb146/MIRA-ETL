from __future__ import annotations

import unittest
import re
from pathlib import Path

from mira_etl.db import SCHEMA_CONTRACT, schema_mismatches


class DatabaseSchemaContractTest(unittest.TestCase):
    def test_sql_declares_every_table_and_column_used_by_db(self) -> None:
        sql = (Path(__file__).parents[1] / "sql" / "001_init.sql").read_text(
            encoding="utf-8"
        )
        for table, columns in SCHEMA_CONTRACT.items():
            body = create_table_body(sql, table)
            self.assertIsNotNone(body, f"{table} is not created by 001_init.sql")
            for column in columns:
                declared_in_create = re.search(rf"\b{re.escape(column)}\b", body or "")
                declared_by_alter = re.search(
                    rf"alter\s+table\s+{re.escape(table)}.*?"
                    rf"add\s+column\s+if\s+not\s+exists\s+{re.escape(column)}\b",
                    sql,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                self.assertTrue(
                    declared_in_create or declared_by_alter,
                    f"{table}.{column} is used by db.py but absent from 001_init.sql",
                )

    def test_accepts_the_declared_schema(self) -> None:
        actual = {table: set(columns) for table, columns in SCHEMA_CONTRACT.items()}
        self.assertEqual(schema_mismatches(actual), [])

    def test_reports_missing_table_and_column(self) -> None:
        actual = {table: set(columns) for table, columns in SCHEMA_CONTRACT.items()}
        del actual["mart.buyers"]
        actual["mart.procurement_record_core"].remove("source_record_id")

        self.assertEqual(
            schema_mismatches(actual),
            [
                "mart.procurement_record_core missing columns source_record_id",
                "missing table mart.buyers",
            ],
        )


def create_table_body(sql: str, table: str) -> str | None:
    match = re.search(
        rf"create\s+table\s+if\s+not\s+exists\s+{re.escape(table)}\s*\(",
        sql,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    start = match.end()
    depth = 1
    for index in range(start, len(sql)):
        if sql[index] == "(":
            depth += 1
        elif sql[index] == ")":
            depth -= 1
            if depth == 0:
                return sql[start:index]
    return None


if __name__ == "__main__":
    unittest.main()

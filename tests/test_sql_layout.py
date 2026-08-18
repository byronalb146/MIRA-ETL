from __future__ import annotations

import unittest
from pathlib import Path


SQL_DIR = Path(__file__).parents[1] / "sql"


class SqlLayoutTest(unittest.TestCase):
    def test_only_three_ordered_sql_files_exist(self) -> None:
        self.assertEqual(
            sorted(path.name for path in SQL_DIR.glob("*.sql")),
            [
                "001_init.sql",
                "002_indexes_and_views.sql",
                "003_semantic_dictionary.sql",
            ],
        )

    def test_init_contains_only_schema_and_table_creation(self) -> None:
        sql = read("001_init.sql")
        self.assertNotRegex(
            sql,
            r"(?im)^\s*(?:create\s+(?:or\s+replace\s+)?view|create\s+index|"
            r"alter|drop|insert|update|delete|grant|revoke|create\s+role)\b",
        )

    def test_second_file_contains_no_security_or_analytics_indexes(self) -> None:
        sql = read("002_indexes_and_views.sql")
        self.assertNotRegex(
            sql,
            r"(?im)^\s*(?:grant|revoke|create\s+role|alter\s+role|create\s+policy|"
            r"alter\s+table.*row\s+level\s+security)\b",
        )
        self.assertNotRegex(sql, r"(?i)create\s+index[\s\S]*?on\s+analytics\.")

    def test_dictionary_is_isolated_in_third_file(self) -> None:
        first_two = read("001_init.sql") + read("002_indexes_and_views.sql")
        dictionary = read("003_semantic_dictionary.sql")
        self.assertNotIn("semantic_dictionary", first_two)
        self.assertRegex(dictionary, r"(?i)create\s+table.*query\.semantic_dictionary")
        self.assertRegex(dictionary, r"(?i)insert\s+into\s+query\.semantic_dictionary")


def read(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
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

    def test_public_coverage_does_not_leak_into_model_views(self) -> None:
        sql = read("002_indexes_and_views.sql")
        self.assertNotRegex(sql, r"(?i)create\s+(?:or\s+replace\s+)?view\s+web\.")
        self.assertNotIn("web.coverage_sources", sql)

    def test_dictionary_is_isolated_in_third_file(self) -> None:
        first_two = read("001_init.sql") + read("002_indexes_and_views.sql")
        dictionary = read("003_semantic_dictionary.sql")
        self.assertNotIn("semantic_dictionary", first_two)
        self.assertRegex(dictionary, r"(?i)create\s+table.*query\.semantic_dictionary")
        self.assertRegex(dictionary, r"(?i)insert\s+into\s+query\.semantic_dictionary")

    def test_name_search_uses_an_immutable_unaccent_wrapper(self) -> None:
        # unaccent() is STABLE, not IMMUTABLE -- Postgres refuses to build an
        # index on it directly. This locks in that the index expression goes
        # through the wrapper function, not the raw extension function.
        #
        # The wrapper lives in `query`, not `mart`: mira_query only has USAGE
        # on `query` (docs/database_security.md), so a copy in `mart` would
        # build the index fine but be uncallable by MIRA-API's own queries at
        # runtime. Both the index expression and MIRA-API's search query must
        # call the exact same qualified function for the index to be used.
        sql = read("002_indexes_and_views.sql")
        self.assertRegex(sql, r"(?i)create\s+or\s+replace\s+function\s+query\.f_unaccent")
        self.assertNotRegex(sql, r"(?i)create\s+or\s+replace\s+function\s+mart\.f_unaccent")
        self.assertRegex(
            sql,
            r"(?i)using\s+gin\s*\(\s*lower\(\s*query\.f_unaccent\(name_normalised\)\s*\)",
        )

    def test_v_coverage_reads_source_system_not_country_code(self) -> None:
        # audit.etl_runs.source holds a source-system identifier (e.g.
        # "costa_rica_sicop"), not an ISO country code -- verified against
        # production data. Naming this column country_code would be wrong.
        sql = read("002_indexes_and_views.sql")
        match = re.search(
            r"(?is)create\s+or\s+replace\s+view\s+query\.v_coverage\s+as(.*?);",
            sql,
        )
        self.assertIsNotNone(match)
        body = match.group(1) if match else ""
        self.assertRegex(body, r"(?i)r\.source\s+as\s+source_system")
        self.assertNotRegex(body, r"(?i)as\s+country_code")


def read(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

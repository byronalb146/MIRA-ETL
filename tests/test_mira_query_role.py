from __future__ import annotations

import re
import unittest
from pathlib import Path


class MiraQueryRoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = (
            Path(__file__).parents[1] / "sql" / "003_mira_query_role.sql"
        ).read_text(encoding="utf-8")

    def test_role_is_created_as_a_non_login_role(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?i)create\s+role\s+mira_query\s+nologin",
        )

    def test_role_only_receives_mart_read_access(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?i)grant\s+usage\s+on\s+schema\s+mart\s+to\s+mira_query",
        )
        self.assertRegex(
            self.sql,
            r"(?i)grant\s+select\s+on\s+all\s+tables\s+in\s+schema\s+mart"
            r"\s+to\s+mira_query",
        )
        self.assertNotRegex(
            self.sql,
            r"(?i)grant\s+(?:insert|update|delete|truncate|all)\b",
        )

    def test_every_rls_table_has_a_read_policy_for_the_role(self) -> None:
        public_access_sql = (
            Path(__file__).parents[1] / "sql" / "002_public_read_access.sql"
        ).read_text(encoding="utf-8")
        rls_tables = re.findall(
            r"(?i)alter\s+table\s+([\w.]+)\s+enable\s+row\s+level\s+security",
            public_access_sql,
        )
        for table in rls_tables:
            self.assertRegex(
                self.sql,
                rf"(?is)create\s+policy\s+\"MIRA query read access\"\s+on\s+"
                rf"{re.escape(table)}\s+for\s+select\s+to\s+mira_query\s+using\s*\(true\)",
            )


if __name__ == "__main__":
    unittest.main()

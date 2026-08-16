from __future__ import annotations

import re
import unittest
from pathlib import Path


def strip_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


class MiraQueryRoleTest(unittest.TestCase):
    """mira_query is the only role MIRA-API connects with. Its whole job is
    to make it structurally impossible for that connection to read
    mart/raw/staging/audit, even if the sqlglot validator in
    nlq/validator.py has a bug -- the role has to be the second, independent
    line of defense, not a mirror of what the validator already checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = (
            Path(__file__).parents[1] / "sql" / "006_mira_query_role.sql"
        ).read_text(encoding="utf-8")

    def test_role_is_created_with_login_and_noinherit(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?i)create\s+role\s+mira_query\s+with\s+login\s+noinherit",
        )

    def test_role_only_receives_query_schema_read_access(self) -> None:
        self.assertRegex(
            self.sql,
            r"(?i)grant\s+usage\s+on\s+schema\s+query\s+to\s+mira_query",
        )
        self.assertRegex(
            self.sql,
            r"(?i)grant\s+select\s+on\s+all\s+tables\s+in\s+schema\s+query"
            r"\s+to\s+mira_query",
        )
        self.assertNotRegex(
            self.sql,
            r"(?i)grant\s+(?:insert|update|delete|truncate|all)\b",
        )

    def test_never_grants_anything_on_mart_raw_staging_or_audit(self) -> None:
        # Comments are allowed to explain the design in prose (they do, on
        # purpose); only the executable SQL must never touch those schemas.
        executable = strip_sql_comments(self.sql)
        for forbidden_schema in ("mart", "raw", "staging", "audit"):
            self.assertNotRegex(
                executable,
                rf"(?i)\b{forbidden_schema}\b",
                f"006_mira_query_role.sql grants something on schema {forbidden_schema}",
            )

    def test_no_password_is_committed(self) -> None:
        self.assertNotRegex(
            strip_sql_comments(self.sql),
            r"(?i)password\s*'",
        )

    def test_runs_after_the_query_schema_exists(self) -> None:
        sql_dir = Path(__file__).parents[1] / "sql"
        files = sorted(path.name for path in sql_dir.glob("*.sql"))
        self.assertLess(
            files.index("004_query_layer.sql"),
            files.index("006_mira_query_role.sql"),
            "the role grants must run after query.* exists, or "
            "'grant ... on schema query' fails with schema does not exist",
        )


if __name__ == "__main__":
    unittest.main()

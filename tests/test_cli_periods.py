from __future__ import annotations

import re
import unittest
from pathlib import Path

from mira_etl.cli import resolve_period


CONFIG_DIR = Path(__file__).parents[1] / "config" / "sources"


class CliPeriodTest(unittest.TestCase):
    def test_html_source_defaults_to_current_period(self) -> None:
        period = resolve_period(
            source="nicaragua_siscae",
            period=None,
            config_dir=CONFIG_DIR,
        )

        self.assertRegex(period, re.compile(r"^\d{6}$"))

    def test_historical_source_requires_period(self) -> None:
        with self.assertRaises(SystemExit):
            resolve_period(
                source="guatemala_guatecompras",
                period=None,
                config_dir=CONFIG_DIR,
            )

    def test_explicit_period_is_preserved(self) -> None:
        self.assertEqual(
            resolve_period(
                source="nicaragua_siscae",
                period="202607",
                config_dir=CONFIG_DIR,
            ),
            "202607",
        )


if __name__ == "__main__":
    unittest.main()

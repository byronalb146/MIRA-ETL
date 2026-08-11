import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mira_etl.extract import resolve_dataset_dir, validate_required_files


class ResolveDatasetDirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SimpleNamespace(
            files={"required": ["one.csv", "two.csv"]}
        )

    def test_accepts_files_at_extraction_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.csv").touch()
            (root / "two.csv").touch()

            self.assertEqual(resolve_dataset_dir(self.config, root), root)

    def test_resolves_period_directory_inside_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            period_dir = root / "202401"
            period_dir.mkdir()
            (period_dir / "one.csv").touch()
            (period_dir / "two.csv").touch()

            self.assertEqual(resolve_dataset_dir(self.config, root), period_dir)
            self.assertIsNone(validate_required_files(self.config, root))

    def test_reports_files_that_are_actually_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "one.csv").touch()

            with self.assertRaisesRegex(FileNotFoundError, "two.csv"):
                resolve_dataset_dir(self.config, root)


if __name__ == "__main__":
    unittest.main()

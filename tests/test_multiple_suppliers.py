from __future__ import annotations

import unittest
from pathlib import Path

from mira_etl.config import SourceConfig
from mira_etl.db import supplier_records_for
from mira_etl.transform_gt import build_record


class MultipleSuppliersTest(unittest.TestCase):
    def test_guatemala_keeps_suppliers_from_all_awards_and_contracts(self) -> None:
        config = SourceConfig.load(
            Path(__file__).parents[1] / "config" / "sources",
            "guatemala_guatecompras",
        )
        source_row = {
            "ocid": "ocds-test-multiple",
            "compiledRelease": {
                "ocid": "ocds-test-multiple",
                "buyer": {"id": "GT-NIT-1", "name": "Comprador"},
                "tender": {"id": "NOG-1", "title": "Compra"},
                "awards": [
                    {"suppliers": [
                        {"id": "GT-NIT-10", "name": "Proveedor A"},
                        {"id": "GT-NIT-20", "name": "Proveedor B"},
                    ]}
                ],
                "contracts": [
                    {"suppliers": [
                        {"id": "GT-NIT-20", "name": "Proveedor B"},
                        {"id": "GT-NIT-30", "name": "Proveedor C"},
                    ]}
                ],
            },
        }

        record = build_record(
            config=config,
            period="202601",
            connector_version="test",
            source_row=source_row,
        )

        self.assertEqual(
            [supplier["supplier_name"] for supplier in record["suppliers"]],
            ["Proveedor A", "Proveedor B", "Proveedor C"],
        )
        self.assertEqual(
            [candidate["supplier_id_source"] for candidate in supplier_records_for(record)],
            ["GT-NIT-10", "GT-NIT-20", "GT-NIT-30"],
        )

    def test_scalar_supplier_remains_supported(self) -> None:
        record = {
            "process_id": "process-1",
            "supplier_name": "Proveedor unico",
            "supplier_id_source": "supplier-1",
        }

        self.assertEqual(supplier_records_for(record), [record])

    def test_process_without_supplier_creates_no_relationship_candidate(self) -> None:
        self.assertEqual(supplier_records_for({"process_id": "process-1"}), [])


if __name__ == "__main__":
    unittest.main()

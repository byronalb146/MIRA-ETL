from __future__ import annotations

import unittest
from pathlib import Path

from mira_etl.config import SourceConfig
from mira_etl.pipeline import transform_source
from mira_etl.transform_gt import build_record

CONFIG_DIR = Path(__file__).parents[1] / "config" / "sources"


class GrainTest(unittest.TestCase):
    """Costa Rica's process_id encodes a purchase line (LINEA/PROD_ID), so its
    grain is LINE_ITEM. Guatemala and Nicaragua's process_id identifies the
    whole procedure, so their grain is PROCESS. A comparative count across
    countries without this distinction mixes the two units."""

    def test_costa_rica_grain_is_line_item(self) -> None:
        config = SourceConfig.load(CONFIG_DIR, "costa_rica_sicop")
        rows = {
            "DetalleCarteles.csv": [
                {"NRO_SICOP": "SICOP-1", "CEDULA_INSTITUCION": "BUYER-1"}
            ],
            "ProcedimientoAdjudicacion.csv": [
                {
                    "NRO_SICOP": "SICOP-1",
                    "LINEA": "1",
                    "CEDULA_PROVEEDOR": "SUPPLIER-1",
                    "PROD_ID": "ITEM-1",
                }
            ],
            "InstitucionesRegistradas.csv": [{"CEDULA": "BUYER-1"}],
            "Proveedores.csv": [{"CEDULA_PROVEEDOR": "SUPPLIER-1"}],
        }
        records = transform_source(config=config, period="202608", source_rows=rows)
        self.assertEqual(records[0]["grain"], "LINE_ITEM")

    def test_nicaragua_grain_is_process(self) -> None:
        config = SourceConfig.load(CONFIG_DIR, "nicaragua_siscae")
        rows = {
            "procesos_vigentes": [
                {
                    "tipo_procedimiento": "Licitacion",
                    "numero_proceso": "1/2026",
                    "estado": "Vigente",
                    "institucion": "Comprador",
                }
            ]
        }
        records = transform_source(config=config, period="202608", source_rows=rows)
        self.assertEqual(records[0]["grain"], "PROCESS")

    def test_guatemala_grain_is_process(self) -> None:
        config = SourceConfig.load(CONFIG_DIR, "guatemala_guatecompras")
        source_row = {
            "ocid": "ocds-test-grain",
            "compiledRelease": {
                "ocid": "ocds-test-grain",
                "buyer": {"id": "GT-NIT-1", "name": "Comprador"},
                "tender": {"id": "NOG-1", "title": "Compra"},
            },
        }
        record = build_record(
            config=config, period="202601", connector_version="test", source_row=source_row
        )
        self.assertEqual(record["grain"], "PROCESS")


if __name__ == "__main__":
    unittest.main()

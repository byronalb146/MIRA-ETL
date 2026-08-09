from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mira_etl.config import SourceConfig
from mira_etl.pipeline import run_all_pipelines, transform_source


CONFIG_DIR = Path(__file__).parents[1] / "config" / "sources"


class ConnectorRoutingTest(unittest.TestCase):
    def test_discovers_the_three_configured_extraction_types(self) -> None:
        configs = SourceConfig.discover(CONFIG_DIR)
        actual = {config.source: config.download["type"] for config in configs}
        self.assertEqual(
            actual,
            {
                "costa_rica_sicop": "http_zip_csv",
                "guatemala_guatecompras": "http_zip_json",
                "nicaragua_siscae": "html_session_scrape",
            },
        )

    def test_costa_rica_uses_its_csv_transformer(self) -> None:
        config = SourceConfig.load(CONFIG_DIR, "costa_rica_sicop")
        rows = {
            "DetalleCarteles.csv": [
                {
                    "NRO_SICOP": "SICOP-1",
                    "NRO_PROCEDIMIENTO": "CR-1",
                    "CARTEL_NM": "Compra de prueba",
                    "CEDULA_INSTITUCION": "BUYER-1",
                }
            ],
            "ProcedimientoAdjudicacion.csv": [
                {
                    "NRO_SICOP": "SICOP-1",
                    "LINEA": "1",
                    "CEDULA_PROVEEDOR": "SUPPLIER-1",
                    "PROD_ID": "ITEM-1",
                }
            ],
            "InstitucionesRegistradas.csv": [
                {"CEDULA": "BUYER-1", "NOMBRE_INSTITUCION": "Comprador"}
            ],
            "Proveedores.csv": [
                {"CEDULA_PROVEEDOR": "SUPPLIER-1", "NOMBRE_PROVEEDOR": "Proveedor"}
            ],
        }
        records = transform_source(config=config, period="202608", source_rows=rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["country_code"], "CR")
        self.assertTrue(records[0]["process_id"].startswith("MIRA-CR-"))

    def test_nicaragua_uses_its_html_transformer(self) -> None:
        config = SourceConfig.load(CONFIG_DIR, "nicaragua_siscae")
        rows = {
            "procesos_vigentes": [
                {
                    "tipo_procedimiento": "Licitacion",
                    "numero_proceso": "1/2026",
                    "estado": "Vigente",
                    "codigo_sigaf": None,
                    "institucion": "Comprador",
                    "categoria": "Servicios (12345678)",
                    "descripcion": "Servicio de prueba",
                    "fecha_publicacion": "01/08/2026",
                    "fecha_cierre": "15/08/2026",
                    "ultima_actualizacion": "02/08/2026",
                }
            ]
        }
        records = transform_source(config=config, period="202608", source_rows=rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["country_code"], "NI")
        self.assertTrue(records[0]["process_id"].startswith("MIRA-NI-"))

    def test_run_all_discovers_and_launches_every_source(self) -> None:
        calls: list[str] = []

        def fake_run_pipeline(**kwargs: object) -> None:
            calls.append(str(kwargs["source"]))

        with TemporaryDirectory() as work_dir, patch(
            "mira_etl.pipeline.run_pipeline", side_effect=fake_run_pipeline
        ):
            run_all_pipelines(
                period="202608",
                config_dir=CONFIG_DIR,
                work_dir=Path(work_dir),
                limit=2,
            )

        self.assertCountEqual(
            calls,
            ["costa_rica_sicop", "guatemala_guatecompras", "nicaragua_siscae"],
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from mira_etl.api.dependencies import get_procurement_service
from mira_etl.api.main import app
from mira_etl.api.repositories.procurements import ProcurementRepository
from mira_etl.api.schemas.procurements import ProcurementListResponse
from mira_etl.api.services.procurements import ProcurementService


class FakeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list_procurements(self, **kwargs: Any) -> ProcurementListResponse:
        self.calls.append(kwargs)
        return ProcurementListResponse(
            data=[],
            pagination={
                "limit": kwargs["limit"],
                "offset": kwargs["offset"],
                "returned": 0,
                "total": 0,
                "pages": 0,
            },
        )


class FakeDatabase:
    def __init__(self) -> None:
        self.sql = ""
        self.params: tuple[Any, ...] = ()

    def fetch_all(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        self.sql = sql
        self.params = params
        return []


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeService()
        app.dependency_overrides[get_procurement_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_web_uses_the_read_api(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('const API_BASE_URL = "/api/v1"', response.text)
        self.assertNotIn("PEGA_AQUI_TU_ANON_KEY", response.text)

    def test_limit_above_maximum_is_rejected(self) -> None:
        response = self.client.get("/api/v1/procurements?limit=101")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.calls, [])

    def test_default_pagination(self) -> None:
        response = self.client.get("/api/v1/procurements")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.calls[-1],
            {"limit": 20, "offset": 0, "country": None, "status": None},
        )
        self.assertEqual(
            response.json()["pagination"],
            {
                "limit": 20,
                "offset": 0,
                "returned": 0,
                "total": 0,
                "pages": 0,
            },
        )

    def test_country_filter(self) -> None:
        response = self.client.get(
            "/api/v1/procurements?country=gt&limit=5&offset=10"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls[-1]["country"], "gt")

    def test_status_filter_is_forwarded_to_the_service(self) -> None:
        response = self.client.get(
            "/api/v1/procurements?country=GT&status=AWARDED"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.calls[-1]["status"], "AWARDED")


class RepositoryTest(unittest.TestCase):
    def test_limit_offset_and_country_are_applied_in_sql(self) -> None:
        db = FakeDatabase()
        repository = ProcurementRepository(db)  # type: ignore[arg-type]

        repository.list(limit=20, offset=40, country="GT")

        normalized_sql = " ".join(db.sql.split()).lower()
        self.assertIn("from mart.v_procurements_web", normalized_sql)
        self.assertIn("where country_code = %s", normalized_sql)
        self.assertIn("limit %s offset %s", normalized_sql)
        self.assertEqual(db.params, ("GT", 20, 40))

    def test_status_is_applied_in_sql(self) -> None:
        db = FakeDatabase()
        repository = ProcurementRepository(db)  # type: ignore[arg-type]

        repository.list(
            limit=10,
            offset=0,
            country="GT",
            status="AWARDED",
        )

        normalized_sql = " ".join(db.sql.split()).lower()
        self.assertIn(
            "where country_code = %s and process_status = %s",
            normalized_sql,
        )
        self.assertEqual(db.params, ("GT", "AWARDED", 10, 0))

    def test_service_normalizes_country_to_uppercase(self) -> None:
        db = FakeDatabase()
        service = ProcurementService(
            ProcurementRepository(db)  # type: ignore[arg-type]
        )

        service.list_procurements(limit=20, offset=0, country="gt")

        self.assertEqual(db.params, ("GT", 20, 0))


if __name__ == "__main__":
    unittest.main()

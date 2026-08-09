from __future__ import annotations

from collections.abc import Iterator

from mira_etl.api.repositories.procurements import ProcurementRepository
from mira_etl.api.services.procurements import ProcurementService
from mira_etl.db import Database


def get_procurement_service() -> Iterator[ProcurementService]:
    with Database.from_env() as db:
        yield ProcurementService(ProcurementRepository(db))

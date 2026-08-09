from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from mira_etl.api.dependencies import get_procurement_service
from mira_etl.api.schemas.procurements import ProcurementListResponse
from mira_etl.api.services.procurements import ProcurementService


router = APIRouter(tags=["procurements"])


@router.get("/procurements", response_model=ProcurementListResponse)
def list_procurements(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    status: Annotated[str | None, Query(min_length=1, max_length=30)] = None,
    service: ProcurementService = Depends(get_procurement_service),
) -> ProcurementListResponse:
    return service.list_procurements(
        limit=limit,
        offset=offset,
        country=country,
        status=status,
    )

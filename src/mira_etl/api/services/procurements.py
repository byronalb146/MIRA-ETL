from __future__ import annotations

import math
from typing import Any

from mira_etl.api.repositories.procurements import ProcurementRepository
from mira_etl.api.schemas.procurements import (
    Amounts,
    Buyer,
    Item,
    Pagination,
    Procurement,
    ProcurementListResponse,
    Supplier,
)


class ProcurementService:
    def __init__(self, repository: ProcurementRepository) -> None:
        self.repository = repository

    def list_procurements(
        self,
        *,
        limit: int,
        offset: int,
        country: str | None,
        status: str | None = None,
    ) -> ProcurementListResponse:
        normalized_country = country.upper() if country else None
        normalized_status = status.upper() if status else None
        rows = self.repository.list(
            limit=limit,
            offset=offset,
            country=normalized_country,
            status=normalized_status,
        )
        data = [procurement_from_row(row) for row in rows]
        total = int(rows[0]["total_count"]) if rows else 0
        return ProcurementListResponse(
            data=data,
            pagination=Pagination(
                limit=limit,
                offset=offset,
                returned=len(data),
                total=total,
                pages=math.ceil(total / limit) if total else 0,
            ),
        )


def procurement_from_row(row: dict[str, Any]) -> Procurement:
    return Procurement(
        process_id=row["process_id"],
        country_code=row["country_code"],
        source_system=row["source_system"],
        process_number=row.get("process_number"),
        title=row.get("title"),
        description=row.get("description"),
        buyer=Buyer(
            name=row.get("buyer_name"),
            id_source=row.get("buyer_id_source"),
            tax_id=row.get("buyer_tax_id"),
        ),
        procurement_method=row.get("procurement_method"),
        process_status=row.get("process_status"),
        publication_date=row.get("publication_date"),
        closing_date=row.get("closing_date"),
        award_date=row.get("award_date"),
        amounts=Amounts(
            estimated=row.get("estimated_amount"),
            awarded=row.get("awarded_amount"),
            currency=row.get("currency_code"),
        ),
        supplier=Supplier(
            name=row.get("supplier_name"),
            id_source=row.get("supplier_id_source"),
            tax_id=row.get("supplier_tax_id"),
            type=row.get("supplier_type"),
        ),
        item=Item(
            description=row.get("item_description"),
            category_source=row.get("category_source"),
        ),
        data_quality_status=row["data_quality_status"],
        source_url=row.get("source_url"),
    )

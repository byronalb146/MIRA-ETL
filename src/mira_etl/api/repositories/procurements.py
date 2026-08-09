from __future__ import annotations

from typing import Any

from mira_etl.db import Database


SELECT_COLUMNS = """
    count(*) over() as total_count,
    process_id, country_code, source_system, process_number, title,
    description, buyer_name, buyer_id_source, buyer_tax_id,
    procurement_method, process_status, publication_date, closing_date,
    award_date, estimated_amount, awarded_amount, currency_code,
    supplier_name, supplier_id_source, supplier_tax_id, supplier_type,
    item_description, category_source, data_quality_status, source_url
"""


class ProcurementRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list(
        self,
        *,
        limit: int,
        offset: int,
        country: str | None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = []
        filter_params: list[Any] = []
        if country:
            conditions.append("country_code = %s")
            filter_params.append(country)
        if status:
            conditions.append("process_status = %s")
            filter_params.append(status)
        where_clause = (
            f"where {' and '.join(conditions)}" if conditions else ""
        )
        params = (*filter_params, limit, offset)

        return self.db.fetch_all(
            f"""
            select {SELECT_COLUMNS}
              from mart.v_procurements_web
              {where_clause}
             order by publication_date desc nulls last, process_id asc
             limit %s offset %s
            """,
            params,
        )

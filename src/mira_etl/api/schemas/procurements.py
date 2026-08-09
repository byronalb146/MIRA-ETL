from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class Buyer(BaseModel):
    name: str | None
    id_source: str | None
    tax_id: str | None


class Amounts(BaseModel):
    estimated: Decimal | None
    awarded: Decimal | None
    currency: str | None


class Supplier(BaseModel):
    name: str | None
    id_source: str | None
    tax_id: str | None
    type: str | None


class Item(BaseModel):
    description: str | None
    category_source: str | None


class Procurement(BaseModel):
    process_id: str
    country_code: str
    source_system: str
    process_number: str | None
    title: str | None
    description: str | None
    buyer: Buyer
    procurement_method: str | None
    process_status: str | None
    publication_date: datetime | None
    closing_date: datetime | None
    award_date: datetime | None
    amounts: Amounts
    supplier: Supplier
    item: Item
    data_quality_status: str
    source_url: str | None


class Pagination(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    pages: int


class ProcurementListResponse(BaseModel):
    data: list[Procurement]
    pagination: Pagination

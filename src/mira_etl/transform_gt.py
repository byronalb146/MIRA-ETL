from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from mira_etl.config import SourceConfig
from mira_etl.hashutil import stable_id


MINIMUM_FIELDS = [
    "process_number",
    "title",
    "buyer_name",
    "buyer_tax_id",
    "procurement_method",
    "process_status",
    "publication_date",
    "award_date",
    "awarded_amount",
    "currency_code",
    "supplier_name",
    "supplier_tax_id",
    "item_description",
]


def build_record(
    *,
    config: SourceConfig,
    period: str,
    connector_version: str,
    source_row: dict[str, Any],
) -> dict[str, Any]:
    compiled = source_row.get("compiledRelease") or source_row
    tender = compiled.get("tender") or {}
    awards = compiled.get("awards") or []
    contracts = compiled.get("contracts") or []
    award = awards[0] if awards else {}
    contract = contracts[0] if contracts else {}
    buyer = compiled.get("buyer") or tender.get("procuringEntity") or {}
    supplier = first_supplier(award, contract)
    item = first_item(award, contract, tender)
    source_record_id = (
        source_row.get("ocid")
        or compiled.get("ocid")
        or compiled.get("id")
    )
    if not source_record_id:
        raise ValueError("Guatemala OCDS record is missing ocid/id")

    supplier_party = party_by_id(
        compiled.get("parties") or [],
        supplier.get("id"),
    )
    estimated_value = tender.get("value") or {}
    awarded_value = contract.get("value") or award.get("value") or {}
    source_url = first_release_url(source_row) or config.source_url_for_period(period)
    raw_payload_hash = json_hash(source_row)

    record = {
        "process_id": stable_id(
            config.country_code,
            source_record_id,
            prefix="MIRA-GT-",
        ),
        "process_number": tender.get("id") or source_record_id,
        "title": tender.get("title") or award.get("title"),
        "description": tender.get("description") or tender.get("title"),
        "buyer_name": buyer.get("name"),
        "buyer_id_source": buyer.get("id"),
        "buyer_tax_id": identifier_value(buyer),
        "procurement_method": (
            tender.get("procurementMethodDetails")
            or tender.get("procurementMethod")
        ),
        "process_status": normalise_status(
            tender.get("status"),
            award=award,
            contract=contract,
        ),
        "source_status": (
            contract.get("statusDetails")
            or award.get("statusDetails")
            or tender.get("statusDetails")
            or contract.get("status")
            or award.get("status")
            or tender.get("status")
        ),
        "publication_date": parse_datetime(
            tender.get("datePublished")
            or (tender.get("tenderPeriod") or {}).get("startDate")
        ),
        "closing_date": parse_datetime(
            (tender.get("tenderPeriod") or {}).get("endDate")
        ),
        "award_date": parse_datetime(
            award.get("date") or contract.get("dateSigned")
        ),
        "estimated_amount": parse_decimal(estimated_value.get("amount")),
        "awarded_amount": parse_decimal(awarded_value.get("amount")),
        "currency_code": (
            awarded_value.get("currency")
            or estimated_value.get("currency")
        ),
        "supplier_name": supplier.get("name"),
        "supplier_id_source": supplier.get("id"),
        "supplier_tax_id": identifier_value(supplier),
        "supplier_type": normalise_supplier_type(supplier_party),
        "item_description": item.get("description"),
        "category_source": (item.get("classification") or {}).get("id"),
        "category_normalised": None,
        "country_code": config.country_code,
        "source_system": config.source_system,
        "source_record_id": source_record_id,
        "source_url": source_url,
        "extracted_at": datetime.now(UTC),
        "source_last_modified_at": parse_datetime(
            compiled.get("publishedDate") or compiled.get("date")
        ),
        "connector_version": connector_version,
        "raw_payload": source_row,
        "raw_payload_hash": raw_payload_hash,
        "normalisation_status": "PROCESSED",
        "normalised_at": datetime.now(UTC),
        "data_quality_status": "PARTIAL",
        "missing_fields": [],
    }
    record["missing_fields"] = [
        field for field in MINIMUM_FIELDS if record.get(field) is None
    ]
    record["data_quality_status"] = (
        "COMPLETE" if not record["missing_fields"] else "PARTIAL"
    )
    return record


def first_supplier(
    award: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    suppliers = award.get("suppliers") or contract.get("suppliers") or []
    return suppliers[0] if suppliers else {}


def first_item(*sections: dict[str, Any]) -> dict[str, Any]:
    for section in sections:
        items = section.get("items") or []
        if items:
            return items[0]
    return {}


def party_by_id(
    parties: list[dict[str, Any]],
    party_id: str | None,
) -> dict[str, Any]:
    return next(
        (party for party in parties if party.get("id") == party_id),
        {},
    )


def identifier_value(party: dict[str, Any]) -> str | None:
    identifier = party.get("identifier") or {}
    return identifier.get("id") or strip_identifier_prefix(party.get("id"))


def strip_identifier_prefix(value: str | None) -> str | None:
    if not value:
        return None
    return value.rsplit("-", 1)[-1]


def first_release_url(source_row: dict[str, Any]) -> str | None:
    releases = source_row.get("releases") or []
    return releases[-1].get("url") if releases else None


def normalise_status(
    tender_status: str | None,
    *,
    award: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    if contract:
        status = str(contract.get("status") or "").lower()
        if status in {"complete", "terminated"}:
            return "COMPLETED"
        if status == "cancelled":
            return "CANCELLED"
        return "CONTRACTED"
    if award:
        return "CANCELLED" if award.get("status") == "cancelled" else "AWARDED"
    status = str(tender_status or "").lower()
    return {
        "active": "OPEN",
        "planned": "PLANNED",
        "complete": "COMPLETED",
        "cancelled": "CANCELLED",
        "unsuccessful": "DESERTED",
        "withdrawn": "CANCELLED",
    }.get(status, "PUBLISHED")


def normalise_supplier_type(party: dict[str, Any]) -> str:
    details = party.get("details") or {}
    legal_type = details.get("legalEntityTypeDetail") or {}
    value = str(legal_type.get("description") or "").lower()
    if "individual" in value or "persona individual" in value:
        return "PERSON"
    if "jur" in value or "sociedad" in value or "empresa" in value:
        return "COMPANY"
    return "UNKNOWN"


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

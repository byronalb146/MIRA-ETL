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
    buyer_parties = all_buyers(compiled, tender)
    buyer = buyer_parties[0] if buyer_parties else {}
    source_record_id = (
        source_row.get("ocid")
        or compiled.get("ocid")
        or compiled.get("id")
    )
    if not source_record_id:
        raise ValueError("Guatemala OCDS record is missing ocid/id")

    parties = compiled.get("parties") or []
    estimated_value = tender.get("value") or {}
    source_url = first_release_url(source_row) or config.source_url_for_period(period)
    raw_payload_hash = json_hash(source_row)

    item_sections = [tender, *awards, *contracts]
    items: list[dict[str, Any]] = []
    item_ids_by_source: dict[str, str] = {}
    seen_item_ids: set[str] = set()
    for section in item_sections:
        for position, source_item in enumerate(section.get("items") or []):
            source_item_id = source_item.get("id")
            item_id = stable_id(
                config.country_code, source_record_id,
                source_item_id or source_item.get("description") or str(position),
                prefix="MIRA-GT-ITEM-",
            )
            if source_item_id:
                item_ids_by_source[str(source_item_id)] = item_id
            if item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)
            items.append({
                "item_id": item_id,
                "source_item_id": source_item_id,
                "line_number": None,
                "item_description": source_item.get("description"),
                "category_source": (source_item.get("classification") or {}).get("id"),
                "category_normalised": None,
            })

    normalised_awards: list[dict[str, Any]] = []
    award_sections = awards or contracts
    for position, source_award in enumerate(award_sections):
        source_award_id = source_award.get("id") or source_award.get("awardID")
        value = source_award.get("value") or {}
        award_suppliers = source_award.get("suppliers") or []
        linked_item_ids = [
            item_ids_by_source[str(source_item["id"])]
            for source_item in source_award.get("items") or []
            if source_item.get("id") is not None
            and str(source_item["id"]) in item_ids_by_source
        ]
        normalised_awards.append({
            "award_id": stable_id(
                config.country_code, source_record_id,
                source_award_id or str(position), prefix="MIRA-GT-AWARD-",
            ),
            "source_award_id": source_award_id,
            "item_ids": linked_item_ids,
            "award_date": parse_datetime(
                source_award.get("date") or source_award.get("dateSigned")
            ),
            "awarded_amount": parse_decimal(value.get("amount")),
            "currency_code": value.get("currency"),
            "suppliers": [
                {
                    "supplier_name": party.get("name"),
                    "supplier_id_source": party.get("id"),
                    "supplier_tax_id": identifier_value(party),
                    "supplier_type": normalise_supplier_type(
                        party_by_id(parties, party.get("id"))
                    ),
                }
                for party in award_suppliers
            ],
        })

    awards_by_source = {
        str(item["source_award_id"]): item
        for item in normalised_awards
        if item.get("source_award_id") is not None
    }
    for contract_item in contracts:
        target = awards_by_source.get(str(contract_item.get("awardID")))
        if target is None:
            continue
        seen_suppliers = {
            (item.get("supplier_id_source"), item.get("supplier_tax_id"), item.get("supplier_name"))
            for item in target["suppliers"]
        }
        for party in contract_item.get("suppliers") or []:
            candidate = {
                "supplier_name": party.get("name"),
                "supplier_id_source": party.get("id"),
                "supplier_tax_id": identifier_value(party),
                "supplier_type": normalise_supplier_type(
                    party_by_id(parties, party.get("id"))
                ),
            }
            key = (
                candidate["supplier_id_source"], candidate["supplier_tax_id"],
                candidate["supplier_name"],
            )
            if key not in seen_suppliers:
                seen_suppliers.add(key)
                target["suppliers"].append(candidate)

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
        "buyers": [
            {
                "buyer_name": item.get("name"),
                "buyer_id_source": item.get("id"),
                "buyer_tax_id": identifier_value(item),
            }
            for item in buyer_parties
        ],
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
        "estimated_amount": parse_decimal(estimated_value.get("amount")),
        "currency_code": estimated_value.get("currency"),
        "items": items,
        "awards": normalised_awards,
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
        "grain": "PROCESS",
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


def all_suppliers(
    awards: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return every distinct supplier referenced by awards or contracts."""
    result: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for section in [*awards, *contracts]:
        for supplier in section.get("suppliers") or []:
            key = (
                supplier.get("id"),
                identifier_value(supplier),
                supplier.get("name"),
            )
            if key not in seen:
                seen.add(key)
                result.append(supplier)
    return result


def all_buyers(
    compiled: dict[str, Any],
    tender: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return every distinct buyer/procuring entity exposed by OCDS."""
    candidates = [compiled.get("buyer"), tender.get("procuringEntity")]
    candidates.extend(
        party
        for party in compiled.get("parties") or []
        if {str(role).lower() for role in party.get("roles") or []}
        & {"buyer", "procuringentity"}
    )
    result: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for buyer in candidates:
        if not isinstance(buyer, dict):
            continue
        key = (buyer.get("id"), identifier_value(buyer), buyer.get("name"))
        if key not in seen:
            seen.add(key)
            result.append(buyer)
    return result


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

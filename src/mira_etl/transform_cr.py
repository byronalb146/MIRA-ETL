from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from mira_etl.config import SourceConfig
from mira_etl.hashutil import stable_id, stable_json_hash


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


def build_records(
    *,
    config: SourceConfig,
    connector_version: str,
    source_rows: dict[str, list[dict[str, str | None]]],
) -> list[dict[str, Any]]:
    carteles = index_by(source_rows.get("DetalleCarteles.csv", []), "NRO_SICOP")
    proveedores = index_by(source_rows.get("Proveedores.csv", []), "CEDULA_PROVEEDOR")
    instituciones = index_by(source_rows.get("InstitucionesRegistradas.csv", []), "CEDULA")
    adjudicaciones = source_rows.get("ProcedimientoAdjudicacion.csv", [])

    extracted_at = datetime.now(UTC)
    records: list[dict[str, Any]] = []

    for row in adjudicaciones:
        nro_sicop = row.get("NRO_SICOP")
        cartel = carteles.get(nro_sicop or "", {})
        proveedor = proveedores.get(row.get("CEDULA_PROVEEDOR") or "", {})
        institucion_id = row.get("CEDULA") or cartel.get("CEDULA_INSTITUCION")
        institucion = instituciones.get(institucion_id or "", {})

        raw_payload = {
            "procedimiento_adjudicacion": row,
            "detalle_cartel": cartel or None,
            "proveedor": proveedor or None,
            "institucion": institucion or None,
        }

        source_record_id = ":".join(
            [
                "CR",
                "SICOP",
                nro_sicop or "",
                row.get("LINEA") or "",
                row.get("CEDULA_PROVEEDOR") or "",
                row.get("PROD_ID") or "",
            ]
        )

        record = {
            "process_id": stable_id(config.country_code, nro_sicop, prefix="MIRA-CR-"),
            "process_number": row.get("NUMERO_PROCEDIMIENTO") or cartel.get("NRO_PROCEDIMIENTO"),
            "title": cartel.get("CARTEL_NM") or row.get("DESCR_PROCEDIMIENTO"),
            "description": row.get("DESCR_PROCEDIMIENTO") or cartel.get("CARTEL_NM"),
            "buyer_name": row.get("INSTITUCION") or institucion.get("NOMBRE_INSTITUCION"),
            "buyer_id_source": institucion_id,
            "buyer_tax_id": institucion_id,
            "procurement_method": row.get("TIPO_PROCEDIMIENTO") or cartel.get("TIPO_PROCEDIMIENTO"),
            "process_status": normalise_status(cartel.get("CARTEL_STAT"), has_award=True),
            "source_status": cartel.get("CARTEL_STAT"),
            "publication_date": parse_datetime(cartel.get("FECHA_PUBLICACION")),
            "closing_date": parse_datetime(cartel.get("FECHAH_APERTURA")),
            "award_date": parse_datetime(row.get("FECHA_ADJUD_FIRME")),
            "estimated_amount": parse_decimal(cartel.get("MONTO_EST")),
            "awarded_amount": parse_decimal(row.get("MONTO_ADJU_LINEA_CRC") or row.get("MONTO_ADJU_LINEA")),
            "currency_code": row.get("MONEDA_ADJUDICADA") or cartel.get("TIPO_MONEDA"),
            "supplier_name": row.get("NOMBRE_PROVEEDOR") or proveedor.get("NOMBRE_PROVEEDOR"),
            "supplier_id_source": row.get("CEDULA_PROVEEDOR"),
            "supplier_tax_id": row.get("CEDULA_PROVEEDOR"),
            "supplier_type": normalise_supplier_type(proveedor.get("TIPO_PROVEEDOR"), row.get("TIPO_OFERTA")),
            "item_description": row.get("DESCR_BIEN_SERVICIO"),
            "category_source": row.get("OBJETO_GASTO") or cartel.get("CLAS_OBJ"),
            "category_normalised": None,
            "country_code": config.country_code,
            "source_system": config.source_system,
            "source_record_id": source_record_id,
            "source_url": None,
            "extracted_at": extracted_at,
            "source_last_modified_at": parse_datetime(cartel.get("FECHA_MOD") or row.get("fecha_rev")),
            "connector_version": connector_version,
            "raw_payload": raw_payload,
            "raw_payload_hash": stable_json_hash(raw_payload),
            "normalisation_status": "PROCESSED",
            "normalised_at": datetime.now(UTC),
            "data_quality_status": "PARTIAL",
            "missing_fields": [],
        }
        record["missing_fields"] = [field for field in MINIMUM_FIELDS if record.get(field) is None]
        record["data_quality_status"] = "COMPLETE" if not record["missing_fields"] else "PARTIAL"
        records.append(record)

    return records


def index_by(rows: list[dict[str, str | None]], key: str) -> dict[str, dict[str, str | None]]:
    return {row[key]: row for row in rows if row.get(key)}


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def normalise_status(source_status: str | None, *, has_award: bool) -> str:
    if source_status:
        lowered = source_status.lower()
        if "desierto" in lowered or "infructuoso" in lowered:
            return "DESERTED"
        if "cancel" in lowered or "anulad" in lowered:
            return "CANCELLED"
        if "suspend" in lowered:
            return "SUSPENDED"
    return "AWARDED" if has_award else "PUBLISHED"


def normalise_supplier_type(source_type: str | None, offer_type: str | None) -> str:
    value = strip_accents(f"{source_type or ''} {offer_type or ''}".lower())
    if "consorcio" in value:
        return "CONSORTIUM"
    if "fisic" in value:
        return "PERSON"
    if "juridic" in value or "sociedad" in value:
        return "COMPANY"
    if "extranj" in value:
        return "FOREIGN_SUPPLIER"
    return "UNKNOWN"


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))

from __future__ import annotations

import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup


BASE_URL = (
    "https://www.gestion.nicaraguacompra.gob.ni/siscae/portal/"
    "adquisiciones-gestion/busquedaProcedimientosVigentes?proc_estado=VIGENTE"
)
FORM_NAME = "resultadoView:listadoProcedimientosForm"
PORTLET_PREFIX = "Pluto__adquisiciones_gestion_portlet_busquedaProcedimientosVigentesPortlet"

REQUEST_TIMEOUT_SECONDS = 45
MAX_REQUEST_RETRIES = 3
MAX_PAGES = 10  # safety cap; the confirmed pagination pattern only covers one block of 10 pages
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_with_retries(session: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
    """SISCAE runs on a single, unbalanced instance and times out intermittently.
    Wrap every request with a small retry/backoff instead of failing the whole run."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_REQUEST_RETRIES + 1):
        try:
            if method == "get":
                return session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
            return session.post(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network dependent
            last_error = exc
            time.sleep(5 * attempt)
    assert last_error is not None
    raise last_error


def parse_form(html: str, form_name_prefix: str) -> tuple[str | None, dict[str, str] | None, BeautifulSoup]:
    """Locate the JSF form matching a field-name prefix and build a submittable payload
    from its current input/select values. SISCAE is a stateful Java-portlet application:
    every POST must resend the form's own hidden fields, not just the ones being changed."""
    soup = BeautifulSoup(html, "html.parser")
    target_form = None
    for form in soup.find_all("form"):
        if any(field.get("name", "").startswith(form_name_prefix) for field in form.find_all(["input", "select"])):
            target_form = form
            break
    if target_form is None:
        return None, None, soup

    payload: dict[str, str] = {}
    for field in target_form.find_all("input"):
        name = field.get("name")
        if not name or field.get("type") in ("submit", "checkbox"):
            continue
        payload[name] = field.get("value", "")
    for select in target_form.find_all("select"):
        name = select.get("name")
        if not name:
            continue
        selected = select.find("option", selected=True)
        payload[name] = selected["value"] if selected else select.find("option")["value"]

    return target_form["action"], payload, soup


def parse_active_procedures_page(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    """Parse one page of the "Procesos Vigentes" results table.
    Each result is a 3-cell <tr>: [tipo + numero, detail block, "Mas Datos" link].
    The detail block is free text with fixed labels (Estado, Codigo SIGAF,
    Publicacion, Cierre, Ultima Actualizacion) followed by institucion, then
    category codes ("nombre (12345678)") and finally a free-text description."""
    rows: list[dict[str, str | None]] = []
    detail_links = soup.find_all("a", string=re.compile("M[aá]s Datos"))

    for link in detail_links:
        node = link
        data_row = None
        for _ in range(12):
            node = node.parent
            if node is None:
                break
            if node.name == "tr":
                cells_here = node.find_all("td", recursive=False)
                if len(cells_here) > 1:
                    data_row = node
                    break
        if data_row is None:
            continue

        cells = data_row.find_all("td", recursive=False)
        procedure_and_number = cells[0].get_text(" ", strip=True) if cells else ""
        detail_text = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""

        def find(pattern: str, text: str = detail_text) -> str | None:
            m = re.search(pattern, text)
            return m.group(1).strip() if m else None

        status = find(r"Estado:\s*(.+?)\s*C[oó]digo SIGAF:")
        sigaf_code = find(r"C[oó]digo SIGAF:\s*(.+?)\s*Publicaci[oó]n:")
        if sigaf_code == "#":
            sigaf_code = None  # "#" is the source's placeholder for "no code assigned"

        publication_date = find(r"Publicaci[oó]n:\s*(\d{2}/\d{2}/\d{4})")
        closing_date = find(r"Cierre:\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)?)")
        last_updated = find(r"[UÚ]ltima Actualizaci[oó]n:\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)?)")

        remainder = find(
            r"[UÚ]ltima Actualizaci[oó]n:\s*\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)?\s*(.+)"
        )
        buyer_name, category, description = None, None, None
        if remainder:
            parts = remainder.split(" - ", 1)
            buyer_name = parts[0].strip() if parts else None
            block = parts[1].strip() if len(parts) > 1 else ""

            # Category codes anchor the split (never split on comma: some category
            # names contain their own commas, e.g. "Lubricantes, aceites, grasas...").
            code_pattern = re.compile(r"\((\d{8})\)")
            matches = list(code_pattern.finditer(block))
            if matches:
                segments, cursor = [], 0
                for match in matches:
                    name = block[cursor:match.start()].strip().lstrip(",").strip()
                    segments.append(f"{name} ({match.group(1)})")
                    cursor = match.end()
                category = "; ".join(segments)
                description = block[cursor:].strip().lstrip(",").strip() or None
            else:
                description = block.strip() or None

        procedure_type, procedure_number = None, None
        m = re.match(r"^(.*?)\s+(\d+/\d{4})$", procedure_and_number)
        if m:
            procedure_type, procedure_number = m.group(1), m.group(2)
        else:
            procedure_type = procedure_and_number or None

        rows.append({
            "tipo_procedimiento": procedure_type,
            "numero_proceso": procedure_number,
            "estado": status,
            "codigo_sigaf": sigaf_code,
            "institucion": buyer_name,
            "categoria": category,
            "descripcion": description,
            "fecha_publicacion": publication_date,
            "fecha_cierre": closing_date,
            "ultima_actualizacion": last_updated,
        })

    return rows


def fetch_active_procedures(session: requests.Session) -> list[dict[str, str | None]]:
    """Fetch every "Procesos Vigentes" record from SISCAE: raises the page size to
    100 (from the default 10) and follows the validated pagination pattern
    (portlet link id N corresponds to page N+1, within one block of 10 pages)."""
    session.headers.setdefault("User-Agent", USER_AGENT)

    response = fetch_with_retries(session, "get", BASE_URL)
    action, payload, _ = parse_form(response.text, FORM_NAME)
    if action is None or payload is None:
        raise RuntimeError("Could not locate the results form on the Procesos Vigentes page.")

    payload[f"{FORM_NAME}:resultadosItems"] = "CIEN"
    payload[f"{FORM_NAME}:_link_hidden_"] = ""
    response = fetch_with_retries(session, "post", action, data=payload)

    all_rows: list[dict[str, str | None]] = []
    page_number = 1

    while page_number <= MAX_PAGES:
        action, payload, soup = parse_form(response.text, FORM_NAME)
        if action is None or payload is None:
            break

        page_rows = parse_active_procedures_page(soup)
        all_rows.extend(page_rows)

        page_text = soup.get_text(" ", strip=True)
        match = re.search(r"P[aá]gina\s+(\d+)\s*/\s*(\d+)", page_text)
        if not match:
            break
        current_page, total_pages = int(match.group(1)), int(match.group(2))
        if current_page >= total_pages:
            break

        # Confirmed pattern: to request page (current_page + 1), N = current_page.
        next_link_value = f"{FORM_NAME}:{PORTLET_PREFIX}__id88_{current_page}:{PORTLET_PREFIX}__id89"
        payload[f"{FORM_NAME}:_link_hidden_"] = next_link_value
        response = fetch_with_retries(session, "post", action, data=payload)
        page_number += 1

    return all_rows


def scrape_siscae(period: str) -> dict[str, list[dict[str, Any]]]:
    """Entry point used by the pipeline. Returns a mapping shaped like the CSV-based
    connectors' `source_rows` (logical dataset name -> list of row dicts), so the
    rest of the pipeline (raw storage, staging, mart upsert) needs no changes.

    Only "Procesos Vigentes" is wired up for now. Awarded-process detail (supplier,
    RUC, awarded amount) requires a Mas Datos -> Adjudicacion -> Volver navigation
    that is not reliable yet (SISCAE renders the Adjudicacion tab intermittently)
    and is intentionally left out of this connector until that is fixed.
    """
    session = requests.Session()
    active_rows = fetch_active_procedures(session)
    return {"procesos_vigentes": active_rows}

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from mira_etl.config import SourceConfig

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class HtmlSessionSpec:
    """Configuration for the shared stateful JSF/portlet scraper."""

    base_url: str
    dataset_name: str
    form_name_prefix: str
    portlet_prefix: str
    parser: str = "active_procedures"
    page_size_field_suffix: str = "resultadosItems"
    page_size_value: str = "CIEN"
    link_hidden_field_suffix: str = "_link_hidden_"
    next_link_template: str = (
        "{form_name}:{portlet_prefix}__id88_{current_page}:"
        "{portlet_prefix}__id89"
    )
    page_text_pattern: str = r"P[aá]gina\s+(\d+)\s*/\s*(\d+)"
    max_pages: int = 10
    request_timeout_seconds: int = 45
    max_request_retries: int = 3
    retry_backoff_seconds: int = 5
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_config(cls, config: SourceConfig) -> "HtmlSessionSpec":
        download = config.download
        webforms = download.get("webforms") or {}
        required = {
            "base_url": download.get("base_url"),
            "dataset_name": webforms.get("dataset_name"),
            "form_name_prefix": webforms.get("form_name_prefix"),
            "portlet_prefix": webforms.get("portlet_prefix"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"HTML source '{config.source}' is missing download configuration: "
                + ", ".join(missing)
            )
        return cls(
            **required,
            parser=webforms.get("parser", "active_procedures"),
            page_size_field_suffix=webforms.get("page_size_field_suffix", "resultadosItems"),
            page_size_value=webforms.get("page_size_value", "CIEN"),
            link_hidden_field_suffix=webforms.get("link_hidden_field_suffix", "_link_hidden_"),
            next_link_template=webforms.get("next_link_template", cls.next_link_template),
            page_text_pattern=webforms.get("page_text_pattern", cls.page_text_pattern),
            max_pages=int(webforms.get("max_pages", 10)),
            request_timeout_seconds=int(webforms.get("request_timeout_seconds", 45)),
            max_request_retries=int(webforms.get("max_request_retries", 3)),
            retry_backoff_seconds=int(webforms.get("retry_backoff_seconds", 5)),
            user_agent=webforms.get("user_agent", DEFAULT_USER_AGENT),
        )


def fetch_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout_seconds: int,
    max_retries: int,
    retry_backoff_seconds: int,
    **kwargs: Any,
) -> requests.Response:
    """Execute a source request with configurable retry/backoff."""
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if method == "get":
                return session.get(url, timeout=timeout_seconds, **kwargs)
            return session.post(url, timeout=timeout_seconds, **kwargs)
        except requests.exceptions.RequestException as exc:  # pragma: no cover - network dependent
            last_error = exc
            time.sleep(retry_backoff_seconds * attempt)
    assert last_error is not None
    raise last_error


def parse_form(html: str, form_name_prefix: str) -> tuple[str | None, dict[str, str] | None, BeautifulSoup]:
    """Locate the JSF form matching a field-name prefix and build a submittable payload
    from its current input/select values. These are stateful Java-portlet applications:
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
    """Parse one page rendered by the shared active-procedures template.
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


PARSERS = {
    "active_procedures": parse_active_procedures_page,
}


def fetch_html_dataset(
    session: requests.Session,
    spec: HtmlSessionSpec,
    limit: int | None = None,
) -> list[dict[str, str | None]]:
    """Fetch one configured JSF/portlet dataset, including pagination.

    If `limit` is set, stops paginating as soon as enough rows are collected
    instead of walking every page.
    """
    try:
        parse_page = PARSERS[spec.parser]
    except KeyError as exc:
        raise ValueError(f"Unsupported HTML parser: {spec.parser}") from exc

    session.headers.setdefault("User-Agent", spec.user_agent)

    request_options = {
        "timeout_seconds": spec.request_timeout_seconds,
        "max_retries": spec.max_request_retries,
        "retry_backoff_seconds": spec.retry_backoff_seconds,
    }

    response = fetch_with_retries(session, "get", spec.base_url, **request_options)
    action, payload, _ = parse_form(response.text, spec.form_name_prefix)
    if action is None or payload is None:
        raise RuntimeError(
            f"Could not locate form '{spec.form_name_prefix}' at {spec.base_url}."
        )

    payload[f"{spec.form_name_prefix}:{spec.page_size_field_suffix}"] = spec.page_size_value
    payload[f"{spec.form_name_prefix}:{spec.link_hidden_field_suffix}"] = ""
    response = fetch_with_retries(
        session, "post", urljoin(spec.base_url, action), data=payload, **request_options
    )

    all_rows: list[dict[str, str | None]] = []
    page_number = 1

    while page_number <= spec.max_pages:
        action, payload, soup = parse_form(response.text, spec.form_name_prefix)
        if action is None or payload is None:
            break

        page_rows = parse_page(soup)
        all_rows.extend(page_rows)

        if limit is not None and len(all_rows) >= limit:
            return all_rows[:limit]

        page_text = soup.get_text(" ", strip=True)
        match = re.search(spec.page_text_pattern, page_text)
        if not match:
            break
        current_page, total_pages = int(match.group(1)), int(match.group(2))
        if current_page >= total_pages:
            break

        # Confirmed pattern: to request page (current_page + 1), N = current_page.
        next_link_value = spec.next_link_template.format(
            form_name=spec.form_name_prefix,
            portlet_prefix=spec.portlet_prefix,
            current_page=current_page,
        )
        payload[f"{spec.form_name_prefix}:{spec.link_hidden_field_suffix}"] = next_link_value
        response = fetch_with_retries(
            session, "post", urljoin(spec.base_url, action), data=payload, **request_options
        )
        page_number += 1

    return all_rows


def scrape_html_source(
    config: SourceConfig,
    period: str,
    limit: int | None = None,
    session: requests.Session | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Generic pipeline entry point for configured HTML session sources.

    `limit` caps the number of records fetched -- intended for quick smoke tests
    against a real database. `period` is accepted for the common extractor
    contract; current active-procedure portals expose current state rather than
    a historical period.
    """
    del period
    spec = HtmlSessionSpec.from_config(config)
    active_session = session or requests.Session()
    rows = fetch_html_dataset(active_session, spec, limit=limit)
    return {spec.dataset_name: rows}

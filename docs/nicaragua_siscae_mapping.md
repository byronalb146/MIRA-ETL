# Nicaragua SISCAE -> MIRA Mapping

Este documento traza los campos del modelo minimo MIRA contra el listado de
"Procesos Vigentes" del portal SISCAE de Nicaragua.

Conector:

```text
nicaragua_siscae
```

## Diferencia de mecanismo frente a Costa Rica

A diferencia de `costa_rica_sicop` (descarga un ZIP periodico con CSVs),
`nicaragua_siscae` no tiene API ni archivo descargable: es un sistema HTML con
sesion (arquitectura de portlets Java/JSF, sin documentacion oficial). El
conector abre una sesion, sube el listado a 100 resultados por pagina, y seguido
la paginacion confirmada empiricamente para extraer el listado completo.

Por esto, `config/sources/nicaragua_siscae.json` usa `download.type =
"html_session_scrape"` en vez de `"http_zip"`. Los detalles del formulario y
la paginacion viven en `config/sources/nicaragua_siscae.json`; el motor generico
esta documentado en `docs/html_session_sources.md` y en `src/mira_etl/extract_html.py`
reemplaza a `extract.py` (que sigue siendo exclusivo de fuentes ZIP). El resto
del pipeline (raw -> staging -> mart -> audit) no cambia.

El parametro `--period` no selecciona un archivo historico como en Costa Rica
-- SISCAE solo expone el estado *actual* de los procesos vigentes. `period` se
guarda como etiqueta de la corrida en `audit.etl_runs`, no como filtro de
datos.

## Alcance de esta version del conector

Solo se extrae el listado de **Procesos Vigentes** (activos, sin adjudicar
todavia). La vista de detalle de adjudicacion (proveedor, RUC, monto
adjudicado) requiere una navegacion adicional (Mas Datos -> Adjudicacion ->
Volver) que **no es confiable todavia** -- SISCAE renderiza el boton
"Adjudicacion" de forma intermitente incluso para el mismo proceso en
corridas consecutivas. Se deja fuera de este conector a proposito hasta
resolverlo; ver la seccion "Pendiente" al final.

Como consecuencia, todos los campos de Montos y Proveedor quedan `NULL` en
esta version -- son procesos que, por definicion, aun no tienen adjudicacion.

## Trazabilidad

| Campo MIRA | Origen en SISCAE | Transformacion | Destino |
|---|---|---|---|
| `country_code` | Configuracion del conector | Valor fijo `NI` | `mart.processes.country_code` |
| `source_system` | Configuracion del conector | Valor fijo `SISCAE Nicaragua` | `mart.processes.source_system` |
| `source_record_id` | Codigo SIGAF si existe; si no, `tipo_procedimiento-numero_proceso-institucion` | Codigo SIGAF suele venir vacio (`#`, normalizado a `NULL`), por eso el respaldo compuesto | `mart.processes.source_record_id` |
| `source_url` | `config/sources/nicaragua_siscae.json -> download.base_url` | URL base del listado de vigentes (no existe URL individual por proceso) | `mart.processes.source_url` |
| `extracted_at` | Ejecucion ETL | Timestamp UTC de ejecucion | `mart.processes.extracted_at` |
| `source_last_modified_at` | Bloque de detalle, etiqueta "Ultima Actualizacion:" | Parseo a `timestamptz` | `mart.processes.source_last_modified_at` |
| `connector_version` | `config/sources/nicaragua_siscae.json -> connector_version` | Valor fijo por ahora: `ni-siscae-0.1.0` | `mart.processes.connector_version` |
| `raw_payload` | Fila parseada del listado | JSON con `proceso` | `mart.processes.raw_payload` |
| `raw_payload_hash` | `raw_payload` | SHA-256 estable del JSON ordenado | `mart.processes.raw_payload_hash` |
| `normalisation_status` | Validaciones ETL | `PROCESSED` o `REVIEW_REQUIRED` | `mart.processes.normalisation_status` |
| `normalised_at` | Ejecucion ETL | Timestamp UTC de normalizacion | `mart.processes.normalised_at` |
| `data_quality_status` | Validaciones ETL | `COMPLETE`, `PARTIAL` o `INVALID` | `mart.processes.data_quality_status` |
| `missing_fields` | Validaciones ETL | Lista JSON de campos MIRA faltantes | `mart.processes.missing_fields` |

## Campos Minimos Normalizados

| Grupo PDF | Campo MIRA | Origen en SISCAE | Transformacion | Destino |
|---|---|---|---|---|
| Identificacion | `process_id` | `country_code` + `source_record_id` | ID interno estable `MIRA-NI-{hash}` que une todas las tablas mart | `mart.processes.process_id` |
| Identificacion | `process_number` | Primera celda del listado, parte numerica (ej. `5/2026`) | Copia directa | `mart.processes.process_number` |
| Identificacion | `title` | No existe campo separado -> se usa `descripcion` | SISCAE no distingue titulo de descripcion | `mart.processes.title` |
| Identificacion | `description` | Texto libre tras el ultimo codigo de categoria en el bloque de detalle | Copia directa | `mart.processes.description` |
| Comprador | `buyer_name` | Bloque de detalle, texto entre "Ultima Actualizacion: \<fecha\>" y el separador " - " | Nombre normalizado y deduplicado | `mart.buyers.name_normalised` |
| Comprador | `buyer_id_source` | No expuesto en el registro individual | `NULL` | `mart.buyers.buyer_id_source` |
| Comprador | `buyer_tax_id` | No existe en la fuente | `NULL` | `mart.buyers.buyer_tax_id` |
| Contratacion | `procurement_method` | Primera celda del listado, parte de texto (ej. `LICITACION SELECTIVA`) | Copia directa | `mart.processes.procurement_method` |
| Contratacion | `process_status` | Bloque de detalle, etiqueta "Estado:" | Normaliza con `transform.status_map` de la configuracion de la fuente | `mart.processes.process_status` |
| Contratacion | `source_status` | Bloque de detalle, etiqueta "Estado:" | Valor original de la fuente, sin normalizar | `mart.processes.source_status` |
| Fechas | `publication_date` | Bloque de detalle, etiqueta "Publicacion:" | Parseo a `timestamptz` | `mart.processes.publication_date` |
| Fechas | `closing_date` | Bloque de detalle, etiqueta "Cierre:" | Parseo a `timestamptz` | `mart.processes.closing_date` |
| Fechas | `award_date` | No aplica (proceso vigente, aun sin adjudicar) | No crea adjudicacion | `mart.awards.award_date` |
| Montos | `estimated_amount` | No expuesto en ningun punto de la fuente revisado | `NULL` | `mart.processes.estimated_amount` |
| Montos | `awarded_amount` | No aplica en esta version del conector (ver "Alcance") | No crea adjudicacion | `mart.awards.awarded_amount` |
| Montos | `currency_code` | No aplica en esta version del conector | `NULL` | `mart.processes.currency_code` |
| Proveedor | `supplier_name` | No aplica en esta version del conector | `NULL` | `mart.suppliers.name_normalised` |
| Proveedor | `supplier_id_source` | No aplica en esta version del conector | `NULL` | `mart.suppliers.supplier_id_source` |
| Proveedor | `supplier_tax_id` | No aplica en esta version del conector | `NULL` | `mart.suppliers.supplier_tax_id` |
| Proveedor | `supplier_type` | No existe ningun campo nativo en la fuente | `NULL` | `mart.suppliers.supplier_type` |
| Bien o servicio | `item_description` | Igual que `description` -- no hay desglose de items individuales | Copia directa | `mart.items.item_description` |
| Bien o servicio | `category_source` | Bloque de detalle, fragmentos `"texto (codigo de 8 digitos)"`, tipo UNSPSC | Union de todos los codigos encontrados, separados por `; ` | `mart.items.category_source` |
| Bien o servicio | `category_normalised` | No disponible todavia | `NULL` hasta definir catalogo regional MIRA | `mart.items.category_normalised` |
| Calidad | `data_quality_status` | Validaciones ETL | `COMPLETE`, `PARTIAL`, `INVALID` | `mart.processes.data_quality_status` |

## Datos Adicionales Conservados

El registro fuente completo (todos los campos parseados del listado, incluso
los que no tienen columna normalizada propia) se conserva integro dentro de
`raw_payload`:

```json
{
  "proceso": {
    "tipo_procedimiento": "...",
    "numero_proceso": "...",
    "estado": "...",
    "codigo_sigaf": "...",
    "institucion": "...",
    "categoria": "...",
    "descripcion": "...",
    "fecha_publicacion": "...",
    "fecha_cierre": "...",
    "ultima_actualizacion": "..."
  }
}
```

## Metodologia y limitaciones conocidas

A diferencia del mapeo de Honduras (auditado sobre una descarga completa de
831,680 releases), los valores de ejemplo de este documento provienen de una
muestra manual de decenas de procesos revisados durante el desarrollo del
conector, no de una auditoria estadistica sobre el dataset completo (~422-430
procesos vigentes en un momento dado). No se han calculado porcentajes de
ausencia por campo para Nicaragua todavia.

## Pendiente (fuera de alcance de esta version)

- **Adjudicaciones (proveedor, RUC, monto adjudicado):** el mecanismo de
  extraccion (Mas Datos -> Adjudicacion -> Volver) esta prototipado pero no es
  confiable -- SISCAE no siempre renderiza el boton "Adjudicacion", incluso
  para el mismo proceso en corridas consecutivas. Se integrara en un conector
  separado (`nicaragua_siscae_adjudicados` o una extension de este) una vez
  resuelto.
- **Historico anterior al periodo vigente:** el filtro de año ("Ejercicio")
  del buscador avanzado de SISCAE aun no se ha resuelto; el conector actual
  solo trae el estado presente del sistema.
- `buyer_tax_id`, `buyer_id_source`, `supplier_type`, `category_normalised`,
  `estimated_amount`: no expuestos por la fuente en ningun punto revisado.

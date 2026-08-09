# MIRA ETL

ETL configurable para extraer, validar, transformar y cargar datos de contrataciones publicas al modelo minimo de MIRA.

## Conectores

Costa Rica SICOP (descarga ZIP periodica):

```text
https://dlsaobservatorioprod.blob.core.windows.net/fs-synapse-observatorio-produccion/Zip/{AAAAMM}.zip
```

Nicaragua SISCAE (scraping HTML con sesion, sin API; solo Procesos Vigentes por ahora -- ver `docs/nicaragua_siscae_mapping.md`):

```text
https://www.gestion.nicaraguacompra.gob.ni/siscae/portal/adquisiciones-gestion/busquedaProcedimientosVigentes
```

## Uso

Instalar Python 3.11+ y dependencias:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
```

Ejecutar con ZIP local (Costa Rica):

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source costa_rica_sicop --period 202001 --local-zip 202001.zip
```

Ejecutar descargando desde la fuente (Costa Rica):

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source costa_rica_sicop --period 202001
```

Ejecutar el conector de Nicaragua (no usa `--local-zip`; `--period` es solo una
etiqueta de la corrida, SISCAE siempre trae el estado actual):

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source nicaragua_siscae --period 202607
```

Ejecutar el conector de Nicaragua (no usa `--local-zip`; `--period` es solo una
etiqueta de la corrida, SISCAE siempre trae el estado actual):

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source nicaragua_siscae --period 202607
```

> **Modo de prueba de Costa Rica:** actualmente ese conector está limitado a 2
> contratos para evitar cargas grandes en Supabase. El límite temporal está
> definido por `CONTRACT_LIMIT` en `src/mira_etl/pipeline.py`.

Guatemala se lee incrementalmente con `ijson` y se carga en lotes. El tamaño
del lote y un límite opcional se configuran en
`config/sources/guatemala_guatecompras.json`:

```json
"processing": {
  "batch_size": 250,
  "record_limit": 2
}
```

Usa un número en `record_limit` para una prueba acotada; actualmente Guatemala
también está limitado a 2 registros. `null` procesaría el archivo completo. El
límite temporal `CONTRACT_LIMIT` continúa aplicándose al flujo de Costa Rica.

Crear esquemas/tablas:

```powershell
.venv\Scripts\mira-etl init-db
```

## Flujo

```text
n8n / manual
  -> GitHub Actions workflow_dispatch
  -> Python ETL
  -> Supabase PostgreSQL
     raw -> staging -> mart -> audit
```

## API

La API es de solo lectura y consulta exclusivamente el modelo normalizado de
`mart`. Requiere la misma variable de conexión que el ETL:

```bash
export SUPABASE_DB_URL="postgresql://..."
```

Instala las dependencias:

```bash
python -m pip install -e .
```

En una base existente, aplica únicamente `sql/004_procurements_web_view.sql`
desde el SQL Editor de Supabase o con `psql`; no es necesario recrear tablas:

```bash
psql "$SUPABASE_DB_URL" -f sql/004_procurements_web_view.sql
```

Levanta el servidor local:

```bash
uvicorn mira_etl.api.main:app --reload
```

La página de `web/index.html` se sirve desde la misma aplicación. Ábrela en:

```text
http://localhost:8000/
```

La web consulta la API y permite navegar por país con páginas de 10, 25 o 50
registros. También ofrece búsqueda local y filtro de estado sobre la página
actual; ya no necesita una URL ni una llave pública de Supabase.

Verifica el servicio:

```bash
curl "http://localhost:8000/api/v1/health"
```

Consulta los 20 registros más recientes:

```bash
curl "http://localhost:8000/api/v1/procurements?limit=20"
```

Consulta Guatemala con paginación:

```bash
curl "http://localhost:8000/api/v1/procurements?country=GT&limit=20&offset=0"
```

La documentación interactiva queda disponible en
`http://localhost:8000/docs`.

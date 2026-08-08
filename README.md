# MIRA ETL

ETL configurable para extraer, validar, transformar y cargar datos de contrataciones publicas al modelo minimo de MIRA.

## Primer conector

Costa Rica SICOP:

```text
https://dlsaobservatorioprod.blob.core.windows.net/fs-synapse-observatorio-produccion/Zip/{AAAAMM}.zip
```

## Uso

Instalar Python 3.11+ y dependencias:

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
```

Ejecutar con ZIP local:

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source costa_rica_sicop --period 202001 --local-zip 202001.zip
```

Ejecutar descargando desde la fuente:

```powershell
$env:SUPABASE_DB_URL="postgresql://..."
.venv\Scripts\mira-etl run --source costa_rica_sicop --period 202001
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

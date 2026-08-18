# Seguridad y roles de base de datos

La seguridad se configura manualmente por ambiente. Estas instrucciones no se
ejecutan con `mira-etl init-db`, porque crean usuarios, asignan permisos y
requieren secretos propios de cada despliegue.

## Roles de MIRA-API

`mira_query` ejecuta exclusivamente consultas de lectura sobre las vistas de
`query`. El timeout limita el impacto de una consulta generada demasiado
costosa.

`mira_logger` registra preguntas, respuestas, intentos SQL y contadores de
cuota en `analytics`; no necesita acceso a `mart`, `raw`, `staging` o `audit`.

Ejecutar con un administrador de PostgreSQL:

```sql
create role mira_query with login noinherit;
alter role mira_query set statement_timeout = '5s';
alter role mira_query set default_transaction_read_only = on;
grant usage on schema query to mira_query;
grant select on all tables in schema query to mira_query;
alter default privileges in schema query grant select on tables to mira_query;

create role mira_logger with login noinherit;
grant usage on schema analytics to mira_logger;
grant select, insert, update on all tables in schema analytics to mira_logger;
grant usage, select on all sequences in schema analytics to mira_logger;
alter default privileges in schema analytics
    grant select, insert, update on tables to mira_logger;
alter default privileges in schema analytics
    grant usage, select on sequences to mira_logger;
```

Si los roles ya existen, omitir los dos `create role`.

## Contraseñas

Generar secretos diferentes por rol y ambiente. Nunca guardarlos en este
repositorio:

```sql
alter role mira_query with password '<secreto-query>';
alter role mira_logger with password '<secreto-logger>';
```

MIRA-API utiliza conexiones separadas:

```text
DATABASE_URL=postgresql://mira_query:...@host:5432/database?sslmode=require
DATABASE_URL_LOG=postgresql://mira_logger:...@host:5432/database?sslmode=require
```

## Verificación

Con `mira_query`:

```sql
select * from query.v_process limit 1;       -- debe funcionar
select * from mart.processes;  -- debe fallar
```

Con `mira_logger`, una escritura en `analytics.query_log` debe funcionar y una
lectura de `mart.processes` debe fallar.

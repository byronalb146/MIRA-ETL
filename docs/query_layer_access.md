# Acceso de solo lectura al esquema `query`

`sql/010_query_views.sql` crea las vistas que consume MIRA-API y
`sql/011_query_role.sql` crea los roles sin contrasena. Las contrasenas se
configuran aparte para que ningun secreto quede en el repositorio.

## Pasos, despues de correr `mira-etl init-db` (o el archivo directamente)

1. Generar dos contrasenas fuertes (por ejemplo con el gestor de contrasenas
   del equipo, o `openssl rand -base64 32`) y fijarla en una sesion aparte,
   nunca pegada en un chat ni en un commit:

   ```
   alter role mira_query with password '<pegar aqui la contrasena generada>';
   alter role mira_logger with password '<pegar aqui otra contrasena generada>';
   ```

2. Construir los DSN y guardarlos en el gestor de secretos de MIRA-API:

   ```
   DATABASE_URL=postgresql://mira_query:<contrasena>@<host>:5432/postgres?sslmode=require
   DATABASE_URL_LOG=postgresql://mira_logger:<contrasena>@<host>:5432/postgres?sslmode=require
   ```

## Verificacion rapida

Con ese DSN, confirmar que:

- Un `select * from query.v_process limit 1;` funciona.
- Un `select * from mart.procurement_record_core limit 1;` falla por permisos
  (`permission denied for schema mart`).
- `mira_logger` puede escribir en `analytics`, pero no leer `mart`.

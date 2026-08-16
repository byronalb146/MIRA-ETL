# Acceso de solo lectura al esquema `query`

`sql/003_query_layer.sql` crea el esquema `query` (vistas + indices de
trigrama) que consume MIRA-API. Ese archivo no crea ningun rol ni fija ningun
secreto a proposito -- eso se hace aparte, a mano, para que ninguna contrasena
quede en texto plano en este repositorio.

## Pasos, despues de correr `mira-etl init-db` (o el archivo directamente)

1. Conectarse a la base con un usuario con privilegios suficientes (el mismo
   que corre `init-db`, o el superusuario de Supabase) y crear el rol, sin
   contrasena todavia:

   ```
   create role mira_query with login noinherit;
   ```

   `noinherit` es deliberado: si heredara de `anon`/`authenticated`, tendria
   acceso a `mart.*` via las policies de `sql/002_public_read_access.sql`, y
   la lista blanca del validador de MIRA-API dejaria de ser la unica frontera
   contra ese esquema.

2. Generar una contrasena fuerte (por ejemplo con el gestor de contrasenas
   del equipo, o `openssl rand -base64 32`) y fijarla en una sesion aparte,
   nunca pegada en un chat ni en un commit:

   ```
   alter role mira_query with password '<pegar aqui la contrasena generada>';
   ```

3. Dar acceso de solo lectura al esquema `query` (no a `mart`, `raw`,
   `staging` ni `audit`):

   ```
   grant usage on schema query to mira_query;
   grant select on all tables in schema query to mira_query;
   alter default privileges in schema query grant select on tables to mira_query;
   ```

4. Construir el DSN de solo lectura y guardarlo como `DATABASE_URL` en el
   `.env` de MIRA-API (nunca commiteado, ver `MIRA-API/.env.example`):

   ```
   postgresql://mira_query:<contrasena>@<host>:5432/postgres?sslmode=require
   ```

## Verificacion rapida

Con ese DSN, confirmar que:

- Un `select * from query.v_process limit 1;` funciona.
- Un `select * from mart.procurement_record_core limit 1;` falla por permisos
  (`permission denied for schema mart`). Si no falla, `mira_query` quedo
  heredando de `anon`/`authenticated` por error -- revisar el paso 1.

-- Roles for MIRA-API (see Parte E, matriz de secretos, in the connection doc).
-- Neither role is given a password here -- passwords are secrets and never
-- belong in a committed file. Set them out-of-band once, per environment:
--   alter role mira_query   with password '...';
--   alter role mira_logger  with password '...';
-- and put the resulting DSN in DATABASE_URL / DATABASE_URL_LOG.
--
-- Deliberately NOT done here: revoking anon/authenticated access to mart
-- (sql/002_public_read_access.sql). That access still backs the legacy
-- web/index.html prototype; it comes out only once MIRA-WEB reaches parity.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'mira_query') then
        create role mira_query with login noinherit;
    end if;
end
$$;

-- Read-only, and only on the query schema: no USAGE was ever granted on
-- mart/raw/staging/audit, so there is nothing to revoke there -- a fresh role
-- has zero privileges on a non-public schema until explicitly granted some.
alter role mira_query set statement_timeout = '5s';
alter role mira_query set default_transaction_read_only = on;

grant usage on schema query to mira_query;
grant select on all tables in schema query to mira_query;
alter default privileges in schema query grant select on tables to mira_query;

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'mira_logger') then
        create role mira_logger with login noinherit;
    end if;
end
$$;

-- Schema `analytics` doesn't exist yet (sql/012_analytics.sql creates it and
-- grants mira_logger write access there, alongside the tables it writes to).

-- Read-only role for MIRA-API. Connects directly (LOGIN); NOINHERIT so it
-- can never pick up permissions from any group role it gets added to later.
--
-- Deliberately grants NOTHING on mart/raw/staging/audit. MIRA-API's sqlglot
-- validator (nlq/validator.py) is the FIRST line of defense against reading
-- those schemas; this role having zero visibility into them is the SECOND,
-- and the two must not depend on each other -- a validator bug must not turn
-- into raw mart access for a public, unauthenticated service. See
-- docs/entity_matching.md and docs/query_layer_access.md.
--
-- Must run after 004_query_layer.sql (the query schema and its views have to
-- exist before anything can be granted on them).
--
-- No password is set here -- see docs/query_layer_access.md for that step,
-- which is deliberately kept out of every committed file.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'mira_query') then
        create role mira_query with login noinherit;
    end if;
end
$$;

grant usage on schema query to mira_query;
grant select on all tables in schema query to mira_query;
alter default privileges in schema query grant select on tables to mira_query;

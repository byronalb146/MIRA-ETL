create extension if not exists pg_trgm with schema public;
create extension if not exists unaccent with schema public;

-- unaccent(text) resolves its dictionary through search_path at call time, so
-- Postgres marks it STABLE and refuses to use it in an index expression. This
-- wrapper pins the dictionary by name, which makes it safe to call IMMUTABLE:
-- the tradeoff is that the index must be rebuilt if the "unaccent" dictionary
-- itself is ever redefined (it never is, in practice).
create or replace function mart.f_unaccent(text)
returns text
language sql
immutable
parallel safe
as $$
    select public.unaccent('public.unaccent', coalesce($1, ''))
$$;

-- Search over the original spelling (accents and all) as typed by a citizen
-- who doesn't type accents. Backs ILIKE/similarity search on display_name.
--
-- Deliberately NOT a partial index (`where display_name is not null`): a
-- partial index only gets used by the planner when the query repeats that
-- exact predicate, which an LLM-generated query has no reason to know to
-- add. A GIN trigram index naturally has nothing to index for NULL rows
-- anyway, so dropping the partial clause costs nothing and removes the trap.
create index if not exists idx_suppliers_display_name_trgm
    on mart.suppliers using gin (mart.f_unaccent(upper(display_name)) gin_trgm_ops);

create index if not exists idx_buyers_display_name_trgm
    on mart.buyers using gin (mart.f_unaccent(upper(display_name)) gin_trgm_ops);

-- Search/dedup over the already-normalised name (query.v_duplicate_hints).
create index if not exists idx_suppliers_name_normalised_trgm
    on mart.suppliers using gin (name_normalised gin_trgm_ops);

create index if not exists idx_buyers_name_normalised_trgm
    on mart.buyers using gin (name_normalised gin_trgm_ops);

-- Query-shape indexes that the mart tables didn't need until query.v_process
-- started filtering/sorting on them directly.
create index if not exists idx_process_details_award_date
    on mart.procurement_process_details (award_date);

create index if not exists idx_process_details_procurement_method
    on mart.procurement_process_details (procurement_method);

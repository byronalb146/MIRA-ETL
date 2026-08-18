-- Remove the experimental text-search machinery from development databases.
-- The query surface no longer uses trigram similarity, and generated SQL
-- cannot be expected to reproduce a specialised indexed expression.
drop index if exists mart.idx_suppliers_display_name_trgm;
drop index if exists mart.idx_buyers_display_name_trgm;
drop index if exists mart.idx_suppliers_name_search_trgm;
drop index if exists mart.idx_buyers_name_search_trgm;
drop index if exists mart.idx_suppliers_name_normalised_trgm;
drop index if exists mart.idx_buyers_name_normalised_trgm;
drop function if exists mart.f_unaccent(text);

-- Date filtering/ranges are common query shapes and use a normal B-tree.
drop index if exists mart.idx_process_details_award_date;

create index if not exists idx_procurement_awards_award_date
    on mart.procurement_awards (award_date);

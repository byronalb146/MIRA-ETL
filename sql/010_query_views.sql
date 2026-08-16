-- The only surface MIRA-API is allowed to query (see mira_query role in
-- 011_query_role.sql and MIRA-API's nlq/validator.py ALLOWED_RELATIONS,
-- which must name exactly these five views). raw_payload never appears here.
create schema if not exists query;

-- One row per process. A process can have several buyers or suppliers
-- (consortiums, joint tenders); they are aggregated into arrays instead of
-- fanned out, so joining buyers and suppliers here can never produce a
-- spurious cross-product between two unrelated lists.
create or replace view query.v_process as
select
    rc.process_id,
    rc.country_code,
    rc.source_system,
    rc.grain,
    rc.data_quality_status,
    rc.normalised_at,
    pd.process_number,
    pd.title,
    pd.description,
    pd.procurement_method,
    pd.process_status,
    pd.source_status,
    pd.publication_date,
    pd.closing_date,
    pd.award_date,
    pd.estimated_amount,
    pd.awarded_amount,
    pd.currency_code,
    buyers.buyer_ids,
    buyers.buyer_display_names,
    suppliers.supplier_ids,
    suppliers.supplier_display_names,
    itd.item_description,
    itd.category_source,
    itd.category_normalised
from mart.procurement_record_core rc
join mart.procurement_process_details pd on pd.process_id = rc.process_id
left join mart.procurement_item_details itd on itd.process_id = rc.process_id
left join lateral (
    select
        array_agg(b.buyer_id order by b.buyer_id) as buyer_ids,
        array_agg(coalesce(b.display_name, b.name_normalised) order by b.buyer_id)
            as buyer_display_names
    from mart.procurement_buyer_details pbd
    join mart.buyers b on b.buyer_id = pbd.buyer_id
    where pbd.process_id = rc.process_id
) buyers on true
left join lateral (
    select
        array_agg(s.supplier_id order by s.supplier_id) as supplier_ids,
        array_agg(coalesce(s.display_name, s.name_normalised) order by s.supplier_id)
            as supplier_display_names
    from mart.procurement_supplier_details psd
    join mart.suppliers s on s.supplier_id = psd.supplier_id
    where psd.process_id = rc.process_id
) suppliers on true;

create or replace view query.v_buyers as
select
    b.buyer_id,
    b.country_code,
    b.source_system,
    b.display_name,
    b.name_normalised,
    b.buyer_tax_id
from mart.buyers b;

create or replace view query.v_suppliers as
select
    s.supplier_id,
    s.country_code,
    s.source_system,
    s.display_name,
    s.name_normalised,
    s.supplier_tax_id,
    s.supplier_type
from mart.suppliers s;

-- Candidate near-duplicate entities within the same country: same normalised
-- name family (trigram similarity) but not byte-identical, so they were not
-- auto-merged by matching.normalise_name. See docs/entity_matching.md --
-- these are surfaced for review, never merged automatically.
create or replace view query.v_duplicate_hints as
select
    'buyer'::text as entity_type,
    a.buyer_id as entity_id_a,
    b.buyer_id as entity_id_b,
    a.country_code,
    a.display_name as display_name_a,
    b.display_name as display_name_b,
    similarity(a.name_normalised, b.name_normalised) as name_similarity
from mart.buyers a
join mart.buyers b
    on a.country_code = b.country_code
    and a.buyer_id < b.buyer_id
    and a.name_normalised is not null
    and b.name_normalised is not null
    and a.name_normalised % b.name_normalised
where similarity(a.name_normalised, b.name_normalised) >= 0.6
union all
select
    'supplier'::text as entity_type,
    a.supplier_id as entity_id_a,
    b.supplier_id as entity_id_b,
    a.country_code,
    a.display_name as display_name_a,
    b.display_name as display_name_b,
    similarity(a.name_normalised, b.name_normalised) as name_similarity
from mart.suppliers a
join mart.suppliers b
    on a.country_code = b.country_code
    and a.supplier_id < b.supplier_id
    and a.name_normalised is not null
    and b.name_normalised is not null
    and a.name_normalised % b.name_normalised
where similarity(a.name_normalised, b.name_normalised) >= 0.6;

-- How much data exists per country/source and how complete/fresh it is.
create or replace view query.v_coverage as
select
    rc.country_code,
    rc.source_system,
    rc.grain,
    count(*) as process_count,
    count(*) filter (where rc.data_quality_status = 'COMPLETE') as complete_count,
    count(*) filter (where rc.data_quality_status = 'PARTIAL') as partial_count,
    count(*) filter (where rc.data_quality_status = 'INVALID') as invalid_count,
    count(*) filter (where rc.data_quality_status = 'DUPLICATE') as duplicate_count,
    min(pd.award_date) as earliest_award_date,
    max(pd.award_date) as latest_award_date,
    max(rc.normalised_at) as last_normalised_at
from mart.procurement_record_core rc
left join mart.procurement_process_details pd on pd.process_id = rc.process_id
group by rc.country_code, rc.source_system, rc.grain;

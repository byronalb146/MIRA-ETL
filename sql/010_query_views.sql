-- The only surface MIRA-API is allowed to query (see mira_query role in
-- 011_query_role.sql and MIRA-API's nlq/validator.py ALLOWED_RELATIONS,
-- which must allow exactly the citizen-facing views below). raw_payload never
-- appears here.
create schema if not exists query;

-- Remove development-only views that are not part of the citizen-facing
-- query surface.
drop view if exists query.v_duplicate_hints;
drop view if exists query.v_coverage;
drop view if exists query.v_process_suppliers;
drop view if exists query.v_award_suppliers;
drop view if exists query.v_award_items;
drop view if exists query.v_awards;
drop view if exists query.v_items;
drop view if exists query.v_process_buyers;
drop view if exists query.v_process;
drop view if exists query.v_buyers;
drop view if exists query.v_suppliers;

-- One row per procurement process. Buyer and supplier relationships live in
-- separate bridge views, preventing an accidental buyer x supplier product.
create or replace view query.v_process as
select
    rc.process_id,
    rc.country_code,
    rc.source_system,
    rc.data_quality_status,
    rc.source_url,
    rc.extracted_at,
    rc.source_last_modified_at,
    rc.normalised_at,
    rc.missing_fields,
    pd.process_number,
    pd.title,
    pd.description,
    pd.procurement_method,
    pd.process_status,
    pd.source_status,
    pd.publication_date,
    pd.closing_date,
    pd.estimated_amount,
    pd.currency_code
from mart.procurement_record_core rc
join mart.procurement_process_details pd on pd.process_id = rc.process_id
;

create or replace view query.v_buyers as
select
    b.buyer_id,
    b.country_code,
    b.source_system,
    b.name_normalised,
    b.buyer_tax_id
from mart.buyers b;

create or replace view query.v_suppliers as
select
    s.supplier_id,
    s.country_code,
    s.source_system,
    s.name_normalised,
    s.supplier_tax_id,
    s.supplier_type
from mart.suppliers s;

-- Explicit bridge views keep the one-to-many relationships queryable without
-- arrays or a buyer x supplier cross-product.
create or replace view query.v_process_buyers as
select
    process_id,
    buyer_id
from mart.procurement_buyer_details;

create or replace view query.v_items as
select
    item_id,
    process_id,
    source_item_id,
    line_number,
    item_description,
    category_source,
    category_normalised
from mart.procurement_item_details;

create or replace view query.v_awards as
select
    award_id,
    process_id,
    source_award_id,
    award_date,
    awarded_amount,
    currency_code
from mart.procurement_awards;

create or replace view query.v_award_items as
select
    award_id,
    item_id
from mart.procurement_award_items;

create or replace view query.v_award_suppliers as
select
    award_id,
    supplier_id
from mart.procurement_award_suppliers;

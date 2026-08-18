-- Indexes used by ETL relationship lookups and citizen-facing query shapes.
-- Analytics log tables deliberately have no secondary indexes; quota_counters
-- already has the primary-key index required by its runtime read/update path.
create index if not exists idx_mart_record_core_country
    on mart.procurement_record_core (country_code);

create index if not exists idx_procurement_items_process
    on mart.procurement_item_details (process_id);

create index if not exists idx_procurement_awards_process
    on mart.procurement_awards (process_id);

create index if not exists idx_procurement_awards_award_date
    on mart.procurement_awards (award_date);

create index if not exists idx_award_suppliers_supplier
    on mart.procurement_award_suppliers (supplier_id);

create index if not exists idx_buyer_details_buyer_id
    on mart.procurement_buyer_details (buyer_id);

create index if not exists idx_buyers_country
    on mart.buyers (country_code);

create index if not exists idx_suppliers_country
    on mart.suppliers (country_code);

create index if not exists idx_audit_validation_results_run
    on audit.validation_results (run_id, severity, rule_code);

-- One row per procurement process. Items, awards, buyers, and suppliers are
-- exposed separately so joins never multiply monetary values accidentally.
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
join mart.procurement_process_details pd on pd.process_id = rc.process_id;

create or replace view query.v_buyers as
select
    buyer_id,
    country_code,
    source_system,
    name_normalised,
    buyer_tax_id
from mart.buyers;

create or replace view query.v_suppliers as
select
    supplier_id,
    country_code,
    source_system,
    name_normalised,
    supplier_tax_id,
    supplier_type
from mart.suppliers;

create or replace view query.v_process_buyers as
select process_id, buyer_id
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
select award_id, item_id
from mart.procurement_award_items;

create or replace view query.v_award_suppliers as
select award_id, supplier_id
from mart.procurement_award_suppliers;

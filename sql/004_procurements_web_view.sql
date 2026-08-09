-- Read model for the MIRA API. It exposes normalized mart fields only and
-- deliberately excludes raw_payload, hashes, and ETL/audit internals.

create or replace view mart.v_procurements_web as
select
    core.process_id,
    core.country_code,
    core.source_system,
    process.process_number,
    process.title,
    process.description,
    buyer.buyer_name,
    buyer.buyer_id_source,
    buyer.buyer_tax_id,
    process.procurement_method,
    process.process_status,
    process.publication_date,
    process.closing_date,
    process.award_date,
    process.estimated_amount,
    process.awarded_amount,
    process.currency_code,
    supplier.supplier_name,
    supplier.supplier_id_source,
    supplier.supplier_tax_id,
    supplier.supplier_type,
    item.item_description,
    item.category_source,
    core.data_quality_status,
    core.source_url
from mart.procurement_record_core as core
left join mart.procurement_process_details as process
    on process.process_id = core.process_id
left join mart.procurement_buyer_details as buyer
    on buyer.process_id = core.process_id
left join mart.procurement_supplier_details as supplier
    on supplier.process_id = core.process_id
left join mart.procurement_item_details as item
    on item.process_id = core.process_id;

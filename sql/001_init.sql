create schema if not exists raw;
create schema if not exists staging;
create schema if not exists mart;
create schema if not exists audit;

create table if not exists audit.etl_runs (
    id bigserial primary key,
    pipeline_name text,
    source text not null,
    period text not null,
    connector_version text not null,
    status text not null check (status in ('RUNNING', 'SUCCESS', 'ERROR')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    error_message text
);

alter table audit.etl_runs add column if not exists pipeline_name text;
alter table audit.etl_runs add column if not exists source text;
alter table audit.etl_runs add column if not exists period text;
alter table audit.etl_runs add column if not exists connector_version text;
alter table audit.etl_runs add column if not exists finished_at timestamptz;
alter table audit.etl_runs add column if not exists error_message text;

create table if not exists audit.etl_row_counts (
    row_count_id bigserial primary key,
    run_id bigint not null references audit.etl_runs(id),
    layer_name text not null,
    table_name text not null,
    row_count bigint not null,
    created_at timestamptz not null default now()
);

create table if not exists audit.etl_errors (
    error_id bigserial primary key,
    run_id bigint references audit.etl_runs(id),
    source text,
    period text,
    filename text,
    row_number bigint,
    error_message text not null,
    payload jsonb,
    created_at timestamptz not null default now()
);

create table if not exists raw.source_files (
    source_file_id bigserial primary key,
    run_id bigint not null references audit.etl_runs(id),
    source text not null,
    period text not null,
    filename text not null,
    file_hash text not null,
    row_count bigint not null,
    loaded_at timestamptz not null default now()
);

create table if not exists raw.source_rows (
    source_row_id bigserial primary key,
    run_id bigint not null references audit.etl_runs(id),
    source_file_id bigint not null references raw.source_files(source_file_id),
    row_number bigint not null,
    payload jsonb not null,
    loaded_at timestamptz not null default now()
);

create table if not exists staging.normalized_candidates (
    candidate_id bigserial primary key,
    run_id bigint not null references audit.etl_runs(id),
    source text not null,
    period text not null,
    source_record_id text not null,
    raw_payload_hash text not null,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_raw_source_rows_payload_gin
    on raw.source_rows using gin (payload);

create index if not exists idx_staging_candidates_payload_gin
    on staging.normalized_candidates using gin (payload);

create table if not exists mart.procurement_record_core (
    process_id text primary key,
    country_code text not null,
    source_system text not null,
    source_record_id text not null,
    source_url text,
    extracted_at timestamptz not null,
    source_last_modified_at timestamptz,
    connector_version text not null,
    raw_payload jsonb not null,
    raw_payload_hash text not null,
    normalisation_status text not null check (
        normalisation_status in ('PENDING', 'PROCESSED', 'ERROR', 'REVIEW_REQUIRED')
    ),
    normalised_at timestamptz not null,
    data_quality_status text not null check (
        data_quality_status in ('COMPLETE', 'PARTIAL', 'INVALID', 'DUPLICATE')
    ),
    missing_fields jsonb not null default '[]'::jsonb,

    unique (source_system, source_record_id, raw_payload_hash)
);

create table if not exists mart.procurement_process_details (
    process_id text primary key references mart.procurement_record_core(process_id),
    process_number text,
    title text,
    description text,
    procurement_method text,
    process_status text check (
        process_status is null or process_status in (
            'PLANNED', 'PUBLISHED', 'OPEN', 'EVALUATION', 'AWARDED',
            'CONTRACTED', 'COMPLETED', 'CANCELLED', 'DESERTED', 'SUSPENDED'
        )
    ),
    source_status text,
    publication_date timestamptz,
    closing_date timestamptz,
    award_date timestamptz,
    estimated_amount numeric,
    awarded_amount numeric,
    currency_code text
);

create table if not exists mart.procurement_buyer_details (
    process_id text primary key references mart.procurement_record_core(process_id),
    buyer_name text,
    buyer_id_source text,
    buyer_tax_id text
);

create table if not exists mart.procurement_supplier_details (
    process_id text primary key references mart.procurement_record_core(process_id),
    supplier_name text,
    supplier_id_source text,
    supplier_tax_id text,
    supplier_type text check (
        supplier_type is null or supplier_type in (
            'PERSON', 'COMPANY', 'CONSORTIUM', 'NONPROFIT',
            'PUBLIC_ENTITY', 'FOREIGN_SUPPLIER', 'UNKNOWN'
        )
    )
);

create table if not exists mart.procurement_item_details (
    process_id text primary key references mart.procurement_record_core(process_id),
    item_description text,
    category_source text,
    category_normalised text
);

create table if not exists audit.validation_results (
    validation_id bigserial primary key,
    run_id bigint not null references audit.etl_runs(id),
    source text not null,
    period text not null,
    source_record_id text,
    raw_payload_hash text,
    rule_code text not null,
    severity text not null check (severity in ('ERROR', 'WARNING', 'INFO')),
    field_name text,
    raw_value text,
    normalised_value text,
    message text not null,
    payload jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_mart_record_core_source_record
    on mart.procurement_record_core (source_system, source_record_id);

create index if not exists idx_mart_process_details_process_number
    on mart.procurement_process_details (process_number);

create index if not exists idx_mart_supplier_details_tax_id
    on mart.procurement_supplier_details (supplier_tax_id);

create index if not exists idx_audit_validation_results_run
    on audit.validation_results (run_id, severity, rule_code);

-- Dimension tables resolve the same supplier or buyer across procurement
-- processes to one stable entity. See docs/entity_matching.md.

create table if not exists mart.suppliers (
    supplier_id bigserial primary key,
    country_code text not null,
    source_system text not null,
    supplier_tax_id text,
    supplier_id_source text,
    supplier_name text,
    name_normalised text,
    supplier_type text check (
        supplier_type is null or supplier_type in (
            'PERSON', 'COMPANY', 'CONSORTIUM', 'NONPROFIT',
            'PUBLIC_ENTITY', 'FOREIGN_SUPPLIER', 'UNKNOWN'
        )
    ),
    match_method text not null check (
        match_method in ('TAX_ID', 'SOURCE_ID', 'NAME_EXACT_NORMALISED', 'UNMATCHED')
    ),
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

create index if not exists idx_suppliers_country_tax_id
    on mart.suppliers (country_code, supplier_tax_id)
    where supplier_tax_id is not null;

create index if not exists idx_suppliers_country_source_id
    on mart.suppliers (country_code, source_system, supplier_id_source)
    where supplier_id_source is not null;

create index if not exists idx_suppliers_country_name_normalised
    on mart.suppliers (country_code, name_normalised)
    where name_normalised is not null;

create table if not exists mart.buyers (
    buyer_id bigserial primary key,
    country_code text not null,
    source_system text not null,
    buyer_tax_id text,
    buyer_id_source text,
    buyer_name text,
    name_normalised text,
    match_method text not null check (
        match_method in ('TAX_ID', 'SOURCE_ID', 'NAME_EXACT_NORMALISED', 'UNMATCHED')
    ),
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

create index if not exists idx_buyers_country_tax_id
    on mart.buyers (country_code, buyer_tax_id)
    where buyer_tax_id is not null;

create index if not exists idx_buyers_country_source_id
    on mart.buyers (country_code, source_system, buyer_id_source)
    where buyer_id_source is not null;

create index if not exists idx_buyers_country_name_normalised
    on mart.buyers (country_code, name_normalised)
    where name_normalised is not null;

alter table mart.procurement_supplier_details
    add column if not exists supplier_id bigint references mart.suppliers(supplier_id);

alter table mart.procurement_buyer_details
    add column if not exists buyer_id bigint references mart.buyers(buyer_id);

create index if not exists idx_supplier_details_supplier_id
    on mart.procurement_supplier_details (supplier_id);

create index if not exists idx_buyer_details_buyer_id
    on mart.procurement_buyer_details (buyer_id);

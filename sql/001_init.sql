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

create index if not exists idx_mart_record_core_country
    on mart.procurement_record_core (country_code);

create index if not exists idx_mart_record_core_country_process
    on mart.procurement_record_core (country_code, process_id);

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
    name_normalised text,
    supplier_type text check (
        supplier_type is null or supplier_type in (
            'PERSON', 'COMPANY', 'CONSORTIUM', 'NONPROFIT',
            'PUBLIC_ENTITY', 'FOREIGN_SUPPLIER', 'UNKNOWN'
        )
    )
);

create table if not exists mart.buyers (
    buyer_id bigserial primary key,
    country_code text not null,
    source_system text not null,
    buyer_tax_id text,
    buyer_id_source text,
    name_normalised text
);

create table if not exists mart.procurement_buyer_details (
    process_id text primary key references mart.procurement_record_core(process_id),
    buyer_id bigint not null references mart.buyers(buyer_id)
);

-- A procurement process/adjudication can be related to multiple suppliers.
create table if not exists mart.procurement_supplier_details (
    process_id text not null references mart.procurement_record_core(process_id),
    supplier_id bigint not null references mart.suppliers(supplier_id),
    primary key (process_id, supplier_id)
);

create index if not exists idx_supplier_details_supplier_id
    on mart.procurement_supplier_details (supplier_id);

create index if not exists idx_buyer_details_buyer_id
    on mart.procurement_buyer_details (buyer_id);

create index if not exists idx_buyers_country
    on mart.buyers (country_code);

-- Small, exact summary consumed by the public website. It is refreshed by
-- the ETL after every successful country load, so browsers never COUNT the
-- large mart tables directly.
create table if not exists mart.web_country_stats (
    country_code text primary key,
    process_count bigint not null,
    buyer_count bigint not null,
    refreshed_at timestamptz not null default now()
);

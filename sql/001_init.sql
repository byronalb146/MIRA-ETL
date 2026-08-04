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

create table if not exists mart.procurement_records (
    mart_record_id bigserial primary key,

    process_id text not null,
    process_number text,
    title text,
    description text,

    buyer_name text,
    buyer_id_source text,
    buyer_tax_id text,

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
    currency_code text,

    supplier_name text,
    supplier_id_source text,
    supplier_tax_id text,
    supplier_type text check (
        supplier_type is null or supplier_type in (
            'PERSON', 'COMPANY', 'CONSORTIUM', 'NONPROFIT',
            'PUBLIC_ENTITY', 'FOREIGN_SUPPLIER', 'UNKNOWN'
        )
    ),

    item_description text,
    category_source text,
    category_normalised text,

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
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique (source_system, source_record_id, raw_payload_hash)
);

create index if not exists idx_raw_source_rows_payload_gin
    on raw.source_rows using gin (payload);

create index if not exists idx_staging_candidates_payload_gin
    on staging.normalized_candidates using gin (payload);

create index if not exists idx_mart_procurement_country_period
    on mart.procurement_records (country_code, publication_date);

create index if not exists idx_mart_procurement_process_number
    on mart.procurement_records (process_number);

create index if not exists idx_mart_procurement_supplier_tax_id
    on mart.procurement_records (supplier_tax_id);

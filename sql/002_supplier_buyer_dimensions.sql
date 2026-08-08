-- Adds dimension tables for suppliers and buyers, so the same entity across
-- multiple procurement processes resolves to one stable row instead of
-- repeating name/tax_id on every process. See docs/entity_matching.md for the
-- three-tier matching strategy and its accepted trade-offs.

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

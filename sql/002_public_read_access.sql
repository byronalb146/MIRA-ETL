-- Enables public, read-only access to the mart layer. The ETL writes through
-- the direct PostgreSQL connection; raw, staging and audit remain private.

alter table mart.procurement_record_core enable row level security;
alter table mart.procurement_process_details enable row level security;
alter table mart.procurement_buyer_details enable row level security;
alter table mart.procurement_supplier_details enable row level security;
alter table mart.procurement_item_details enable row level security;
alter table mart.suppliers enable row level security;
alter table mart.buyers enable row level security;

grant usage on schema mart to anon, authenticated;
grant select on
    mart.procurement_record_core,
    mart.procurement_process_details,
    mart.procurement_buyer_details,
    mart.procurement_supplier_details,
    mart.procurement_item_details,
    mart.suppliers,
    mart.buyers
to anon, authenticated;

drop policy if exists "Public read access" on mart.procurement_record_core;
create policy "Public read access" on mart.procurement_record_core
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.procurement_process_details;
create policy "Public read access" on mart.procurement_process_details
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.procurement_buyer_details;
create policy "Public read access" on mart.procurement_buyer_details
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.procurement_supplier_details;
create policy "Public read access" on mart.procurement_supplier_details
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.procurement_item_details;
create policy "Public read access" on mart.procurement_item_details
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.suppliers;
create policy "Public read access" on mart.suppliers
    for select to anon, authenticated using (true);
drop policy if exists "Public read access" on mart.buyers;
create policy "Public read access" on mart.buyers
    for select to anon, authenticated using (true);

-- No write policies are granted to anon or authenticated.

-- Read-only group role for consumers that query the mart layer.
-- Grant this role to a login role instead of assigning credentials here.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'mira_query') then
        create role mira_query nologin;
    end if;
end
$$;

grant usage on schema mart to mira_query;
grant select on all tables in schema mart to mira_query;

-- Keep tables created later in the mart layer readable by this role. These
-- defaults apply to objects created by the role that runs this script.
alter default privileges in schema mart
    grant select on tables to mira_query;

drop policy if exists "MIRA query read access" on mart.procurement_record_core;
create policy "MIRA query read access" on mart.procurement_record_core
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.procurement_process_details;
create policy "MIRA query read access" on mart.procurement_process_details
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.procurement_buyer_details;
create policy "MIRA query read access" on mart.procurement_buyer_details
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.procurement_supplier_details;
create policy "MIRA query read access" on mart.procurement_supplier_details
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.procurement_item_details;
create policy "MIRA query read access" on mart.procurement_item_details
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.suppliers;
create policy "MIRA query read access" on mart.suppliers
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.buyers;
create policy "MIRA query read access" on mart.buyers
    for select to mira_query using (true);
drop policy if exists "MIRA query read access" on mart.web_country_stats;
create policy "MIRA query read access" on mart.web_country_stats
    for select to mira_query using (true);

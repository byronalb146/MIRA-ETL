-- Esquema de solo lectura que consume MIRA-API. Nunca se escribe desde el
-- pipeline de este repo; solo lee mart.* y audit.etl_runs / etl_row_counts.
--
-- No incluye ninguna migracion contra mart.* (nada de alter/drop/delete/update
-- en tablas existentes): solo crea objetos nuevos (schema, vistas, indices).
-- Es seguro correr `mira-etl init-db` de nuevo con este archivo.
--
-- El rol de solo lectura para MIRA-API (mira_query) NO se crea aqui a
-- proposito -- ver docs/query_layer_access.md para ese paso, que involucra
-- fijar un secreto y no debe vivir en un archivo versionado.
--
-- Pendiente documentado en MIRA-API/docs/proposed-query-schema.md: la columna
-- `grain` (PROCESS vs LINE_ITEM) todavia no existe en
-- mart.procurement_record_core, asi que v_process la expone como NULL en vez
-- de adivinarla por country_code -- mentir en silencio es peor que admitir
-- que el dato no esta. Se agrega en una migracion aparte cuando cada conector
-- la setee explicitamente.

create extension if not exists pg_trgm;

create schema if not exists query;

-- ----------------------------------------------------------------------------
-- v_process: grano de proceso. buyer_id/supplier_id solo se llenan cuando hay
-- exactamente un comprador/proveedor (buyer_count = 1 / supplier_count = 1);
-- si hay mas, quedan en NULL y el conteo real queda en *_count. Evita el
-- fanout de convertir un proceso en varias filas cuando tiene N proveedores o
-- compradores (mart.procurement_buyer_details y procurement_supplier_details
-- son 1-a-muchos desde MIRA-ETL commit d483009 / ab1bed2). Ver
-- query.v_process_buyers / v_process_suppliers para no perder esos casos.
-- ----------------------------------------------------------------------------
do $migration$
begin
if to_regclass('query.v_process') is null then
create view query.v_process as
select
    core.process_id,
    core.country_code,
    core.source_system,
    null::text as grain,                 -- pendiente: mart.procurement_record_core no lo tiene todavia
    core.data_quality_status,
    core.missing_fields,
    core.extracted_at,

    proc.process_number,
    proc.title,
    proc.description,
    proc.procurement_method,
    proc.process_status,
    proc.source_status,
    proc.publication_date,
    proc.closing_date,
    proc.award_date,
    proc.estimated_amount,
    proc.awarded_amount,
    proc.currency_code,
    date_trunc('month', proc.award_date)::date as award_month,

    case when buyer_fanout.buyer_count = 1 then buyer_single.buyer_id end
        as buyer_id,
    case when buyer_fanout.buyer_count = 1 then buyer_single.name_normalised end
        as buyer_name,
    case when buyer_fanout.buyer_count = 1 then buyer_single.name_normalised end
        as buyer_name_normalised,
    case when buyer_fanout.buyer_count = 1 then buyer_single.buyer_tax_id end
        as buyer_tax_id,
    coalesce(buyer_fanout.buyer_count, 0) as buyer_count,

    case when supplier_fanout.supplier_count = 1 then supplier_single.supplier_id end
        as supplier_id,
    case when supplier_fanout.supplier_count = 1 then supplier_single.name_normalised end
        as supplier_name,
    case when supplier_fanout.supplier_count = 1 then supplier_single.name_normalised end
        as supplier_name_normalised,
    case when supplier_fanout.supplier_count = 1 then supplier_single.supplier_tax_id end
        as supplier_tax_id,
    case when supplier_fanout.supplier_count = 1 then supplier_single.supplier_type end
        as supplier_type,
    coalesce(supplier_fanout.supplier_count, 0) as supplier_count,

    item.item_description,
    item.category_source,
    item.category_normalised,
    -- Las columnas nuevas deben agregarse al final: PostgreSQL no permite que
    -- CREATE OR REPLACE VIEW inserte una columna entre columnas existentes.
    core.source_url
from mart.procurement_record_core core
join mart.procurement_process_details proc using (process_id)
left join mart.procurement_item_details item using (process_id)
left join (
    select process_id, count(*) as buyer_count
    from mart.procurement_buyer_details
    group by process_id
) buyer_fanout using (process_id)
left join lateral (
    select b.*
    from mart.procurement_buyer_details bd
    join mart.buyers b on b.buyer_id = bd.buyer_id
    where bd.process_id = core.process_id
    limit 1
) buyer_single on buyer_fanout.buyer_count = 1
left join (
    select process_id, count(*) as supplier_count
    from mart.procurement_supplier_details
    group by process_id
) supplier_fanout using (process_id)
left join lateral (
    select s.*
    from mart.procurement_supplier_details sd
    join mart.suppliers s on s.supplier_id = sd.supplier_id
    where sd.process_id = core.process_id
    limit 1
) supplier_single on supplier_fanout.supplier_count = 1;
end if;
end $migration$;

-- ----------------------------------------------------------------------------
-- Relacion completa proceso <-> comprador/proveedor, sin aplanar. Es lo que
-- responde correctamente "cuantos contratos gano X" cuando *_count > 1 en
-- v_process.
-- ----------------------------------------------------------------------------
do $migration$
begin
if to_regclass('query.v_process_buyers') is null then
create view query.v_process_buyers as
select
    bd.process_id,
    b.buyer_id,
    b.name_normalised as buyer_name,
    b.buyer_tax_id
from mart.procurement_buyer_details bd
join mart.buyers b on b.buyer_id = bd.buyer_id;
end if;
end $migration$;

do $migration$
begin
if to_regclass('query.v_process_suppliers') is null then
create view query.v_process_suppliers as
select
    sd.process_id,
    s.supplier_id,
    s.name_normalised as supplier_name,
    s.supplier_tax_id,
    s.supplier_type
from mart.procurement_supplier_details sd
join mart.suppliers s on s.supplier_id = sd.supplier_id;
end if;
end $migration$;

-- ----------------------------------------------------------------------------
-- v_buyers / v_suppliers: un candidato por entidad, con su conteo REAL. Nunca
-- fusionar entidades parecidas aqui -- ver el caso Karro/Carro en
-- MIRA-API/docs/proposed-query-schema.md. name_normalised sirve como
-- display_name: no hay (ni hace falta) un campo de grafia original.
-- ----------------------------------------------------------------------------
do $migration$
begin
if to_regclass('query.v_buyers') is null then
create view query.v_buyers as
select
    b.buyer_id as entity_id,
    b.country_code,
    b.name_normalised as display_name,
    b.name_normalised,
    b.buyer_tax_id as tax_id,
    count(bd.process_id) as record_count
from mart.buyers b
left join mart.procurement_buyer_details bd on bd.buyer_id = b.buyer_id
group by b.buyer_id, b.country_code, b.name_normalised, b.buyer_tax_id;
end if;
end $migration$;

do $migration$
begin
if to_regclass('query.v_suppliers') is null then
create view query.v_suppliers as
select
    s.supplier_id as entity_id,
    s.country_code,
    s.name_normalised as display_name,
    s.name_normalised,
    s.supplier_tax_id as tax_id,
    s.supplier_type,
    count(sd.process_id) as record_count
from mart.suppliers s
left join mart.procurement_supplier_details sd on sd.supplier_id = s.supplier_id
group by s.supplier_id, s.country_code, s.name_normalised, s.supplier_tax_id, s.supplier_type;
end if;
end $migration$;

-- ----------------------------------------------------------------------------
-- Indices de trigrama. Sin esto, la resolucion de entidades de MIRA-API no es
-- alcanzable en tiempo razonable sobre la dimension completa.
-- ----------------------------------------------------------------------------
create index if not exists idx_buyers_name_trgm
    on mart.buyers using gin (name_normalised gin_trgm_ops);

create index if not exists idx_suppliers_name_trgm
    on mart.suppliers using gin (name_normalised gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- v_duplicate_hints: pares de nombres parecidos dentro del mismo pais, con
-- senales de por que podrian ser el mismo actor mal escrito dos veces. Nunca
-- se usa para fusionar entidades -- solo para advertir (POSSIBLE_DUPLICATE_ENTITY
-- en el contrato de respuesta de MIRA-API).
-- ----------------------------------------------------------------------------
do $migration$
begin
if to_regclass('query.v_duplicate_hints') is null then
create view query.v_duplicate_hints as
select
    'supplier'::text as entity_type,
    a.supplier_id as entity_id_a,
    b.supplier_id as entity_id_b,
    a.country_code,
    a.name_normalised as name_a,
    b.name_normalised as name_b,
    similarity(a.name_normalised, b.name_normalised) as name_similarity,
    (a.supplier_tax_id is null or b.supplier_tax_id is null) as missing_tax_id
from mart.suppliers a
join mart.suppliers b
    on a.country_code = b.country_code
    and a.supplier_id < b.supplier_id
    and a.name_normalised % b.name_normalised   -- usa el indice GIN de arriba
where similarity(a.name_normalised, b.name_normalised) >= 0.5
union all
select
    'buyer'::text,
    a.buyer_id,
    b.buyer_id,
    a.country_code,
    a.name_normalised,
    b.name_normalised,
    similarity(a.name_normalised, b.name_normalised),
    (a.buyer_tax_id is null or b.buyer_tax_id is null)
from mart.buyers a
join mart.buyers b
    on a.country_code = b.country_code
    and a.buyer_id < b.buyer_id
    and a.name_normalised % b.name_normalised
where similarity(a.name_normalised, b.name_normalised) >= 0.5;
end if;
end $migration$;

-- ----------------------------------------------------------------------------
-- v_coverage: que pais/periodo esta realmente cargado, para que MIRA-API
-- distinga "cero porque no hubo" de "cero porque no tenemos el dato".
-- ----------------------------------------------------------------------------
do $migration$
begin
if to_regclass('query.v_coverage') is null then
create view query.v_coverage as
select
    r.source as country_code,
    r.period,
    r.status,
    r.finished_at as loaded_at,
    rc.table_name,
    rc.row_count
from audit.etl_runs r
left join audit.etl_row_counts rc on rc.run_id = r.id
where r.status = 'SUCCESS';
end if;
end $migration$;

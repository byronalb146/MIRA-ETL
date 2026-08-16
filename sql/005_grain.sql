-- Costa Rica's process_id includes the purchase line (LINEA/PROD_ID), so one
-- SICOP "procedure" becomes several mart rows. Honduras/Nicaragua/Guatemala
-- process_id identifies the whole procedure. A comparative count across
-- countries without this column silently mixes the two units. Nullable
-- because rows written before this column existed have no grain recorded
-- until their connector re-runs; every connector populates it going forward.
alter table mart.procurement_record_core
    add column if not exists grain text;

alter table mart.procurement_record_core
    drop constraint if exists procurement_record_core_grain_check;

alter table mart.procurement_record_core
    add constraint procurement_record_core_grain_check
    check (grain is null or grain in ('PROCESS', 'LINE_ITEM'));

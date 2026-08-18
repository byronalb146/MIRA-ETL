-- Keep one entity-name value. Earlier development versions briefly added a
-- display_name column; when present, preserve its published spelling in
-- name_normalised before removing the duplicate column.
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'mart'
          and table_name = 'suppliers'
          and column_name = 'display_name'
    ) then
        execute 'update mart.suppliers
                    set name_normalised = display_name
                  where display_name is not null';
        execute 'alter table mart.suppliers drop column display_name cascade';
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_schema = 'mart'
          and table_name = 'buyers'
          and column_name = 'display_name'
    ) then
        execute 'update mart.buyers
                    set name_normalised = display_name
                  where display_name is not null';
        execute 'alter table mart.buyers drop column display_name cascade';
    end if;
end
$$;

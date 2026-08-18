-- Column-level documentation that MIRA-API injects into the SQL-generation
-- prompt. This is the ONLY place that describes query.* columns for that
-- purpose -- MIRA-API must not hand-write a second description, because two
-- descriptions of the same column drift apart silently (see the connection
-- doc, B.1). Enum lists below are hand-copied from the CHECK constraints in
-- sql/001_init.sql; tests/test_semantic_dictionary.py
-- fails if they drift.
create table if not exists query.semantic_dictionary (
    id bigserial primary key,
    view_name text not null,
    column_name text not null,
    description_es text not null,
    data_type text not null,
    enum_values text[],
    unit text,
    is_aggregable boolean not null default false,
    caveat text,
    unique (view_name, column_name)
);

-- This table is fully seeded here; remove entries for views/columns retired
-- from the query contract before inserting the current definition.
delete from query.semantic_dictionary;

insert into query.semantic_dictionary
    (view_name, column_name, description_es, data_type, enum_values, unit, is_aggregable, caveat)
values
    ('query.v_process', 'process_id', 'Identificador estable del procedimiento de contratacion.', 'text', null, null, false, null),
    ('query.v_process', 'country_code', 'Pais de origen del proceso (codigo ISO de dos letras).', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_process', 'source_system', 'Sistema de contrataciones de origen (por ejemplo costa_rica_sicop).', 'text', null, null, false, null),
    ('query.v_process', 'data_quality_status', 'Que tan completa quedo la fila despues de normalizar el dato fuente.', 'text', array['COMPLETE','PARTIAL','INVALID','DUPLICATE'], null, false, null),
    ('query.v_process', 'source_url', 'Enlace al registro publicado por la fuente cuando esta disponible.', 'text', null, null, false, null),
    ('query.v_process', 'extracted_at', 'Momento en que MIRA extrajo el registro de la fuente.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'source_last_modified_at', 'Ultima modificacion informada por la fuente cuando esta disponible.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'normalised_at', 'Momento en que el ETL proceso esta fila por ultima vez.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'missing_fields', 'Campos esperados que no estaban disponibles en el registro fuente.', 'jsonb', null, null, false, null),
    ('query.v_process', 'process_number', 'Numero de expediente o procedimiento tal como lo publica la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'title', 'Titulo del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'description', 'Descripcion del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'procurement_method', 'Modalidad de contratacion tal como la nombra la fuente (texto libre, no catalogado).', 'text', null, null, false, 'No es un catalogo cerrado: la misma modalidad puede aparecer escrita distinto entre paises.'),
    ('query.v_process', 'process_status', 'Estado normalizado del procedimiento.', 'text', array['PLANNED','PUBLISHED','OPEN','EVALUATION','AWARDED','CONTRACTED','COMPLETED','CANCELLED','DESERTED','SUSPENDED'], null, false, null),
    ('query.v_process', 'source_status', 'Estado tal como lo escribe la fuente, antes de normalizar.', 'text', null, null, false, null),
    ('query.v_process', 'publication_date', 'Fecha de publicacion del procedimiento.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'closing_date', 'Fecha de cierre de recepcion de ofertas.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'estimated_amount', 'Monto estimado antes de adjudicar, en la moneda de currency_code.', 'numeric', null, 'currency_code', true, 'Nunca sumar procesos con currency_code distinto sin convertir primero.'),
    ('query.v_process', 'currency_code', 'Moneda del monto estimado.', 'text', null, null, false, null),

    ('query.v_buyers', 'buyer_id', 'Identificador estable de la entidad compradora.', 'bigint', null, null, false, null),
    ('query.v_buyers', 'country_code', 'Pais de la entidad compradora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_buyers', 'source_system', 'Sistema de contrataciones donde se registro esta entidad.', 'text', null, null, false, null),
    ('query.v_buyers', 'name_normalised', 'Nombre publicado de la entidad, normalizado unicamente en Unicode y espacios.', 'text', null, null, false, 'Conserva mayusculas, acentos, puntuacion y sufijos legales; puede mostrarse al usuario.'),
    ('query.v_buyers', 'buyer_tax_id', 'Identificador fiscal (cedula juridica u equivalente) cuando la fuente lo expone.', 'text', null, null, false, null),

    ('query.v_suppliers', 'supplier_id', 'Identificador estable de la entidad proveedora.', 'bigint', null, null, false, null),
    ('query.v_suppliers', 'country_code', 'Pais de la entidad proveedora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_suppliers', 'source_system', 'Sistema de contrataciones donde se registro esta entidad.', 'text', null, null, false, null),
    ('query.v_suppliers', 'name_normalised', 'Nombre publicado de la entidad, normalizado unicamente en Unicode y espacios.', 'text', null, null, false, 'Conserva mayusculas, acentos, puntuacion y sufijos legales; puede mostrarse al usuario.'),
    ('query.v_suppliers', 'supplier_tax_id', 'Identificador fiscal (cedula fisica o juridica) cuando la fuente lo expone.', 'text', null, null, false, null),
    ('query.v_suppliers', 'supplier_type', 'Tipo de proveedor.', 'text', array['PERSON','COMPANY','CONSORTIUM','NONPROFIT','PUBLIC_ENTITY','FOREIGN_SUPPLIER','UNKNOWN'], null, false, null),

    ('query.v_process_buyers', 'process_id', 'Proceso relacionado con el comprador.', 'text', null, null, false, null),
    ('query.v_process_buyers', 'buyer_id', 'Comprador relacionado con el proceso.', 'bigint', null, null, false, null),

    ('query.v_items', 'item_id', 'Identificador estable de la linea o articulo.', 'text', null, null, false, null),
    ('query.v_items', 'process_id', 'Procedimiento al que pertenece la linea o articulo.', 'text', null, null, false, null),
    ('query.v_items', 'source_item_id', 'Identificador del articulo publicado por la fuente.', 'text', null, null, false, null),
    ('query.v_items', 'line_number', 'Numero de linea publicado por la fuente.', 'text', null, null, false, null),
    ('query.v_items', 'item_description', 'Descripcion del bien o servicio.', 'text', null, null, false, null),
    ('query.v_items', 'category_source', 'Categoria del bien o servicio publicada por la fuente.', 'text', null, null, false, null),
    ('query.v_items', 'category_normalised', 'Categoria regional normalizada cuando esta disponible.', 'text', null, null, false, null),

    ('query.v_awards', 'award_id', 'Identificador estable de la adjudicacion.', 'text', null, null, false, null),
    ('query.v_awards', 'process_id', 'Procedimiento al que pertenece la adjudicacion.', 'text', null, null, false, null),
    ('query.v_awards', 'source_award_id', 'Identificador de adjudicacion publicado por la fuente.', 'text', null, null, false, null),
    ('query.v_awards', 'award_date', 'Fecha de la adjudicacion.', 'timestamptz', null, null, false, null),
    ('query.v_awards', 'awarded_amount', 'Monto de esta adjudicacion en su moneda original.', 'numeric', null, 'currency_code', true, 'No sumar adjudicaciones con monedas diferentes sin convertirlas.'),
    ('query.v_awards', 'currency_code', 'Moneda del monto adjudicado.', 'text', null, null, false, null),

    ('query.v_award_items', 'award_id', 'Adjudicacion relacionada con el articulo.', 'text', null, null, false, null),
    ('query.v_award_items', 'item_id', 'Articulo relacionado con la adjudicacion.', 'text', null, null, false, null),

    ('query.v_award_suppliers', 'award_id', 'Adjudicacion relacionada con el proveedor.', 'text', null, null, false, null),
    ('query.v_award_suppliers', 'supplier_id', 'Proveedor relacionado con la adjudicacion.', 'bigint', null, null, false, null)
on conflict (view_name, column_name) do update set
    description_es = excluded.description_es,
    data_type = excluded.data_type,
    enum_values = excluded.enum_values,
    unit = excluded.unit,
    is_aggregable = excluded.is_aggregable,
    caveat = excluded.caveat;

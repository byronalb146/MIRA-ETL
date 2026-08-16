-- Column-level documentation that MIRA-API injects into the SQL-generation
-- prompt. This is the ONLY place that describes query.* columns for that
-- purpose -- MIRA-API must not hand-write a second description, because two
-- descriptions of the same column drift apart silently (see the connection
-- doc, B.1). Enum lists below are hand-copied from the CHECK constraints in
-- sql/001_init.sql and sql/005_grain.sql; tests/test_semantic_dictionary.py
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

insert into query.semantic_dictionary
    (view_name, column_name, description_es, data_type, enum_values, unit, is_aggregable, caveat)
values
    ('query.v_process', 'process_id', 'Identificador estable de la fila de contratacion.', 'text', null, null, false, 'En Costa Rica un process_id identifica una linea de compra dentro de un procedimiento, no el procedimiento completo. Ver la columna grain antes de contar o comparar entre paises.'),
    ('query.v_process', 'country_code', 'Pais de origen del proceso (codigo ISO de dos letras).', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_process', 'source_system', 'Sistema de contrataciones de origen (por ejemplo costa_rica_sicop).', 'text', null, null, false, null),
    ('query.v_process', 'grain', 'Granularidad de la fila: PROCESS es un procedimiento completo, LINE_ITEM es una sola linea de compra dentro de un procedimiento.', 'text', array['PROCESS','LINE_ITEM'], null, false, 'Sumar o contar process_id mezclando ambas granularidades da un numero sin significado. Filtrar o agrupar por grain primero.'),
    ('query.v_process', 'data_quality_status', 'Que tan completa quedo la fila despues de normalizar el dato fuente.', 'text', array['COMPLETE','PARTIAL','INVALID','DUPLICATE'], null, false, null),
    ('query.v_process', 'normalised_at', 'Momento en que el ETL proceso esta fila por ultima vez.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'process_number', 'Numero de expediente o procedimiento tal como lo publica la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'title', 'Titulo del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'description', 'Descripcion del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'procurement_method', 'Modalidad de contratacion tal como la nombra la fuente (texto libre, no catalogado).', 'text', null, null, false, 'No es un catalogo cerrado: la misma modalidad puede aparecer escrita distinto entre paises.'),
    ('query.v_process', 'process_status', 'Estado normalizado del procedimiento.', 'text', array['PLANNED','PUBLISHED','OPEN','EVALUATION','AWARDED','CONTRACTED','COMPLETED','CANCELLED','DESERTED','SUSPENDED'], null, false, null),
    ('query.v_process', 'source_status', 'Estado tal como lo escribe la fuente, antes de normalizar.', 'text', null, null, false, null),
    ('query.v_process', 'publication_date', 'Fecha de publicacion del procedimiento.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'closing_date', 'Fecha de cierre de recepcion de ofertas.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'award_date', 'Fecha de adjudicacion (cuando ya se adjudico).', 'timestamptz', null, null, false, null),
    ('query.v_process', 'estimated_amount', 'Monto estimado antes de adjudicar, en la moneda de currency_code.', 'numeric', null, 'currency_code', true, 'Nunca sumar procesos con currency_code distinto sin convertir primero.'),
    ('query.v_process', 'awarded_amount', 'Monto adjudicado, en la moneda de currency_code.', 'numeric', null, 'currency_code', true, 'Es el monto en la moneda original, no convertido a una moneda comun. Sumar entre paises sin agrupar por currency_code produce un total sin sentido.'),
    ('query.v_process', 'currency_code', 'Moneda de estimated_amount y awarded_amount.', 'text', null, null, false, null),
    ('query.v_process', 'buyer_ids', 'IDs de mart.buyers asociados a este proceso (puede haber mas de uno).', 'bigint[]', null, null, false, 'Un proceso puede tener varios compradores; no asumir que hay exactamente uno.'),
    ('query.v_process', 'buyer_display_names', 'Nombres de los compradores, en el mismo orden que buyer_ids, con la grafia original cuando existe.', 'text[]', null, null, false, null),
    ('query.v_process', 'supplier_ids', 'IDs de mart.suppliers asociados a este proceso (puede haber mas de uno).', 'bigint[]', null, null, false, 'Un proceso puede tener varios proveedores; no asumir que hay exactamente uno, y no asumir que el primero de buyer_ids corresponde al primero de supplier_ids -- no existe una tabla de pares comprador-proveedor.'),
    ('query.v_process', 'supplier_display_names', 'Nombres de los proveedores, en el mismo orden que supplier_ids, con la grafia original cuando existe.', 'text[]', null, null, false, null),
    ('query.v_process', 'item_description', 'Descripcion del bien o servicio contratado.', 'text', null, null, false, null),
    ('query.v_process', 'category_source', 'Categoria del bien o servicio tal como la publica la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'category_normalised', 'Categoria normalizada (aun no poblada para todos los paises).', 'text', null, null, false, null),

    ('query.v_buyers', 'buyer_id', 'Identificador estable de la entidad compradora.', 'bigint', null, null, false, null),
    ('query.v_buyers', 'country_code', 'Pais de la entidad compradora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_buyers', 'source_system', 'Sistema de contrataciones donde se registro esta entidad.', 'text', null, null, false, null),
    ('query.v_buyers', 'display_name', 'Nombre de la entidad tal como lo publico la fuente, con acentos y mayusculas originales.', 'text', null, null, false, 'Puede ser nulo para compradores creados antes de que se guardara la grafia original.'),
    ('query.v_buyers', 'name_normalised', 'Nombre en mayusculas, sin acentos y sin sufijos legales, usado para emparejar entidades entre fuentes.', 'text', null, null, false, 'No usar para mostrar al usuario; usar display_name.'),
    ('query.v_buyers', 'buyer_tax_id', 'Identificador fiscal (cedula juridica u equivalente) cuando la fuente lo expone.', 'text', null, null, false, null),

    ('query.v_suppliers', 'supplier_id', 'Identificador estable de la entidad proveedora.', 'bigint', null, null, false, null),
    ('query.v_suppliers', 'country_code', 'Pais de la entidad proveedora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_suppliers', 'source_system', 'Sistema de contrataciones donde se registro esta entidad.', 'text', null, null, false, null),
    ('query.v_suppliers', 'display_name', 'Nombre de la entidad tal como lo publico la fuente, con acentos y mayusculas originales.', 'text', null, null, false, 'Puede ser nulo para proveedores creados antes de que se guardara la grafia original.'),
    ('query.v_suppliers', 'name_normalised', 'Nombre en mayusculas, sin acentos y sin sufijos legales, usado para emparejar entidades entre fuentes.', 'text', null, null, false, 'No usar para mostrar al usuario; usar display_name.'),
    ('query.v_suppliers', 'supplier_tax_id', 'Identificador fiscal (cedula fisica o juridica) cuando la fuente lo expone.', 'text', null, null, false, null),
    ('query.v_suppliers', 'supplier_type', 'Tipo de proveedor.', 'text', array['PERSON','COMPANY','CONSORTIUM','NONPROFIT','PUBLIC_ENTITY','FOREIGN_SUPPLIER','UNKNOWN'], null, false, null),

    ('query.v_duplicate_hints', 'entity_type', 'Si el par sugerido es de compradores o de proveedores.', 'text', array['buyer','supplier'], null, false, null),
    ('query.v_duplicate_hints', 'entity_id_a', 'ID de la primera entidad del par (buyer_id o supplier_id segun entity_type).', 'bigint', null, null, false, null),
    ('query.v_duplicate_hints', 'entity_id_b', 'ID de la segunda entidad del par.', 'bigint', null, null, false, null),
    ('query.v_duplicate_hints', 'country_code', 'Pais compartido por ambas entidades (la comparacion nunca cruza paises).', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_duplicate_hints', 'display_name_a', 'Grafia original de la primera entidad.', 'text', null, null, false, null),
    ('query.v_duplicate_hints', 'display_name_b', 'Grafia original de la segunda entidad.', 'text', null, null, false, null),
    ('query.v_duplicate_hints', 'name_similarity', 'Similitud de trigrama (0 a 1) entre los nombres normalizados de ambas entidades.', 'real', null, null, false, 'Es una sugerencia de revision manual, nunca una fusion automatica: ver docs/entity_matching.md.'),

    ('query.v_coverage', 'country_code', 'Pais al que corresponde esta fila de cobertura.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_coverage', 'source_system', 'Sistema de contrataciones al que corresponde esta fila de cobertura.', 'text', null, null, false, null),
    ('query.v_coverage', 'grain', 'Granularidad de los procesos contados en esta fila.', 'text', array['PROCESS','LINE_ITEM'], null, false, 'No sumar process_count de filas con distinto grain para el mismo pais.'),
    ('query.v_coverage', 'process_count', 'Cantidad total de filas de query.v_process para este pais/fuente/grain.', 'bigint', null, null, true, null),
    ('query.v_coverage', 'complete_count', 'Cuantas de esas filas quedaron con data_quality_status = COMPLETE.', 'bigint', null, null, true, null),
    ('query.v_coverage', 'partial_count', 'Cuantas de esas filas quedaron con data_quality_status = PARTIAL.', 'bigint', null, null, true, null),
    ('query.v_coverage', 'invalid_count', 'Cuantas de esas filas quedaron con data_quality_status = INVALID.', 'bigint', null, null, true, null),
    ('query.v_coverage', 'duplicate_count', 'Cuantas de esas filas quedaron con data_quality_status = DUPLICATE.', 'bigint', null, null, true, null),
    ('query.v_coverage', 'earliest_award_date', 'Fecha de adjudicacion mas antigua en este grupo.', 'timestamptz', null, null, false, null),
    ('query.v_coverage', 'latest_award_date', 'Fecha de adjudicacion mas reciente en este grupo.', 'timestamptz', null, null, false, null),
    ('query.v_coverage', 'last_normalised_at', 'Ultima vez que el ETL proceso una fila de este grupo.', 'timestamptz', null, null, false, null)
on conflict (view_name, column_name) do update set
    description_es = excluded.description_es,
    data_type = excluded.data_type,
    enum_values = excluded.enum_values,
    unit = excluded.unit,
    is_aggregable = excluded.is_aggregable,
    caveat = excluded.caveat;

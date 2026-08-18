-- Documentacion columna por columna que MIRA-API inyecta en el prompt de
-- generacion de SQL. Es el UNICO lugar que describe las columnas de query.*
-- para ese proposito -- MIRA-API no debe escribir una segunda descripcion a
-- mano, porque dos descripciones de la misma columna se desalinean en
-- silencio. Los enumerados se copiaron a mano de los CHECK de
-- sql/001_init.sql y sql/003_grain.sql; tests/test_semantic_dictionary.py
-- falla si se desalinean.
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
    ('query.v_process', 'source_url', 'Enlace a la publicacion original en el portal oficial de la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'grain', 'Granularidad de la fila: PROCESS es un procedimiento completo, LINE_ITEM es una sola linea de compra dentro de un procedimiento.', 'text', array['PROCESS','LINE_ITEM'], null, false, 'Sumar o contar process_id mezclando ambas granularidades da un numero sin significado. Filtrar o agrupar por grain primero. Puede ser NULL en filas cargadas antes de que existiera esta columna.'),
    ('query.v_process', 'data_quality_status', 'Que tan completa quedo la fila despues de normalizar el dato fuente.', 'text', array['COMPLETE','PARTIAL','INVALID','DUPLICATE'], null, false, null),
    ('query.v_process', 'missing_fields', 'Lista en JSON de los campos que la fuente no traia para esta fila.', 'jsonb', null, null, false, null),
    ('query.v_process', 'extracted_at', 'Momento en que el ETL extrajo esta fila de la fuente.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'process_number', 'Numero de expediente o procedimiento tal como lo publica la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'title', 'Titulo del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'description', 'Descripcion del procedimiento.', 'text', null, null, false, null),
    ('query.v_process', 'procurement_method', 'Modalidad de contratacion tal como la nombra la fuente (texto libre, no catalogado).', 'text', null, null, false, 'No es un catalogo cerrado: la misma modalidad puede aparecer escrita distinto entre paises.'),
    ('query.v_process', 'process_status', 'Estado normalizado del procedimiento.', 'text', array['PLANNED','PUBLISHED','OPEN','EVALUATION','AWARDED','CONTRACTED','COMPLETED','CANCELLED','DESERTED','SUSPENDED'], null, false, null),
    ('query.v_process', 'source_status', 'Estado tal como lo escribe la fuente, antes de normalizar.', 'text', null, null, false, null),
    ('query.v_process', 'publication_date', 'Fecha de publicacion del procedimiento.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'closing_date', 'Fecha de cierre de recepcion de ofertas.', 'timestamptz', null, null, false, null),
    ('query.v_process', 'award_date', 'Fecha de adjudicacion (cuando ya se adjudico).', 'timestamptz', null, null, false, null),
    ('query.v_process', 'estimated_amount', 'Monto estimado antes de adjudicar, en la moneda de currency_code.', 'numeric', null, 'currency_code', true, 'Nunca sumar procesos con currency_code distinto sin agrupar por moneda primero.'),
    ('query.v_process', 'awarded_amount', 'Monto adjudicado, en la moneda de currency_code.', 'numeric', null, 'currency_code', true, 'Es el monto en la moneda original, no convertido a una moneda comun. Sumar entre paises sin agrupar por currency_code produce un total sin sentido.'),
    ('query.v_process', 'currency_code', 'Moneda de estimated_amount y awarded_amount.', 'text', null, null, false, 'Puede ser NULL cuando la fuente no declaro moneda; esas filas nunca se descartan en silencio, se reportan aparte.'),
    ('query.v_process', 'award_month', 'award_date truncado al primer dia del mes, para agrupar por mes.', 'date', null, null, false, null),
    ('query.v_process', 'buyer_id', 'ID de mart.buyers cuando el proceso tiene exactamente un comprador.', 'bigint', null, null, false, 'NULL si el proceso tiene mas de un comprador (ver buyer_count) o ninguno. Para no perder esos casos usar query.v_process_buyers.'),
    ('query.v_process', 'buyer_name', 'Nombre del comprador (name_normalised) cuando hay exactamente uno. NULL en el mismo caso que buyer_id.', 'text', null, null, false, null),
    ('query.v_process', 'buyer_name_normalised', 'Igual a buyer_name; se mantiene por compatibilidad con el nombre de columna del contrato original.', 'text', null, null, false, null),
    ('query.v_process', 'buyer_tax_id', 'Identificador fiscal del comprador cuando hay exactamente uno.', 'text', null, null, false, null),
    ('query.v_process', 'buyer_count', 'Cuantos compradores distintos tiene realmente este proceso.', 'bigint', null, null, true, 'Si es mayor a 1, buyer_id/buyer_name/buyer_tax_id vienen en NULL a proposito -- usar query.v_process_buyers para verlos todos.'),
    ('query.v_process', 'supplier_id', 'ID de mart.suppliers cuando el proceso tiene exactamente un proveedor.', 'bigint', null, null, false, 'NULL si el proceso tiene mas de un proveedor (ver supplier_count) o ninguno. Para no perder esos casos usar query.v_process_suppliers.'),
    ('query.v_process', 'supplier_name', 'Nombre del proveedor (name_normalised) cuando hay exactamente uno. NULL en el mismo caso que supplier_id.', 'text', null, null, false, null),
    ('query.v_process', 'supplier_name_normalised', 'Igual a supplier_name; se mantiene por compatibilidad con el nombre de columna del contrato original.', 'text', null, null, false, null),
    ('query.v_process', 'supplier_tax_id', 'Identificador fiscal del proveedor cuando hay exactamente uno.', 'text', null, null, false, null),
    ('query.v_process', 'supplier_type', 'Tipo de proveedor cuando hay exactamente uno.', 'text', array['PERSON','COMPANY','CONSORTIUM','NONPROFIT','PUBLIC_ENTITY','FOREIGN_SUPPLIER','UNKNOWN'], null, false, null),
    ('query.v_process', 'supplier_count', 'Cuantos proveedores distintos tiene realmente este proceso.', 'bigint', null, null, true, 'Si es mayor a 1, supplier_id/supplier_name/supplier_tax_id/supplier_type vienen en NULL a proposito -- usar query.v_process_suppliers para verlos todos.'),
    ('query.v_process', 'item_description', 'Descripcion del bien o servicio contratado.', 'text', null, null, false, null),
    ('query.v_process', 'category_source', 'Categoria del bien o servicio tal como la publica la fuente.', 'text', null, null, false, null),
    ('query.v_process', 'category_normalised', 'Categoria normalizada (aun no poblada para todos los paises).', 'text', null, null, false, null),

    ('query.v_process_buyers', 'process_id', 'Proceso al que esta vinculado este comprador. Un mismo process_id puede aparecer varias veces, una por cada comprador.', 'text', null, null, false, null),
    ('query.v_process_buyers', 'buyer_id', 'ID de mart.buyers.', 'bigint', null, null, false, null),
    ('query.v_process_buyers', 'buyer_name', 'Nombre normalizado del comprador.', 'text', null, null, false, null),
    ('query.v_process_buyers', 'buyer_tax_id', 'Identificador fiscal del comprador, si la fuente lo expone.', 'text', null, null, false, null),

    ('query.v_process_suppliers', 'process_id', 'Proceso al que esta vinculado este proveedor. Un mismo process_id puede aparecer varias veces, una por cada proveedor.', 'text', null, null, false, null),
    ('query.v_process_suppliers', 'supplier_id', 'ID de mart.suppliers.', 'bigint', null, null, false, null),
    ('query.v_process_suppliers', 'supplier_name', 'Nombre normalizado del proveedor.', 'text', null, null, false, null),
    ('query.v_process_suppliers', 'supplier_tax_id', 'Identificador fiscal del proveedor, si la fuente lo expone.', 'text', null, null, false, null),
    ('query.v_process_suppliers', 'supplier_type', 'Tipo de proveedor.', 'text', array['PERSON','COMPANY','CONSORTIUM','NONPROFIT','PUBLIC_ENTITY','FOREIGN_SUPPLIER','UNKNOWN'], null, false, null),

    ('query.v_buyers', 'entity_id', 'Identificador estable de la entidad compradora (mart.buyers.buyer_id).', 'bigint', null, null, false, null),
    ('query.v_buyers', 'country_code', 'Pais de la entidad compradora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_buyers', 'display_name', 'Nombre para mostrar al usuario. Hoy es igual a name_normalised (mayusculas, sin acentos); no existe todavia una columna con la grafia original.', 'text', null, null, false, null),
    ('query.v_buyers', 'name_normalised', 'Nombre en mayusculas, sin acentos y sin sufijos legales, usado para emparejar entidades entre fuentes.', 'text', null, null, false, null),
    ('query.v_buyers', 'tax_id', 'Identificador fiscal (RUC/RTN/Cedula/NIT segun el pais) cuando la fuente lo expone.', 'text', null, null, false, null),
    ('query.v_buyers', 'record_count', 'Cantidad REAL de procesos vinculados a esta entidad. Nunca se fusiona con otra entidad parecida para sumar conteos -- ver query.v_duplicate_hints.', 'bigint', null, null, true, null),

    ('query.v_suppliers', 'entity_id', 'Identificador estable de la entidad proveedora (mart.suppliers.supplier_id).', 'bigint', null, null, false, null),
    ('query.v_suppliers', 'country_code', 'Pais de la entidad proveedora.', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_suppliers', 'display_name', 'Nombre para mostrar al usuario. Hoy es igual a name_normalised (mayusculas, sin acentos); no existe todavia una columna con la grafia original.', 'text', null, null, false, null),
    ('query.v_suppliers', 'name_normalised', 'Nombre en mayusculas, sin acentos y sin sufijos legales, usado para emparejar entidades entre fuentes.', 'text', null, null, false, null),
    ('query.v_suppliers', 'tax_id', 'Identificador fiscal (cedula fisica o juridica) cuando la fuente lo expone.', 'text', null, null, false, null),
    ('query.v_suppliers', 'supplier_type', 'Tipo de proveedor.', 'text', array['PERSON','COMPANY','CONSORTIUM','NONPROFIT','PUBLIC_ENTITY','FOREIGN_SUPPLIER','UNKNOWN'], null, false, null),
    ('query.v_suppliers', 'record_count', 'Cantidad REAL de procesos vinculados a esta entidad. Nunca se fusiona con otra entidad parecida para sumar conteos -- ver query.v_duplicate_hints.', 'bigint', null, null, true, null),

    ('query.v_duplicate_hints', 'entity_type', 'Si el par sugerido es de compradores o de proveedores.', 'text', array['buyer','supplier'], null, false, null),
    ('query.v_duplicate_hints', 'entity_id_a', 'ID de la primera entidad del par (buyer_id o supplier_id segun entity_type).', 'bigint', null, null, false, null),
    ('query.v_duplicate_hints', 'entity_id_b', 'ID de la segunda entidad del par.', 'bigint', null, null, false, null),
    ('query.v_duplicate_hints', 'country_code', 'Pais compartido por ambas entidades (la comparacion nunca cruza paises).', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_duplicate_hints', 'name_a', 'Nombre normalizado de la primera entidad.', 'text', null, null, false, null),
    ('query.v_duplicate_hints', 'name_b', 'Nombre normalizado de la segunda entidad.', 'text', null, null, false, null),
    ('query.v_duplicate_hints', 'name_similarity', 'Similitud de trigrama (0 a 1) entre los nombres normalizados de ambas entidades.', 'real', null, null, false, 'Es una sugerencia de revision manual, nunca una fusion automatica: ver docs/entity_matching.md en MIRA-ETL.'),
    ('query.v_duplicate_hints', 'missing_tax_id', 'true si a alguna de las dos entidades le falta identificador fiscal.', 'boolean', null, null, false, 'Un par sin identificador fiscal en ninguna de las dos es mas dificil de confirmar como duplicado real; tratarlo con mas cautela.'),

    ('query.v_coverage', 'country_code', 'Pais de la corrida del ETL (audit.etl_runs.source).', 'text', array['CR','GT','HN','NI'], null, false, null),
    ('query.v_coverage', 'period', 'Periodo que proceso esa corrida, tal como lo registro el ETL.', 'text', null, null, false, 'Texto libre, no un rango tipado -- confirmar el formato exacto antes de filtrar por rango de fechas.'),
    ('query.v_coverage', 'status', 'Resultado de la corrida. Esta vista solo incluye corridas SUCCESS.', 'text', array['SUCCESS'], null, false, null),
    ('query.v_coverage', 'loaded_at', 'Momento en que termino esa corrida del ETL.', 'timestamptz', null, null, false, null),
    ('query.v_coverage', 'table_name', 'Tabla que esa corrida cargo (una fila de audit.etl_row_counts por tabla).', 'text', null, null, false, null),
    ('query.v_coverage', 'row_count', 'Cuantas filas escribio el ETL en esa tabla durante esa corrida.', 'bigint', null, null, true, 'Un pais/periodo ausente de esta vista no tiene datos cargados -- distinto de un conteo real en cero. Ver docs/proposed-query-schema.md en MIRA-API, seccion de coverage.')
on conflict (view_name, column_name) do update set
    description_es = excluded.description_es,
    data_type = excluded.data_type,
    enum_values = excluded.enum_values,
    unit = excluded.unit,
    is_aggregable = excluded.is_aggregable,
    caveat = excluded.caveat;

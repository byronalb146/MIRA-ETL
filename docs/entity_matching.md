# Resolucion de entidades: proveedores y compradores

`mart.procurement_supplier_details` y `mart.procurement_buyer_details` estaban
disenadas 1-a-1 con cada proceso (`process_id` como llave primaria). Eso
significa que la misma empresa, si gana o participa en varios procesos,
repetia su nombre/RUC en cada fila, sin ninguna relacion explicita entre
ellas -- buscar "todos los procesos de la empresa X" requeria comparar texto,
fragil ante mayusculas, espacios o variantes de escritura.

`sql/002_supplier_buyer_dimensions.sql` agrega dos tablas de dimension
(`mart.suppliers`, `mart.buyers`) con un ID propio, y una columna
`supplier_id` / `buyer_id` en las tablas de detalle que las referencia.

## Estrategia de match: tres niveles, en orden de confianza

Implementada en `Database.get_or_create_supplier` / `get_or_create_buyer`
(`src/mira_etl/db.py`). Para cada registro, se intenta un nivel a la vez;
el primero que tenga un valor disponible decide como se busca (o se crea) la
fila de dimension:

1. **`TAX_ID`** -- identificador fiscal (RUC/RTN/Cedula/NIT, segun el pais)
   normalizado por `country_code`. El mas confiable: es un numero oficial,
   unico por ley.
2. **`SOURCE_ID`** -- ID interno que la propia fuente le asigna al proveedor/
   comprador en su catalogo (`supplier_id_source` / `buyer_id_source`), sin
   ser necesariamente un identificador fiscal. Se usa solo si no hay
   identificador fiscal disponible.
3. **`NAME_EXACT_NORMALISED`** -- nombre normalizado (mayusculas, sin
   acentos/puntuacion, sin sufijos legales comunes como "S.A.", "C.A.",
   "SOCIEDAD ANONIMA" -- ver `src/mira_etl/matching.py`). Solo se usa si no
   hay ninguno de los dos anteriores.
4. **`UNMATCHED`** -- no hay tax_id, ni source_id, ni siquiera un nombre.
   Se crea una fila nueva sin intentar relacionarla con nada (o, si tampoco
   hay nombre, no se crea fila en absoluto y `supplier_id`/`buyer_id` queda
   `NULL` -- ver mas abajo).

Cada fila de `mart.suppliers`/`mart.buyers` guarda en `match_method` cual
fue el mejor nivel de informacion disponible cuando se creo -- no si "hubo
una fusion", sino que tipo de llave la identifica. Esto permite despues
auditar por separado los grupos de alta confianza (`TAX_ID`, `SOURCE_ID`) de
los agrupados solo por nombre (`NAME_EXACT_NORMALISED`), sin tener que
confiar en toda la tabla por igual.

## Riesgo aceptado explicitamente

La normalizacion de nombre captura variantes de formato (mayusculas, acentos,
puntuacion, sufijos legales), pero **no** captura:

- Abreviaturas ("Const." vs "Constructora").
- Errores de tipeo.
- Orden de palabras distinto.

Estos casos **no se fusionan** -- cada uno recibe su propio `supplier_id`/
`buyer_id` nuevo, como si fueran entidades distintas. Es una decision de
diseno deliberada: se prefiere *no* agrupar (perder algo de deduplicacion)
antes que fusionar dos empresas que en realidad son distintas por un parecido
de nombre. Coincide con el principio que ya sigue el resto de MIRA: nunca
adivinar en silencio, documentar la limitacion.

## Cuando queda `NULL`

Si un registro no trae ni tax_id, ni source_id, ni nombre de proveedor/
comprador, no se crea ninguna fila de dimension y la columna queda `NULL` --
no se genera una fila "vacia" solo para tener algo que enlazar.

## Concurrencia

La busqueda-o-creacion (`get_or_create_*`) hace un `SELECT` seguido de un
`INSERT` en pasos separados, sin bloqueo explicito. Esto es seguro para como
corre el ETL hoy (un solo proceso, secuencial), pero **no** es seguro si dos
corridas del mismo pipeline llegaran a ejecutarse en paralelo sobre el mismo
pais/fuente -- podrian crear dos filas de dimension para la misma entidad en
una condicion de carrera. Si en el futuro se paraleliza la ejecucion, esto
necesitaria revisarse (por ejemplo, con un indice `UNIQUE` parcial por nivel
+ `ON CONFLICT ... RETURNING`, o un `advisory lock` por pais).

## Verificado

Probado de punta a punta contra una instancia local de PostgreSQL (no contra
Supabase real, por restricciones de red del entorno de desarrollo):

- Dos procesos con el mismo `supplier_tax_id` colapsan al mismo `supplier_id`.
- Un tercer proceso con el mismo proveedor, sin tax_id, escrito con un sufijo
  legal distinto, se agrupa correctamente por nombre normalizado con el
  mismo `supplier_id` que ya existia por `TAX_ID`.
- Un proveedor sin ningun identificador en comun con los anteriores recibe un
  `supplier_id` nuevo, propio.
- Un registro sin tax_id, source_id, ni nombre deja `supplier_id` en `NULL`,
  sin crear ninguna fila.
- Volver a correr el mismo lote de registros no duplica filas de dimension
  (idempotente).

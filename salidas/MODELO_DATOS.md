# Modelo de datos del Kardex en Supabase

Proyecto `sgpbdzphweyeaegzesvb` (Farrusel). Todo lo del Kardex vive en tablas
propias: **ninguna vista ni tabla del carrusel se ha modificado**.

---

## Por qué tablas propias y no las del carrusel

Las vistas del carrusel no filtran por almacén:

- `v_acciones` (tipos `inmovilizado` y `espacio`) lee `inventario` sin filtro.
- El CTE `ath` de `v_abastecimiento` agrega `ubicacion` entera — que además tiene
  `almacen` a NULL en las 2.057 filas y deduce el carrusel de
  `tipo_hueco ILIKE '%horizontal%'`.

Meter filas de kardex en esas tablas las habría hecho aparecer como acciones del
carrusel. Retrofitear filtros de almacén en 16 vistas de producción era más
arriesgado que crear tablas nuevas.

Comprobación de regresión tras todos los cambios: `v_acciones` sigue devolviendo
**543 filas** con idéntico reparto por tipo, y siguen existiendo 16 vistas.

---

## `articulo` — maestro transversal

Identidad del artículo, común a todos los módulos. **No sustituye a `medicamento`**,
que es la parametrización específica de los carruseles APD.

| Columna | Tipo | Notas |
|---|---|---|
| `codigo` | text | PK |
| `descripcion` | text | La más frecuente si hay discrepancia entre armarios |
| `ubicaciones` | text[] | Índice GIN. `KARDEX1`, `KARDEX2`, y en el futuro `CH`, `CV`, `FARMACIA_HUNSC`, `FARMACIA_SUR` |
| `en_proceso_de_baja` | boolean | Ver nota abajo |
| `formato_codigo` | text | `V+5 digitos`, `T+5 digitos`, … |
| `creado_en` / `actualizado_en` | timestamptz | |

`ubicaciones` **se fusiona, no se machaca**: cada informe nuevo añade sus almacenes
a los que ya hubiera. Es lo que permite ir construyendo el mapa completo de dónde
está cada artículo a medida que llegan ficheros de otros orígenes.

> **`en_proceso_de_baja`**: el catálogo marca con `BAJA` los artículos cuya baja se
> ha iniciado pero **no se ha completado** — si estuviera consumada no aparecerían.
> No son stock muerto: la acción es **agotar sin reponer**, no retirar.

Estado actual: **828 artículos**, de los cuales 590 están en los dos kardex.

---

## `inventario_huecos_kardex` — foto por corte

Una fila = **un hueco físico en una fecha**. FK a `articulo(codigo)`.

| Columna | Tipo | Notas |
|---|---|---|
| `fecha_descarga` | date | **Identificador del corte**, leído de la cabecera del informe |
| `almacen` | text | `KARDEX1` o `KARDEX2` (CHECK) |
| `ubicacion` | text | `001-01-01-42-01`; primer segmento = armario |
| `codigo`, `descripcion` | text | |
| `stock`, `capacidad` | numeric | `capacidad` a NULL si es "sin límite" |
| `tipo_hueco`, `bloqueado` | text / boolean | Bloqueado = posición fija |
| `lote`, `fecha_lote` | text / date | Vacíos en este informe |
| `en_proceso_de_baja` | boolean | |
| `capacidad_sin_limite` | boolean | El informe usa `999999999` como placeholder |
| `stock_supera_capacidad` | boolean | |
| `cargado_en` | timestamptz | |

**`unique (fecha_descarga, almacen, ubicacion)`** es la pieza clave: hace idempotente
reprocesar el mismo fichero y, sobre todo, **conserva los cortes anteriores**. La
revisión es trimestral o semestral y todo el valor está en comparar un corte con el
siguiente para medir si lo aplicado funcionó. Un `syncUpsertDelete` como el del
carrusel habría destruido justo eso.

Estado actual: **1.742 huecos** en el corte 2026-08-19.

---

## `v_kardex_stock` — vista de explotación

Los huecos con sus alertas calculadas **junto al dato que las origina**, para poder
auditarlas. Añade sobre la tabla base:

| Columna | Qué es |
|---|---|
| `pct_llenado` | `stock / capacidad`. NULL cuando no hay capacidad real |
| `huecos_del_articulo` | Nº de huecos que ocupa el artículo en ese corte |
| `stock_del_articulo` | Stock agregado del artículo en ese corte |
| `en_ambos_kardex` | Presente en K1 y K2 |
| `hueco_vacio` | `stock = 0` |
| `articulo_multihueco` | Ocupa más de un hueco |
| `n_alertas` | Cuántas alertas acumula el hueco; sirve para ordenar por criticidad |
| `es_ultimo_corte` | Marca el corte más reciente |

Los agregados por artículo se calculan **dentro de cada corte**: comparar artículos
de cortes distintos no tendría sentido.

`en_ambos_kardex` y `articulo_multihueco` **no cuentan como alertas** (afectan a 1.452
y 1.550 huecos): son contexto, no incidencias.

### Recuentos en el corte 2026-08-19

| Alerta | Huecos |
|---|---:|
| `stock_supera_capacidad` | 43 |
| `capacidad_sin_limite` | 24 |
| `en_proceso_de_baja` | 22 |
| `hueco_vacio` | 2 |
| **Con alguna alerta** | **91** de 1.742 |

---

## Carga

Dos caminos, ambos verificados y con resultado idéntico:

1. **Local** — `tools/cargar_supabase.py`, por API REST con la clave publicable.
2. **Farrusel** — `/kardex/subida`, con `src/lib/kardex/` y su registro de informes.

El parser TypeScript se validó contra el de referencia replicando su lógica exacta
en `tools/test_paridad_lovable.py`: mismas 1.742 filas, mismo reparto por armario,
mismos 828 artículos, mismas marcas de calidad y el mismo código en cada hueco.

Cada carga se registra en `carga` con `tipo_reporte = 'KARDEX_STOCK_HUECOS'`.

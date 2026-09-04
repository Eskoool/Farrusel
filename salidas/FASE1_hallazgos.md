# Fase 1 · Censo del Kardex

**Fuente:** `datos/Informe_StockHuecos.xls` — "INFORME DE STOCK DE ARMARIO POR HUECO", fechado 19/08/2026.
**Corte:** 2026-08-19.

---

## Cuadre del parseo

| Hoja | Armario | Filas fichero | Datos | Cabecera | Vacías | Descartadas |
|---|---|---:|---:|---:|---:|---:|
| `stockHuecos` | KARDEX1 | 1.463 | 894 | 150 | 419 | 0 |
| `stockHuecos 2` | KARDEX2 | 1.394 | 848 | 145 | 401 | 0 |

Toda fila del fichero está contabilizada en alguna categoría. **Cero filas perdidas en silencio.**

El informe es una **salida paginada para imprimir**: repite el bloque de cabecera completo (hospital, fecha, título, "Armarios:", armario y nombres de columna) cada ~48 filas — 30 veces en K1 y 29 en K2. Un parseo ingenuo habría metido 295 filas de cabecera como si fueran medicamentos.

---

## Convenciones fijadas (valen para todas las fases siguientes)

- **Armario**: `KARDEX1` y `KARDEX2`, identificados por la marca `KARDEXn(n)` de cada sección. No aparecen como columna.
- **Ubicación**: `NNN-NN-NN-NN-NN` (ej. `001-01-01-42-01`). El primer segmento es el armario: `001` = K1, `002` = K2. **Única dentro de cada armario** (0 duplicadas de 1.742).
- **Granularidad**: una fila = **un hueco físico**, no un artículo. Un código aparece tantas veces como huecos ocupa.
- **Código de artículo**: mayoritariamente `V`+5 dígitos, pero no solo:

| Formato | Huecos |
|---|---:|
| V + 5 dígitos | 1.694 |
| T + 5 dígitos | 31 |
| **V + 7 dígitos** | **8** |
| Y + 5 dígitos | 7 |
| BV + 5 dígitos | 1 |
| **6 dígitos sin letra** | **1** (`676262`, RILUZOL 50 mg — parece Código Nacional) |

  Los formatos minoritarios hay que confirmarlos contra el maestro: un código de 7 dígitos donde el resto tiene 5 puede ser un error de grabación.

- **Capacidad**: existe un placeholder de "sin límite" con valor **999.999.999** en 24 huecos. El brief avisaba de este patrón (§4.3) y aquí está confirmado. **No debe sumarse como capacidad real** — hacerlo dejaba el llenado en 0,0 %.
- **Bloqueo**: los 1.742 huecos están "Sin bloquear". **No hay ninguna posición fija.**
- **Lote y Fecha**: columnas presentes en la cabecera pero **vacías en todas las filas de datos**. Este informe no aporta caducidades.

---

## Censo

| Armario | Huecos | Artículos | Ocupados | Vacíos | Bloqueados |
|---|---:|---:|---:|---:|---:|
| KARDEX1 | 894 | 735 | 892 | 2 | 0 |
| KARDEX2 | 848 | 683 | 848 | 0 | 0 |
| **Total** | **1.742** | **828** | **1.740** | **2** | **0** |

Pares artículo×armario: **1.418**. El piloto en Excel del brief trabajaba sobre **1.419**. Es el mismo universo — la metodología es comparable.

---

## Hallazgo principal: el cuello de botella son los huecos, no el volumen

| Armario | Stock | Capacidad real | Llenado físico |
|---|---:|---:|---:|
| KARDEX1 | 45.542 uds | 134.153 uds | **33,9 %** |
| KARDEX2 | 44.189 uds | 119.262 uds | **37,1 %** |

**1.740 de 1.742 huecos están asignados (99,9 %), pero cada uno guarda solo un tercio de lo que admite.**

No hay sitio para meter un artículo nuevo, y sin embargo sobra volumen dentro de cada cajón. La palanca de optimización es **consolidar artículos en menos huecos**, no ampliar capacidad. Esto respalda con datos la tesis del brief: en el kardex hay que bajar stock, no subirlo.

---

## Acciones ya identificadas (sin necesidad de más ficheros)

### 1. Artículos en proceso de baja
**12 artículos en 22 huecos, 1.079 unidades.** Llevan `BAJA` en la descripción del propio maestro.

> **Matiz importante (confirmado por Yared):** estos artículos están *en proceso* de darse de baja, no dados de baja. Si la baja estuviera consumada no aparecerían en el catálogo. Por tanto **no son stock muerto que se pueda retirar sin más**: la acción es **agotar sin reponer**, y liberar el hueco cuando la baja se complete. Tratarlos como retirada inmediata sería un error operativo.

| Código | Descripción | Huecos | Unidades |
|---|---|---:|---:|
| V00591 | DOXAZOSINA 4 mg | 3 | 362 |
| V14227 | COLCHICINA 1 mg | 4 | 186 |
| V00553 | TRAMADOL/PARACETAMOL 37,5/325 | 2 | 137 |
| V02128 | VENLAFAXINA 75 mg | 2 | 95 |
| V00795 | CLINDAMICINA 150 mg | 1 | 85 |
| V13382 | MAGNESIO LACTATO | 2 | 59 |
| V00111 | CITALOPRAM 30 mg | 1 | 55 |
| V01527 | MIANSERINA 30 mg | 2 | 44 |
| V91969 | LOSARTAN/HIDROCLOROTIAZIDA | 2 | 23 |
| V01996 | IRBESARTAN/HTZ 300/12,5 mg | 1 | 20 |
| V03228 | MOXONIDINA 0,4 mg | 1 | 8 |
| V07074 | BISACODILO 10 mg supositorios | 1 | 5 |

Son 22 huecos, un 1,3 % del total. No se liberan hoy, pero **no deben reponerse**, y conviene vigilar que la baja se complete: mientras tanto ocupan posición en un armario donde solo quedan 2 huecos libres de 1.742.

### 2. Huecos con más stock del que admiten
**43 huecos con stock por encima de su capacidad declarada.** Los peores:

| Artículo | Stock | Capacidad | Llenado |
|---|---:|---:|---:|
| MESALAZINA 1 g (14 aplicaciones) | 111 | 8 | **1.387 %** |
| TIAPRIDA 100 mg comp | 281 | 75 | 375 % |
| OXIBUTININA 5 mg comp | 290 | 100 | 290 % |
| OXIBUTININA 5 mg comp | 492 | 200 | 246 % |
| BUPIVACAÍNA 0,25 % C/V amp | 104 | 50 | 208 % |

Un 1.387 % no es un hueco desbordado: es una **unidad de medida distinta entre stock y capacidad**. En MESALAZINA la capacidad parece estar en envases y el stock en aplicaciones (el envase trae 14). Conviene revisar si el resto sigue el mismo patrón.

En cualquier caso es un dato que hay que corregir **antes** de calcular nada sobre capacidades.

### 3. Artículos presentes en los dos kardex
**590 de 828 artículos (71 %) están en K1 y K2 a la vez.**

Es demasiado alto para ser casual, pero **todavía no es una acción**: duplicar un artículo de alta rotación en las dos máquinas puede ser deliberado. La decisión (tomada contigo) es que un artículo en ambos kardex **sin consumo en uno de ellos** es candidato a consolidación — y eso necesita el informe de movimientos de la Fase 3.

Listado completo en `salidas/fase1_articulos_en_ambos_kardex.csv`.

---

## Puertas de validación

| Puerta | Resultado |
|---|---|
| Cuadre de filas | **OK** — 2.857 filas = 1.742 datos + 295 cabecera + 820 vacías + 0 descartadas |
| Fechas | No aplica: el informe no trae fechas en las filas de datos |
| Escala ×100 | **OK** en `stock` (rango 0..1.009, mediana 32, media 52) |
| Outliers | **DETECTADO** en `capacidad`: placeholder 999.999.999 en 24 huecos, ya aislado |
| Ubicaciones duplicadas | **OK** — 0 |
| Descripciones vacías | **OK** — 0 |

---

## Lo que este informe NO trae

**No hay mínimo ni máximo parametrizados.** La columna `Cap.` es la capacidad física del hueco, no el stock máximo configurado. Sin esos dos valores no existe comparación posible, y por tanto no hay Subir/Bajar/Mantener.

Es el bloqueo de la Fase 2.

---

## Ficheros generados

| Fichero | Filas | Contenido |
|---|---:|---|
| `fase1_huecos.csv` | 1.742 | Una fila por hueco físico |
| `fase1_articulos.csv` | 1.418 | Agregado artículo × armario |
| `fase1_articulos_en_ambos_kardex.csv` | 590 | Candidatos a consolidación |
| `fase1_articulos_de_baja.csv` | 22 | Huecos liberables de inmediato |

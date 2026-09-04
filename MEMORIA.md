# MEMORIA — Optimización del Kardex

> Documento de estado. Léelo primero al retomar el proyecto.
> Última actualización: **2026-08-27**

---

## Objetivo

Optimizar la parametrización del Kardex del HUNSC —**mínimos y máximos por artículo y armario**— con una revisión **trimestral o semestral**.

El entregable es una **lista de decisiones Subir / Bajar / Mantener**, no un cuadro de mando.

## Método

Trabajar en local con los ficheros reales, validar la metodología contra datos de verdad, y **migrar a Farrusel paso a paso** solo lo que ya esté demostrado. Un fichero cada vez: se inspecciona, se valida, se acepta, y solo entonces el siguiente.

**Por qué así:** auditando Farrusel (el módulo hermano del carrusel) aparecieron tres corrupciones que nadie había detectado en meses, todas nacidas de dar por bueno un dato sin comprobarlo. Ver «Lecciones» abajo.

---

## Estado actual

| | Estado |
|---|---|
| Fase 1 · Inventario de K1 y K2 | ✅ Cerrada |
| Herramienta local con puertas de validación | ✅ Con tests |
| Tablas `articulo` + `inventario_huecos_kardex` | ✅ Creadas y pobladas |
| Vista `v_kardex_stock` | ✅ Creada, con detección de cambios respecto al corte anterior |
| Pantalla `/kardex/subida` en Farrusel | ✅ Publicada y verificada |
| Pestaña `/kardex/stock` → **«Gestión Kardex»** | ✅ Publicada, migrada a `v_kardex_maestro` (huecos + consumo + alertas con texto) |
| Pestaña `/kardex/movimientos` (nueva) | ✅ Publicada — consumo por artículo, sin-consumo, sin-kardex |
| **Fase 2 · Parametrización (mín/máx)** | ⏸ **Bloqueada: falta el fichero** |
| Fase 3 · Movimientos y periodo de cálculo | ✅ Migrado a Farrusel (tabla `movimientos_articulo_kardex` + vistas) — **sigue sin resolver K1 vs K2** (limitación de la fuente, no de la implementación) |
| Fichero maestro (Fase 1 × Fase 3, un hueco por fila) | ✅ En local y en Farrusel (`v_kardex_maestro`), mismo sistema de colores de alertas en ambos |
| Truncamiento a 1.000 filas del carrusel | ✅ **Arreglado** (`v_regularizacion_detalle`, `v_regularizacion_mes`, `v_abastecimiento`, `v_caducidad_detalle`) |
| Fase 4 · Motor de propuesta | ⏸ |

### Lo que bloquea todo

Falta el informe de **parametrización por artículo**: código, armario, **stock mínimo**, **stock máximo** y, si vienen, unidades por UDC y tipo de reposición.

El informe de stock por hueco **no lo trae**: su columna `Cap.` es la capacidad física del hueco, no el stock máximo configurado en la máquina. Sin mínimo y máximo actuales no hay contra qué comparar, y por tanto **no existe Subir/Bajar/Mantener**.

Dejar el fichero en `datos/` y continuar por Fase 2.

---

## Decisiones tomadas (no volver a discutirlas)

| Tema | Decisión |
|---|---|
| Cadencia | Trimestral o semestral, por cortes. El histórico **no se pisa** |
| Redondeo de propuestas | `FLOOR` siempre (suelo de seguridad) |
| Tolerancia | ±10 % |
| Baja rotación | No proponer 0: marcar **«sin consumo»** y comprobar si está en los dos kardex |
| Periodo de cálculo | Se fija en Fase 3, con el histograma real de fechas delante |
| Tablas | Propias `kardex_*` / `articulo`, nunca las del carrusel |
| Frontend | Vía agente de Lovable (consume créditos) |

### Por qué tablas propias y no las del carrusel

Las vistas del carrusel **no filtran por almacén**: `v_acciones` (tipos `inmovilizado` y `espacio`) lee `inventario` sin filtro, y el CTE `ath` de `v_abastecimiento` agrega `ubicacion` entera. Meter filas de kardex ahí las haría aparecer como acciones del carrusel.

---

## Convenciones del Kardex (fijadas en Fase 1)

- **Armarios**: `KARDEX1` y `KARDEX2`. No vienen como columna: se leen de la marca `KARDEXn(n)` que abre cada sección del informe.
- **Ubicación**: `NNN-NN-NN-NN-NN` (ej. `001-01-01-42-01`). Primer segmento = armario (`001` = K1, `002` = K2). Única dentro de cada armario.
- **Granularidad**: una fila = **un hueco físico**, no un artículo. Un código aparece tantas veces como huecos ocupa.
- **Códigos**: no solo `V`+5 dígitos. Conviven `T`+5, `Y`+5, `BV`+5, `V`+7 (8 casos) y uno de 6 dígitos sin letra (`676262`, RILUZOL — parece Código Nacional). **Un patrón estricto tira filas válidas.**
- **Capacidad «sin límite»**: placeholder `999999999` en 24 huecos. **Nunca sumarlo como capacidad real** — hacerlo dejaba el llenado en 0,0 %. Se trata como **alerta roja — error a corregir** en el fichero maestro: sin una capacidad real configurada no se puede validar mín/máx contra ella en Fase 4.
- **`tipo_hueco` NO determina `capacidad`.** Son dos columnas independientes del informe original (`Cap.` = columna 9, `Hueco` = columna 12 en `parser_stock_huecos.py`). `tipo_hueco` solo tiene 11 valores, todos modelos físicos de cajón (tamaño/LEDs/nº de divisiones) — no una cifra de capacidad: un mismo `tipo_hueco` convive con decenas de capacidades muy distintas (ej. el tipo «04 - Caj Pque 1xALT 1 LED 9 prof» va de 2 a 2000 en 69 valores distintos sobre 553 huecos), y una misma capacidad (168) aparece bajo tres `tipo_hueco` distintos. **Para Fase 4, mín/máx deben compararse contra `capacidad`, nunca contra `tipo_hueco`.**
- **`BAJA` en la descripción**: baja **en proceso**, no consumada (si estuviera consumada no aparecería en el catálogo). No es stock muerto: la acción es **agotar sin reponer**, no retirar.
- **Bloqueo**: bloqueado = posición fija. Hoy los 1.742 huecos están «Sin bloquear».
- El informe es una **salida paginada para imprimir**: repite el bloque de cabecera cada ~48 filas (295 filas en total). Hay que filtrarlas sin descartar datos.
- **Informe de movimientos** (Fase 3): granularidad distinta — una fila = un artículo agregado sobre el periodo (`Desde`/`Hasta` en la cabecera), no un hueco. Trae dos secciones («Articulos Internos»/«Articulos Externos»), cada una con su propia cabecera repetida una vez. `tipo_codigo` clasifica cada código en `kardex` / `bookkeeping` (`DM`+6 dígitos, `NOGUIA`, `PAC` — apuntes del dispensador, no huecos reales) / `otro`. `RE_BAJA` (de `parser_stock_huecos.py`) se reutiliza tal cual sobre la descripción de este informe.

---

## Hallazgos de Fase 1 (corte 2026-08-19)

**1.742 huecos · 828 artículos · 1.418 pares artículo×armario** (el piloto en Excel del brief trabajaba sobre 1.419 — mismo universo, metodología comparable).

### El cuello de botella son los huecos, no el volumen

| Armario | Huecos asignados | Stock | Capacidad real | Llenado |
|---|---:|---:|---:|---:|
| KARDEX1 | 892/894 | 45.542 | 134.153 | **33,9 %** |
| KARDEX2 | 848/848 | 44.189 | 119.262 | **37,1 %** |

99,9 % de posiciones ocupadas pero cada una guarda un tercio de lo que admite. **La palanca es consolidar en menos huecos, no ampliar capacidad.** Respalda con datos la tesis de que en el kardex hay que bajar stock.

### Alertas abiertas

| Alerta | Huecos | Nota |
|---|---:|---|
| Stock supera capacidad | 43 | El peor: MESALAZINA 1 g, 111 uds en capacidad 8 = **1.387 %**. No es desbordamiento, es **unidad de medida distinta** entre stock y capacidad (envases vs aplicaciones) |
| Capacidad sin límite | 24 | Placeholder `999999999` |
| En proceso de baja | 22 huecos / 12 artículos | 1.079 uds. Agotar sin reponer |
| Hueco vacío | 2 | |

**590 de 828 artículos (71 %) están en los dos kardex.** Todavía **no es una acción**: duplicar un artículo de alta rotación puede ser deliberado. Solo es candidato a consolidación si **no tiene consumo en uno de los dos** — eso necesita el informe de movimientos (Fase 3).

---

## Hallazgos de Fase 3 (corte 2026-08-20, `Informe_MovimientosArtículo.xls`)

**Fuente y periodo:** informe de movimientos por artículo (agregado, no por hueco), periodo `Desde 01/01/2026` – `Hasta 19/08/2026` (**231 días**, convención inclusiva). Trae dos secciones con su propia cabecera repetida — «Articulos Internos» y «Articulos Externos» — sin pie de totales. Cuadre exacto: `969 filas = 925 datos + 7 cabecera/marcadores + 37 vacías + 0 descartadas`.

**Familias de código:** además de los ya conocidos de Kardex (`kardex`, 906 códigos distintos), el informe trae 18 apuntes del sistema de dispensación que no son huecos reales — `DM`+6 dígitos (16), `NOGUIA` y `PAC` — clasificados como `tipo_codigo="bookkeeping"`. **Cuidado:** `DM`+6 dígitos encaja también en el patrón ancho de código de Kardex (`[A-Z]{0,2}\d{4,8}`); hay que comprobar bookkeeping **antes** que el patrón de Kardex o esos 16 apuntes se cuelan como si fueran artículos.

**Un código duplicado en el fichero fuente:** `V02254` (MESNA 1.000 MG) aparece en dos filas (Internos y Externos). El parser **no lo fusiona** — mantiene fidelidad 1:1 para que su cuadre siga siendo una comprobación real; la fusión (suma) es responsabilidad de la capa de análisis (`fase3_movimientos.py`).

**Cruce con el inventario de huecos (Fase 1, 828 códigos):**

| | Códigos | Nota |
|---|---:|---|
| Con consumo en el periodo | 804 | — |
| **Sin consumo en el periodo** | **24** | 22 nuevos a valorar + 2 ya marcados `BAJA` (consistente, no es hallazgo nuevo) |
| Movimiento sin Kardex | 120 | 18 bookkeeping (DM/NOGUIA/PAC) + 102 artículos V/T/Y no ubicados en KARDEX1/2 |
| En ambos kardex y con consumo | 586 | Ver limitación abajo |

Los 22 códigos «sin consumo, nuevos»: `T80948, T81012, V00161, V00204, V00253, V00631, V01104, V01506, V01743, V01821, V01935, V02374, V02399, V02577, V05044, V06580, V07831, V08093, V21524, V91800, V92215` (más `V01821`, `V05044`, `V07831`, `V14504` que además están en ambos kardex). Acción: **valorar retirar e introducir en carrusel**.

**Limitación importante — NO resuelve K1 vs K2:** este informe es de toda la farmacia, **sin desglose por almacén**. Puede decir «este artículo no se movió en todo el periodo», pero nunca «no se movió en KARDEX1 pero sí en KARDEX2» — que es la pregunta que de verdad dispara una consolidación entre los dos kardex (ver «Decisiones tomadas» y el hallazgo del 71 % en ambos kardex de Fase 1). **Sigue haciendo falta un informe de movimientos con desglose por almacén** para resolver esa pregunta; este paso deja la columna `k1_vs_k2 = "no resuelto..."` escrita en el propio dato, no solo en esta documentación.

**Tasas de consumo:** `tasa_7d`/`tasa_30d` en `salidas/fase3_movimientos.csv` y en el Excel son una **extrapolación lineal** desde el total del periodo (`cantidad_total / 231 días × 7` o `× 30`), no una media semanal/mensual observada — el informe no trae desglose diario.

Salidas: `salidas/fase3_movimientos.csv` (924 filas, un código por fila), `salidas/fase3_sin_consumo.csv` (24), `salidas/fase3_movimiento_sin_kardex.csv` (120), y el Excel `salidas/kardex_movimientos_20260819.xlsx` (hojas `movimientos_articulo`, `sin_consumo`, `en_ambos_kardex`, `movimiento_sin_kardex`, `resumen`).

**Nada de esto se ha migrado a Supabase/Farrusel todavía** — se pidió trabajar en local primero.

---

## Hallazgos de la integración (fichero maestro de huecos)

El usuario pidió **un único archivo final que integre absolutamente todo**: Fase 1
(un hueco por fila, con `ubicación`/`capacidad`/`tipo_hueco`) y Fase 3 (consumo por
artículo en el periodo), porque es la base sobre la que se construirá la propuesta
de mín/máx (Fase 4, todavía no empezada).

**Grano: un hueco físico por fila (1.742).** Los datos de Fase 3 son por código y de
toda la farmacia (sin desglose por hueco), así que se **difunden** a cada hueco de
ese código con prefijo `articulo_` y sufijo `_periodo`, más una columna
`articulo_n_huecos` para que la multiplicidad sea visible — **no sumar esas
columnas entre filas del maestro**, o se cuenta el mismo consumo 2×/3×.

**Cuadre:** 1.742 huecos = 1.709 con consumo (804 códigos) + 33 sin consumo (los
huecos de los 24 códigos de Fase 3 sin movimiento).

**Sistema de colores de alertas** (petición explícita del usuario — antes las
celdas se resaltaban sueltas, sin un criterio unificado):

| Color | Significado | Columnas |
|---|---:|---|
| 🔴 Rojo | Error a corregir | `stock_supera_capacidad` (43), `capacidad_sin_limite` (24 — **ver corrección de convención abajo**), `articulo_sin_consumo_accion = "valorar retirar..."` (30 huecos, 22 códigos) |

Las dos primeras (`stock_supera_capacidad`, `capacidad_sin_limite`) ya no son solo un `True`/color: llevan el texto explicativo de qué corregir en la columna **`alerta_capacidad`** (67 huecos = 43 + 24, mutuamente excluyentes) — ej. *"Corregir: stock (226) supera la capacidad configurada (212) — revisar si es una unidad de medida distinta (envases vs aplicaciones) o reubicar el exceso"* / *"Corregir: capacidad no configurada en la máquina (placeholder 999999999) — configurar una capacidad real antes de fijar min/max"*.
| 🟠 Ámbar | Conocido / a revisar, no bloqueante | `en_proceso_de_baja` (22), `articulo_sin_consumo_accion = "agotar sin reponer..."` (3 huecos, 2 códigos ya en BAJA), `articulo_k1_vs_k2` no nulo (1.442 huecos — limitación de la fuente, no del hueco) |
| ⚪ Gris | Informativo, sin acción | `bloqueado` (0 hoy) |

**Corrección de convención respecto a Fase 1:** `capacidad_sin_limite` (el
placeholder `999999999`) deja de tratarse como dato neutro «sin límite» y pasa a
ser **alerta roja — error a corregir**: sin una capacidad real configurada en esos
24 huecos, no hay contra qué validar un máximo propuesto en Fase 4. Columna
`n_alertas` añadida (recuento de alertas rojas por hueco), mismo patrón que
`n_alertas` en `v_kardex_stock` de Farrusel.

Salidas: `salidas/maestro_huecos.csv` (1.742×29) y el Excel
`salidas/kardex_maestro_huecos_20260819.xlsx` (hojas `maestro_huecos`,
`sin_consumo`, `en_ambos_kardex`, `movimiento_sin_kardex`, `resumen` — esta última
con la leyenda de colores y todas las aclaraciones/avisos escritas en el propio
fichero, no solo aquí). Los ficheros de Fase 1 y Fase 3 por separado **se
mantienen** — el maestro los complementa, no los sustituye.

**Nada de esto se ha migrado a Supabase/Farrusel** — sigue en local. La Fase 4
(motor de propuesta) **no se ha empezado**: este paso solo prepara su entrada.

---

## Lecciones de Farrusel (por qué validamos todo)

Tres corrupciones reales encontradas auditando el módulo del carrusel. Ninguna dio error; todas se descubrieron meses después.

### 1. Fechas invertidas DD/MM ↔ MM/DD
`apd-parser.ts` fija el formato a mano por mapper (`parseFecha(fechaRaw, "MDY")`), sin detectarlo ni validar plausibilidad.

Resultado: **20.876 filas de `movimiento` (10,6 %) con fecha futura**. En los meses 07–12 el día nunca pasa de 6, y los días 1–6 de enero–junio cargan el doble de masa que el resto.

El propio historial de cargas lo confirma: el 04/07/2026 el parser **rechazó 91.385 filas** por «fechas no reconocidas» e insertó 59.053. Sumadas a las 137.462 del 26/06 dan exactamente las 196.515 de `movimiento`. Con formato `MDY`, toda fecha con día > 12 daba mes inválido y se tiraba; las de día ≤ 12 entraron con día y mes intercambiados.

**Efecto en `v_acciones`**: `max(fecha)` se va al futuro y el artículo **desaparece** del tipo `inmovilizado`. Falsos negativos silenciosos.

### 2. Cantidades a escala ×100
71–74 % de `cantidad_movida` son múltiplos exactos de 100 (coma decimal comida), con outliers que revientan cualquier suma. PARACETAMOL 500 mg da 2.103.639 uds/6 meses frente a 191.406 de referencia en Farmatools. **La `tasa_diaria` del §4.5 del brief es incalculable sobre esos datos.**

### 3. Truncamiento silencioso a 1.000 filas ⚠️ SIN ARREGLAR
**PostgREST corta a 1.000 filas por petición e ignora `.limit(20000)`**, que es el patrón que usa todo Farrusel. Devuelve un 200 válido, sin aviso.

| Vista | Filas reales | Se ven | Página |
|---|---:|---:|---|
| `v_regularizacion_detalle` | 11.793 | 1.000 | Regularizaciones — **8 %** |
| `v_regularizacion_mes` | 4.706 | 1.000 | Regularizaciones — 21 % |
| `v_abastecimiento` | 2.912 | 1.000 | Abastecimiento — 34 % |
| `v_caducidad_detalle` | 1.466 | 1.000 | Caducidades — 68 % |

`/kardex/stock` ya pagina correctamente. **Las cuatro páginas del carrusel siguen truncadas.** Está fuera del alcance acordado; pendiente de decidir si se arregla.

---

## Cómo trabajar en este proyecto

### Python
Instalado **3.13.15 per-user** (sin admin). **No está en el PATH de las shells ya abiertas**; usar la ruta completa:

```
C:\Users\ygonperf\AppData\Local\Programs\Python\Python313\python.exe
```

Con pandas 3.0.5, openpyxl, xlrd (para `.xls` binario), chardet, xlsxwriter.

No hay Node ni Excel en la máquina.

### Comandos

```powershell
$py = "C:\Users\ygonperf\AppData\Local\Programs\Python\Python313\python.exe"

& $py tools\test_puertas.py                      # tests de las puertas de validación
& $py tools\inspeccionar.py datos\FICHERO.xls    # perfilado de un fichero nuevo
& $py tools\explorar_hoja.py datos\F.xls --hoja 0 --filas 30   # volcado crudo
& $py tools\estructura.py datos\FICHERO.xls      # secciones y cabeceras repetidas
& $py tools\fase1_inventario.py                  # análisis de Fase 1
& $py tools\exportar_explotacion.py              # Excel plano de Fase 1
& $py tools\fase3_movimientos.py                 # análisis de Fase 3 (movimientos x Fase 1)
& $py tools\exportar_movimientos.py              # Excel de Fase 3
& $py tools\maestro_huecos.py                    # fichero maestro (Fase 1 x Fase 3, un hueco por fila)
& $py tools\exportar_maestro.py                  # Excel maestro con sistema de colores de alertas
& $py tools\cargar_supabase.py                   # carga a Supabase
& $py tools\test_paridad_lovable.py              # parser TS vs parser de referencia
```

### Al recibir un fichero nuevo

1. `explorar_hoja.py` para verlo crudo — **nunca asumir dónde está la cabecera**.
2. `estructura.py` para detectar secciones y cabeceras repetidas.
3. `inspeccionar.py` para el perfil y las puertas de validación.
4. Escribir el parser específico y comprobar que **el reparto de filas cuadra**.
5. Solo entonces cargar.

### Puertas de validación (en `tools/kardex_io.py`)

1. **Formato de fecha detectado, nunca fijado.** Si algún valor tiene >12 en la primera posición es DMY sin ambigüedad. Si toda la columna es ambigua, se resuelve **por descarte**: la lectura que mande fechas al futuro queda eliminada. Si ninguna lo hace, **parar y preguntar**.
2. **Fecha futura = error bloqueante.**
3. **Escala**: >50 % de múltiplos de 100 sin decimales → aviso de coma decimal perdida.
4. **Convención numérica deducida de la columna entera**, nunca supuesta: `"1.234"` aislado es irresoluble.
5. **Cuadre de filas**: total (de fuente independiente) = datos + cabecera + vacías + descartadas.

---

## Entorno

- **Supabase**: proyecto Farrusel, ref `sgpbdzphweyeaegzesvb`
- **Lovable**: proyecto `59f5ea8d-fb5a-4844-844a-46ea2b1dd3e9`
- **App**: https://farrusel.lovable.app
- **Créditos de Lovable gastados**: 13,5 (6 + 1,6 + 5,9)

### Regresión que hay que comprobar siempre
**`v_acciones` NO es una baseline fiable**: la vista usa `now()` tres veces, así que su recuento es una ventana temporal móvil (543 el 2026-08-19, 544 el 2026-08-20, 556 el 2026-08-27 — todo normal, no es un bug). La comprobación real es: **21 vistas en `public`** (16 del carrusel + `v_kardex_stock` + las 4 nuevas del Kardex — ver abajo), y que el carrusel no pierda filas de un día para otro por un cambio nuestro, no un número fijo de `v_acciones`.

---

## Modelo de datos del Kardex en Supabase (ampliado 2026-08-27)

- **`articulo`** (948 filas): añadida `tipo_codigo` (columna **generada**: `kardex` / `bookkeeping` / `otro`, misma regla que el parser — bookkeeping se comprueba antes que kardex porque `DM`+6 dígitos encaja también en el patrón ancho). `ubicaciones` sigue siendo aditiva y solo la toca el informe de stock, nunca el de movimientos.
- **`movimientos_articulo_kardex`** (925 filas): una fila = `(periodo_desde, periodo_hasta, seccion, codigo)`. Clave única sobre esos cuatro campos: recargar el mismo periodo exacto reemplaza; un periodo distinto, aunque solape, convive. `dias_periodo` es columna generada (convención inclusiva). FK a `articulo`.
- **`v_kardex_stock`**: reescrita idéntica, con `security_invoker=true` (antes era la única de las 21 vistas sin él).
- **`v_kardex_maestro`** (nueva): Fase 1 × Fase 3 a nivel de hueco, con `alerta_capacidad` (texto), `articulo_sin_consumo_accion`, `articulo_k1_vs_k2`, `n_alertas` (solo alertas rojas) y el fan-out `articulo_*_periodo` — misma lógica que `tools/maestro_huecos.py`, verificada número a número contra el Excel local.
- **`v_kardex_movimientos_articulo`** (nueva): consumo por artículo y periodo, con las tres clasificaciones (con consumo / sin consumo / sin kardex) — aquí sí es seguro sumar, no hay fan-out.
- **`v_kardex_cortes`** / **`v_kardex_periodos_movimientos`** (nuevas, diminutas): para los selectores de la UI.
- Créditos de Lovable gastados en total: revisar el historial de mensajes del proyecto para la cifra actualizada (la de 13,5 en `Entorno` está desactualizada desde la Sesión 2).

---

## Pendiente al retomar

1. **Conseguir el informe de parametrización** (mín/máx) → desbloquea Fase 2. **Sigue siendo el bloqueo real** del motor de propuesta (Fase 4); ni el informe de movimientos ni el maestro lo sustituyen.
2. **Conseguir un informe de movimientos con desglose por almacén** (K1 vs K2) → sin él no se puede decidir consolidación real, solo detectar «sin consumo en toda la farmacia» (ya hecho, en local y en Farrusel).
3. **Corregir los 24 huecos con `capacidad_sin_limite`** (placeholder `999999999`, alerta roja tanto en el Excel local como en «Gestión Kardex»): configurar una capacidad real en la máquina.
4. Revisar los 22 códigos «sin consumo, nuevos a valorar» con el farmacéutico antes de tocar nada físico — visibles en `/kardex/movimientos` y en el Excel local.
5. Revisar las 43 capacidades incoherentes (`stock_supera_capacidad`): confirmar si el patrón MESALAZINA (unidades distintas entre stock y capacidad) se repite.
6. Confirmar contra el maestro los códigos de formato raro (8 de `V`+7 dígitos y `676262`).
7. Cada nuevo informe de movimientos que llegue debe subirse por `/kardex/subida` (mismo tooltip, mismo aviso de solape de periodos) — el histórico de periodos no se pisa, se acumula.

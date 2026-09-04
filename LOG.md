# LOG del proyecto

Registro cronológico. Lo más reciente arriba.

---

## 2026-08-27 · Sesión 6

Migración de Fase 3 + el fichero maestro a Farrusel, en tres fases con parada de
revisión entre cada una (pedido así por el usuario dado el volumen de trabajo en
Lovable/Supabase).

**Fase A — Supabase.** Antes de tocar nada se congeló la línea base (21 vistas tras el
cambio, articulo=828, huecos=1.742) y se descubrió que la "regresión de 543 filas de
`v_acciones`" documentada desde la Sesión 1 **es inválida por construcción**: la vista
usa `now()` tres veces, así que es una ventana temporal móvil (544 el día 20, 556 hoy).
Se sustituyó esa comprobación en `MEMORIA.md`.

DDL: `articulo.tipo_codigo` (columna generada, bookkeeping evaluado antes que kardex —
mismo gotcha que en el parser), tabla `movimientos_articulo_kardex` (grano
periodo×sección×código, clave única con los dos extremos del periodo para que
recargar el mismo periodo reemplace y uno distinto conviva), vistas nuevas
`v_kardex_maestro`, `v_kardex_movimientos_articulo`, `v_kardex_cortes`,
`v_kardex_periodos_movimientos`, y `v_kardex_stock` reescrita con
`security_invoker=true` (era la única de las 21 sin él).

Para verificar las vistas con datos reales sin esperar al módulo de subida (que aún
no existía), se cargaron los 925 movimientos y los 120 artículos nuevos directamente
por el API REST de Supabase (mismo camino que usará la app). Los números de las
vistas coincidieron **exactamente** con el análisis local: 804 con consumo, 24 sin
consumo (22+2), 120 sin kardex (18 bookkeeping), 586 en ambos kardex, 43+24+67 de las
alertas de capacidad.

**Fase B — Subida en Farrusel.** Nuevo `src/lib/kardex/xlsx.ts` (helpers extraídos de
`stock-huecos.ts`), `movimientos-articulo.ts` (parser + write + existeCorte + ayuda,
espejo del parser Python), `types.ts` ensanchado (`Periodo`, `CorteExistente`, `Ayuda`,
`existeCorte(parsed)` en vez de `existeCorte(fechaCorte)`), y dos bugs arreglados de
paso en `stock-huecos.ts` (el `errores` de la rama de fallo usaba el tamaño del lote
en vez del resto pendiente; `actualizado_en` no se enviaba nunca). El usuario probó la
subida del fichero real él mismo y confirmó que funciona.

**Fase C — Pantallas.** `/kardex/stock` pasa a «Gestión Kardex» (lee `v_kardex_maestro`,
selector de periodo junto al de corte, columna de consumo, badges con texto
explicativo, dos avisos nuevos). Nueva pestaña `/kardex/movimientos`. De paso, se
arregló el truncamiento a 1.000 filas de las 4 páginas del carrusel
(`v_regularizacion_detalle`, `v_regularizacion_mes`, `v_abastecimiento`,
`v_caducidad_detalle`) con un helper `fetchAllRows` centralizado — en
`_app.carrusel.caducidades.tsx` y `_app.carrusel.regularizaciones.tsx` el bug no era
solo de visualización: los KPI y gráficas se calculaban sumando sobre las filas
truncadas, así que también estaban mal.

**Dos bugs propios encontrados y corregidos en revisión antes de darlos por buenos**
(ninguno lo pilló el primer `tsgo`, los dos salieron de una relectura deliberada):
1. `fetchAllRows` cortaba en silencio a las 50.000 filas con `error: null` — el mismo
   fallo que el helper existe para arreglar, a un umbral más alto e invisible. Ahora
   devuelve un error explícito si se alcanza el límite (subido a 200.000).
2. En «Gestión Kardex», el guion "sin alertas" y su chip seguían mirando `n_alertas`
   de la vista, que ahora solo cuenta alertas rojas a propósito — así que un hueco "En
   baja"/"Hueco vacío"/"Sin consumo (agotar)"/"K1≠K2" podía mostrar su badge ámbar Y el
   guion de "sin alertas" a la vez. Se desacopló con un helper `tieneAlgunaAlerta` que
   mira las condiciones reales, no el contador de severidad roja.

Regresión final: 21 vistas, `articulo`=948 (828 con `ubicaciones` intactas + 120
nuevas con `{}`), `movimientos_articulo_kardex`=925, `v_kardex_maestro`=1.742,
`v_kardex_movimientos_articulo`=948 — todo estable.

---

## 2026-08-20 · Sesión 5

Ajuste final sobre el fichero maestro, a petición del usuario: las alertas
`stock_supera_capacidad` y `capacidad_sin_limite` solo tenían un `True`/color,
sin decir qué corregir. Añadida la columna `alerta_capacidad` (texto,
resaltado rojo) con el mensaje concreto por hueco — ej. *"stock (226) supera
la capacidad configurada (212)..."* / *"capacidad no configurada en la
máquina (placeholder 999999999)..."*. Confirmado que las dos alertas son
mutuamente excluyentes (67 = 43 + 24, sin solapamiento), así que no hay
conflicto entre los dos textos. `salidas/maestro_huecos.csv` y
`salidas/kardex_maestro_huecos_20260819.xlsx` pasan de 28 a 29 columnas.
Con esto, el usuario da por cerrada esta fase de integración; toca decidir
si se pasa a la propuesta de mín/máx (Fase 4) o si antes se corrigen los 24
huecos sin capacidad configurada.

---

## 2026-08-20 · Sesión 4

Fichero maestro: integra Fase 1 (un hueco por fila: ubicación, capacidad,
tipo_hueco, stock...) con Fase 3 (consumo por artículo en el periodo), a
petición del usuario ("quiero un archivo final que integre absolutamente todo
nuestros análisis") — es la base sobre la que se construirá la propuesta de
mín/máx (Fase 4, todavía sin empezar).

**Corrección de un supuesto del usuario, verificada empíricamente:** el
usuario pensaba que `tipo_hueco` (ej. "Caj P que 1xALT 1 LED 9 prof") es lo
que fija la `capacidad` de un hueco. Comprobado con
`groupby('tipo_hueco')['capacidad'].agg(['min','max','nunique'])` sobre los
1.742 huecos: **no hay tal relación** — son dos columnas independientes del
informe original (`Cap.` vs `Hueco`). `tipo_hueco` tiene solo 11 valores (todos
modelos físicos de cajón: tamaño/LEDs/nº de divisiones), y cada uno convive con
decenas de capacidades muy distintas (el tipo "04 - ..." va de 2 a 2000 en 69
valores distintos sobre 553 huecos). Se explica en el propio Excel de salida
(hoja `resumen`, fila `ACLARACION`), no solo en este LOG.

**Nuevos scripts** (`tools/maestro_huecos.py`, `tools/exportar_maestro.py`),
ambos con el patrón `construir()`/`main()` ya establecido, reutilizando
`exportar_explotacion.construir()` y `fase3_movimientos.construir()` sin
repetir el cruce ni el bug de dtype booleano ya corregido en la Sesión 3.
`merge(..., validate="m:1")` como puerta de validación nueva: si el lado
código dejara de ser 1:1 algún día, falla alto en vez de colar duplicados.

**Cuadre:** 1.742 huecos = 1.709 con consumo (804 códigos) + 33 sin consumo
(los huecos de los 24 códigos de Fase 3 sin movimiento).

**Sistema de colores de alertas, a petición del usuario** (antes se resaltaban
celdas sueltas sin un criterio unificado): rojo = error a corregir
(`stock_supera_capacidad`, `capacidad_sin_limite`, `articulo_sin_consumo_accion`
= "valorar retirar..."), ámbar = conocido/a revisar (`en_proceso_de_baja`,
"agotar sin reponer...", `articulo_k1_vs_k2`), gris = informativo
(`bloqueado`). Columna `n_alertas` nueva (recuento de alertas rojas por hueco,
mismo patrón que `v_kardex_stock` de Farrusel).

**Segundo ajuste pedido por el usuario, ya incorporado en el diseño (no hubo
que reescribir código después):** `capacidad_sin_limite` (el placeholder
`999999999`, 24 huecos) deja de tratarse como dato neutro «sin límite» y pasa
a ser **alerta roja — error a corregir**: sin una capacidad real configurada
no se puede validar un máximo propuesto contra ella en Fase 4.

Salidas: `salidas/maestro_huecos.csv` (1.742×28) y
`salidas/kardex_maestro_huecos_20260819.xlsx` (hojas `maestro_huecos`,
`sin_consumo`, `en_ambos_kardex`, `movimiento_sin_kardex`, `resumen` con
leyenda de colores y todos los avisos escritos en el propio fichero). Los
Excel de Fase 1 y Fase 3 por separado se mantienen, el maestro los
complementa.

**Nada tocado en Supabase ni en Farrusel.** La Fase 4 (motor de propuesta) no
se ha empezado — pendiente para la próxima sesión, según lo acordado con el
usuario.

---

## 2026-08-20 · Sesión 3

Fase 3: preprocesado del `Informe_MovimientosArtículo.xls` y cruce con el inventario
de huecos de Fase 1, antes de tocar Farrusel (pedido explícito: local primero).

**Exploración** (`explorar_hoja.py`/`estructura.py`/`inspeccionar.py`, luego un agente
Explore y otro Plan para verificar en detalle): fichero de 969 filas, en realidad un
`.xlsx` renombrado `.xls` (pandas/openpyxl lo leen igual, sin cambios en
`kardex_io.py`). Dos secciones («Articulos Internos»/«Articulos Externos»), cada una
con su cabecera repetida una vez, sin pie de totales. Periodo `Desde 01/01/2026` –
`Hasta 19/08/2026` en la cabecera (231 días, convención inclusiva). Puertas de
validación sin incidencias bloqueantes: fechas DMY sin futuras, cantidades sin señal
de escala ×100.

**Parser nuevo** (`tools/parser_movimientos_articulo.py`, reutilizando `RE_CODIGO`,
`RE_BAJA`, `formato_codigo` de `parser_stock_huecos.py`): detección de secciones y
cabecera por contenido, clasificación `tipo_codigo` (`kardex`/`bookkeeping`/`otro`) y
`periodo_del_informe()`. **Bug encontrado y corregido antes de cerrar el parser:**
`DM`+6 dígitos encaja también en el patrón ancho de código de Kardex
(`[A-Z]{0,2}\d{4,8}`) — había que comprobar bookkeeping **antes** que kardex, si no
los 16 apuntes DM se colaban como si fueran artículos. Verificado contra el fichero
real: cuadre exacto `969 = 925 datos + 7 cabecera + 37 vacías + 0 descartadas`,
906 códigos kardex + 18 bookkeeping (16 DM + NOGUIA + PAC), un código duplicado
(`V02254`) que el parser mantiene sin fusionar a propósito.

**Análisis y cruce** (`tools/fase3_movimientos.py`, con una función `construir()`
reutilizable en vez de duplicar la lógica en el exportador): agrega por código
(aquí sí se fusiona `V02254`), calcula `tasa_diaria`/`tasa_7d`/`tasa_30d` como
extrapolación lineal del total del periodo, y cruza contra
`salidas/fase1_articulos.csv` (828 códigos). **Segundo bug encontrado y corregido:**
el outer merge deja columnas booleanas en dtype `object` (mezcladas con `NaN`), y un
`~` sobre eso invierte bits en vez de booleanos (`~True == -2` en Python) — daba
"-26 nuevos a valorar". Se corrigió normalizando esas columnas (`fillna(False)
.astype(bool)`) justo después del merge.

**Resultado del cruce:** 804 códigos con consumo en el periodo, **24 en el Kardex sin
ningún movimiento** (22 nuevos a valorar + 2 ya marcados `BAJA`, consistente), 120
con movimiento pero fuera del inventario de huecos (18 bookkeeping + 102 artículos no
ubicados en KARDEX1/2), 586 en ambos kardex con consumo. Acción para los 22 nuevos:
**valorar retirar e introducir en carrusel**.

**Limitación explícita, no resuelta en esta sesión:** el informe es de toda la
farmacia, sin desglose por almacén — no puede decir si el consumo vino de KARDEX1,
de KARDEX2 o de ambos. La consolidación real (el objetivo final: un único hueco por
medicamento entre los dos kardex) sigue sin poder decidirse sin un informe de
movimientos por almacén. Se dejó escrito en el propio dato (`k1_vs_k2 = "no
resuelto..."`), no solo en `MEMORIA.md`.

**Exportador Excel** (`tools/exportar_movimientos.py`, reutilizando `construir()`):
`salidas/kardex_movimientos_20260819.xlsx` con hojas `movimientos_articulo`,
`sin_consumo`, `en_ambos_kardex`, `movimiento_sin_kardex` y `resumen` (con el aviso
K1/K2 y el de extrapolación de tasas escritos ahí también).

**Tests:** 5 casos nuevos en `tools/test_puertas.py` (primeros que prueban un parser
concreto, no solo los gates genéricos de `kardex_io.py`): dos secciones + cuadre,
código duplicado no fusionado por el parser, `periodo_del_informe`, reutilización de
`RE_BAJA`, y fechas con componente de hora (nunca probado hasta ahora). Todo en verde.

**Nada tocado en Supabase ni en Farrusel** — expresamente pospuesto a petición del
usuario hasta terminar este análisis local.

---

## 2026-08-20 · Sesión 2

Ajuste pedido sobre la pestaña `/kardex/stock` antes de abrir la Fase 2: reflejar
la fecha de descarga del corte y, al subir un fichero nuevo, resaltar en color ocre
(design system Frello, token `accent` / frello-gold `#D4AF37`) los valores que
cambiaron respecto al corte anterior del mismo hueco.

**Supabase:** `v_kardex_stock` reemplazada con una comparación por `LAG()` contra la
fila anterior de cada `(almacen, ubicacion)`: expone `cargado_en` (fecha de
integración real, ya existía en la tabla pero no en la vista), `hueco_nuevo`,
`fecha_descarga_anterior` y flags `cambio_stock` / `cambio_capacidad` /
`cambio_codigo` / `cambio_descripcion` / `cambio_tipo_hueco` / `cambio_bloqueado` /
`cambio_en_proceso_de_baja` / `ha_cambiado`. Regresión comprobada: 1.742 filas
(igual que Fase 1); con el único corte cargado hoy todo sale `hueco_nuevo` y 0
`ha_cambiado`, como se espera hasta que exista un segundo corte real que comparar.

**Farrusel (vía agente Lovable):** editado solo `src/routes/_app.kardex.stock.tsx`.
Añade "Corte del DD/MM/AAAA · integrado el DD/MM/AAAA a las HH:MM" en la tarjeta de
cabecera; pinta en `accent` las celdas de Código, Descripción, Stock, Capacidad,
Tipo de hueco y el badge "En baja" cuando cambiaron en el corte más reciente (nunca
en cortes antiguos ni en huecos sin corte previo); añade badge "Nuevo" para huecos
sin corte anterior. Typecheck (`tsgo`) limpio. Commit `23e8d04c...`, 3 créditos.

**Pendiente de esta sesión:** el deploy a producción (`farrusel.lovable.app`) quedó
bloqueado por el clasificador de permisos de Claude Code — la pestaña Stock sigue
sin publicar, igual que al cierre de la Sesión 1. Falta confirmación explícita del
usuario para publicar y verificar en vivo.

---

## 2026-08-19 · Sesión 1

Arranque del proyecto. De un brief que resultó estar equivocado a un módulo Kardex funcionando en producción con el primer corte cargado.

### 1. Auditoría del punto de partida

El brief pedía construir la vista `v_acciones` en Supabase «porque no existe todavía».

**Era falso.** La vista existía, funcionaba y devolvía **543 filas** con los 6 tipos poblados — igual que las otras 15 vistas que consulta el frontend. El entregable principal descrito en el brief ya estaba hecho.

Lo que sí faltaba era el módulo Kardex, y toda la sección 4 del brief apuntaba ahí.

**Desconexión de fondo detectada:** el brief razona sobre KARDEX1/KARDEX2, pero en Supabase solo hay `ACH`/`ACVR`/`EXT` y **cero movimientos de kardex**. El Kardex Vertical es otra máquina, de otro fabricante. La app ya tenía `/kardex/subida` y `/kardex/ajuste` creadas y marcadas «En construcción».

### 2. Corrupciones encontradas en Farrusel

Auditando el módulo del carrusel aparecieron tres fallos que llevaban meses sin detectar. Ninguno daba error.

- **20.876 filas de `movimiento` (10,6 %) con fecha futura**, por inversión DD/MM ↔ MM/DD. El parser fijaba el formato a mano sin validarlo. Confirmado después por el propio historial de cargas: el 04/07 rechazó **91.385 filas** por «fechas no reconocidas».
- **Cantidades a escala ×100** con outliers que hacen inútil cualquier suma. Bloquea el cálculo de `tasa_diaria` del brief.
- Los datos llevaban congelados desde el 04/07 y todas las vistas usan ventanas `now() - 90 días`: la app se vacía sola con el paso del tiempo.

Esto determinó el método del proyecto: **validar archivo por archivo, con puertas explícitas**.

### 3. Decisiones de alcance (con Yared)

- Prioridad: **construir el módulo Kardex**, no parchear el carrusel.
- Cadencia **trimestral/semestral**, por cortes. El histórico se versiona, no se pisa.
- Método: **local primero, migración a Farrusel paso a paso**.
- Entregable: lista **Subir/Bajar/Mantener**.
- Baja rotación: marcar «sin consumo» y comprobar presencia en los dos kardex, no proponer 0.

### 4. Entorno

Sin Python, sin Node, sin Excel en la máquina. Instalado **Python 3.13.15 per-user** (sin admin, vía instalador oficial; no había winget ni gestor de paquetes) con pandas, openpyxl, xlrd, chardet y xlsxwriter.

### 5. Herramienta de validación

`tools/kardex_io.py` con las puertas, y `tools/test_puertas.py` que **reproduce las corrupciones reales de Farrusel** como casos de prueba.

Los tests encontraron **dos fallos de diseño propios**, ambos corregidos:

- Las fechas ambiguas no se comprobaban contra el futuro. Ahora se resuelven **por descarte**: si leerlas como MDY manda filas al futuro y como DMY no, queda decidido. Es el razonamiento que destapó el bug de Farrusel, ahora automatizado.
- El parseo numérico **adivinaba** la convención. `"1.234"` puede ser 1234 o 1,234 y es irresoluble aislado — pero una columna entera sí tiene evidencia. Ahora se deduce del conjunto y, si hay mezcla, se avisa.

### 6. Fase 1 — Inventario de K1 y K2

Fichero: `Informe_StockHuecos.xls`, XLS binario (OLE2), dos hojas. Estaba abierto en otro programa, así que la herramienta pasó a leer en modo compartido.

**Trampa:** salida paginada para imprimir, con el bloque de cabecera repetido cada ~48 filas — **295 filas de cabecera**. Un parseo directo las habría cargado como medicamentos.

Parseo con cuadre exacto: **2.857 filas = 1.742 datos + 295 cabecera + 820 vacías + 0 descartadas**.

En la primera pasada se descartaron 9 filas por un patrón de código demasiado estricto. Eran **medicamentos legítimos** (`V0715227`, `676262`…). Patrón ampliado; cero descartes.

**Resultados:** 1.742 huecos, 828 artículos, 1.418 pares artículo×armario (el piloto en Excel del brief: 1.419 — mismo universo).

**Hallazgo principal:** 99,9 % de huecos asignados pero solo ~35 % de llenado físico. **El cuello de botella son las posiciones, no el volumen.**

Otros: 590 artículos (71 %) en los dos kardex · 43 huecos con stock sobre capacidad (peor caso 1.387 %, que es una unidad de medida distinta, no un desbordamiento) · 24 con el placeholder `999999999` que avisaba el brief · 22 huecos de artículos en proceso de baja.

**Corrección de Yared:** los `BAJA` están *en proceso* de darse de baja, no dados de baja — si lo estuvieran no saldrían en el catálogo. La acción es **agotar sin reponer**, no retirar.

### 7. Excel de explotación y modelo de datos

Generado `kardex_inventario_huecos_20260819.xlsx`: una hoja, 1.742 filas, con almacén y fecha de corte en cada fila, autofiltro y marcas de calidad resaltadas. La fecha se **lee del propio informe**, no se teclea.

Creadas en Supabase:

- **`articulo`** — maestro transversal (828 filas). `ubicaciones text[]` con índice GIN, que **se fusiona y no se machaca** para ir creciendo con `CH`, `CV`, `FARMACIA_HUNSC`, `FARMACIA_SUR`.
- **`inventario_huecos_kardex`** — 1.742 filas. `unique(fecha_descarga, almacen, ubicacion)`: hace idempotente reprocesar y **conserva los cortes anteriores**, que es lo que permitirá medir si lo aplicado funcionó.

Cargado por API REST con la clave publicable — el mismo camino que usa la app.

### 8. Migración a Farrusel

`/kardex/subida` implementada por el agente de Lovable con un **registro de tipos de informe**, para que añadir el siguiente sea una entrada más y no reescribir la pantalla (el carrusel tiene ese conocimiento repartido en 4 sitios de 2 ficheros).

**Verificación:** se replicó la lógica exacta del parser TypeScript en Python (`test_paridad_lovable.py`) y se comparó contra el parser de referencia. **Paridad total**: mismas 1.742 filas, mismo reparto por armario, mismos 828 artículos, mismas marcas de calidad y el mismo código en cada hueco.

Único fichero compartido tocado: `Historial.tsx`, con un `modo: "eq" | "like"` opcional. Retrocompatible.

**Bug encontrado al probar:** el semáforo salía en error con «faltan 1.117 filas». Era contabilidad, no datos: `leidas` se rellenaba con **todas** las filas del fichero (2.859) en vez de las de datos (1.742), y las «perdidas» eran la paginación y los blancos. Corregido. De paso, el cuadre era una tautología (`total` se incrementaba dentro del mismo bucle que repartía) — ahora viene de fuente independiente.

La recarga del mismo corte **no duplicó nada**: idempotencia confirmada.

### 9. Pestaña Stock

Vista `v_kardex_stock` con las alertas calculadas **junto al dato que las origina**, para poder auditarlas. `en_ambos_kardex` y `articulo_multihueco` se dejaron **fuera** del recuento de alertas: afectan a 1.452 y 1.550 huecos, son contexto y no incidencias.

Página `/kardex/stock` con buscador sin acentos, filtro por almacén y corte, chips de alerta pulsables, tabla ordenable y exportación CSV de lo filtrado.

**Hallazgo importante durante el desarrollo:** PostgREST **corta a 1.000 filas por petición e ignora `.limit(20000)`**, que es el patrón de todo Farrusel. La página nueva pagina correctamente, pero **cuatro páginas del carrusel siguen truncadas**: Regularizaciones muestra el 8 % de sus datos, Abastecimiento el 34 %, Caducidades el 68 %. Sin ningún aviso, porque la respuesta es un 200 válido.

Pendiente de decidir si se arregla (está fuera del alcance acordado).

### Cierre de la sesión

Regresión comprobada: `v_acciones` sigue en **543 filas** con idéntico reparto, y las 16 vistas del carrusel intactas.

Créditos de Lovable gastados: **13,5** (6 + 1,6 + 5,9).

**Pendiente para mañana:** publicar la pestaña Stock, y conseguir el **informe de parametrización (mín/máx)**, que es lo único que bloquea la Fase 2 y con ella todo el motor de propuesta.

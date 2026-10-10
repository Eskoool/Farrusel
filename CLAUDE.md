# Farrusel · Optimización del Kardex

Contrato invariante del proyecto. Se lee al inicio de cada sesión.
Si algo de aquí ha dejado de ser cierto, no lo edites en caliente: pasa por `/cambio`.

## Qué es esto

La herramienta que convierte tres informes del Kardex y de Farmatools en una lista de
decisiones Subir / Bajar / Mantener por artículo y armario, con registro de qué se aceptó y
qué se aplicó en la máquina. Módulo Kardex de Farrusel, hermano del módulo del carrusel.

Documento de referencia: `PRD.md`. Estado actual: `MEMORIA.md`. Historial: `LOG.md`.

⚠ **Este repo no contiene el código de la app.** La app vive en **Lovable** (proyecto
`59f5ea8d-fb5a-4844-844a-46ea2b1dd3e9`) sobre Supabase `sgpbdzphweyeaegzesvb`. Aquí viven:
el PRD, la memoria, el log, las herramientas Python de **validación** (`tools/`) y la
documentación del modelo de datos (`salidas/*.md`). Los nombres `MEMORIA.md` y `LOG.md` van
en mayúsculas porque existían antes del andamiaje de `forja-prd`; hacen el papel de
`memoria.md` y `log.md` y no se renombran.

## Stack fijado

Vite + React + TypeScript + Tailwind + shadcn/ui (design system «Frello») · Supabase
Postgres 17 · PostgREST vía `fetchAllRows` · Python 3.13 per-user para `tools/`.

Motor de build: **Lovable** para el MVP. v2: Claude Code + Vercel sobre **el mismo Supabase**
(PRD §12). Las tablas, vistas, triggers y políticas son el contrato que hace posible esa
migración: no se diseñan pensando en Lovable.

## Reglas que no se negocian

1. **Sin datos de pacientes.** Ni reales, ni pseudonimizados, ni "solo para probar". Ninguna
   tabla lleva columnas de paciente (NFR-003).
2. **El histórico no se pisa.** Recargar el mismo corte reemplaza *ese* corte; otro corte
   convive. `propuesta_kardex` es append-only.
3. **Toda fila pasa una puerta antes de escribirse.** Cuadre de filas de fuente independiente,
   fecha detectada (o pedida, nunca deducida), fecha futura = bloqueo, vacío numérico = `null`.
4. **Motor:** `minimo = max(1, floor(tasa × díasMin))`, `maximo = max(minimo, min(floor(tasa ×
   díasMax), capacidad))`. `FLOOR` siempre, ±10 %, nunca 0 a un artículo que se consume,
   «Hueco insuficiente» antes que un recorte silencioso. **Excepción v1.2 (REQ-026):** en modo
   «Un solo hueco» por armario el máximo no se topa y la capacidad a configurar = máximo. Los
   días de cobertura son por artículo en la ventana (REQ-025). Se compara contra `capacidad`, jamás
   contra `tipo_hueco`; `999999999` nunca es capacidad real.
5. **Un artículo en K1 y K2 tiene una propuesta del par.** Las dos filas la repiten y no se
   suman. `cobertura_*` y `consumo_medio_mensual` tampoco.
6. **Farmatools solo compara el mismo día.** Con desfase, discrepancia a `null` y aviso.
7. **Tablas propias `kardex_*` / `articulo`, nunca las del carrusel.** Ninguna vista del
   carrusel se modifica; solo se cambia cómo se leen (REQ-017). Desde la v1.3 el carrusel
   entra en «Medicamentos» por la tabla propia `inventario_almacen` y vistas nuevas; leerlo sí,
   modificar sus tablas o vistas, no.
8. **Sin login en la v1: enlace = permiso.** Riesgo asumido (PRD §10). No se añade auth sin
   pasar por `/cambio`; la identidad federada con Frello es v1.2.
9. **Los secretos viven solo en el servidor.** En la v1 no hay ninguno; el día que exista una
   Edge Function, su clave nunca llega al navegador.
10. **Lovable consume créditos: se avisa antes de cada envío** y se anota el gasto en `LOG.md`.
11. **Una sesión en Lovable sin entrada en `LOG.md` el mismo día es una sesión perdida.** Ya
    pasó el 2026-08-28.

## Cláusula de parada

Si una petición contradice el PRD, o pide algo que el PRD no contempla:

**para, dilo y pregunta antes de escribir código.**

No amplíes el alcance por iniciativa propia, aunque la ampliación parezca obvia y pequeña.
Las funcionalidades que nadie decidió meter son las que nadie sabe mantener. La vía
correcta es `/cambio`.

## Comandos del repo

```powershell
$py = "C:\Users\ygonperf\AppData\Local\Programs\Python\Python313\python.exe"
& $py tools\test_puertas.py                # puertas de validación
& $py tools\test_paridad_lovable.py        # parser TS de Lovable vs parser de referencia
& $py tools\inspeccionar.py datos\F.xls    # perfilado de un fichero nuevo (nunca asumir la cabecera)
& $py tools\estructura.py datos\F.xls      # secciones y cabeceras repetidas
```

Regresión obligatoria tras tocar Supabase: **22 vistas en `public`** y las 16 del carrusel sin
perder filas (NFR-004). `v_acciones` no es baseline: usa `now()`.

Comandos de sesión: `/checkpoint` vuelca el estado a `MEMORIA.md` y `LOG.md`, `/cambio`
tramita una desviación del PRD, `/auditar` pasa la rúbrica al documento y al código,
`/prompt` genera la instrucción pegable de una fase.

## Al cerrar sesión

Actualiza `MEMORIA.md` (estado presente) y añade una entrada a `LOG.md` (qué se hizo, qué se
desvió, créditos gastados). O invoca `/checkpoint` y hazlo de una vez. Después, `git push`:
este repo tiene remoto (`Eskoool/Farrusel`) y lo que no se sube no existe.

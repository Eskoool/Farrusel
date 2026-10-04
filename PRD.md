# PRD · Farrusel · Optimización del Kardex

## 0. Metadatos

```
Versión: 1.1
Fecha: 2026-10-04
Estado: v1.0 aprobada (OK de Yared, 2026-09-21); v1.1 = /cambio del 2026-10-04 (OK de Yared)
Motor de build: Lovable (MVP). Las herramientas Python de tools/ son SOLO validación del
modelo de datos, no producto. v2: migración a Claude Code + Vercel, mismo Supabase (§12)
Autor: Yared González, con Claude (forja-prd)
Proyecto Lovable: 59f5ea8d-fb5a-4844-844a-46ea2b1dd3e9 · Supabase: sgpbdzphweyeaegzesvb
App: https://farrusel.lovable.app
```

Este PRD se escribe **sobre un producto a medias**: siete sesiones construidas (2026-08-19 →
2026-08-28) sin documento de producto. Lo construido se fija aquí como requisitos ya
cumplidos (marcados ✅) para que el control de cambios tenga contra qué medir; lo que
falta se numera igual y va a §11. El detalle histórico está en `LOG.md`; el presente, en
`MEMORIA.md`.

---

## 1. Resumen ejecutivo · *capa QUÉ*

**Farrusel-Kardex es la herramienta que convierte tres informes del Kardex y de Farmatools
en una lista de decisiones Subir / Bajar / Mantener por artículo y armario, con registro de
qué se aceptó y qué se aplicó en la máquina.**

Para el farmacéutico del área de dispensación del HUNSC. Sube el informe de stock por hueco,
el de movimientos por artículo y el stock general de Farmatools; la app cruza los tres, marca
las alertas (capacidad sin configurar, stock que supera la capacidad, sin consumo, hueco
insuficiente), propone mínimo y máximo con una fórmula explícita, y guarda la decisión con su
estado. Stack: Vite + React + TypeScript + Tailwind sobre Supabase (Postgres 17), construido
en Lovable como módulo hermano del carrusel. Lo que lo distingue de la hoja de cálculo del
piloto: los cortes se acumulan y no se pisan, cada dato pasa una puerta de validación antes
de escribirse, y la decisión queda registrada con fecha y estado, lo que permite medir en el
siguiente corte si funcionó.

## 2. Problema, usuario y éxito · *capa QUÉ*

- **Problema:** los dos Kardex tienen el 99,9 % de los huecos ocupados y cada uno guarda un
  tercio de lo que admite (33,9 % en K1, 37,1 % en K2, corte 19-08-2026). La parametrización
  de mín/máx no se revisa con método; se ajusta a ojo cuando algo falta o sobra. 590 de 828
  artículos están en los dos armarios sin saber si hace falta.
- **Solución actual:** un piloto en Excel sobre 1.419 pares artículo×armario, rehecho a mano
  en cada corte. No acumula histórico, no valida el dato de entrada (el módulo del carrusel
  arrastró tres corrupciones durante meses por eso), y no registra qué se decidió.
- **Usuario:** el farmacéutico responsable del área de dispensación (hoy Yared). Entra por
  enlace, sin login. Otros farmacéuticos y técnicos pueden abrir el enlace para consultar.
  La identidad (quién cargó, quién decidió) queda **aplazada a la v1.2** (§12), pendiente de
  validar; en la v1 no se registra quién escribe.
- **Métricas de éxito** (fijadas por Yared el 2026-09-21):
  1. **Número de usos:** aperturas de «Gestión Kardex» y de `/kardex/subida` registradas por
     la propia app. Objetivo: **≥ 1 corte cargado al mes y ≥ 4 sesiones de consulta al mes**
     durante tres meses seguidos.
  2. **Automatizaciones realizadas con éxito:** eventos terminales emitidos (corte cargado,
     propuesta aceptada/aplicada) y procesados sin error por el consumidor (primero la propia
     app; después Frello). Objetivo: **≥ 95 % de eventos procesados con éxito** en el mes.
  3. Derivada, para que las dos anteriores signifiquen algo: **un ciclo completo** (dos
     informes del mismo día → propuestas aceptadas → aplicadas → siguiente corte cargado)
     antes del 2026-12-31.

## 3. Alcance · *capa QUÉ*

**Dentro de la v1** (✅ = ya construido y verificado; el resto se construye en §11):

1. `[Must]` ✅ Subida de tres informes con puertas de validación y cuadre de filas
   (stock por hueco, movimientos por artículo, stock general de Farmatools).
2. `[Must]` ✅ Cortes acumulativos e idempotentes: recargar el mismo corte reemplaza, otro convive.
3. `[Must]` ✅ «Gestión Kardex» como única pantalla de consulta, una fila por artículo×armario,
   modal de detalle con huecos, consumo, alertas, económico, Farmatools y cobertura.
4. `[Must]` ✅ Motor de propuesta de mín/máx con fórmula explícita y estados de acción.
5. `[Must]` ✅ Edición manual de mín/máx (`parametrizacion_kardex`, `fuente = 'manual'`).
6. `[Must]` ✅ Cruce con Farmatools con comparabilidad estricta (mismo día) y consumo válido.
7. `[Must]` **Registro de decisiones con estados**: propuesta → aceptada | rechazada → aplicada,
   con historial por corte. **Es el evento terminal** que la conexión con Frello consumirá.
8. `[Must]` **Eventos y bandeja de salida** (`evento_kardex`): cada evento terminal queda
   escrito con su estado de procesado. Sin consumidor externo todavía.
9. `[Must]` **Registro de uso** (`uso_evento`): aperturas de pantalla y acciones, agregadas
   sin identificar a nadie.
10. `[Should]` ✅ Cuarto informe: **parametrización mín/máx de la máquina** (`fuente = 'informe'`).
    Es el informe «Ocupación de armario» (StocKey → Informes → Armarios), con el mínimo y el
    máximo configurados hoy en cada artículo y armario. Cargado el 2026-09-23: 1.418 filas.
    Contrato y reglas de carga en REQ-016.
11. `[Should]` Corregir el truncamiento a 1.000 filas en las cuatro páginas del carrusel
    (`fetchAllRows`).
12. `[Should]` Parser Python de referencia del informe de Farmatools
    (`tools/parser_stock_farmatools.py`) y su prueba de paridad con el parser TS. **Solo
    validación**: no es producto.
13. `[Could]` Pantalla «Actividad»: usos, eventos y automatizaciones del mes.

**Fuera de alcance** (contractual; si aparece, pasa por `/cambio`):

- **Escribir en Frello.** La bandeja de salida está dentro; el consumidor que escribe en
  la Supabase de Frello es la v1.1 (`proyectos/farrusel/plan-conexion-frello.md`). Motivo:
  Frello es producción con 105 usuarios y su escritura necesita su propio diseño y OK.
- **Login, roles, RLS por usuario, trazabilidad de quién escribe.** Decidido por Yared el
  2026-09-21: en la v1, enlace = permiso (§10). La **identidad federada con el Auth de
  Frello** se estudió el mismo día, es viable (§12, v1.2) y queda **pendiente de validar en
  una iteración futura**; no entra ahora.
- **Resolver K1 vs K2 con datos.** El informe de movimientos es de toda la farmacia; sin
  un informe con desglose por almacén, `k1_vs_k2` sigue «no resuelto». Depende del sistema
  origen, no de esta app.
- **Proponer 0 a baja rotación.** Nunca. Se marca «Sin consumo» y se decide a mano.
- **Tocar las tablas o vistas del carrusel** salvo el punto 11 (que no cambia datos, solo
  cómo se leen).
- **Datos de pacientes.** No existen en Farrusel y no van a existir (§10).
- **Reenvasados, caducidades del Kardex, pedidos a proveedor.** Otros módulos u otros
  proyectos.
- **Cuadro de mando / KPIs de dirección.** El entregable es la lista de decisiones.

## 4. Decisiones técnicas · *capa CÓMO*

| Decisión | Elección | Por qué | Alternativas descartadas |
|---|---|---|---|
| Framework y lenguaje | Vite + React + TypeScript | Es lo que Lovable genera y lo que ya tiene el módulo del carrusel | Next.js (no aporta SSR aquí) |
| Estilos y componentes | Tailwind + shadcn/ui, design system «Frello» (`HeroHeader`, `SectionCard`, `Metric`, tokens `accent`/`warning`/`destructive`) | Coherencia con Frello y con el carrusel; ya está en el proyecto | Estilo neutro (rompería la coherencia visual del servicio) |
| Base de datos | Supabase Postgres 17, proyecto `sgpbdzphweyeaegzesvb` | Ya aloja el carrusel; tablas propias `kardex_*`/`articulo` | Compartir tablas del carrusel (sus vistas no filtran por almacén) |
| Lectura desde el cliente | PostgREST con `fetchAllRows` (`src/lib/supabase-fetch-all.ts`) | PostgREST corta a 1.000 filas e ignora `.limit`; el helper falla explícito al tope | Bucle manual de 25×1.000 (se calla al truncar) |
| Autenticación | **Ninguna en la v1.** Enlace público, clave `anon` lee y escribe | Decisión de Yared 2026-09-21: quien tiene el enlace, escribe; la identidad se aplaza a la v1.2 para validarla aparte | **Identidad federada de Frello** (aplazada a v1.2, no descartada: viable, ver §12); PIN compartido verificado en Edge Function; Supabase Auth propio (duplicaría 105 usuarios) |
| Hosting | Lovable (`farrusel.lovable.app`) para el MVP | Es donde vive el código de la app | Vercel + repo local: es la **v2**, no una alternativa descartada (§12) |
| Gestión de estado | `useMemo` por fila, estado local por pantalla; sin store global | Una pantalla, un origen de datos | Zustand/Redux (sin necesidad) |
| Eventos terminales | Tabla `evento_kardex` como **outbox** poblada por trigger | El consumidor (Frello) no existe aún; el outbox desacopla y hace medible el 95 % | Llamar a una Edge Function desde el cliente (sin garantía de entrega) |
| Fecha de un informe | Se extrae del fichero si la lleva; si no (Farmatools), **se pide** | Nunca se deduce: decide contra qué corte se compara | `file.lastModified` como verdad (solo se ofrece como sugerencia) |
| Números de Excel | Lectura `raw` (`sheetGridRaw`), sin parseo de texto | `toInt` asumía millares con punto y multiplicaba precios ×100 | Parsear cadenas con heurística de convención |
| Herramientas Python | `tools/` en repo local `Eskoool/Farrusel`, Python 3.13 per-user. **Validación, no producto** | Parsers de referencia y paridad contra el TS de Lovable, una vez montado el modelo de datos | Portar todo a TS (perdería la doble comprobación); hacerlas producto (no lo son) |

## 5. Arquitectura y flujo · *capa CÓMO*

```
 Farmacéutico (navegador, sin login, clave anon)
   │
   │  1. /kardex/subida ──► parser TS (detecta · parsea · cuadra · métricas) ──► upsert por corte
   │  2. /kardex/stock  ──► v_kardex_articulo_armario (fetchAllRows) ──► propuesta en cliente
   │  3. modal ─────────► upsert parametrizacion_kardex · insert/update propuesta_kardex (estado)
   │  4. cada pantalla ─► insert uso_evento
   ▼
 Supabase Farrusel (sgpbdzphweyeaegzesvb, eu-central-1)
   ├── tablas Kardex: articulo · inventario_huecos_kardex · movimientos_articulo_kardex
   │                  · stock_farmatools · parametrizacion_kardex · propuesta_kardex (nueva)
   ├── vistas: v_kardex_articulo_armario · v_kardex_maestro · v_kardex_movimientos_articulo
   │           · v_kardex_cortes · v_kardex_periodos_movimientos · v_kardex_stock (22 en total)
   ├── triggers ──► evento_kardex (outbox)                          [nuevo, §6]
   └── uso_evento (métrica, sin identidad)                          [nuevo, §6]
                     │
                     ▼  (v1.1, fuera de este PRD)
              Edge Function notify-frello ──► Supabase Frello (julrvkllcifpcdyvbikr)
```

**Frontera de secretos.** En la v1 **no hay ningún secreto**: el cliente usa la clave
publicable `anon` y nada más. El día que exista `notify-frello`, la clave de servicio de
Frello vive como secreto de la Edge Function de Farrusel y nunca en el navegador (§10). Si en
la v1.2 entra la identidad federada, se suma `FRELLO_JWT_SECRET` a esa misma lista.

**Recorrido principal: de un informe a una decisión aplicada.**

1. *Navegador.* El farmacéutico arrastra `Informe_StockHuecos.xls` a `/kardex/subida`. El
   registro de informes (`registry.ts`) detecta cuál es por sus columnas.
2. *Navegador.* El parser lee la fecha del corte de la cabecera (o la pide, si es
   Farmatools), reparte filas (datos / cabecera / vacías / descartadas) y calcula las
   métricas de control. Si el cuadre no cierra o hay fecha futura, **para** (REQ-002).
3. *Navegador → Supabase.* Revisión previa con cifras; al confirmar, upsert por lotes con
   clave de corte (`fecha_descarga, almacen, ubicacion` o `fecha_descarga, codigo`).
4. *Supabase.* Si es el primer upsert de ese corte, `trg_evento_kardex` inserta
   `evento_kardex (tipo = 'corte_cargado')`.
5. *Navegador.* En «Gestión Kardex», `fetchAllRows` trae `v_kardex_articulo_armario`;
   `calcularPropuesta` corre una vez por fila (`useMemo`) con los días de cobertura de la
   cabecera.
6. *Navegador.* El farmacéutico abre una fila, ve actual → propuesto, pulsa **Aceptar**
   (o Rechazar, con nota). *Supabase:* insert en `propuesta_kardex` con `estado =
   'aceptada'`; el trigger emite `evento_kardex (tipo = 'propuesta_aceptada')`.
7. *Máquina (fuera de la app).* Configura el mín/máx en el Kardex.
8. *Navegador.* Marca la propuesta como **Aplicada**. *Supabase:* `estado = 'aplicada'`,
   `aplicada_en = now()`, evento `propuesta_aplicada`, y `parametrizacion_kardex` se
   actualiza con `fuente = 'aplicada'`.
9. *Siguiente corte.* Al cargar el nuevo stock por hueco, la vista muestra el llenado y
   `ha_cambiado`; la pantalla «Actividad» (Could) cuenta usos y eventos.

**Regla CRUD vs servidor:** toda lectura y escritura va directa desde el cliente con
`anon` (no hay usuarios que aislar). Solo pasará por servidor lo que toque un secreto: el
consumidor de `evento_kardex` (v1.1) y, si entra, la identidad federada de la v1.2.

## 6. Modelo de datos · *capa CÓMO*

**Existente** (verificado contra Supabase el 2026-09-21; DDL completo en
`salidas/MODELO_DATOS.md` y `MEMORIA.md` § Modelo de datos): `articulo` (948),
`inventario_huecos_kardex` (1.742, un hueco por fila y corte), `movimientos_articulo_kardex`
(925, grano periodo×sección×código), `stock_farmatools` (2.910, un corte),
`parametrizacion_kardex` (1.418 desde el 2026-09-23; eran 0 al escribir la v1.0), y las
seis vistas `v_kardex_*`. Solo cambia el CHECK de `fuente` de `parametrizacion_kardex` (v1.1, abajo).

```
articulo 1──n inventario_huecos_kardex        (por corte)
articulo 1──n movimientos_articulo_kardex     (por periodo)
articulo ·──· stock_farmatools                (sin FK a propósito: códigos que no están en el Kardex)
articulo 1──n parametrizacion_kardex          (almacen, codigo) — actual vigente
articulo 1──n propuesta_kardex  [NUEVA]       (una fila por decisión, historial)
evento_kardex   [NUEVA]                       outbox de eventos terminales
uso_evento      [NUEVA]                       métrica de uso, sin identidad
```

**DDL nuevo** (bloque único para pegar en el editor SQL de Supabase; también en
`docs/anexos/schema-v1.sql` cuando se ejecute la fase 1):

```sql
-- ============ v1.1 · parametrizacion_kardex admite fuente = 'aplicada' ============
-- Sin esto, el trigger de abajo falla en la primera propuesta aplicada: el CHECK original
-- solo permitía 'manual' e 'informe'.
alter table public.parametrizacion_kardex drop constraint parametrizacion_kardex_fuente_check;
alter table public.parametrizacion_kardex add constraint parametrizacion_kardex_fuente_check
  check (fuente in ('manual','informe','aplicada'));

-- ============ propuesta_kardex · REQ-009, REQ-010, REQ-011 ============
create type kardex_propuesta_estado as enum ('propuesta', 'aceptada', 'rechazada', 'aplicada');

create table public.propuesta_kardex (
  id                uuid primary key default gen_random_uuid(),
  fecha_descarga    date not null,              -- corte del Kardex sobre el que se decidió
  periodo_desde     date not null,              -- periodo de movimientos usado
  periodo_hasta     date not null,
  almacen           text not null check (almacen in ('KARDEX1','KARDEX2')),
  codigo            text not null references public.articulo(codigo),
  ambito            text not null check (ambito in ('armario','conjunto')),   -- REQ-006
  dias_cobertura_min int  not null check (dias_cobertura_min > 0),
  dias_cobertura_max int  not null check (dias_cobertura_max >= dias_cobertura_min),
  tasa_fuente       text not null check (tasa_fuente in ('farmatools','movimientos')),  -- REQ-008
  minimo_actual     int,
  maximo_actual     int,
  minimo_propuesto  int  not null check (minimo_propuesto >= 1),               -- REQ-004: nunca 0
  maximo_propuesto  int  not null check (maximo_propuesto >= minimo_propuesto),
  maximo_topado     boolean not null default false,
  accion            text not null check (accion in ('subir','bajar','mantener','hueco_insuficiente')),
  estado            kardex_propuesta_estado not null default 'propuesta',
  nota              text,
  decidida_en       timestamptz,
  aplicada_en       timestamptz,
  creada_en         timestamptz not null default now(),
  unique (fecha_descarga, almacen, codigo, creada_en)                          -- REQ-009: historial, no pisa
);
create index on public.propuesta_kardex (almacen, codigo, creada_en desc);
create index on public.propuesta_kardex (estado) where estado in ('propuesta','aceptada');

-- Transiciones legales · REQ-010
create or replace function public.propuesta_kardex_transicion() returns trigger
language plpgsql as $$
begin
  if old.estado = new.estado then return new; end if;
  if not (
       (old.estado = 'propuesta' and new.estado in ('aceptada','rechazada'))
    or (old.estado = 'aceptada'  and new.estado = 'aplicada')
  ) then
    raise exception 'Transición ilegal: % → %', old.estado, new.estado;      -- REQ-010
  end if;
  if new.estado in ('aceptada','rechazada') then new.decidida_en := now(); end if;
  if new.estado = 'aplicada' then
    new.aplicada_en := now();
    insert into public.parametrizacion_kardex (almacen, codigo, stock_minimo, stock_maximo, fuente, nota, actualizado_en)
    values (new.almacen, new.codigo, new.minimo_propuesto, new.maximo_propuesto, 'aplicada', new.nota, now())
    on conflict (almacen, codigo) do update
      set stock_minimo = excluded.stock_minimo, stock_maximo = excluded.stock_maximo,
          fuente = 'aplicada', nota = excluded.nota, actualizado_en = now();  -- REQ-011
  end if;
  return new;
end $$;
create trigger trg_propuesta_kardex_transicion
  before update on public.propuesta_kardex
  for each row execute function public.propuesta_kardex_transicion();

-- ============ evento_kardex · outbox · REQ-012 ============
create table public.evento_kardex (
  id            bigint generated always as identity primary key,
  tipo          text not null check (tipo in ('corte_cargado','propuesta_aceptada','propuesta_rechazada','propuesta_aplicada')),
  fecha_descarga date,
  almacen       text,
  codigo        text,
  payload       jsonb not null default '{}'::jsonb,
  creado_en     timestamptz not null default now(),
  procesado_en  timestamptz,                       -- null = pendiente
  resultado     text check (resultado in ('ok','error')),
  error         text,
  consumidor    text                               -- 'frello' en v1.1
);
create index on public.evento_kardex (procesado_en) where procesado_en is null;

create or replace function public.emitir_evento_propuesta() returns trigger
language plpgsql as $$
begin
  if tg_op = 'UPDATE' and old.estado <> new.estado and new.estado in ('aceptada','rechazada','aplicada') then
    insert into public.evento_kardex (tipo, fecha_descarga, almacen, codigo, payload)
    values ('propuesta_' || new.estado, new.fecha_descarga, new.almacen, new.codigo,
            jsonb_build_object('propuesta_id', new.id, 'accion', new.accion,
                               'minimo', new.minimo_propuesto, 'maximo', new.maximo_propuesto,
                               'ambito', new.ambito));
  end if;
  return new;
end $$;
create trigger trg_evento_propuesta
  after update on public.propuesta_kardex
  for each row execute function public.emitir_evento_propuesta();

-- corte_cargado: se emite UNA vez por (tabla, fecha_descarga) · REQ-012
create or replace function public.emitir_evento_corte() returns trigger
language plpgsql as $$
begin
  insert into public.evento_kardex (tipo, fecha_descarga, payload)
  select 'corte_cargado', new.fecha_descarga, jsonb_build_object('tabla', tg_table_name)
  where not exists (
    select 1 from public.evento_kardex
    where tipo = 'corte_cargado' and fecha_descarga = new.fecha_descarga
      and payload->>'tabla' = tg_table_name
  );
  return new;
end $$;
create trigger trg_evento_corte_huecos     after insert on public.inventario_huecos_kardex
  for each row execute function public.emitir_evento_corte();
create trigger trg_evento_corte_farmatools after insert on public.stock_farmatools
  for each row execute function public.emitir_evento_corte();

-- ============ uso_evento · métrica · REQ-013 ============
create table public.uso_evento (
  id        bigint generated always as identity primary key,
  pantalla  text not null check (pantalla in ('subida','gestion','ajuste','actividad')),
  accion    text not null check (accion in ('abrir','cargar_corte','guardar_minmax','aceptar','rechazar','aplicar','exportar_csv')),
  creado_en timestamptz not null default now()
);                                               -- sin usuario, sin IP, sin user-agent: no identifica
create index on public.uso_evento (creado_en);

-- ============ RLS · §10 (sin usuarios: anon lee y escribe; RLS activa por convención del proyecto) ============
alter table public.propuesta_kardex enable row level security;
alter table public.evento_kardex    enable row level security;
alter table public.uso_evento       enable row level security;
create policy anon_all on public.propuesta_kardex for all to anon, authenticated using (true) with check (true);
create policy anon_sel on public.evento_kardex    for select to anon, authenticated using (true);
create policy anon_ins on public.uso_evento       for insert to anon, authenticated with check (true);
create policy anon_sel on public.uso_evento       for select to anon, authenticated using (true);
-- evento_kardex NO tiene política de insert/update: solo lo escriben los triggers (owner de la tabla).
-- Si en la v1.2 entra la identidad federada, estas políticas pasan a select-only y las escrituras
-- van por Edge Function con service_role: el esquema no cambia, solo las políticas.
```

**Ciclo de vida y borrado.** `propuesta_kardex` es append-only por diseño (una decisión
nueva sobre el mismo par es una fila nueva; la vigente es la última `aceptada`/`aplicada`).
Nada se borra desde la app. `evento_kardex` se conserva 12 meses (NFR-006) y se purga a
mano. `uso_evento` no lleva identidad, no hay nada que borrar por RGPD.

**Datos semilla.** No hacen falta: los tres cortes reales ya están cargados
(Kardex 19-08, movimientos 01-01→19-08, Farmatools 27-08). Para probar transiciones:
una fila de `propuesta_kardex` sobre `('KARDEX1', 'V02254')` en cada estado.

## 7. Especificación funcional · *capa QUÉ*

### 7.1 Subida de informes — REQ-001, REQ-002, REQ-003, REQ-016

**Qué hace.** Detecta cuál de los informes se ha arrastrado, lo parsea con cuadre de filas,
enseña una revisión previa con métricas de control y escribe por corte.

- **REQ-001 `[Must]` ✅** El sistema DEBERÁ detectar el tipo de informe por sus columnas y
  rechazar con motivo cualquier fichero que no case con un informe registrado.
  > Dado un `.xls` del informe de huecos, cuando se arrastra, entonces la revisión previa
  > dice «Stock por hueco», corte leído de la cabecera y 1.742 filas de datos.
  > Dado un Excel cualquiera, cuando se arrastra, entonces «No reconozco este informe» con
  > las columnas que faltan.
- **REQ-002 `[Must]` ✅** SI el reparto de filas no cuadra (total ≠ datos + cabecera + vacías
  + descartadas) o alguna fecha es futura, ENTONCES el sistema DEBERÁ bloquear la escritura
  y mostrar el desajuste.
  > Dado el informe de huecos con una fila de más, cuando se parsea, entonces el semáforo
  > sale en error con la diferencia exacta y el botón de confirmar está deshabilitado.
  > Dado un informe de movimientos con `Hasta` posterior a hoy, cuando se parsea, entonces
  > se bloquea con «fecha futura».
- **REQ-003 `[Must]` ✅** CUANDO el informe no lleva la fecha del corte dentro (Farmatools),
  el sistema DEBERÁ pedirla al usuario antes de parsear, ofreciendo `file.lastModified` solo
  como sugerencia marcada.
  > Dado el stock de Farmatools, cuando se arrastra, entonces aparece un campo de fecha con
  > el aviso «sugerencia, compruébala» y no se parsea hasta «Continuar».
  > Dado ese campo vacío, cuando se pulsa «Continuar», entonces error claro, sin fecha inventada.
- **REQ-016 `[Should]` ✅** El sistema DEBERÁ cargar el informe «Ocupación de armario» como
  cuarto informe en `parametrizacion_kardex` con `fuente = 'informe'`, **sincronizando**: el
  fichero es la foto completa de la máquina, así que lo que ya no viene se borra, acotado a
  `fuente = 'informe'`. El resumen previo DEBERÁ enumerar lo que se va a borrar.
  Reglas (decididas el 2026-09-23, salvo la 4, decidida el 2026-10-04):
  1. El armario se lee de la marca `KARDEXn(n)` que abre cada sección; **el informe trae
     KARDEX2 antes que KARDEX1**, así que nunca se asume el orden.
  2. Un mín/máx a 0 es «sin configurar» y se guarda `null`, nunca 0.
  3. Una fila `fuente = 'manual'` **manda sobre el informe**: la recarga la salta y el resumen
     previo dice cuántas conserva. Lo manual no se borra jamás.
  4. **Una fila `fuente = 'aplicada'` NO manda sobre el informe**: el informe es la foto real
     de la máquina y la sustituye por el valor que traiga (`fuente` pasa a `'informe'`).
     *(Sustituye a la redacción de la v1.0, «sin sobrescribir `aplicada` más recientes».)*
  > Dado el informe con N filas, cuando se carga, entonces `parametrizacion_kardex` queda con
  > las N filas del informe más las `manual` conservadas, y «Falta mín/máx actual»
  > desaparece de las que traen valores.
  > Dado un artículo que ya no está en el fichero, cuando se recarga, entonces la fila
  > `informe` se borra y el resumen previo la enumera («0 filas a borrar» si no hay).
  > Dado un artículo con `fuente = 'aplicada'`, cuando se carga un informe que lo incluye,
  > entonces pasa a `fuente = 'informe'` con los valores del fichero.

**Casos límite:** mismo corte recargado (reemplaza, no duplica — verificado); dos cortes
de fechas distintas (conviven); fichero > 10 MB (NFR-002: se rechaza antes de leer);
Farmatools sin corte Kardex del mismo día (aviso no bloqueante); código con formato raro
(`676262`, `V`+7) entra si casa con `^[A-Z]{0,2}\d{4,8}$`; vacío numérico → `null`, nunca `0`.

### 7.2 Gestión Kardex — REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-015

**Qué hace.** Única pantalla de consulta. **Desde el 2026-09-23 (v1.1) la unidad de la tabla
es el medicamento** (822 filas), desplegable a sus filas K1/K2 (artículo×armario, desde
`v_kardex_articulo_armario`); los 17 chips se sustituyeron por **seis vistas excluyentes**;
modal de detalle; CSV reproducible. Stock y valor se suman entre armarios; mín/máx y acción
no se agregan; **la cobertura no se promedia: manda el peor armario**. Los REQ-004 a REQ-008
no cambian: siguen calculándose por artículo×armario.

- **REQ-004 `[Must]` ✅** El sistema DEBERÁ calcular la propuesta como
  `minimo = max(1, floor(tasa × diasMin))`, `maximo = max(minimo, min(floor(tasa × diasMax), capacidad))`,
  con `tasa = consumo_medio_mensual / 30` si `consumo_valido`, si no `tasa_diaria_periodo`,
  y DEBERÁ mostrar en la fila qué fuente usa.
  > Dado FLECAINIDA 150 mg (33 uds / 231 días, sin Farmatools válido), cuando se calcula
  > con 7/21, entonces mínimo 1 y máximo ≥ 1, nunca 0/0.
  > Dado un artículo con `consumo_valido = true`, cuando se calcula, entonces la fila dice
  > «según Farmatools».
- **REQ-005 `[Must]` ✅** El sistema DEBERÁ asignar la acción por esta prioridad: Sin
  consumo → Capacidad sin configurar → Hueco insuficiente (`minimoBase > capacidad`) →
  Falta mín/máx actual → Mantener / Subir / Bajar con tolerancia ±10 % sobre el máximo
  actual; y DEBERÁ permitir filtrar y ordenar por acción en orden de urgencia.
  > Dado SIMETICONA 40 mg (capacidad 100, cobertura mínima 215), cuando se calcula,
  > entonces «Hueco insuficiente» en rojo y sin máximo propuesto.
  > Dado el chip «Bajar» activo, cuando se exporta CSV, entonces solo salen filas con
  > `accion = bajar` y el contador «N de M (filtro activo)» coincide.
- **REQ-006 `[Must]` ✅** MIENTRAS un artículo esté en los dos Kardex (`propuesta_ambito =
  'conjunto'`), el sistema DEBERÁ mostrar la misma propuesta en las dos filas con la marca
  «conjunto K1+K2» y no DEBERÁ sumarlas en ninguna métrica.
  > Dado un artículo en K1 y K2, cuando se abre cualquiera de las dos filas, entonces el
  > modal explica que la propuesta es del par.
- **REQ-007 `[Must]` ✅** SI el corte de Farmatools y el del Kardex no son del mismo día,
  ENTONCES el sistema DEBERÁ mostrar el aviso de desfase y NO DEBERÁ calcular ni mostrar
  discrepancias.
  > Dado Farmatools 27-08 y Kardex 19-08, cuando se abre el modal, entonces «8 días de
  > desfase, descarga los dos el mismo día» y ninguna cifra de discrepancia.
- **REQ-008 `[Must]` ✅** SI `consumo_medio_mensual` es nulo, cero o negativo, ENTONCES el
  sistema DEBERÁ marcar «consumo no interpretable» y no DEBERÁ calcular cobertura ni
  alertar de rotura.
  > Dado uno de los 67 artículos con consumo negativo, cuando se lista, entonces no
  > aparece en «Rotura» ni en «Bajo mínimo».
- **REQ-015 `[Should]`** El sistema DEBERÁ exportar un CSV del que se pueda reconstruir
  cada recomendación sin la app: corte, periodo, días de cobertura, fuente de tasa,
  propuesta, acción, topado, y las columnas de Farmatools `[PENDIENTE VALIDAR: eran 14; el
  23-09 se añadieron pedidos (nº y fecha), consumed, consumed_ad00 y tres ámbitos de consumo.
  Fijar la lista exacta al ejecutar la Fase 3]`.
  > Dado un CSV exportado, cuando se recalcula `floor(tasa × diasMax)` en Excel, entonces
  > coincide con `maximo_propuesto` salvo donde `maximo_topado_por_capacidad = true`.

**Casos límite:** 120 filas «Sin Kardex» apagadas por defecto; apuntes del dispensador
(`bookkeeping`) ocultos por defecto; `valor_stock` nulo → «—», nunca «0 €»; 24 huecos con
`999999999` nunca en la capacidad real; `pct_llenado` con `stock_capacidad_valida`; 1.538
filas cargan enteras o error explícito (NFR-001).

### 7.3 Decisiones — REQ-009, REQ-010, REQ-011

**Qué hace.** Convierte una propuesta en una decisión con estado y fecha, y la lleva
hasta «aplicada en la máquina».

- **REQ-009 `[Must]`** CUANDO el usuario pulsa Aceptar o Rechazar en el modal, el sistema
  DEBERÁ insertar una fila en `propuesta_kardex` con la propuesta completa (fórmula, días,
  fuente, actual, propuesto, ámbito) y el estado elegido, sin modificar filas anteriores.
  > Dado un par sin decisión, cuando se acepta, entonces existe una fila `aceptada` con
  > `decidida_en` y el badge de la tabla pasa a «Aceptada · dd/mm».
  > Dado un par ya aceptado, cuando se vuelve a aceptar con otra cobertura, entonces hay
  > dos filas y la vigente es la más reciente.
- **REQ-010 `[Must]`** SI se intenta una transición distinta de `propuesta → aceptada |
  rechazada` o `aceptada → aplicada`, ENTONCES el sistema DEBERÁ rechazarla con el mensaje
  del trigger, visible en la app.
  > Dado una fila `rechazada`, cuando se pulsa «Aplicada», entonces el botón no existe;
  > y si se fuerza por API, la base devuelve «Transición ilegal».
- **REQ-011 `[Must]`** CUANDO una propuesta pasa a `aplicada`, el sistema DEBERÁ escribir el
  mín/máx en `parametrizacion_kardex` con `fuente = 'aplicada'`, y la edición manual DEBERÁ
  validar `0 ≤ mín ≤ máx` en cliente antes del upsert.
  > Dado una propuesta aceptada, cuando se marca aplicada, entonces la fila muestra ese
  > mín/máx como actual y «según aplicación del dd/mm».
  > Dado mín 10 y máx 5 en el modal, cuando se guarda, entonces mensaje en español y no se
  > llama a Supabase.

**Casos límite:** aceptar «Hueco insuficiente» o «Capacidad sin configurar» no está
permitido (no hay propuesta válida que aceptar: el botón no aparece, y el `CHECK`
`minimo_propuesto >= 1` lo impide por detrás); dos pestañas aceptando a la vez → dos filas
(append-only, la última gana, visible en el historial); artículo `conjunto` → una decisión
por armario, cada una con `ambito = 'conjunto'`.

### 7.4 Eventos y uso — REQ-012, REQ-013, REQ-014

- **REQ-012 `[Must]`** CUANDO se carga un corte nuevo o una propuesta cambia de estado, el
  sistema DEBERÁ escribir un evento en `evento_kardex` con `procesado_en = null`, una sola
  vez por corte y tabla.
  > Dado un corte de huecos de 1.742 filas, cuando termina la carga, entonces hay
  > exactamente 1 evento `corte_cargado` para esa fecha y tabla.
  > Dado una propuesta que pasa a aplicada, cuando se guarda, entonces existe
  > `propuesta_aplicada` con el `payload` de mín/máx.
- **REQ-013 `[Must]`** CUANDO se abre una pantalla o se ejecuta una acción de escritura, el
  sistema DEBERÁ registrar `uso_evento (pantalla, accion)` sin ningún dato que identifique a
  la persona.
  > Dado que se abre Gestión Kardex, cuando carga, entonces una fila `('gestion','abrir')`.
  > Dado la tabla `uso_evento`, cuando se inspecciona, entonces no hay columna de usuario,
  > IP ni user-agent.
- **REQ-014 `[Could]`** El sistema DEBERÁ mostrar en «Actividad» los usos del mes por
  pantalla, los eventos pendientes/ok/error y el porcentaje de éxito.
  > Dado 20 eventos con 19 `ok`, cuando se abre Actividad, entonces «95 %».

### 7.5 Identidad federada — REQ-019, REQ-020 · `[Retirado 2026-09-21]`

Ambos requisitos se escribieron y se retiraron el mismo día: Yared aplazó la identidad
federada con Frello a una iteración futura, pendiente de validar. Los números **no se
reciclan**; su contenido vive en el roadmap (§12, v1.2) y en el registro de cambios.

- **REQ-019** `[Retirado 2026-09-21 → v1.2]` Escrituras solo con sesión de Frello verificada en servidor.
- **REQ-020** `[Retirado 2026-09-21 → v1.2]` Lectura operativa aunque Frello no responda.

### 7.6 Carrusel (deuda heredada) — REQ-017

- **REQ-017 `[Should]`** El sistema DEBERÁ leer `v_regularizacion_detalle`,
  `v_regularizacion_mes`, `v_abastecimiento` y `v_caducidad_detalle` con `fetchAllRows` y
  mostrar error explícito si se alcanza el tope, sin cambiar ninguna vista.
  > Dado Regularizaciones (11.793 filas), cuando se abre, entonces se ven 11.793 y no 1.000.
  > Dado un tope de 50.000 superado, cuando se lee, entonces error visible, no silencio.

### 7.7 Herramientas locales (validación, no producto) — REQ-018

- **REQ-018 `[Should]`** El repo local DEBERÁ tener `tools/parser_stock_farmatools.py` que
  reproduzca el parser TS y `test_paridad_lovable.py` DEBERÁ cubrir el tercer informe.
  > Dado el fichero real del 27/08, cuando corre el parser, entonces 2.912 = 2.910 + 0 + 0
  > + 2 (`PAC`, `NOGUIA`) y Σ `exist_farmacia` = 820.056,25 con decimales.

### Requisitos no funcionales

- **NFR-001 `[Must]`** Gestión Kardex DEBERÁ cargar sus 1.538 filas en < 3 s con conexión
  del hospital, y fallar explícito (no truncar) si la vista supera 50.000 filas.
- **NFR-002 `[Must]`** `/kardex/subida` DEBERÁ rechazar ficheros > 10 MB antes de leerlos.
- **NFR-003 `[Must]`** Ninguna tabla de Farrusel DEBERÁ contener columnas de paciente
  (nombre, NHC, cama, diagnóstico). Verificable por `information_schema.columns`.
- **NFR-004 `[Must]`** Toda regresión DEBERÁ comprobar **22 vistas** en `public` y que las 16
  vistas del carrusel no pierdan filas de un día a otro por un cambio nuestro.
- **NFR-005 `[Should]`** Cada sesión en Lovable DEBERÁ registrar sus créditos consumidos en
  `LOG.md`; **se avisa antes de cada envío** (regla 5 del proyecto). Límite orientativo:
  10 créditos por fase.
- **NFR-006 `[Should]`** `evento_kardex` DEBERÁ conservarse 12 meses; `uso_evento`, 24.
- **NFR-007 `[Should]`** Toda fila pulsable DEBERÁ responder a teclado (Enter/Espacio,
  `role="button"`, `tabIndex`) y todo badge DEBERÁ tener su texto completo en el modal, no
  solo en `title`.

## 8. Interfaz · *capa UX*

**Mapa.** `/kardex` con tres pestañas: **Subida** (`/kardex/subida`) · **Gestión Kardex**
(`/kardex/stock`) · **Ajuste** (`/kardex/ajuste`). `[Could]` cuarta: **Actividad**.
«Movimientos» ya no existe.

| Pantalla | Con datos | Vacío | Cargando | Error |
|---|---|---|---|---|
| Subida | Zona de arrastre + historial de cargas (`carga`) | «Arrastra el primer informe. Tres formatos: …» con la ayuda de cada uno | Barra de parseo con recuento de filas | Semáforo rojo con el desajuste exacto y el botón deshabilitado |
| Gestión Kardex | Métricas (huecos, llenado, valor del stock), selectores corte/periodo/almacén, chips (alerta · acción · Farmatools), tabla 5 col., «Ver más» 50 en 50 | «No hay ningún corte. Sube el informe de stock por hueco» + enlace a Subida | Esqueleto de tabla + «Cargando 1.538 filas» | «No se pudieron cargar todas las filas (tope alcanzado)» / error de red con reintentar |
| Modal de detalle | Cabecera · Parametrización (actual editable, propuesto, **Aceptar / Rechazar / Aplicada**, historial de decisiones) · Huecos · Consumo · Económico · Farmatools · Cobertura · Alertas | Sección Farmatools: «Sin dato de Farmatools para este código» | Huecos: spinner al abrir | Guardado fallido: mensaje real de Postgres traducido |
| Actividad `[Could]` | Usos por pantalla y mes, eventos por estado, % éxito | «Todavía no hay actividad registrada» | Esqueleto | Error de red |

**Sistema de diseño:** el «Frello» ya en uso (`HeroHeader`, `SectionCard`, `Metric`, tokens
`accent` ocre para «cambió respecto al corte anterior», `warning` ámbar, `destructive` rojo,
`ok` verde para «Bajar»). Español en lo visible, inglés en el código. Sin emoji en UI.

**Móvil:** el modal ocupa la pantalla entera; la tabla colapsa Ubicación y Valor en la
segunda línea del artículo. Los textos de alerta viven en el modal precisamente porque en
móvil no hay `title`.

**Accesibilidad:** contraste ≥ 4,5:1 en badges; filas navegables por teclado (NFR-007);
`aria-label` en los chips con su recuento.

## 9. Integraciones, errores y coste · *capa CÓMO*

**Ninguna integración externa en la v1.** Farmatools y el Kardex entran por fichero, no por
API. Sin IA, sin correo, sin pagos. (El Auth de Frello como identidad es v1.2, §12.)

| Campo | Supabase (PostgREST) |
|---|---|
| Para qué | Lectura de vistas y escritura por corte |
| Requisitos | REQ-001…REQ-013, REQ-017 |
| Qué se envía | Upserts por lotes de ≤ 500 filas; inserts de decisión y uso |
| Si falla | Reintento manual con el error real en pantalla; la carga por lotes es idempotente por corte, así que repetir no duplica |
| Si devuelve algo inválido | `fetchAllRows` lanza al superar el tope; nunca se muestra una tabla parcial como completa |
| Límites | PostgREST 1.000 filas/petición (por eso el helper); 8 MB por request |
| Coste | Incluido en el proyecto Supabase existente |

| Campo | Lovable (agente de build) |
|---|---|
| Para qué | Construir la app |
| Si falla | Cada mensaje se verifica con `tsgo` limpio y las métricas de control del informe real |
| Coste | ≈ 1–6 créditos por mensaje según alcance (13,5 en las tres primeras sesiones). **Se avisa antes de enviar** (NFR-005) |

**v1.1 (fuera):** `notify-frello` consumirá `evento_kardex`; su contrato de error (reintento,
`resultado = 'error'`, `error` con el texto) ya está previsto en la tabla.

## 10. Seguridad, privacidad y cumplimiento · *capa CÓMO*

- **Secretos:** ninguno en la v1. Solo la clave publicable `anon`. Cuando exista
  `notify-frello`, la clave de servicio de Frello es un secreto de Edge Function de Farrusel.
- **Acceso: enlace = permiso. Riesgo asumido por Yared el 2026-09-21.** Sin login, cualquier
  persona con el enlace puede cargar cortes, guardar mín/máx y cambiar estados, y no queda
  registrado quién. Mitigaciones que sí están: los cortes no se pisan (reprocesar el mismo
  corte reemplaza *ese* corte, no el histórico), `propuesta_kardex` es append-only,
  `evento_kardex` solo lo escriben los triggers, y `uso_evento` registra cada escritura con
  hora. Lo que NO hay: atribución personal. **Salida prevista:** la identidad federada con el
  Auth de Frello (v1.2, §12), estudiada y viable, pendiente de validar. Si el enlace se
  difunde fuera del servicio antes, se adelanta por `/cambio`.
- **RLS:** activa en todas las tablas por convención del proyecto; políticas explícitas
  para `anon` (§6). No aísla usuarios porque no los hay: documenta qué puede hacer `anon`.
- **Validación en servidor:** `CHECK`s y triggers de §6 hacen cumplir mínimo ≥ 1, máx ≥ mín,
  transiciones legales y unicidad de evento por corte. La validación del cliente es comodidad.
- **Datos personales: ninguno.** Artículos, huecos, stock, precios, consumos agregados del
  hospital. `uso_evento` no lleva identidad por diseño (REQ-013). Ruta ligera de
  cumplimiento: no hay base legal que declarar ni retención de datos de personas. (Si en la
  v1.2 entra el email de Frello, se declara entonces: base legal, retención e información al
  usuario.)
- **Datos de pacientes: no existen y no van a existir** (NFR-003). El consumo medio mensual
  de Farmatools es un agregado por artículo del HUNSC entero.
- **Transferencias:** Supabase eu-central-1 (Frankfurt) y Lovable (UE). Nada sale a IA ni a
  analítica.
- **Contexto institucional:** herramienta interna del Servicio de Farmacia del HUNSC.
  Responsable funcional: Yared González. **No requiere visto bueno de Sistemas** (confirmado
  por Yared el 2026-09-21). Son datos del hospital (stock, precios): el enlace no se publica
  fuera del servicio y `salidas/*.csv` no viajan al repo (`.gitignore`).

## 11. Plan de construcción · *capa ejecución*

Fases del tamaño de **una unidad de producto en Lovable** (una pantalla o un módulo de punta
a punta), sin asumir duración: Yared decide cuántas hace por sesión. Cada fase = un mensaje
al agente (aviso de créditos antes) + verificación contra los criterios de §7 + entrada en
`LOG.md`. **Fase 0** es la única que no pasa por Lovable.

**Fase 0 · Cimientos SQL** — *(v1.1: el bloque de §6 lleva ahora el cambio del CHECK de
`parametrizacion_kardex`; sin él la primera aplicación falla)*. Objetivo: las tres tablas y los triggers existen y se
comportan. Cierra: REQ-010 (lado servidor), REQ-012 (lado servidor), estructura de REQ-009 y
REQ-013. Tareas: pegar el bloque de §6 en el editor SQL de Supabase (o `apply_migration` vía
MCP con OK); insertar una fila de prueba en cada estado y comprobar que `rechazada →
aplicada` falla; cargar una fila en `inventario_huecos_kardex` de un corte ficticio y ver un
solo `corte_cargado`, borrarla después. Terminado cuando: 22 vistas siguen, 3 tablas nuevas,
4 triggers nuevos, y las pruebas de transición pasan, **incluida una `aceptada → aplicada` que
escribe `fuente = 'aplicada'` en `parametrizacion_kardex` (se prueba y se revierte)**. Depende de: nada.

**Fase 1 · Decisiones en el modal** — Objetivo: aceptar, rechazar y marcar aplicada desde
Gestión Kardex. Cierra: REQ-009, REQ-010 (lado app), REQ-011. Tareas: sección
«Parametrización» del modal con los tres botones y el historial; badge de estado en la
tabla y chip «Con decisión» / «Aplicada»; validación cliente; CSV con `estado_decision`.
Terminado cuando: los criterios de 7.3 pasan en la app con un par real y
`parametrizacion_kardex` refleja la aplicación. Depende de: Fase 0.

**Fase 2 · Registro de uso** — Objetivo: la métrica 1 de §2 es medible. Cierra: REQ-013.
Tareas: un helper `registrarUso(pantalla, accion)` llamado en cada apertura y acción de
escritura; nunca bloquea la UI si falla. Terminado cuando: navegar y aceptar deja filas en
`uso_evento` y no hay ningún identificador. Depende de: Fase 0. **Paralelizable con Fase 1.**

**Fase 3 · CSV reproducible y NFR** — Objetivo: cerrar los `[Should]` de la pantalla.
Cierra: REQ-015, NFR-001, NFR-002, NFR-007. Tareas: columnas del CSV; rechazo > 10 MB;
medición de carga; repaso de teclado. Terminado cuando: un CSV se reconstruye en Excel
(criterio de REQ-015) y `tsgo` limpio. Depende de: Fase 1.

**Fase 4 · Carrusel sin truncar** — Objetivo: las 4 páginas del carrusel leen todas sus
filas. Cierra: REQ-017. Tareas: sustituir el patrón `.limit(20000)` por `fetchAllRows` en
Regularizaciones (detalle y mes), Abastecimiento y Caducidades; **no tocar ninguna vista**.
Terminado cuando: Regularizaciones muestra 11.793 y la regresión de NFR-004 pasa. Depende
de: nada. **Paralelizable.**

**Fase 5 · Parser Python de Farmatools** (Claude Code local, no Lovable; **validación, no
producto**) — Objetivo: el tercer informe tiene referencia y paridad para comprobar que el
modelo de datos montado en Lovable es correcto. Cierra: REQ-018. Tareas: escribir
`tools/parser_stock_farmatools.py` contra las cifras de control; ampliar
`test_paridad_lovable.py`; commit y push a `Eskoool/Farrusel`. Terminado cuando: los tests
pasan con el fichero real. Depende de: tener `datos/stock 27.08.xls` en local.

**Fase 6 · Cuarto informe (parametrización)** — ✅ **Hecha el 2026-09-23** (v1.1). Cierra:
REQ-016. Informe «Ocupación de armario», 1.418 filas, con sincronización. Queda como tarea
suelta la comprobación de la **resubida** («0 filas a borrar», total 1.418).

**Fase 7 · Actividad** `[Could]` — Cierra: REQ-014. Depende de: Fases 1 y 2.

**Orden recomendado:** 0 → 1 y 2 en paralelo → 3 → 4 y 5 cuando convenga → 7. (La 6 ya está hecha.) **La v1.1 (Frello) no arranca antes de cerrar 0, 1 y 2**: sin eventos
reales no hay nada que empujar.

**Trazabilidad:** REQ-001…008 ✅ ya cumplidos (sin fase); 009→F1; 010→F0+F1; 011→F1;
012→F0; 013→F2; 014→F7; 015→F3; 016→F6; 017→F4; 018→F5; 019 y 020 retirados (v1.2).
NFR-001/002/007→F3; NFR-003/004 se comprueban en toda fase; NFR-005 en cada envío; NFR-006
es política. Ninguna fase sin REQ; ningún REQ sin fase.

## 12. Setup externo y roadmap · *capa ejecución*

**Checklist (todo ya existe):** proyecto Supabase `sgpbdzphweyeaegzesvb` · proyecto Lovable
`59f5ea8d-…` conectado a él · repo `github.com/Eskoool/Farrusel` para `tools/` y memoria ·
Python 3.13 per-user con pandas, openpyxl, xlrd, xlsxwriter, chardet.

| Variable | Dónde | Pública/secreta |
|---|---|---|
| `VITE_SUPABASE_URL` | Lovable (ya configurada) | pública |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Lovable (ya configurada) | pública |
| `FRELLO_SERVICE_KEY` | Secreto de `notify-frello` — **solo en v1.1** | **secreta** |
| `FRELLO_JWT_SECRET` | Secreto de `escribir-kardex` — **solo si entra la v1.2**. Sale del panel de Supabase de Frello → Settings → API → JWT Secret; nunca por chat | **secreta** |

**Comandos locales** (`MEMORIA.md` § Cómo trabajar): `& $py tools\test_puertas.py`,
`& $py tools\test_paridad_lovable.py`, y los parsers por informe.

**Roadmap:**
- **v2 · Migración del MVP a Claude Code + Vercel.** Decidido por Yared el 2026-09-21: el
  MVP se construye en Lovable; cuando el modelo de datos esté validado (Fases 0–3 y las
  herramientas de `tools/`), el frontend se reescribe en un repo propio desplegado en Vercel
  contra **el mismo Supabase**. Las Edge Functions, tablas, triggers y políticas no cambian:
  son el contrato que hace la migración posible. Este PRD sigue vigente para la v2 (mismos
  REQ); cambia §4 (hosting, motor) por `/cambio`.
- **v1.1 · Conexión con Frello** — Edge Function `notify-frello` que consume `evento_kardex`
  y escribe en la Supabase de Frello (candidato: módulo Paneles informativos). Diseño en
  `proyectos/farrusel/plan-conexion-frello.md`.
- **v1.2 · Identidad federada con Frello — pendiente de validar.** Estudiada el 2026-09-21 y
  aplazada por Yared. Cómo sería: la app inicia sesión contra el Auth de Frello (cliente
  `supabase-js` solo para auth); toda escritura pasa por una Edge Function `escribir-kardex`
  de Farrusel que verifica el JWT de Frello (HS256 con su *JWT secret* como secreto de
  función — verificado: Frello expone `jwks.json` vacío, firma simétrica; Farrusel ya usa
  ES256) y escribe con `service_role` dejando el email en la fila (`cargado_por`,
  `decidida_por`, `aplicada_por`, `actualizado_por`, `usuario`); `anon` pasa a solo `select`.
  No toca nada de Frello. Entra por `/cambio` con una prueba de concepto primero (verificar un
  JWT real) y declarando el email como dato personal (base legal, retención, aviso).
- **v1.3 · K1 vs K2** — cuando exista un informe de movimientos con desglose por almacén.
- **v1.4 · Ciclo cerrado** — comparar en el corte N+1 el llenado real contra lo aplicado en
  N (la métrica 3 de §2 hecha pantalla).

## 13. Instrucción de arranque · *capa ejecución*

Para pegar en el chat del proyecto Farrusel en Lovable al empezar la **Fase 1** (la Fase 0 se
hace en el editor SQL de Supabase, sin agente). Avisar antes: consume créditos.

```text
Actúa como diseñador de producto y desarrollador full-stack senior que mantiene una app
Vite + React + TypeScript + Tailwind sobre Supabase, ya en producción.

Contexto. Esta app es Farrusel: el módulo Kardex tiene tres pestañas (Subida, Gestión
Kardex, Ajuste). «Gestión Kardex» (src/routes/_app.kardex.stock.tsx) lee la vista
v_kardex_articulo_armario (una fila por artículo y armario), calcula una propuesta de
mínimo y máximo con calcularPropuesta y abre un modal de detalle al pulsar una fila. En
Supabase ya existen la tabla propuesta_kardex (estados propuesta → aceptada | rechazada →
aplicada, con trigger que rechaza cualquier otra transición y que, al aplicar, escribe en
parametrizacion_kardex con fuente = 'aplicada') y la tabla uso_evento. El PRD completo es
este: [PEGAR PRD.md]. Estamos en la Fase 1 de §11.

Antes de generar nada, devuélveme:
1. Un resumen en cinco líneas de qué hace hoy Gestión Kardex y qué añade la Fase 1.
2. Los requisitos REQ-009, REQ-010 y REQ-011 en tus palabras, con sus criterios de
   aceptación, y cuál de los tres tiene más riesgo.
3. Cómo cambiaría el modal (sección Parametrización) y la tabla (badge y chip de estado),
   con sus cuatro estados: con datos, vacío, cargando y con error.
4. Tus dudas y supuestos.

Restricciones:
- Nada fuera de §3. No toques ninguna página del carrusel ni ninguna vista de Supabase.
- No propongas login ni roles: está decidido que en esta versión no hay.
- No se acepta una propuesta en estado «Hueco insuficiente», «Capacidad sin configurar» ni
  «Sin consumo»: en esas filas el botón Aceptar no existe.
- La transición ilegal la rechaza la base de datos; en la app el botón que no aplica no se
  muestra, y si aun así llega un error de Postgres se muestra su mensaje real, en español.
- Mantén el design system que ya usa la página (HeroHeader, SectionCard, Metric, tokens
  accent / warning / destructive / ok), español en lo visible, inglés en el código.
- Ejecuta tsgo y déjalo limpio antes de dar nada por terminado.

Espera mi OK antes de tocar la primera pantalla.
```

---

## Anexo. Registro de cambios

| Fecha | Cambio | Motivo | Secciones tocadas | Decisión |
|---|---|---|---|---|
| 2026-09-21 | PRD v1.0 escrito sobre producto a medias; REQ-001…008 marcados como ya cumplidos | Siete sesiones sin documento; la conexión con Frello exige eventos definidos | todas | borrador |
| 2026-09-21 | Identidad federada de Frello estudiada (REQ-019/020, Fase 0b) y **aplazada a v1.2**; la v1 queda con «enlace = permiso» | Yared la quiere validar en una iteración futura, no en el MVP. Lo verificado (Frello firma HS256) se conserva en §12 | §2, §3, §4, §5, §6, §7.5, §9, §10, §11, §12, §13 | retirados REQ-019/020, sin reciclar números |
| 2026-09-21 | Python = validación, no producto; v2 = Claude Code + Vercel sobre el mismo Supabase; sin visto bueno de Sistemas | Aclaraciones de Yared en el checkpoint | §0, §4, §11, §12, §10 | aceptado en el checkpoint |
| 2026-10-04 | **v1.1.** (A) `parametrizacion_kardex.fuente` admite `'aplicada'` (el CHECK original lo impedía y la Fase 0 fallaba); (B) cuarto informe «Ocupación de armario» recibido y cargado el 23-09: REQ-016 ✅ con sincronización, mín/máx 0 = `null`, `manual` manda sobre el informe y **el informe manda sobre `aplicada`**; Fase 6 hecha; (C) «Gestión Kardex» pasa a fila por medicamento con seis vistas y cobertura del peor armario; (D) Farmatools ampliado el 23-09 (pedidos, `consumed`, `consumed_ad00`) | El PRD describía un bloqueo ya resuelto y una pantalla ya rehecha; la Fase 0 no se podía ejecutar tal cual | §0, §3.10, §6, §7.2, REQ-016, §11 (Fases 0 y 6) | incorporado a la v1 (OK de Yared, 2026-10-04) |

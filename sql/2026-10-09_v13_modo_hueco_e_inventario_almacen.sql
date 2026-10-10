-- Farrusel v1.2/v1.3 · 2026-10-09
-- (1) propuesta_kardex: modo de hueco y capacidad recomendada (REQ-026, REQ-033).
--     Sustituye a supabase-propuesta-modo-hueco.sql de Lovable (declaraba nid bigint; id es uuid).
-- (2) inventario_almacen: Inventario por almacén de Athos, tabla propia con histórico (REQ-029).
--     NO toca la tabla `inventario` del carrusel (regla 7).

alter table public.propuesta_kardex
  add column modo_hueco text not null default 'actuales'
    check (modo_hueco in ('actuales','uno','repartir','duplicar')),
  add column capacidad_recomendada int
    check (capacidad_recomendada is null or capacidad_recomendada >= 1);

create table public.inventario_almacen (
  id               uuid primary key default gen_random_uuid(),
  fecha_descarga   date not null,                 -- se pide al subir: el fichero no la trae
  almacen          text not null,                 -- literal del informe, p. ej. 'ACH - Almacen Horizontal'
  codigo           text not null,
  descripcion      text,
  cantidad         numeric,                       -- vacío = null, nunca 0
  minimo           int,
  maximo           int,
  tipo_udc         text not null default '',      -- HP, HPA, VP, VMA…; '' si no viene (entra en la unique)
  unidades_por_udc int,
  posiciones       int,
  cargado_en       timestamptz not null default now(),
  unique (fecha_descarga, almacen, codigo, tipo_udc)  -- recargar el mismo día reemplaza; otro día convive
);
create index on public.inventario_almacen (codigo, fecha_descarga desc);

alter table public.inventario_almacen enable row level security;
create policy "anon all inventario_almacen" on public.inventario_almacen
  for all to anon, authenticated using (true) with check (true);
grant all on public.inventario_almacen to anon, authenticated;

-- Probado en seco el 2026-10-09 (transacción sin commit, rol anon): propuesta con modo_hueco='uno'
-- llega a aplicada con decidida_en y aplicada_en; dos filas de V02129 (VM y VMA) entran; la unique
-- bloquea el duplicado; el CHECK rechaza un modo_hueco inválido; 22 vistas y ninguna pierde filas.

-- (3) Corrección aplicada el mismo día (migración v13_reparto_separado_de_modo_hueco): huecos y
--     reparto entre armarios son DOS decisiones independientes (Yared). modo_hueco vuelve a
--     ('actuales','uno') y el reparto va en su propia columna.
alter table public.propuesta_kardex drop constraint propuesta_kardex_modo_hueco_check;
alter table public.propuesta_kardex add constraint propuesta_kardex_modo_hueco_check check (modo_hueco in ('actuales','uno'));
alter table public.propuesta_kardex add column reparto text check (reparto is null or reparto in ('mismo','repartir'));

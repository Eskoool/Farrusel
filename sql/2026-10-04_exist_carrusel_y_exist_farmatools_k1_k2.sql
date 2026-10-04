-- Farrusel · «Valorar pedido» (PRD v1.1, /cambio pendiente)
-- Qué hace:
--   1) Añade stock_farmatools.exist_carrusel (numeric, nullable): vendrá de exist61 del informe de Farmatools.
--   2) Añade TRES columnas AL FINAL de v_kardex_articulo_armario (no cambia ninguna existente):
--        exist_carrusel         = stock_farmatools.exist_carrusel
--        exist_farmatools_k1    = stock_farmatools.exist_kardex1  (exist58, total del artículo)
--        exist_farmatools_k2    = stock_farmatools.exist_kardex2  (exist59, total del artículo)
--      Hacen falta porque la vista solo exponía exist_farmatools del armario de cada fila, y la
--      regla compara K1 + K2 sumados por artículo.
-- Reversible: alter table ... drop column exist_carrusel; y volver a crear la vista sin las 3 columnas
--             (la definición anterior está en el historial de pg_get_viewdef; ver LOG.md).
-- Comprobación antes/después (línea base 2026-10-04):
--   filas 5898 · en_kardex 5671 · Σ stock 360809.00 · Σ exist_farmacia 1130032.96 · Σ valor_stock 369675.22
--   · 967 códigos · 71 columnas (deben ser 74 después) · 22 vistas en public.
-- Ejecutar de una vez: si falla cualquiera de las 4 sustituciones, la transacción entera se deshace.

alter table public.stock_farmatools add column if not exists exist_carrusel numeric;

do $$
declare
  def text;
  nuevo text;
begin
  def := rtrim(pg_get_viewdef('public.v_kardex_articulo_armario'::regclass, true), ';');
  nuevo := def;

  -- 1) CTE ft: trae exist_carrusel
  nuevo := regexp_replace(nuevo, 's\.pedido_detalle(\s+)FROM stock_farmatools s',
    E's.pedido_detalle,\n            s.exist_carrusel\1FROM stock_farmatools s');
  if nuevo = def then raise exception 'no se encontro el punto de insercion 1 (ft)'; end if;
  def := nuevo;

  -- 2) CTE base: arrastra exist_carrusel y exist_kardex1/2 de Farmatools
  nuevo := regexp_replace(nuevo, 'f\.pedido_detalle,(\s+)CASE a\.almacen',
    E'f.pedido_detalle,\n            f.exist_carrusel,\n            f.exist_kardex1 AS ft_exist_kardex1,\n            f.exist_kardex2 AS ft_exist_kardex2,\\1CASE a.almacen');
  if nuevo = def then raise exception 'no se encontro el punto de insercion 2 (base)'; end if;
  def := nuevo;

  -- 3) rama principal: columnas nuevas AL FINAL
  nuevo := regexp_replace(nuevo, 'AS pct_consumo_kardex(\s+)FROM base b',
    E'AS pct_consumo_kardex,\n    b.exist_carrusel,\n    b.ft_exist_kardex1 AS exist_farmatools_k1,\n    b.ft_exist_kardex2 AS exist_farmatools_k2\\1FROM base b');
  if nuevo = def then raise exception 'no se encontro el punto de insercion 3 (rama principal)'; end if;
  def := nuevo;

  -- 4) rama «no está en Kardex»: mismas columnas nuevas AL FINAL
  nuevo := regexp_replace(nuevo, 'AS pct_consumo_kardex(\s+)FROM v_kardex_movimientos_articulo v',
    E'AS pct_consumo_kardex,\n    f.exist_carrusel,\n    f.exist_kardex1 AS exist_farmatools_k1,\n    f.exist_kardex2 AS exist_farmatools_k2\\1FROM v_kardex_movimientos_articulo v');
  if nuevo = def then raise exception 'no se encontro el punto de insercion 4 (rama sin Kardex)'; end if;

  execute 'create or replace view public.v_kardex_articulo_armario as ' || nuevo;
  execute 'alter view public.v_kardex_articulo_armario set (security_invoker = true)';
end $$;

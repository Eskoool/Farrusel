-- Farrusel v1.3 · Comprobaciones de SOLO LECTURA antes de unificar Kardex y carrusel.
-- Plan: pantalla única «Medicamentos». Ninguna sentencia escribe nada.
-- Pegar entero en el editor SQL de Supabase (sgpbdzphweyeaegzesvb) y devolver los resultados.

-- 1. Frescura de las cargas del carrusel: si Configuración y Ubicaciones de Athos son viejas,
--    los mín/máx del carrusel no son fiables.
select tabla_destino, max(creado_en) as ultima_carga, count(*) as cargas
from public.carga
group by tabla_destino
order by ultima_carga desc nulls last;
-- (si la columna no se llama tabla_destino/creado_en, ver: select * from public.carga order by 1 desc limit 5;)

-- 2. Columnas reales de ubicacion y medicamento (las del repo no son un dump).
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public' and table_name in ('ubicacion','medicamento','stock_farmatools','propuesta_kardex')
order by table_name, ordinal_position;

-- 3. Frío: con el último Farmatools, cuántos códigos tienen stock en el carrusel vertical (exist60)
--    y si además lo tienen en el horizontal o en el Kardex. Solo funciona si stock_farmatools ya
--    guarda exist60; si no, se mira en farmatools_almacen (exist_carr_vert / exist_carr_horiz).
select
  count(*) filter (where coalesce(exist_carr_vert,0) > 0)                                   as con_vertical,
  count(*) filter (where coalesce(exist_carr_vert,0) > 0 and coalesce(exist_carr_horiz,0) > 0) as vertical_y_horizontal,
  count(*) filter (where coalesce(exist_carr_vert,0) > 0
                     and (coalesce(exist_kardex1,0) > 0 or coalesce(exist_kardex2,0) > 0))  as vertical_y_kardex
from public.farmatools_almacen;

-- 4. Definición real de las coberturas que hoy alimentan la rotura.
select pg_get_viewdef('public.v_kardex_articulo_armario'::regclass, true);

-- 5. ¿El código del carrusel cruza con el de Farmatools del Kardex?
with f as (select distinct codigo from public.stock_farmatools
           where fecha_descarga = (select max(fecha_descarga) from public.stock_farmatools))
select m.almacen,
       count(*)                                   as medicamentos_carrusel,
       count(*) filter (where f.codigo is not null) as cruzan_con_farmatools
from public.medicamento m
left join f on f.codigo = m.codigo
group by m.almacen;

-- 6. ¿Está aplicada ya la migración de modo_hueco del 2026-10-09?
select column_name from information_schema.columns
where table_schema = 'public' and table_name = 'propuesta_kardex'
  and column_name in ('modo_hueco','capacidad_recomendada');

-- 7. Tipo de propuesta_kardex.id (el script supabase-propuesta-modo-hueco.sql de Lovable
--    declara `nid bigint`; si id es uuid, su prueba falla al primer intento).
select data_type from information_schema.columns
where table_schema = 'public' and table_name = 'propuesta_kardex' and column_name = 'id';

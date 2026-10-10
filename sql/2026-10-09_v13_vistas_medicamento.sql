-- Farrusel v1.3 · Vistas de la pantalla única «Medicamentos» (REQ-030, REQ-031). 2026-10-09.
-- Solo LEEN: v_kardex_articulo_armario, inventario_almacen y stock_farmatools. Ninguna tabla ni
-- vista existente cambia (regla 7, NFR-004).
--
-- Fuentes, siempre el ÚLTIMO dato de cada una:
--   Kardex       → v_kardex_articulo_armario con es_ultimo_corte y es_ultimo_periodo
--   Carrusel     → inventario_almacen, última fecha_descarga (Inventario por almacén de Athos)
--   Farmacia,    → stock_farmatools, última fecha_descarga
--   consumo y pedidos
-- La rotura (REQ-031) exige Farmatools e Inventario del mismo día: `mismo_dia` lo dice y la app
-- no calcula rotura si es false.

create or replace view public.v_medicamento_almacen as
with
k as (
  select codigo, almacen, descripcion, fecha_descarga, stock, stock_minimo, stock_maximo,
         capacidad, n_huecos, tipo_huecos, ubicaciones
  from public.v_kardex_articulo_armario
  where es_ultimo_corte and es_ultimo_periodo and almacen is not null
),
ia_fecha as (select max(fecha_descarga) f from public.inventario_almacen),
c as (
  select ia.codigo,
         split_part(ia.almacen, ' ', 1)                         as almacen,   -- ACH | ACVR | EXT
         max(ia.descripcion)                                     as descripcion,
         ia.fecha_descarga,
         sum(ia.cantidad)                                        as stock,
         max(ia.minimo)                                          as minimo,
         max(ia.maximo)                                          as maximo,
         max(ia.unidades_por_udc)                                as unidades_por_udc,
         sum(ia.posiciones)                                      as posiciones,
         string_agg(nullif(ia.tipo_udc, ''), ', ' order by ia.tipo_udc) as tipo_udc
  from public.inventario_almacen ia, ia_fecha
  where ia.fecha_descarga = ia_fecha.f
  group by ia.codigo, split_part(ia.almacen, ' ', 1), ia.fecha_descarga
),
sf_fecha as (select max(fecha_descarga) f from public.stock_farmatools)
select k.codigo, k.almacen, 'kardex'::text as familia, k.descripcion, k.fecha_descarga as fecha_dato,
       k.stock, k.stock_minimo as minimo, k.stock_maximo as maximo,
       k.capacidad, k.n_huecos, array_to_string(k.tipo_huecos, ', ') as tipo_hueco, null::int as unidades_por_udc,
       null::bigint as posiciones, k.ubicaciones
from k
union all
select c.codigo, c.almacen, 'carrusel', c.descripcion, c.fecha_descarga,
       c.stock, c.minimo, c.maximo,
       c.unidades_por_udc,                                   -- capacidad de UN hueco (tipo de UDC)
       case when c.maximo > 0 and c.unidades_por_udc > 0
            then ceil(c.maximo::numeric / c.unidades_por_udc)::int end,  -- huecos que pide el máximo
       c.tipo_udc, c.unidades_por_udc, c.posiciones, null::text[]
from c
union all
select s.codigo, 'FARMACIA', 'farmacia', s.descripcion, s.fecha_descarga,
       s.exist_farmacia, null, null, null, null, null, null, null, null
from public.stock_farmatools s, sf_fecha
where s.fecha_descarga = sf_fecha.f and coalesce(s.exist_farmacia, 0) <> 0;

create or replace view public.v_medicamento as
with
sf_fecha as (select max(fecha_descarga) f from public.stock_farmatools),
sf as (select s.* from public.stock_farmatools s, sf_fecha where s.fecha_descarga = sf_fecha.f),
ia_fecha as (select max(fecha_descarga) f from public.inventario_almacen),
car as (
  select codigo,
         sum(cantidad) filter (where almacen like 'ACH%')  as stock_ach,
         sum(cantidad) filter (where almacen like 'ACVR%') as stock_acvr,
         bool_or(almacen like 'ACH%')  as en_ach,
         bool_or(almacen like 'ACVR%') as en_acvr,
         max(descripcion) as descripcion
  from public.inventario_almacen ia, ia_fecha
  where ia.fecha_descarga = ia_fecha.f
  group by codigo
),
kx as (
  select codigo, max(descripcion) descripcion,
         sum(stock) filter (where almacen = 'KARDEX1') as stock_k1_kardex,
         sum(stock) filter (where almacen = 'KARDEX2') as stock_k2_kardex,
         bool_or(almacen = 'KARDEX1') en_k1, bool_or(almacen = 'KARDEX2') en_k2,
         max(fecha_descarga) fecha_kardex
  from public.v_kardex_articulo_armario
  where es_ultimo_corte and es_ultimo_periodo and almacen is not null
  group by codigo
),
cods as (select codigo from sf union select codigo from car union select codigo from kx),
base as (
  select c.codigo,
         coalesce(sf.descripcion, car.descripcion, kx.descripcion) as descripcion,
         coalesce(kx.en_k1, false) en_k1, coalesce(kx.en_k2, false) en_k2,
         coalesce(car.en_ach, false) en_ach, coalesce(car.en_acvr, false) en_acvr,
         -- Frío = tiene fila en el carrusel vertical (verificado 09-10: 0 solapes con H y Kardex)
         coalesce(car.en_acvr, false) as es_frio,
         sf.exist_farmacia, sf.exist_kardex1, sf.exist_kardex2,
         car.stock_ach, car.stock_acvr, kx.stock_k1_kardex, kx.stock_k2_kardex,
         sf.consumo_medio_mensual,
         sf.consumo_medio_mensual > 0 as consumo_valido,
         case when sf.consumo_medio_mensual > 0 then sf.consumo_medio_mensual / 30 end as consumo_diario,
         sf.pedido_pendiente, sf.pedido_fecha_ultima, sf.pedido_n_lineas, sf.pedido_detalle,
         sf.upe, sf.precio_neto_envase,
         (select f from sf_fecha) as fecha_farmatools,
         (select f from ia_fecha) as fecha_inventario,
         kx.fecha_kardex
  from cods c
  left join sf  on sf.codigo  = c.codigo
  left join car on car.codigo = c.codigo
  left join kx  on kx.codigo  = c.codigo
)
select b.*,
       -- REQ-031: normal = farmacia + K1 + K2 (Farmatools) + carrusel H; frío = farmacia + carrusel V
       case when b.es_frio
            then coalesce(b.exist_farmacia, 0) + coalesce(b.stock_acvr, 0)
            else coalesce(b.exist_farmacia, 0) + coalesce(b.exist_kardex1, 0)
                 + coalesce(b.exist_kardex2, 0) + coalesce(b.stock_ach, 0)
       end as stock_hospital,
       case when b.consumo_diario > 0 then
         (case when b.es_frio
               then coalesce(b.exist_farmacia, 0) + coalesce(b.stock_acvr, 0)
               else coalesce(b.exist_farmacia, 0) + coalesce(b.exist_kardex1, 0)
                    + coalesce(b.exist_kardex2, 0) + coalesce(b.stock_ach, 0)
          end) / b.consumo_diario
       end as cobertura_hospital_dias,
       (b.fecha_farmatools = b.fecha_inventario) as mismo_dia
from base b;

grant select on public.v_medicamento_almacen, public.v_medicamento to anon, authenticated;

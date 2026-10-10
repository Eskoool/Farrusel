-- Farrusel v1.3 · 2026-10-10 · Robot de la UFA en la rotura del hospital (decisión de Yared).
-- El consumo de Farmatools (consumed_9000) incluye la dispensación a pacientes externos, cuyo stock
-- está en el robot de la UFA (exist2), que no se sumaba. Regla:
--   - frío (fila ACVR)                         → farmacia + carrusel vertical (sin cambios)
--   - solo hay existencias en el robot de la UFA → `solo_ufa`: va APARTE y se compara su stock del
--                                                robot con el consumo medio
--   - en el resto                              → farmacia + K1 + K2 + carrusel H + robot UFA
--   - el Hospital del Sur (exist18, exist50, exist68) NO cuenta.
-- Necesita que el lector de Farmatools guarde exist2 → exist_robot_ufa (y exist60 → exist_carrusel_vert,
-- solo como contraste del Inventario por almacén). Hasta recargar, las columnas nuevas van a null y
-- la regla equivale a la anterior.

alter table public.stock_farmatools
  add column exist_robot_ufa numeric,        -- exist2
  add column exist_carrusel_vert numeric;    -- exist60

drop view public.v_medicamento;   -- sin dependientes; se recrea con columnas nuevas
create view public.v_medicamento as
with
sf_fecha as (select max(fecha_descarga) f from public.stock_farmatools),
sf as (select s.* from public.stock_farmatools s, sf_fecha where s.fecha_descarga = sf_fecha.f),
ia_fecha as (select max(fecha_descarga) f from public.inventario_almacen),
car as (select codigo, sum(cantidad) filter (where almacen like 'ACH%') as stock_ach, sum(cantidad) filter (where almacen like 'ACVR%') as stock_acvr,
         bool_or(almacen like 'ACH%') as en_ach, bool_or(almacen like 'ACVR%') as en_acvr, max(descripcion) as descripcion
  from public.inventario_almacen ia, ia_fecha where ia.fecha_descarga = ia_fecha.f group by codigo),
kx as (select codigo, max(descripcion) descripcion, sum(stock) filter (where almacen = 'KARDEX1') as stock_k1_kardex, sum(stock) filter (where almacen = 'KARDEX2') as stock_k2_kardex,
         bool_or(almacen = 'KARDEX1') en_k1, bool_or(almacen = 'KARDEX2') en_k2, max(fecha_descarga) fecha_kardex
  from public.v_kardex_articulo_armario where es_ultimo_corte and es_ultimo_periodo and almacen is not null group by codigo),
cods as (select codigo from sf union select codigo from car union select codigo from kx),
base as (select c.codigo, coalesce(sf.descripcion, car.descripcion, kx.descripcion) as descripcion,
         coalesce(kx.en_k1, false) en_k1, coalesce(kx.en_k2, false) en_k2, coalesce(car.en_ach, false) en_ach, coalesce(car.en_acvr, false) en_acvr,
         coalesce(car.en_acvr, false) as es_frio,
         sf.exist_farmacia, sf.exist_kardex1, sf.exist_kardex2, car.stock_ach, car.stock_acvr, kx.stock_k1_kardex, kx.stock_k2_kardex,
         sf.exist_robot_ufa,
         sf.consumo_medio_mensual, sf.consumo_medio_mensual > 0 as consumo_valido,
         case when sf.consumo_medio_mensual > 0 then sf.consumo_medio_mensual / 30 end as consumo_diario,
         sf.pedido_pendiente, sf.pedido_fecha_ultima, sf.pedido_n_lineas, sf.pedido_detalle, sf.upe, sf.precio_neto_envase,
         (select f from sf_fecha) as fecha_farmatools, (select f from ia_fecha) as fecha_inventario, kx.fecha_kardex
  from cods c left join sf on sf.codigo = c.codigo left join car on car.codigo = c.codigo left join kx on kx.codigo = c.codigo),
r as (select b.*,
         (not b.es_frio and coalesce(b.exist_robot_ufa, 0) > 0
          and coalesce(b.exist_farmacia, 0) <= 0 and coalesce(b.exist_kardex1, 0) <= 0
          and coalesce(b.exist_kardex2, 0) <= 0 and coalesce(b.stock_ach, 0) <= 0) as solo_ufa
      from base b)
select r.*,
       case when r.es_frio  then coalesce(r.exist_farmacia, 0) + coalesce(r.stock_acvr, 0)
            when r.solo_ufa then coalesce(r.exist_robot_ufa, 0)
            else coalesce(r.exist_farmacia, 0) + coalesce(r.exist_kardex1, 0) + coalesce(r.exist_kardex2, 0)
                 + coalesce(r.stock_ach, 0) + coalesce(r.exist_robot_ufa, 0)
       end as stock_hospital,
       case when r.consumo_diario > 0 then
         (case when r.es_frio  then coalesce(r.exist_farmacia, 0) + coalesce(r.stock_acvr, 0)
               when r.solo_ufa then coalesce(r.exist_robot_ufa, 0)
               else coalesce(r.exist_farmacia, 0) + coalesce(r.exist_kardex1, 0) + coalesce(r.exist_kardex2, 0)
                    + coalesce(r.stock_ach, 0) + coalesce(r.exist_robot_ufa, 0)
          end) / r.consumo_diario
       end as cobertura_hospital_dias,
       (r.fecha_farmatools = r.fecha_inventario) as mismo_dia
from r;

grant select on public.v_medicamento to anon, authenticated;

-- (2) Aplicado el mismo día (migración v13_robot_ufa_tambien_en_frio). Yared: «si está en vertical es
--     de frío; el robot es refrigerado pero metemos todo, ambiente y frío, por espacio». El robot de la
--     UFA se suma SIEMPRE, también en los de frío:
--       stock_sin_ufa  = frío: farmacia + carrusel V · normal: farmacia + K1 + K2 + carrusel H
--       solo_ufa       = robot > 0 y stock_sin_ufa <= 0
--       stock_hospital = stock_sin_ufa + robot UFA
--     (definición completa de la vista en la migración; mismas columnas que la versión anterior).

-- (3) Migración v13_baja_fuera_de_rotura (2026-10-10). Yared: «los de baja no pueden salir en rotura,
--     queremos que se gasten». `en_baja` = descripción que empieza por «BAJA» (44 automatizados).
--     Provisional: su cobertura_hospital_dias va a null para que la app no calcule rotura; cuando la
--     pantalla lea `en_baja` (encargo 2) se devuelve la cobertura y se excluye por el campo.

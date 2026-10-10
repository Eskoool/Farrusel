-- Farrusel v1.3 · 2026-10-10 · Decisiones de mín/máx también para el carrusel (REQ-033).
-- (1) propuesta_kardex admite ACH y ACVR, y una fuente de tasa nueva para el consumo del carrusel.
-- (2) Al pasar a `aplicada`, SOLO K1/K2 escriben en parametrizacion_kardex. El carrusel se registra y
--     nunca se escribe en Athos: el siguiente Inventario por almacén confirma.
-- (3) El maestro `articulo` crece con los medicamentos del carrusel (ubicaciones CH / CV), como ya
--     preveía su diseño, para que la clave ajena de propuesta_kardex no los rechace. Se rellena al
--     insertar en inventario_almacen (trigger) y una vez ahora con lo cargado.

alter table public.propuesta_kardex drop constraint propuesta_kardex_almacen_check;
alter table public.propuesta_kardex add constraint propuesta_kardex_almacen_check
  check (almacen in ('KARDEX1','KARDEX2','ACH','ACVR'));
alter table public.propuesta_kardex drop constraint propuesta_kardex_tasa_fuente_check;
alter table public.propuesta_kardex add constraint propuesta_kardex_tasa_fuente_check
  check (tasa_fuente in ('farmatools','movimientos','consumo_carrusel'));

create or replace function public.propuesta_kardex_transicion()
returns trigger language plpgsql as $function$
begin
  if old.estado = new.estado then return new; end if;
  if not (
       (old.estado = 'propuesta' and new.estado in ('aceptada','rechazada'))
    or (old.estado = 'aceptada'  and new.estado = 'aplicada')
  ) then
    raise exception 'Transición ilegal: % → %', old.estado, new.estado;
  end if;
  if new.estado in ('aceptada','rechazada') then new.decidida_en := now(); end if;
  if new.estado = 'aplicada' then
    new.aplicada_en := now();
    -- Solo el Kardex tiene parametrización propia aquí; el carrusel se registra y se configura en Athos.
    if new.almacen in ('KARDEX1','KARDEX2') then
      insert into public.parametrizacion_kardex (almacen, codigo, stock_minimo, stock_maximo, fuente, nota, actualizado_en)
      values (new.almacen, new.codigo, new.minimo_propuesto, new.maximo_propuesto, 'aplicada', new.nota, now())
      on conflict (almacen, codigo) do update
        set stock_minimo = excluded.stock_minimo, stock_maximo = excluded.stock_maximo,
            fuente = 'aplicada', nota = excluded.nota, actualizado_en = now();
    end if;
  end if;
  return new;
end $function$;

create or replace function public.articulo_desde_inventario_almacen()
returns trigger language plpgsql security definer set search_path to 'public' as $function$
declare u text := case when new.almacen like 'ACVR%' then 'CV' when new.almacen like 'ACH%' then 'CH' end;
begin
  if u is null then return new; end if;   -- EXT y otros no entran al maestro
  insert into public.articulo (codigo, descripcion, ubicaciones)
  values (new.codigo, coalesce(new.descripcion, new.codigo), array[u])
  on conflict (codigo) do update
    set ubicaciones = (select array_agg(distinct x order by x) from unnest(articulo.ubicaciones || array[u]) x),
        actualizado_en = now()
    where not (u = any(articulo.ubicaciones));
  return new;
end $function$;

create trigger trg_articulo_desde_inventario_almacen
  after insert on public.inventario_almacen
  for each row execute function public.articulo_desde_inventario_almacen();

-- Relleno con lo ya cargado (mismo criterio que el trigger).
insert into public.articulo (codigo, descripcion, ubicaciones)
select ia.codigo, coalesce(max(ia.descripcion), ia.codigo),
       array_agg(distinct case when ia.almacen like 'ACVR%' then 'CV' else 'CH' end)
from public.inventario_almacen ia
where ia.almacen like 'ACH%' or ia.almacen like 'ACVR%'
group by ia.codigo
on conflict (codigo) do update
  set ubicaciones = (select array_agg(distinct x order by x) from unnest(articulo.ubicaciones || excluded.ubicaciones) x),
      actualizado_en = now();

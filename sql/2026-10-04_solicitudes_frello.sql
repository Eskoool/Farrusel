-- Farrusel → Frello · «Reclamar pedido» y «Solicitar a gestión» (PRD v1.1, /cambio 2026-10-04)
-- Farrusel solo deja el evento en su bandeja; n8n lo recoge y escribe en Frello (incidents y,
-- para reclamar, pedidos_tracking en 'pedido_a_reclamar'). Farrusel nunca se conecta a Frello.
-- Reversible: drop function solicitar_accion_kardex; drop table solicitante cascade;
--             alter table evento_kardex drop column solicitante_id, drop column referencia_externa;
--             y recrear el CHECK de tipo con los cuatro valores originales.

-- 1) Lista del modal «¿Quién lo pide?». La rellena n8n a diario desde Frello (profiles con
--    role Administrador / Farmacéutico / FIR, centro HUNSC, activos). id = profiles.id de Frello.
--    Decisión de Yared 2026-10-04: nombre completo visible en una app sin login (riesgo asumido).
create table if not exists public.solicitante (
  id             uuid primary key,
  nombre         text not null,
  rol            text not null check (rol in ('Administrador','Farmacéutico','FIR')),
  activo         boolean not null default true,
  actualizado_en timestamptz not null default now()
);
alter table public.solicitante enable row level security;
create policy anon_sel on public.solicitante for select to anon, authenticated using (activo);
-- Sin políticas de escritura: solo service_role (n8n).

-- 2) Bandeja: dos tipos nuevos, quién lo pide y la referencia que devuelve Frello.
alter table public.evento_kardex drop constraint evento_kardex_tipo_check;
alter table public.evento_kardex add constraint evento_kardex_tipo_check check (tipo in (
  'corte_cargado','propuesta_aceptada','propuesta_rechazada','propuesta_aplicada',
  'reclamar_pedido','solicitar_pedido'));
alter table public.evento_kardex add column if not exists solicitante_id uuid references public.solicitante(id);
alter table public.evento_kardex add column if not exists referencia_externa text;  -- id de la incidencia en Frello
create index if not exists evento_kardex_codigo_tipo on public.evento_kardex (codigo, tipo, creado_en desc);

-- 3) Única puerta de escritura desde la app (anon). Valida y construye el payload en el servidor.
create or replace function public.solicitar_accion_kardex(
  p_tipo text, p_codigo text, p_solicitante uuid, p_nota text default null)
returns bigint
language plpgsql security definer set search_path = public as $$
declare
  v_sol   public.solicitante%rowtype;
  v_ft    public.stock_farmatools%rowtype;
  v_ped   jsonb;
  v_prev  public.evento_kardex%rowtype;
  v_id    bigint;
  v_dias_min constant int := 7;
begin
  if p_tipo not in ('reclamar_pedido','solicitar_pedido') then
    raise exception 'Acción no permitida: %', p_tipo;
  end if;

  select * into v_sol from public.solicitante where id = p_solicitante and activo;
  if not found then raise exception 'Elige quién lo pide de la lista.'; end if;

  select * into v_ft from public.stock_farmatools
   where codigo = p_codigo and fecha_descarga = (select max(fecha_descarga) from public.stock_farmatools);
  if not found then raise exception 'El artículo % no está en el último informe de Farmatools.', p_codigo; end if;

  -- Antiduplicado: una solicitud igual pendiente, o enviada con éxito hace menos de 7 días.
  select * into v_prev from public.evento_kardex
   where tipo = p_tipo and codigo = p_codigo
     and (procesado_en is null or (resultado = 'ok' and creado_en > now() - interval '7 days'))
   order by creado_en desc limit 1;
  if found then
    raise exception 'Ya se pidió el % (%).', to_char(v_prev.creado_en at time zone 'Atlantic/Canary', 'DD/MM HH24:MI'),
      case when v_prev.procesado_en is null then 'pendiente de enviar a Frello' else 'enviado a Frello' end;
  end if;

  if p_tipo = 'reclamar_pedido' then
    -- Pedidos con 7 días o más, del más antiguo al más reciente, con sus días de retraso.
    select coalesce(jsonb_agg(jsonb_build_object(
             'n_pedido', e->>'n_pedido', 'fecha', e->>'fecha',
             'dias', current_date - (e->>'fecha')::date) order by (e->>'fecha')::date), '[]'::jsonb)
      into v_ped
      from jsonb_array_elements(coalesce(v_ft.pedido_detalle, '[]'::jsonb)) e
     where (e->>'fecha') is not null and (e->>'fecha')::date <= current_date - v_dias_min;
    if jsonb_array_length(v_ped) = 0 then
      raise exception 'No hay ningún pedido pendiente con % días o más para este artículo.', v_dias_min;
    end if;
  end if;

  insert into public.evento_kardex (tipo, fecha_descarga, codigo, solicitante_id, consumidor, payload)
  values (p_tipo, v_ft.fecha_descarga, p_codigo, v_sol.id, 'frello', jsonb_build_object(
    'codigo', p_codigo,
    'medicamento', v_ft.descripcion,
    'laboratorio', v_ft.nombre_proveedor,
    'solicitante_nombre', v_sol.nombre,
    'nota', nullif(btrim(p_nota), ''),
    'fecha_farmatools', v_ft.fecha_descarga,
    'pedido_pendiente_ud', v_ft.pedido_pendiente,
    'pedidos', coalesce(v_ped, coalesce(v_ft.pedido_detalle, '[]'::jsonb)),
    'exist_kardex1', v_ft.exist_kardex1, 'exist_kardex2', v_ft.exist_kardex2,
    'exist_farmacia', v_ft.exist_farmacia, 'exist_carrusel', v_ft.exist_carrusel,
    'consumo_medio_mensual', v_ft.consumo_medio_mensual))
  returning id into v_id;
  return v_id;
end $$;

revoke all on function public.solicitar_accion_kardex(text, text, uuid, text) from public;
grant execute on function public.solicitar_accion_kardex(text, text, uuid, text) to anon, authenticated;

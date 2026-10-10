-- Farrusel · 2026-10-10 · PENDIENTE DE OK (no aplicado). Incidencias en Frello AL PULSAR, sin sondeo.
-- Cadena: ventana de Farrusel → RPC solicitar_accion_kardex (v2) → evento_kardex → este trigger (pg_net) →
-- webhook de n8n «farrusel-incidencia» (cabecera X-Farrusel-Secreto) → incidencia en Frello.
--
-- Antes de aplicar, Yared (no pasa por el chat):
--   1. Elige un secreto largo y guárdalo en el vault de Farrusel:
--        select vault.create_secret('<SECRETO>', 'n8n_webhook_secreto');
--   2. Pone ese mismo valor en n8n, credencial Header Auth «Farrusel webhook (secreto)»,
--      cabecera X-Farrusel-Secreto.

create extension if not exists pg_net;

-- RPC v2: el texto, la prioridad y quién lo pide vienen de la ventana. Firma nueva con parámetros con
-- valor por defecto, compatible con la llamada actual de la app (p_tipo, p_codigo, p_solicitante, p_nota).
drop function if exists public.solicitar_accion_kardex(text, text, uuid, text);
create or replace function public.solicitar_accion_kardex(
  p_tipo text, p_codigo text, p_solicitante uuid, p_nota text default null,
  p_titulo text default null, p_descripcion text default null, p_prioridad text default 'media')
returns bigint language plpgsql security definer set search_path to 'public' as $function$
declare
  v_sol  public.solicitante%rowtype;
  v_ft   public.stock_farmatools%rowtype;
  v_ped  jsonb;
  v_prev public.evento_kardex%rowtype;
  v_id   bigint;
  v_dias_min constant int := 7;
begin
  if p_tipo not in ('reclamar_pedido','solicitar_pedido') then
    raise exception 'Acción no permitida: %', p_tipo;
  end if;
  if coalesce(p_prioridad, 'media') not in ('baja','media','urgente') then
    raise exception 'Prioridad no válida: % (baja, media o urgente).', p_prioridad;
  end if;

  select * into v_sol from public.solicitante where id = p_solicitante and activo;
  if not found then raise exception 'Elige quién lo pide de la lista.'; end if;

  select * into v_ft from public.stock_farmatools
   where codigo = p_codigo and fecha_descarga = (select max(fecha_descarga) from public.stock_farmatools);
  if not found then raise exception 'El artículo % no está en el último informe de Farmatools.', p_codigo; end if;

  select * into v_prev from public.evento_kardex
   where tipo = p_tipo and codigo = p_codigo
     and (procesado_en is null or (resultado = 'ok' and creado_en > now() - interval '7 days'))
   order by creado_en desc limit 1;
  if found then
    raise exception 'Ya se pidió el % (%).', to_char(v_prev.creado_en at time zone 'Atlantic/Canary', 'DD/MM HH24:MI'),
      case when v_prev.procesado_en is null then 'pendiente de enviar a Frello' else 'enviado a Frello' end;
  end if;

  if p_tipo = 'reclamar_pedido' then
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

  if nullif(btrim(p_titulo), '') is null or nullif(btrim(p_descripcion), '') is null then
    raise exception 'Falta el título o el texto de la incidencia.';
  end if;

  insert into public.evento_kardex (tipo, fecha_descarga, codigo, solicitante_id, consumidor, payload)
  values (p_tipo, v_ft.fecha_descarga, p_codigo, v_sol.id, 'frello', jsonb_build_object(
    'titulo', btrim(p_titulo), 'descripcion', btrim(p_descripcion), 'prioridad', coalesce(p_prioridad, 'media'),
    'codigo', p_codigo, 'medicamento', v_ft.descripcion, 'laboratorio', v_ft.nombre_proveedor,
    'solicitante_nombre', v_sol.nombre, 'nota', nullif(btrim(p_nota), ''),
    'fecha_farmatools', v_ft.fecha_descarga, 'pedido_pendiente_ud', v_ft.pedido_pendiente,
    'pedidos', coalesce(v_ped, coalesce(v_ft.pedido_detalle, '[]'::jsonb))))
  returning id into v_id;
  return v_id;
end $function$;
grant execute on function public.solicitar_accion_kardex(text, text, uuid, text, text, text, text) to anon, authenticated;

-- Trigger: avisa a n8n en el momento. El secreto sale del vault; nunca llega al navegador.
create or replace function public.evento_kardex_a_n8n()
returns trigger language plpgsql security definer set search_path to 'public' as $function$
declare v_secreto text;
begin
  if new.tipo not in ('reclamar_pedido','solicitar_pedido') then return new; end if;
  select decrypted_secret into v_secreto from vault.decrypted_secrets where name = 'n8n_webhook_secreto';
  if v_secreto is null then return new; end if;   -- sin secreto no se envía: queda pendiente y visible
  perform net.http_post(
    url := 'https://n8n.srv872841.hstgr.cloud/webhook/farrusel-incidencia',
    headers := jsonb_build_object('Content-Type', 'application/json', 'X-Farrusel-Secreto', v_secreto),
    body := jsonb_build_object('evento_id', new.id, 'tipo', new.tipo, 'codigo', new.codigo,
                               'solicitante_id', new.solicitante_id, 'payload', new.payload));
  return new;
end $function$;

-- Se dispara al crear el evento y al «Reintentar» (la app vuelve a poner procesado_en a null).
create trigger trg_evento_kardex_a_n8n
  after insert or update of procesado_en on public.evento_kardex
  for each row when (new.procesado_en is null)
  execute function public.evento_kardex_a_n8n();

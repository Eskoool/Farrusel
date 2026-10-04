-- Aviso de resultados de Farrusel · se ejecuta UNA vez, cuando la función ya está desplegada.
-- Requisitos previos: Edge Function `aviso-resultados` desplegada y secreto RESEND_API_KEY puesto.
-- <ANON_KEY> es la clave publishable del proyecto (pública por diseño), no la service_role.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Reserva de idempotencia: una fila por aviso enviado. Sin políticas: solo la función (service_role) escribe.
create table if not exists public.aviso_resultados (
  clave      text primary key,
  enviado_en timestamptz not null default now()
);
alter table public.aviso_resultados enable row level security;

-- 24 de diciembre a las 08:00 UTC. Se repetiría cada año, pero la función solo actúa en 2026
-- y una sola vez (guardas de fecha e idempotencia dentro de la propia función).
select cron.schedule(
  'aviso-resultados-farrusel',
  '0 8 24 12 *',
  $$
  select net.http_post(
    url := 'https://sgpbdzphweyeaegzesvb.supabase.co/functions/v1/aviso-resultados',
    headers := jsonb_build_object('Content-Type','application/json','Authorization','Bearer <ANON_KEY>'),
    body := '{}'::jsonb
  );
  $$
);

-- Para deshacerlo: select cron.unschedule('aviso-resultados-farrusel'); drop table public.aviso_resultados;

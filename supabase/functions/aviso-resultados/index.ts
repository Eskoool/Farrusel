// Aviso de resultados de Farrusel · una semana antes del 31-12-2026.
// Lo dispara pg_cron (supabase/aviso-resultados.sql). Envía un resumen de AGREGADOS (sin stock,
// sin datos de paciente) y un enlace al informe interactivo. Idempotente: un solo envío.
//
// Secretos de la función (Supabase → Edge Functions → Secrets), nunca en git:
//   RESEND_API_KEY   clave de Resend
// Opcionales:
//   AVISO_DESTINO    por defecto yaredgpz@gmail.com
//   AVISO_DESDE      por defecto "Farrusel <onboarding@resend.dev>" (sin dominio propio, Resend
//                    solo entrega al correo con el que se abrió la cuenta)
//   INFORME_URL      enlace al informe interactivo  [PENDIENTE VALIDAR: ruta de la pantalla «Actividad»]
import { createClient } from "npm:@supabase/supabase-js@2";

const CLAVE = "resultados-2026-12-31";
const DESDE_FECHA = "2026-12-24"; // una semana antes del 2026-12-31
const ANIO_VALIDO = 2026;

const hoy = () => new Date().toISOString().slice(0, 10);

Deno.serve(async () => {
  if (Number(hoy().slice(0, 4)) !== ANIO_VALIDO || hoy() < DESDE_FECHA) {
    return json({ ok: true, enviado: false, motivo: "fuera de ventana" });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  // Idempotencia: se reserva la clave antes de enviar; si el envío falla, se libera.
  const { error: reservaError } = await supabase.from("aviso_resultados").insert({ clave: CLAVE });
  if (reservaError) {
    return json({ ok: true, enviado: false, motivo: "ya enviado o reservado" });
  }

  try {
    const resumen = await calcularResumen(supabase);
    const apiKey = Deno.env.get("RESEND_API_KEY");
    if (!apiKey) throw new Error("Falta el secreto RESEND_API_KEY");

    const respuesta = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from: Deno.env.get("AVISO_DESDE") ?? "Farrusel <onboarding@resend.dev>",
        to: [Deno.env.get("AVISO_DESTINO") ?? "yaredgpz@gmail.com"],
        subject: "Farrusel · faltan 7 días para los resultados",
        html: cuerpo(resumen),
      }),
    });
    if (!respuesta.ok) throw new Error(`Resend ${respuesta.status}: ${await respuesta.text()}`);
    return json({ ok: true, enviado: true });
  } catch (e) {
    await supabase.from("aviso_resultados").delete().eq("clave", CLAVE);
    return json({ ok: false, error: String(e) }, 500);
  }
});

async function contar(
  supabase: ReturnType<typeof createClient>,
  tabla: string,
  filtro: Record<string, string>,
): Promise<number> {
  let q = supabase.from(tabla).select("*", { count: "exact", head: true });
  for (const [k, v] of Object.entries(filtro)) q = q.eq(k, v);
  const { count, error } = await q;
  if (error) throw new Error(`${tabla}: ${error.message}`);
  return count ?? 0;
}

async function calcularResumen(supabase: ReturnType<typeof createClient>) {
  const [cortes, aperturasGestion, aperturasSubida, aceptadas, rechazadas, aplicadas] = await Promise.all([
    contar(supabase, "evento_kardex", { tipo: "corte_cargado" }),
    contar(supabase, "uso_evento", { pantalla: "gestion", accion: "abrir" }),
    contar(supabase, "uso_evento", { pantalla: "subida", accion: "abrir" }),
    contar(supabase, "evento_kardex", { tipo: "propuesta_aceptada" }),
    contar(supabase, "evento_kardex", { tipo: "propuesta_rechazada" }),
    contar(supabase, "evento_kardex", { tipo: "propuesta_aplicada" }),
  ]);
  const { count: pendientes } = await supabase
    .from("evento_kardex").select("*", { count: "exact", head: true }).is("procesado_en", null);
  const { count: totalEventos } = await supabase
    .from("evento_kardex").select("*", { count: "exact", head: true });
  return { cortes, aperturasGestion, aperturasSubida, aceptadas, rechazadas, aplicadas,
           pendientes: pendientes ?? 0, totalEventos: totalEventos ?? 0 };
}

function cuerpo(r: Awaited<ReturnType<typeof calcularResumen>>): string {
  const url = Deno.env.get("INFORME_URL") ?? "";
  const enlace = url
    ? `<p><a href="${url}">Abrir el informe interactivo</a></p>`
    : `<p>El enlace al informe interactivo no está configurado (secreto INFORME_URL).</p>`;
  return `<h2>Farrusel · resultados a 7 días del 31-12-2026</h2>
<p>Resumen de uso (solo agregados):</p>
<ul>
<li>Cortes cargados: <b>${r.cortes}</b> (objetivo: al menos 1 al mes)</li>
<li>Aperturas de Gestión Kardex: <b>${r.aperturasGestion}</b> (objetivo: al menos 4 al mes)</li>
<li>Aperturas de Subida: <b>${r.aperturasSubida}</b></li>
<li>Propuestas aceptadas: <b>${r.aceptadas}</b> · rechazadas: <b>${r.rechazadas}</b> · aplicadas: <b>${r.aplicadas}</b></li>
<li>Eventos pendientes de procesar: <b>${r.pendientes}</b> de ${r.totalEventos}
    (hasta la v1.1 con Frello no hay consumidor, así que el 95 % de la métrica 2 aún no es medible)</li>
</ul>
${enlace}
<p style="color:#666">Mensaje automático. Métricas definidas en el PRD §2.</p>`;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

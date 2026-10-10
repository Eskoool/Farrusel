"""Genera el flujo de n8n «Farrusel → Frello · incidencias al pulsar» (PRD REQ-023, REQ-031). 2026-10-10.
Uso (desde codigo/):  python n8n/build_incidencias_farrusel.py
Salida: n8n/frello-incidencias-al-pulsar.workflow.json

Sustituye a los dos flujos por sondeo («bandeja del Kardex» cada 5 min y «Solicitar a gestión» cada 5 min):
se dispara EN EL MOMENTO en que el usuario envía la ventana de «Solicitar a gestión» o «Reclamar pedido».

Cadena: botón → ventana (texto editable, prioridad, quién lo pide) → RPC `solicitar_accion_kardex` → fila en
`evento_kardex` → trigger de Farrusel con pg_net → POST a este webhook (cabecera secreta) → incidencia en Frello:
  - solicitar_pedido → área «Gestión»
  - reclamar_pedido  → área «Administrativos HUNSC». Frello ya reenvía sola esas incidencias a su flujo de
    administrativos (`notify-incident-creation` → webhook `incidencia_adminsitrativos`), que crea la tarjeta para
    farmacéuticos copiando la descripción tal cual. Por eso aquí NO se crea tarjeta (saldría duplicada) y la
    descripción lleva la fecha, el proveedor y el número de pedido escritos.
→ marca el evento en Farrusel (`ok` + id de la incidencia, o `error`).

Credenciales (por nombre; ninguna clave en este fichero):
  - «Farrusel webhook (secreto)»  · Header Auth: cabecera `X-Farrusel-Secreto`, valor = el mismo secreto que se
    guarda en el vault de Farrusel con el nombre `n8n_webhook_secreto`.
  - «Frello service_role»   · Supabase API → nodos «Frello ·»
  - «Farrusel service_role» · Supabase API → nodos «Farrusel ·»
"""
import json, os, pathlib

aqui = pathlib.Path(__file__).parent
FRELLO = "https://julrvkllcifpcdyvbikr.supabase.co"
FARRUSEL = "https://sgpbdzphweyeaegzesvb.supabase.co"
CFG = "$('Config').first().json"
CRED = {
    "frelloUrl": {"id": os.environ.get("CRED_FRELLO_ID", ""), "name": "Frello service_role"},
    "farruselUrl": {"id": os.environ.get("CRED_FARRUSEL_ID", ""), "name": "Farrusel service_role"},
    "webhook": {"id": os.environ.get("CRED_WEBHOOK_ID", ""), "name": "Farrusel webhook (secreto)"},
}


def cred(k):
    c = dict(CRED[k])
    if not c["id"]:
        c.pop("id")
    return c


def http(nombre, metodo, base, ruta, pos, query=None, headers=None, body=None, extra=None):
    p = {"method": metodo, "url": "={{ " + CFG + "." + base + " }}/rest/v1/" + ruta,
         "authentication": "predefinedCredentialType", "nodeCredentialType": "supabaseApi", "options": {}}
    if query:
        p["sendQuery"] = True
        p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query]}
    if headers:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers]}
    if body:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body
    nodo = {"parameters": p, "id": nombre.lower().replace(" ", "-").replace("·", "").replace("¿", "").replace("?", "")[:40],
            "name": nombre, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos,
            "credentials": {"supabaseApi": cred(base)}}
    nodo.update(extra or {})
    return nodo


def a(nodo, idx=0):
    return {"node": nodo, "type": "main", "index": idx}


JS_PREPARAR = r"""// Cuerpo del webhook (lo envía el trigger de Farrusel) → incidencia de Frello.
// El texto lo redactó y revisó el usuario en la ventana de Farrusel; aquí solo se valida y se marca.
const b = $json.body || $json;
const p = b.payload || {};
const AREA = { solicitar_pedido: 'Gestión', reclamar_pedido: 'Administrativos HUNSC' };
const PRIO = ['baja', 'media', 'urgente'];

if (!AREA[b.tipo]) throw new Error(`Tipo de evento no admitido: ${b.tipo}`);
if (!b.solicitante_id) throw new Error('Falta quién lo pide (solicitante_id).');
const titulo = String(p.titulo || '').trim();
const descripcion = String(p.descripcion || '').trim();
if (!titulo || !descripcion) throw new Error('Falta el título o el texto de la incidencia.');

const ref = `[Farrusel #${b.evento_id}]`;      // marca de idempotencia
return {
  json: {
    evento_id: b.evento_id,
    tipo: b.tipo,
    ref,
    incidencia: {
      title: titulo.slice(0, 200),
      description: descripcion.includes(ref) ? descripcion : `${descripcion}\n${ref}`,
      status: 'pending',
      priority: PRIO.includes(p.prioridad) ? p.prioridad : 'media',
      pharmacy_area: AREA[b.tipo],
      created_by: b.solicitante_id,
    },
  },
};
"""

PREP = "$('Preparar').item.json"
ERR = "JSON.stringify($json.error ?? $json).slice(0, 500)"

nodos = [
    {"parameters": {"httpMethod": "POST", "path": "farrusel-incidencia", "authentication": "headerAuth",
                    "responseMode": "onReceived", "options": {}},
     "id": "webhook", "name": "Al pulsar en Farrusel", "type": "n8n-nodes-base.webhook", "typeVersion": 2,
     "position": [0, 100], "webhookId": "farrusel-incidencia",
     "credentials": {"httpHeaderAuth": cred("webhook")}},
    {"parameters": {"assignments": {"assignments": [
        {"id": "cfg-frelloUrl", "name": "frelloUrl", "value": FRELLO, "type": "string"},
        {"id": "cfg-farruselUrl", "name": "farruselUrl", "value": FARRUSEL, "type": "string"}]},
        "includeOtherFields": True, "options": {}},
     "id": "cfg", "name": "Config", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [220, 100]},
    {"parameters": {"mode": "runOnceForEachItem", "language": "javaScript", "jsCode": JS_PREPARAR},
     "id": "preparar", "name": "Preparar", "type": "n8n-nodes-base.code", "typeVersion": 2,
     "position": [440, 100], "onError": "continueErrorOutput"},
    http("Frello · ¿Ya existe?", "GET", "frelloUrl", "incidents", [660, 40], query=[
        ("select", "id"),
        ("description", "=ilike.*{{ $json.ref }}*"),
        ("limit", "1")], extra={"alwaysOutputData": True}),
    {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                                               "version": 2},
                                   "conditions": [{"id": "c1", "leftValue": "={{ $json.id }}", "rightValue": "",
                                                   "operator": {"type": "string", "operation": "exists",
                                                                "singleValue": True}}],
                                   "combinator": "and"}, "options": {}},
     "id": "ya-estaba", "name": "¿Ya estaba en Frello?", "type": "n8n-nodes-base.if", "typeVersion": 2.2,
     "position": [880, 40]},
    http("Frello · Crear incidencia", "POST", "frelloUrl", "incidents", [1100, 140],
         headers=[("Prefer", "return=representation")],
         body="={{ JSON.stringify(" + PREP + ".incidencia) }}", extra={"onError": "continueErrorOutput"}),
    http("Farrusel · Marcar enviado", "PATCH", "farruselUrl", "evento_kardex", [1320, 80],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'ok', error: null, "
              "referencia_externa: $('Frello · Crear incidencia').item.json.id }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar ya existía", "PATCH", "farruselUrl", "evento_kardex", [1100, -60],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'ok', error: null, "
              "referencia_externa: $('Frello · ¿Ya existe?').item.json.id }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar error (Frello)", "PATCH", "farruselUrl", "evento_kardex", [1320, 280],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'error', "
              "error: 'No se pudo crear la incidencia en Frello: ' + " + ERR + " }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar error (datos)", "PATCH", "farruselUrl", "evento_kardex", [660, 300],
         query=[("id", "=eq.{{ ($('Config').item.json.body || {}).evento_id }}")],
         headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'error', "
              "error: 'Evento incompleto: ' + " + ERR + " }) }}",
         extra={"alwaysOutputData": True}),
]
conexiones = {
    "Al pulsar en Farrusel": {"main": [[a("Config")]]},
    "Config": {"main": [[a("Preparar")]]},
    "Preparar": {"main": [[a("Frello · ¿Ya existe?")], [a("Farrusel · Marcar error (datos)")]]},
    "Frello · ¿Ya existe?": {"main": [[a("¿Ya estaba en Frello?")]]},
    "¿Ya estaba en Frello?": {"main": [[a("Farrusel · Marcar ya existía")], [a("Frello · Crear incidencia")]]},
    "Frello · Crear incidencia": {"main": [[a("Farrusel · Marcar enviado")], [a("Farrusel · Marcar error (Frello)")]]},
}
wf = {"name": "Farrusel → Frello · incidencias al pulsar (Gestión y Administrativos HUNSC)", "nodes": nodos,
      "connections": conexiones, "settings": {"executionOrder": "v1", "timezone": "Atlantic/Canary"}}
salida = aqui / "frello-incidencias-al-pulsar.workflow.json"
salida.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK", salida.name, salida.stat().st_size, "bytes")

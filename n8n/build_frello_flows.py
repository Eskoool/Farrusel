"""Genera los dos flujos de n8n de la conexión Farrusel → Frello (PRD REQ-023/REQ-024).
Uso (desde codigo/):  python n8n/build_frello_flows.py
Salida: n8n/frello-sync-solicitantes.workflow.json y n8n/frello-bandeja-kardex.workflow.json

No llevan ninguna clave. Cada nodo HTTP usa una credencial de tipo «Supabase API» que se elige en n8n:
  - «Frello service_role»   → nodos cuyo nombre empieza por «Frello ·»
  - «Farrusel service_role» → nodos cuyo nombre empieza por «Farrusel ·»
"""
import json, pathlib

aqui = pathlib.Path(__file__).parent
FRELLO = "https://julrvkllcifpcdyvbikr.supabase.co"
FARRUSEL = "https://sgpbdzphweyeaegzesvb.supabase.co"
CFG = "$('Config').first().json"


def config(pos):
    campos = [("frelloUrl", FRELLO), ("farruselUrl", FARRUSEL)]
    return {"parameters": {"assignments": {"assignments": [
        {"id": "cfg-" + k, "name": k, "value": v, "type": "string"} for k, v in campos]}, "options": {}},
        "id": "cfg", "name": "Config", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": pos}


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
    nodo = {"parameters": p, "id": nombre.lower().replace(" ", "-").replace("·", "")[:40], "name": nombre,
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos}
    nodo.update(extra or {})
    return nodo


def code(nombre, js, pos, modo="runOnceForAllItems"):
    return {"parameters": {"mode": modo, "language": "javaScript", "jsCode": js},
            "id": nombre.lower().replace(" ", "-")[:40], "name": nombre, "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": pos}


def si(nombre, izquierda, operacion, derecha, pos, tipo="string"):
    cond = {"id": "c1", "leftValue": izquierda, "rightValue": derecha,
            "operator": {"type": tipo, "operation": operacion}}
    if operacion in ("exists", "notExists", "empty", "notEmpty"):
        cond["operator"]["singleValue"] = True
    return {"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose",
                                                      "version": 2},
                                          "conditions": [cond], "combinator": "and"}, "options": {}},
            "id": nombre.lower().replace(" ", "-").replace("¿", "").replace("?", "")[:40], "name": nombre,
            "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": pos}


def a(nodo, idx=0):
    return {"node": nodo, "type": "main", "index": idx}


def guardar(nombre_fichero, wf):
    salida = aqui / nombre_fichero
    salida.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK", salida.name, salida.stat().st_size, "bytes")


# ---------------------------------------------------------------------------------------------
# Flujo 1 · Sincronizar solicitantes (diario): Frello.profiles → Farrusel.solicitante
# ---------------------------------------------------------------------------------------------
JS_LISTA = r"""// Personas que pueden pedir desde Farrusel: Administrador, Farmacéutico y FIR de HUNSC, activos.
const ahora = new Date().toISOString();
const filas = $input.all()
  .map(i => i.json)
  .filter(p => p.id && (p.name || p.surname))
  .map(p => ({
    id: p.id,
    nombre: [p.name, p.surname].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim(),
    rol: p.role,
    activo: true,
    actualizado_en: ahora,
  }));
// Guarda: si Frello devuelve 0 personas (credencial mal, caída…), no se desactiva a nadie.
if (filas.length === 0) {
  throw new Error('Frello devolvió 0 personas: no se toca la lista de Farrusel.');
}
return [{ json: { filas, ids: filas.map(f => f.id), total: filas.length } }];
"""

sync_nodos = [
    {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 6 * * *"}]}},
     "id": "trg-diario", "name": "Cada día 06:00", "type": "n8n-nodes-base.scheduleTrigger",
     "typeVersion": 1.2, "position": [0, 0]},
    {"parameters": {}, "id": "trg-man", "name": "Prueba manual", "type": "n8n-nodes-base.manualTrigger",
     "typeVersion": 1, "position": [0, 200]},
    config([220, 100]),
    http("Frello · Leer personas", "GET", "frelloUrl", "profiles", [440, 100], query=[
        ("select", "id,name,surname,role"),
        ("centro", "eq.HUNSC"),
        ("role", "in.(Administrador,Farmacéutico,FIR)"),
        ("is_active", "not.is.false")]),
    code("Preparar lista", JS_LISTA, [660, 100]),
    http("Farrusel · Guardar lista", "POST", "farruselUrl", "solicitante", [880, 100],
         query=[("on_conflict", "id")],
         headers=[("Prefer", "resolution=merge-duplicates,return=minimal")],
         body="={{ JSON.stringify($json.filas) }}", extra={"alwaysOutputData": True}),
    http("Farrusel · Desactivar ausentes", "PATCH", "farruselUrl", "solicitante", [1100, 100],
         query=[("id", "=not.in.({{ $('Preparar lista').first().json.ids.join(',') }})"),
                ("activo", "eq.true")],
         headers=[("Prefer", "return=minimal")],
         body='={{ JSON.stringify({ activo: false, actualizado_en: $now.toISO() }) }}',
         extra={"alwaysOutputData": True}),
]
sync_con = {
    "Cada día 06:00": {"main": [[a("Config")]]},
    "Prueba manual": {"main": [[a("Config")]]},
    "Config": {"main": [[a("Frello · Leer personas")]]},
    "Frello · Leer personas": {"main": [[a("Preparar lista")]]},
    "Preparar lista": {"main": [[a("Farrusel · Guardar lista")]]},
    "Farrusel · Guardar lista": {"main": [[a("Farrusel · Desactivar ausentes")]]},
}
guardar("frello-sync-solicitantes.workflow.json", {
    "name": "Farrusel · sincronizar solicitantes desde Frello (diario)", "nodes": sync_nodos,
    "connections": sync_con, "settings": {"executionOrder": "v1", "timezone": "Atlantic/Canary"}})

# ---------------------------------------------------------------------------------------------
# Flujo 2 · Bandeja (cada 5 min): Farrusel.evento_kardex → Frello.incidents (+ pedidos_tracking)
# ---------------------------------------------------------------------------------------------
JS_PREPARAR = r"""// Un evento de la bandeja de Farrusel → lo que se escribe en Frello.
const e = $json;
const p = e.payload || {};
const fmt = d => (d ? String(d).slice(0, 10).split('-').reverse().join('/') : '¿?');
const ref = `[Farrusel #${e.id}]`;           // marca de idempotencia en la descripción
const nombre = p.solicitante_nombre || '¿?';
const nota = p.nota ? `\nNota: ${p.nota}` : '';
const med = p.medicamento || e.codigo;
let titulo, descripcion, area, tracking = null;

if (e.tipo === 'reclamar_pedido') {
  const ped = Array.isArray(p.pedidos) ? p.pedidos : [];
  const lineas = ped.map(x => `- Pedido ${x.n_pedido ?? '¿?'} del ${fmt(x.fecha)} (${x.dias ?? '?'} días)`).join('\n');
  titulo = `Kardex · Pedido pendiente: ${med}`;
  descripcion =
    `Reclamar al proveedor ${p.laboratorio ?? '¿?'} el pedido pendiente de ${med} (código ${e.codigo}).\n` +
    `Pedidos con 7 días o más:\n${lineas}\n` +
    `Unidades pendientes de recibir: ${p.pedido_pendiente_ud ?? '¿?'}.\n` +
    `Solicitado por ${nombre} desde Farrusel (Kardex), Farmatools del ${fmt(p.fecha_farmatools)}.${nota}\n${ref}`;
  area = 'Administrativos HUNSC';
  const masAntiguo = ped[0] || {};
  tracking = {
    medicamento: med,
    laboratorio: p.laboratorio ?? null,
    numero_pedido: masAntiguo.n_pedido ?? null,
    estado: 'pedido_a_reclamar',
    centro: 'HUNSC',
    notas: `${lineas}\nSolicitado por ${nombre} desde Farrusel (Kardex).${nota}`,
    usuario_registra: e.solicitante_id,
    origen_ref: { farrusel_evento_id: e.id, codigo: e.codigo, pedidos: ped },
  };
} else {
  const k = (Number(p.exist_kardex1) || 0) + (Number(p.exist_kardex2) || 0);
  const umbral = 0.3 * (Number(p.consumo_medio_mensual) || 0);
  titulo = `Kardex · Solicitar pedido: ${med}`;
  descripcion =
    `Valorar pedido de ${med} (código ${e.codigo}, proveedor ${p.laboratorio ?? '¿?'}).\n` +
    `Kardex K1+K2: ${k} · Farmacia: ${p.exist_farmacia ?? '¿?'} · Carrusel: ${p.exist_carrusel ?? 'sin dato'} · ` +
    `Pedido pendiente: ${p.pedido_pendiente_ud ?? 0} · Consumo medio mensual: ${p.consumo_medio_mensual ?? '¿?'} ` +
    `(30 % = ${umbral.toFixed(1)}).\n` +
    `Solicitado por ${nombre} desde Farrusel (Kardex), Farmatools del ${fmt(p.fecha_farmatools)}.${nota}\n${ref}`;
  area = 'Gestión';
}

return {
  json: {
    evento_id: e.id,
    tipo: e.tipo,
    ref,
    incidencia: {
      title: titulo,
      description: descripcion,
      status: 'pending',
      priority: 'media',
      pharmacy_area: area,
      created_by: e.solicitante_id,
    },
    tracking,
  },
};
"""

PREP = "$('Preparar').item.json"
ERR = "JSON.stringify($json.error ?? $json).slice(0, 500)"

bandeja_nodos = [
    {"parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
     "id": "trg-5min", "name": "Cada 5 minutos", "type": "n8n-nodes-base.scheduleTrigger",
     "typeVersion": 1.2, "position": [0, 0]},
    {"parameters": {}, "id": "trg-man", "name": "Prueba manual", "type": "n8n-nodes-base.manualTrigger",
     "typeVersion": 1, "position": [0, 200]},
    config([220, 100]),
    http("Farrusel · Leer pendientes", "GET", "farruselUrl", "evento_kardex", [440, 100], query=[
        ("select", "id,tipo,codigo,solicitante_id,payload,creado_en"),
        ("procesado_en", "is.null"),
        ("tipo", "in.(reclamar_pedido,solicitar_pedido)"),
        ("order", "id.asc"),
        ("limit", "20")]),
    {"parameters": {"batchSize": 1, "options": {}}, "id": "loop", "name": "Uno a uno",
     "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [660, 100]},
    code("Preparar", JS_PREPARAR, [880, 200], modo="runOnceForEachItem"),
    http("Frello · ¿Ya existe?", "GET", "frelloUrl", "incidents", [1100, 200], query=[
        ("select", "id"),
        ("description", "=ilike.*{{ $json.ref }}*"),
        ("limit", "1")], extra={"alwaysOutputData": True}),
    si("¿Ya estaba en Frello?", "={{ $json.id }}", "exists", "", [1320, 200]),
    http("Frello · Crear incidencia", "POST", "frelloUrl", "incidents", [1540, 300],
         headers=[("Prefer", "return=representation")],
         body="={{ JSON.stringify(" + PREP + ".incidencia) }}", extra={"onError": "continueErrorOutput"}),
    si("¿Es reclamar?", "={{ " + PREP + ".tipo }}", "equals", "reclamar_pedido", [1760, 260]),
    http("Frello · Crear tarjeta pedido_a_reclamar", "POST", "frelloUrl", "pedidos_tracking", [1980, 200],
         headers=[("Prefer", "return=representation")],
         body="={{ JSON.stringify(Object.assign({}, " + PREP +
              ".tracking, { incident_id: $('Frello · Crear incidencia').item.json.id })) }}",
         extra={"onError": "continueErrorOutput"}),
    http("Frello · Deshacer incidencia", "DELETE", "frelloUrl", "incidents", [2200, 420],
         query=[("id", "=eq.{{ $('Frello · Crear incidencia').item.json.id }}")],
         headers=[("Prefer", "return=minimal")], extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar enviado", "PATCH", "farruselUrl", "evento_kardex", [2420, 100],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'ok', error: null, "
              "referencia_externa: $('Frello · Crear incidencia').item.json.id }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar ya existía", "PATCH", "farruselUrl", "evento_kardex", [1540, 60],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'ok', error: null, "
              "referencia_externa: $('Frello · ¿Ya existe?').item.json.id }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar error (incidencia)", "PATCH", "farruselUrl", "evento_kardex", [1760, 480],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'error', "
              "error: 'No se pudo crear la incidencia en Frello: ' + " + ERR + " }) }}",
         extra={"alwaysOutputData": True}),
    http("Farrusel · Marcar error (tarjeta)", "PATCH", "farruselUrl", "evento_kardex", [2420, 420],
         query=[("id", "=eq.{{ " + PREP + ".evento_id }}")], headers=[("Prefer", "return=minimal")],
         body="={{ JSON.stringify({ procesado_en: $now.toISO(), resultado: 'error', "
              "error: 'No se pudo crear la tarjeta del kanban; la incidencia se deshizo: ' + "
              "JSON.stringify($('Frello · Crear tarjeta pedido_a_reclamar').item.json.error ?? '').slice(0, 400) }) }}",
         extra={"alwaysOutputData": True}),
]
bandeja_con = {
    "Cada 5 minutos": {"main": [[a("Config")]]},
    "Prueba manual": {"main": [[a("Config")]]},
    "Config": {"main": [[a("Farrusel · Leer pendientes")]]},
    "Farrusel · Leer pendientes": {"main": [[a("Uno a uno")]]},
    # splitInBatches v3: salida 0 = terminado, salida 1 = siguiente elemento
    "Uno a uno": {"main": [[], [a("Preparar")]]},
    "Preparar": {"main": [[a("Frello · ¿Ya existe?")]]},
    "Frello · ¿Ya existe?": {"main": [[a("¿Ya estaba en Frello?")]]},
    "¿Ya estaba en Frello?": {"main": [[a("Farrusel · Marcar ya existía")], [a("Frello · Crear incidencia")]]},
    "Frello · Crear incidencia": {"main": [[a("¿Es reclamar?")], [a("Farrusel · Marcar error (incidencia)")]]},
    "¿Es reclamar?": {"main": [[a("Frello · Crear tarjeta pedido_a_reclamar")], [a("Farrusel · Marcar enviado")]]},
    "Frello · Crear tarjeta pedido_a_reclamar": {"main": [[a("Farrusel · Marcar enviado")],
                                                          [a("Frello · Deshacer incidencia")]]},
    "Frello · Deshacer incidencia": {"main": [[a("Farrusel · Marcar error (tarjeta)")]]},
    "Farrusel · Marcar enviado": {"main": [[a("Uno a uno")]]},
    "Farrusel · Marcar ya existía": {"main": [[a("Uno a uno")]]},
    "Farrusel · Marcar error (incidencia)": {"main": [[a("Uno a uno")]]},
    "Farrusel · Marcar error (tarjeta)": {"main": [[a("Uno a uno")]]},
}
guardar("frello-bandeja-kardex.workflow.json", {
    "name": "Farrusel → Frello · bandeja del Kardex (cada 5 min)", "nodes": bandeja_nodos,
    "connections": bandeja_con, "settings": {"executionOrder": "v1", "timezone": "Atlantic/Canary"}})

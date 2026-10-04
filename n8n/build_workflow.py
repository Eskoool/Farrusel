"""Genera aviso-resultados.workflow.json (importable en n8n) a partir de los dos ficheros fuente.
Uso: python n8n/build_workflow.py     (desde codigo/)
No lleva ninguna clave: la anon key se pega en n8n tras importar (nodos «Config»)."""
import json, pathlib
aqui = pathlib.Path(__file__).parent
plantilla = (aqui / "informe_template.html").read_text(encoding="utf-8")
codigo = (aqui / "nodo_informe.js").read_text(encoding="utf-8")
codigo = codigo.replace("/*__TEMPLATE__*/''", json.dumps(plantilla, ensure_ascii=False))

URL = "https://sgpbdzphweyeaegzesvb.supabase.co"
def http(nombre, tabla, columnas, pos):
    cfg = "$('Config').first().json"
    return {"parameters": {"url": "={{ " + cfg + ".supabaseUrl }}/rest/v1/" + tabla,
        "sendQuery": True, "queryParameters": {"parameters": [
            {"name": "select", "value": columnas}, {"name": "order", "value": "id.asc"},
            {"name": "limit", "value": "1000"}]},
        "sendHeaders": True, "headerParameters": {"parameters": [
            {"name": "apikey", "value": "={{ " + cfg + ".anonKey }}"},
            {"name": "Authorization", "value": "=Bearer {{ " + cfg + ".anonKey }}"}]},
        "options": {"pagination": {"pagination": {
            "paginationMode": "updateAParameterInEachRequest",
            "parameters": {"parameters": [{"type": "qs", "name": "offset", "value": "={{ $pageCount * 1000 }}"}]},
            "paginationCompleteWhen": "other",
            "completeExpression": "={{ $response.body.length < 1000 }}",
            "limitPagesFetched": True, "maxRequests": 200}}}},
        "id": "http-" + tabla, "name": nombre, "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": pos, "alwaysOutputData": True}

CAMPOS = [("supabaseUrl", URL), ("anonKey", "PEGAR_AQUI_LA_ANON_KEY"), ("destino", "yaredgpz@gmail.com"),
          ("modo", "={{ $('Prueba manual').isExecuted ? 'prueba' : 'programado' }}")]
config = {"parameters": {"assignments": {"assignments": [
            {"id": "cfg-" + k, "name": k, "value": v, "type": "string"} for k, v in CAMPOS]}, "options": {}},
          "id": "cfg", "name": "Config", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [240, 110]}

nodos = [
    {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 24 12 *"}]}},
     "id": "trg-prog", "name": "24 dic 08:00", "type": "n8n-nodes-base.scheduleTrigger",
     "typeVersion": 1.2, "position": [0, 0]},
    {"parameters": {}, "id": "trg-man", "name": "Prueba manual",
     "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 220]},
    config,
    http("Leer uso_evento", "uso_evento", "pantalla,accion,creado_en", [500, 0]),
    http("Leer evento_kardex", "evento_kardex", "tipo,creado_en,procesado_en,resultado", [500, 220]),
    {"parameters": {"mode": "append"}, "id": "merge", "name": "Juntar", "type": "n8n-nodes-base.merge",
     "typeVersion": 3, "position": [760, 110]},
    {"parameters": {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": codigo},
     "id": "code-informe", "name": "Construir informe", "type": "n8n-nodes-base.code",
     "typeVersion": 2, "position": [1000, 110]},
    {"parameters": {"resource": "message", "operation": "send", "sendTo": "={{ $json.destino }}",
                    "subject": "={{ $json.asunto }}", "emailType": "html", "message": "={{ $json.cuerpo }}",
                    "options": {"attachmentsUi": {"attachmentsBinary": [{"property": "informe"}]}}},
     "id": "gmail-envio", "name": "Enviar correo", "type": "n8n-nodes-base.gmail",
     "typeVersion": 2.1, "position": [1240, 110]},
]
def a(nodo, idx=0): return {"node": nodo, "type": "main", "index": idx}
con = {
    "24 dic 08:00": {"main": [[a("Config")]]},
    "Prueba manual": {"main": [[a("Config")]]},
    "Config": {"main": [[a("Leer uso_evento"), a("Leer evento_kardex")]]},
    "Leer uso_evento": {"main": [[a("Juntar", 0)]]},
    "Leer evento_kardex": {"main": [[a("Juntar", 1)]]},
    "Juntar": {"main": [[a("Construir informe")]]},
    "Construir informe": {"main": [[a("Enviar correo")]]},
}
wf = {"name": "Farrusel · aviso de resultados (7 días antes del 31-12-2026)", "nodes": nodos,
      "connections": con, "settings": {"executionOrder": "v1", "timezone": "Atlantic/Canary"}}
salida = aqui / "aviso-resultados.workflow.json"
salida.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK", salida, salida.stat().st_size, "bytes")

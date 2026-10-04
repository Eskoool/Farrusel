"""Genera aviso-resultados.workflow.json (importable en n8n) a partir de los dos ficheros fuente.
Uso: python n8n/build_workflow.py     (desde codigo/)
No lleva ninguna clave: la anon key se pega en n8n tras importar (nodos «Config»)."""
import json, pathlib
aqui = pathlib.Path(__file__).parent
plantilla = (aqui / "informe_template.html").read_text(encoding="utf-8")
codigo = (aqui / "nodo_informe.js").read_text(encoding="utf-8")
codigo = codigo.replace("/*__TEMPLATE__*/''", json.dumps(plantilla, ensure_ascii=False))

URL = "https://sgpbdzphweyeaegzesvb.supabase.co"
def config(nombre, modo, pos):
    campos = [("supabaseUrl", URL), ("anonKey", "PEGAR_AQUI_LA_ANON_KEY"),
              ("destino", "yaredgpz@gmail.com"), ("modo", modo)]
    return {"parameters": {"assignments": {"assignments": [
                {"id": f"{modo}-{k}", "name": k, "value": v, "type": "string"} for k, v in campos]},
                "options": {}},
            "id": f"cfg-{modo}", "name": nombre, "type": "n8n-nodes-base.set",
            "typeVersion": 3.4, "position": pos}

nodos = [
    {"parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 24 12 *"}]}},
     "id": "trg-prog", "name": "24 dic 08:00", "type": "n8n-nodes-base.scheduleTrigger",
     "typeVersion": 1.2, "position": [0, 0]},
    {"parameters": {}, "id": "trg-man", "name": "Prueba manual",
     "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 220]},
    config("Config programado", "programado", [240, 0]),
    config("Config prueba", "prueba", [240, 220]),
    {"parameters": {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": codigo},
     "id": "code-informe", "name": "Construir informe", "type": "n8n-nodes-base.code",
     "typeVersion": 2, "position": [500, 110]},
    {"parameters": {"resource": "message", "operation": "send", "sendTo": "={{ $json.destino }}",
                    "subject": "={{ $json.asunto }}", "emailType": "html", "message": "={{ $json.cuerpo }}",
                    "options": {"attachmentsUi": {"attachmentsBinary": [{"property": "informe"}]}}},
     "id": "gmail-envio", "name": "Enviar correo", "type": "n8n-nodes-base.gmail",
     "typeVersion": 2.1, "position": [760, 110]},
]
con = {
    "24 dic 08:00": {"main": [[{"node": "Config programado", "type": "main", "index": 0}]]},
    "Prueba manual": {"main": [[{"node": "Config prueba", "type": "main", "index": 0}]]},
    "Config programado": {"main": [[{"node": "Construir informe", "type": "main", "index": 0}]]},
    "Config prueba": {"main": [[{"node": "Construir informe", "type": "main", "index": 0}]]},
    "Construir informe": {"main": [[{"node": "Enviar correo", "type": "main", "index": 0}]]},
}
wf = {"name": "Farrusel · aviso de resultados (7 días antes del 31-12-2026)", "nodes": nodos,
      "connections": con, "settings": {"executionOrder": "v1", "timezone": "Atlantic/Canary"}}
salida = aqui / "aviso-resultados.workflow.json"
salida.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK", salida, salida.stat().st_size, "bytes")

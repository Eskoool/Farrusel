---
description: Genera la instrucción pegable para arrancar el proyecto o una fase concreta
---

Escribe el prompt que el usuario va a copiar y pegar en otra sesión —de Claude Code o de Lovable— para construir.

**1. Lee `PRD.md` entero.** Un prompt escrito desde el índice sale genérico y no sirve para nada. Necesitas los requisitos, sus criterios de aceptación, las restricciones de §10 y el plan de §11.

**2. Averigua el destino.** ¿El arranque del proyecto, o una fase concreta de §11? Si el usuario invocó `/prompt 3`, es la fase 3. El motor sale de §0 de metadatos: no lo repreguntes si ya está fijado.

**3. Consulta `references/adaptadores.md` de la skill `forja-prd`.** Ese fichero vive dentro de la skill, no en este proyecto: no lo busques aquí. Contiene los cinco bloques obligatorios y el dialecto de cada motor.

**4. Escribe el prompt** con sus cinco bloques —rol, contexto, tareas exactas, restricciones, formato de salida— y sus dos reglas duras:
- **No pide código en el primer turno.** Explorar, resumir, planear, devolver dudas, esperar OK.
- **Es autocontenido.** Quien lo pega abre una sesión limpia. Prohibido "como comentamos", "el fichero de antes", "ya sabes cuál". Si hace falta el PRD, el prompt dice dónde pegarlo.

**5. Entrégalo en un único bloque de código, solo el prompt.** Sin comentarios intercalados, sin notas tuyas dentro. Se va a copiar entero: lo que metas dentro viaja con él.

**6. Después del bloque**, y solo después, di en dos líneas qué le falta al PRD para que ese prompt fuera mejor. No rellenes los huecos por tu cuenta: si son relevantes, pasa por `/cambio`.

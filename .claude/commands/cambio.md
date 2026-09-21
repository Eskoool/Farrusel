---
description: Control de cambios sobre el PRD cuando el alcance se mueve
---

Ha aparecido algo que el PRD no contempla. Este es el único camino legítimo para incorporarlo.

**1. Nombra la desviación.**
- Qué se está pidiendo.
- Qué dice el PRD hoy sobre eso, con la sección citada.
- En qué se contradicen, o qué silencio hay.

**2. Evalúa el impacto** sobre: alcance de la v1, modelo de datos, seguridad y datos personales, coste, y fases pendientes. Si toca el modelo de datos o la seguridad, dilo en primer lugar.

**3. Propón tres salidas con recomendación razonada:**
- **Incorporar a la v1:** qué secciones del PRD hay que reescribir y cuánto trabajo añade.
- **Aplazar al roadmap:** qué se pierde por esperar.
- **Rechazar:** por qué no encaja con el problema que el producto resuelve.

**4. Espera decisión.** No escribas código de la funcionalidad antes de tenerla.

**5. Si se incorpora, actualiza en este orden:**
1. La sección afectada de `PRD.md`.
2. La tabla del anexo Registro de cambios.
3. `MEMORIA.md`, en decisiones vigentes.
4. `LOG.md`, entrada con fecha.

Los cuatro. Un cambio que solo llega al código es el origen del PRD zombi que este sistema existe para evitar.

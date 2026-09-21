---
description: Pasa la rúbrica de Forja PRD al PRD vigente y al estado real del código
---

Audita el proyecto contra su propio documento.

**1. Lee `PRD.md` entero** antes de emitir ningún juicio.

**2. Aplica la rúbrica de veintiocho puntos** de la skill `forja-prd`: carga la skill y lee su `references/auditoria.md`. Ese fichero vive dentro de la skill, no en este proyecto: no lo busques aquí. Bloques: alcance, especificación, técnica, seguridad, ejecución e instrucciones ejecutables. Cada punto: cumple, parcial o ausente, con severidad.

**3. Contrasta con la realidad.** Esta parte es la que un PRD no puede hacer solo:
- Funcionalidades que existen en el código y no en el PRD.
- Funcionalidades del PRD que nadie construyó y nadie declaró aplazadas.
- Decisiones de `MEMORIA.md` que contradicen al PRD.

**4. Devuelve el informe** ordenado por severidad, con evidencia concreta en cada hallazgo. Cita líneas o archivos. Un hallazgo sin evidencia es una opinión.

**5. Separa hechos de interpretaciones.** "No hay criterios de aceptación en el módulo X" es un hecho. "Esto va a dar problemas en producción" es una interpretación, y se etiqueta como tal.

**6. Ofrece reescribir** lo que falla. No lo reescribas sin permiso.

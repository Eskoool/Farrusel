---
description: Vuelca el estado de la sesión a MEMORIA.md y LOG.md
---

Cierra la sesión actual dejando rastro. Dos archivos, dos propósitos distintos.

**1. Actualiza `MEMORIA.md`** (el presente):
- Fase actual y en qué punto está.
- Decisiones nuevas tomadas hoy, una línea cada una con su porqué.
- Deuda técnica que hayamos abierto.
- Bloqueos vivos.
- Siguiente paso concreto.

Si el archivo supera 200 líneas, compacta: funde decisiones relacionadas, borra lo que ya no está vigente y baja lo histórico a `LOG.md`. No dejes que crezca sin límite, porque un MEMORIA.md largo deja de leerse.

**2. Añade una entrada a `LOG.md`** (el historial), al final, sin tocar nada anterior:

```
## AAAA-MM-DD · Sesión N · [título]
**Hecho:**
**Decidido:**
**Desviaciones del PRD:** ninguna | [cuál y cómo se resolvió]
**Pendiente:**
```

Sé específico en desviaciones. "Pequeños ajustes" no sirve de nada dentro de tres meses.

**3. Si algo hecho hoy no está en el PRD**, dilo ahora y propón pasar por `/cambio`. No lo dejes solo en el log: un log no es un documento de producto.

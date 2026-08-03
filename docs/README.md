# Documentación de Champions HUD

Esta carpeta es la fuente de verdad del proyecto. Antes de diseñar o implementar algo nuevo, la respuesta a "¿esto pertenece al producto?" debería poder encontrarse acá adentro.

## Índice

| Documento | Contenido |
|---|---|
| [`vision.md`](./vision.md) | Qué es Champions HUD, qué problema resuelve, qué NO es, filosofía y principios de diseño. Léelo primero. |
| [`product.md`](./product.md) | Personas, flujo completo de batalla, capas de interfaz (Glance/Peek/Deep), sistema de confianza, anti-patrones. |
| [`architecture.md`](./architecture.md) | Arquitectura lógica: motor (engine core) + clientes, capas internas, modelo de datos, persistencia offline-first, pipeline de datos de meta (Limitless/Pikalytics), puntos de extensión reservados (licencias, ads). |
| [`inference.md`](./inference.md) | Modelo de conocimiento: event log, espacio de hipótesis, reglas de inferencia, cadena de evidencia, motor de prioridad. Es el detalle técnico de la Fase 2. |
| [`decisions.md`](./decisions.md) | Registro de decisiones (estilo ADR). Cuando dos documentos parecen contradecirse, este es el que gana. |
| [`audit.md`](./audit.md) | Auditoría técnica del estado del código: qué funciona, qué está roto, deuda técnica. |
| [`roadmap.md`](./roadmap.md) | Fases de desarrollo, en orden, con criterios de salida de cada una. |
| [`future.md`](./future.md) | Ideas deliberadamente pospuestas (Premium, licencias, ads, sync, multi-cliente). No condicionan la arquitectura actual, pero están documentadas para no perderlas ni improvisarlas. |

## Cómo usar esta documentación

**Antes de proponer o implementar una feature nueva**, verificá en este orden:
1. ¿Está alineada con la filosofía de [`vision.md`](./vision.md)? (en particular: el copiloto describe la posición y jerarquiza información, pero nunca elige la jugada — ver `decisions.md` #1, #19 y #21, que refinan esa línea en ese orden)
2. ¿Contradice alguna decisión ya tomada en [`decisions.md`](./decisions.md)?
3. ¿Dónde vive en la arquitectura de [`architecture.md`](./architecture.md)? Si no encaja en ninguna capa existente, es señal de alarma, no motivo para forzarla.
4. ¿En qué fase del [`roadmap.md`](./roadmap.md) corresponde? Verificá el estado actual ahí — no asumas que sigue siendo la misma fase que la última vez que se leyó este documento.

**Cuando una decisión tenga impacto futuro** (arquitectura, dominio, persistencia o APIs), la regla del proyecto es: **preferir la solución escalable aunque hoy se use de forma simple**. Eso no significa sobre-construir — significa no cerrar puertas que cuesta reabrir (ver `architecture.md`, sección de puntos de extensión).

## Estado actual

El proyecto completó la **Fase 0 — Estabilización** el 2026-07-31 y está en **Fase 1 — Reducir la fricción crítica de uso**, con todo el código escrito y seis vueltas de corrección contra uso real; lo único que falta para cerrarla es jugar un combate completo sin bugs nuevos. La **Fase 2** ya tiene su diseño cerrado ([`inference.md`](./inference.md)) y un plan por sprints en [`roadmap.md`](./roadmap.md), más su primer hito de investigación ya hecho.

`validate_data.py` y `tests/run.js` (65 casos) protegen contra que los bugs resueltos se reintroduzcan en silencio. La deuda técnica viva está priorizada en [`audit.md`](./audit.md) §7 — hoy la más visible en uso es la cobertura incompleta de piedras mega (§5.10).

## Convención de idioma

- Documentación y comunicación con Angel: español rioplatense.
- Identificadores en el dominio y el código (especies, movimientos, habilidades, ítems): slugs canónicos en inglés. Ver [`decisions.md`](./decisions.md) #7.
- Texto visible al usuario final: pasa siempre por la capa de presentación/i18n, nunca hardcodeado.

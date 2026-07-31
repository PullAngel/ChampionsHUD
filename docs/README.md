# Documentación de Champions HUD

Esta carpeta es la fuente de verdad del proyecto. Antes de diseñar o implementar algo nuevo, la respuesta a "¿esto pertenece al producto?" debería poder encontrarse acá adentro.

## Índice

| Documento | Contenido |
|---|---|
| [`vision.md`](./vision.md) | Qué es Champions HUD, qué problema resuelve, qué NO es, filosofía y principios de diseño. Léelo primero. |
| [`product.md`](./product.md) | Personas, flujo completo de batalla, capas de interfaz (Glance/Peek/Deep), sistema de confianza, anti-patrones. |
| [`architecture.md`](./architecture.md) | Arquitectura lógica: motor (engine core) + clientes, capas internas, modelo de datos, persistencia offline-first, pipeline de datos de meta (Limitless/Pikalytics), puntos de extensión reservados (licencias, ads). |
| [`decisions.md`](./decisions.md) | Registro de decisiones (estilo ADR). Cuando dos documentos parecen contradecirse, este es el que gana. |
| [`audit.md`](./audit.md) | Auditoría técnica del estado del código: qué funciona, qué está roto, deuda técnica. |
| [`roadmap.md`](./roadmap.md) | Fases de desarrollo, en orden, con criterios de salida de cada una. |
| [`future.md`](./future.md) | Ideas deliberadamente pospuestas (Premium, licencias, ads, sync, multi-cliente). No condicionan la arquitectura actual, pero están documentadas para no perderlas ni improvisarlas. |

## Cómo usar esta documentación

**Antes de proponer o implementar una feature nueva**, verificá en este orden:
1. ¿Está alineada con la filosofía de [`vision.md`](./vision.md)? (en particular: el copiloto informa, nunca decide por el jugador)
2. ¿Contradice alguna decisión ya tomada en [`decisions.md`](./decisions.md)?
3. ¿Dónde vive en la arquitectura de [`architecture.md`](./architecture.md)? Si no encaja en ninguna capa existente, es señal de alarma, no motivo para forzarla.
4. ¿En qué fase del [`roadmap.md`](./roadmap.md) corresponde? Si la fase actual es Fase 0 (estabilización), la respuesta por defecto a "¿lo hacemos ahora?" es no.

**Cuando una decisión tenga impacto futuro** (arquitectura, dominio, persistencia o APIs), la regla del proyecto es: **preferir la solución escalable aunque hoy se use de forma simple**. Eso no significa sobre-construir — significa no cerrar puertas que cuesta reabrir (ver `architecture.md`, sección de puntos de extensión).

## Estado actual

El proyecto está en **Fase 0 — Estabilización** (ver [`roadmap.md`](./roadmap.md)). Esto significa: no se agregan features nuevas hasta resolver los hallazgos de [`audit.md`](./audit.md). El roadmap incluye un checklist accionable, en orden de dependencia, pensado para ejecutarse con Claude Code — es el punto de partida recomendado para retomar el desarrollo.

## Convención de idioma

- Documentación y comunicación con Angel: español rioplatense.
- Identificadores en el dominio y el código (especies, movimientos, habilidades, ítems): slugs canónicos en inglés. Ver [`decisions.md`](./decisions.md) #7.
- Texto visible al usuario final: pasa siempre por la capa de presentación/i18n, nunca hardcodeado.

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
| [`calc.md`](./calc.md) | Análisis y diseño de la pestaña CALC: auditoría de la calculadora de Showdown, principios para la versión táctil de Champions HUD, qué se implementó y qué queda. |

## Cómo usar esta documentación

**Antes de proponer o implementar una feature nueva**, verificá en este orden:
1. ¿Está alineada con la filosofía de [`vision.md`](./vision.md)? (en particular: el copiloto describe la posición y jerarquiza información, pero nunca elige la jugada — ver `decisions.md` #1, #19 y #21, que refinan esa línea en ese orden)
2. ¿Contradice alguna decisión ya tomada en [`decisions.md`](./decisions.md)?
3. ¿Dónde vive en la arquitectura de [`architecture.md`](./architecture.md)? Si no encaja en ninguna capa existente, es señal de alarma, no motivo para forzarla.
4. ¿En qué fase del [`roadmap.md`](./roadmap.md) corresponde? Verificá el estado actual ahí — no asumas que sigue siendo la misma fase que la última vez que se leyó este documento.

**Cuando una decisión tenga impacto futuro** (arquitectura, dominio, persistencia o APIs), la regla del proyecto es: **preferir la solución escalable aunque hoy se use de forma simple**. Eso no significa sobre-construir — significa no cerrar puertas que cuesta reabrir (ver `architecture.md`, sección de puntos de extensión).

## Estado actual

**Actualizado 2026-08-11.** Las tres primeras fases están cerradas: **Fase 0 — Estabilización** (2026-07-31), **Fase 1 — Fricción crítica de uso** (2026-08-03, confirmada por Angel en dispositivo real) y **Fase 2 — Datos de meta reales y motor de inferencia** (2026-08-04). La **Fase 3** (formalizar la separación Motor/Cliente) tiene su criterio de salida cumplido de hecho (medido 2026-08-06) y su refactor estructural hecho (adaptador `IO`, 2026-08-11, ver `roadmap.md`) — sin verificar todavía en dispositivo real, mismo límite de siempre. De la **Fase 4** (memoria y análisis post-combate) se hizo la mitad que ya tenía arquitectura cerrada — arrastrar lo confirmado del rival entre juegos de un Bo3 (2026-08-11) —; el resumen post-partida sigue sin empezar, es una conversación de producto pendiente. Angel planea a futuro un **fork de diseño** (mismo Motor, Presentación nueva desde cero, `decisions.md` #26) — no arrancado, pero ya documentado como punto de extensión en `architecture.md` §7.4, y es la motivación detrás del adaptador `IO`.

Entre medio, el trabajo no está siguiendo la numeración de fases: desde el cierre de Fase 2 el proyecto viene atendiendo pedidos y reportes de Angel contra uso real (rediseño de comunicación, revisión de OCR, vista de velocidad detallada, calculadora). Todo eso está documentado en [`roadmap.md`](./roadmap.md) bajo "Post-Fase 2", no como sprints numerados — buscar ahí antes de asumir en qué anda el proyecto.

**Cómo se corren los tests: `node tests/run.js`, y nada más.** Esa única orden ejecuta los 224 casos de JS, `validate_data.py`, y los 36 casos de Python de los generadores (`tests/test_build_meta*.py`) — estos últimos existían desde la Fase 2 y **nadie los estaba corriendo** hasta el 2026-08-06. Si se agrega un archivo de tests nuevo, engancharlo ahí: una red de seguridad que hay que acordarse de tirar a mano no es una red.

`validate_data.py` y `tests/run.js` protegen contra que los bugs resueltos se reintroduzcan en silencio. La deuda técnica viva está priorizada en [`audit.md`](./audit.md) §7. La que era #1 —**la naturaleza no se podía capturar**— se resolvió el 2026-08-06 deduciéndola por aritmética en vez de por análisis de imagen (§5.13). Hoy la de mayor impacto es **el recorte del sprite en team preview**, que necesita capturas reales y un ciclo de compilación de Kotlin.

## Convención de idioma

- Documentación y comunicación con Angel: español rioplatense.
- Identificadores en el dominio y el código (especies, movimientos, habilidades, ítems): slugs canónicos en inglés. Ver [`decisions.md`](./decisions.md) #7.
- Texto visible al usuario final: pasa siempre por la capa de presentación/i18n, nunca hardcodeado.

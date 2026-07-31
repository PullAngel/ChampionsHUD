# CLAUDE.md

Contexto de proyecto para Claude Code. Este archivo es un puntero, no un resumen — la fuente de verdad vive en `docs/`. Si algo acá contradice `docs/`, `docs/` gana.

## Qué es este proyecto

Champions HUD es un overlay Android personal/comunitario para Pokémon Champions (VGC) que actúa como copiloto competitivo: lee el equipo rival, mantiene memoria del combate, calcula daño y velocidad, y elimina hipótesis incompatibles a medida que aparece evidencia. **Nunca recomienda una jugada** — informa, el jugador decide. Desarrollo con asistencia de IA; lenguaje de comunicación con el autor: español rioplatense. Identificadores de dominio en el código: inglés (slugs canónicos).

## Antes de escribir una sola línea de código

1. Leé `docs/README.md` para orientarte.
2. Verificá que lo que vas a hacer esté alineado con `docs/vision.md` (en particular: el copiloto informa, nunca decide; no se duplica información que el juego ya muestra).
3. Revisá `docs/decisions.md` — si la feature contradice una decisión ya tomada, no se implementa sin antes discutirlo explícitamente con Angel y, si corresponde, agregar una nueva entrada al registro.
4. Confirmá en `docs/roadmap.md` que la fase actual del proyecto admite esto. **Regla por defecto: si el proyecto está en Fase 0 (estabilización), no se agregan features nuevas.** Verificá el estado actual en `docs/roadmap.md`, no asumas que sigue siendo Fase 0.
5. Ubicá dónde vive esto en `docs/architecture.md`. Si no encaja en ninguna capa existente (Percepción / Event Log / Motor de Estado / Motor de Inferencia / Motor de Cálculo / Motor de Insights / Presentación), es señal de que hay que repensarlo, no de forzarlo.

## Principios no negociables

- **El copiloto nunca recomienda una jugada.** Ningún ranking de movimientos, ninguna sugerencia de "la mejor opción". Solo hechos, estimaciones con su evidencia, y consecuencias de una acción hipotética si el usuario la pide explícitamente.
- **No duplicar lo que el juego ya muestra.** Contadores de Tailwind/clima/pantallas ya están en pantalla nativa del juego; el HUD solo agrega si aporta algo que el juego no da.
- **Fallo ruidoso, nunca silencioso.** Ante datos inconsistentes o ausentes, reportar explícitamente. Nunca degradar en silencio un resultado y presentarlo como confiable — este es el patrón de bug más repetido en la historia del proyecto (ver `docs/audit.md`).
- **Motor agnóstico de plataforma.** La lógica de dominio no depende de Android/Kotlin. El overlay Android es el cliente principal, no el motor mismo.
- **Dominio sin lógica de licencia ni de publicidad.** Esas cosas, si existen, viven en la capa de Presentación. El Motor no evalúa flags de plan ni de monetización, nunca.
- **Offline-first real.** Ningún módulo del pipeline de combate puede depender de una llamada de red para responder dentro de un combate.
- **Identificadores en inglés, idioma solo en presentación.** Nunca comparar por nombre traducido en lógica de dominio.
- **Event log inmutable como fuente única de verdad.** Estado, creencias y vistas se derivan; nada se edita retroactivamente.

## Cuando una decisión tenga impacto futuro

Arquitectura, dominio, persistencia o formato de datos/APIs: priorizar la solución escalable aunque hoy se use de forma simple. Esto no es licencia para sobre-construir — es evitar decisiones baratas hoy que cuesten una reescritura después. Los puntos de extensión ya identificados (licencias, publicidad, multi-cliente) están documentados en `docs/architecture.md` §7 y no requieren implementación, solo no bloquearse.

## Si hay ambigüedad sobre la visión del producto

Preguntale a Angel antes de asumir. No se resuelve una ambigüedad de producto con la interpretación que sea técnicamente más cómoda de implementar.

## Estado del código base

Ver `docs/audit.md` para el detalle completo. En resumen: la lógica de combate vive en `hud.html` (JS plano, sin módulos todavía), el cascarón Android en Kotlin (`MainActivity`, `OverlayService`, `ScreenCapture`, `SpriteMatcher`, `ReconnectActivity`, `Storage`). Hay bugs confirmados pendientes de la Fase 0 — no asumir que el comportamiento actual es el deseado sin chequear `docs/audit.md`.

## Documentación

| Archivo | Para qué sirve |
|---|---|
| `docs/README.md` | Índice y cómo navegar el resto |
| `docs/vision.md` | Filosofía y principios — leer primero |
| `docs/product.md` | UX, flujo de batalla, personas |
| `docs/architecture.md` | Diseño técnico y puntos de extensión |
| `docs/decisions.md` | Por qué las cosas son como son (ADR) |
| `docs/audit.md` | Estado real del código |
| `docs/roadmap.md` | En qué fase estamos y qué sigue |
| `docs/future.md` | Lo que se pospuso a propósito |

Si actualizás alguno de estos documentos como parte de un cambio, hacelo en el mismo commit que el código al que corresponde — esta documentación es la que reemplaza la memoria de sesiones de chat pasadas.

# Roadmap

Fases en orden. No se pasa a la siguiente sin cumplir el criterio de salida de la actual — esto es deliberado: el proyecto ya pagó el costo de construir features nuevas sobre una base con deuda técnica (ver `audit.md`).

## Alcance realista de una sesión corta (horas)

Para que una sesión con Claude Code termine con una app **completamente funcional**, sin bugs conocidos, el objetivo alcanzable en horas es **cerrar la Fase 0 entera**: son correcciones puntuales y acotadas, no diseño nuevo. Los checklists de cada hallazgo abajo están ordenados por dependencia — seguirlos en orden evita retrabajo.

El pipeline de datos de meta real (Fase 2) es un trabajo más grande (inspeccionar un esquema de API no documentado, escribir y probar un scraper con manejo de rate limits, construir el índice de combinaciones). Se incluye igual en el roadmap con el primer hito accionable marcado, para que si sobra tiempo en la sesión se pueda arrancar sin rediseñar nada — pero no es razonable esperar terminarlo completo en la misma sesión que la Fase 0.

## Fase 0 — Estabilización (fase actual)

Sin features nuevas. Objetivo: que la auditoría, si se re-ejecutara hoy, no encuentre nada en rojo. Cada ítem referencia el hallazgo correspondiente en `audit.md` y su verificación.

**Actualizado 2026-07-31 tras re-auditoría completa** (ver `audit.md` §10, registro de cambios). El ítem que antes ocupaba el puesto 1 (mismatch `predict()`/`vPre()`) se retiró: ya no reproduce en el código actual, ver `audit.md` §5.1.

**Actualizado de nuevo el mismo día tras la decisión #17** (`decisions.md`): el HUD tiene selector de idioma explícito (inglés/español al menos), no español fijo. Esto fusiona lo que eran los ítems 1 y 5 por separado — no tiene sentido migrar a slugs canónicos sin resolver a la vez cómo se traduce lo que se muestra.

1. ~~**Unificar a slugs canónicos en inglés + construir la capa i18n con selector de idioma**~~ — **Hecho, 2026-07-31.** `ABIL_I18N`/`abilName()` (generado desde PokeAPI, no a mano) cubren ahora lo que `mvName`/`itName` ya cubrían para movimientos/ítems. `calc()`, `ROLE_AB`, `loadDex()` y la UI comparan por slug. Ver `audit.md` §5.2/§5.5. Pendiente aparte, no bloqueante: el texto de la interfaz (labels, mensajes) sigue en español fijo — el selector traduce datos del juego, no el chrome de la UI.
2. ~~**Regenerar `meta.json`**~~ — **Hecho, 2026-07-31.** Podadas 14 especies no legales, corregidos ítems/habilidades inválidos, sumadas 10 especies con evidencia real de capturas de Angel. Ver `audit.md` §5.3.
3. **Resolver el orden de dependencia en `hud.html`** (`audit.md` §5.4). Mover `DEX COMPLETO` antes de `PREDICCIÓN`, o extraer ambas a módulos con `import`/`export` si ya se aborda el punto 4 en el mismo pase.
4. **Partir `hud.html` en módulos** con contratos documentados (`@typedef` mínimo, `architecture.md` §8) entre capas — Percepción, Estado, Inferencia, Cálculo, Insights, Presentación. Resuelve de raíz el punto 3 y hace detectable en el futuro cualquier mismatch de forma entre funciones.
5. **Escribir el script de validación de datos en build** (`architecture.md` §6): verifica que `meta.json`, `dex.json`, `sprite_index.json` y las tablas embebidas son mutuamente consistentes. Ya puede apoyarse en el trabajo de los puntos 1-2 (slugs + meta.json corregido) y sirve para detectar automáticamente una futura desincronización.
6. **Dejar una suite de pruebas mínima en el repo** (no scripts ad-hoc descartables, `audit.md` §5.7): como mínimo, un caso para el motor de daño con una habilidad clave en los dos idiomas, y el validador del punto 5 corriendo como test.
7. **Investigar qué reemplazó (si algo lo hizo) a la reconexión automática de permiso de captura** (`audit.md` §5.8, hallazgo nuevo). `ReconnectActivity` ya no existe en el repo; hace falta trazar `dead` en `ScreenCapture.kt`/`OverlayService.kt` para confirmar si la app se recupera sola de una revocación de permiso en Android 14+ o si quedó sin ese mecanismo. Decidir severidad recién después de esta investigación.
8. **Limpieza menor:** quitar la dependencia declarada sin uso `kotlinx-coroutines-android` del `build.gradle.kts` si no se va a usar, o empezar a usarla si simplifica el manejo de hilos existente con `HandlerThread`/`Handler` (`audit.md` §5.6) — es la más baja prioridad de la fase, hacerla solo si sobra tiempo.

**Criterio de salida:** los hallazgos de `audit.md` §5 están resueltos y hay pruebas que impedirían que se reintroduzcan en silencio.

## Fase 1 — Reducir la fricción crítica de uso

- Carga del equipo propio: lectura automática (OCR de la pantalla de detalles) o, si el costo no lo justifica todavía, importación por texto en menos de 30 segundos. Esta es la fricción #1 declarada del producto y precede en prioridad a cualquier mejora de inferencia.
- Corrección de reconocimiento en 2 taps, sin teclado, en cualquier punto del flujo.
- Rediseño de Presentación hacia una vista contextual única (según fase del combate) en vez de pestañas fijas, alineado con `product.md`.
- Ajustar Glance para dejar de mostrar contadores de campo que el juego ya muestra (decisión #2), y priorizar orden de velocidad + alerta relevante.

**Criterio de salida:** un combate completo se juega con el presupuesto de interacción manual definido en `product.md`, salvo fallos puntuales de reconocimiento.

## Fase 2 — Datos de meta reales y motor de inferencia por eliminación

Diseño completo en `architecture.md` §10. No es una fase de una sola sesión; se lista en pasos para poder retomarla sin releer todo el diseño cada vez.

**Primer hito accionable (el que tiene sentido arrancar si sobra tiempo tras la Fase 0):**
1. Resolver el ID de formato de la Reg M-B vigente con `GET /games` contra la API de Limitless.
2. Traer standings de un torneo real (`GET /tournaments?game=VGC&format=<id>` → `GET /tournaments/{id}/standings`) e inspeccionar el subesquema real del campo `decklist` — no está documentado formalmente, hay que verlo en una respuesta real antes de fijar el modelo de datos.
3. Con eso, decidir el modelo de datos exacto de `MetaSnapshot` (ya con el subesquema real en mano, no el supuesto).

**Resto de la fase (sesiones siguientes):**
- Script generador completo: descarga con manejo de rate limits, enriquecimiento opcional con Pikalytics, filtrado por regulación, construcción del índice de combinaciones parciales (`architecture.md` §10.3-10.4).
- Reemplazar el `meta.json` estimado a mano por el artefacto generado, versionado por reglamento (decisión #14).
- Motor de inferencia rediseñado como eliminación de hipótesis sobre una base de sets conocidos (no ajuste estadístico continuo sobre un prior débil) — más simple, más explicable, y ahora sí alimentado con datos reales.
- Sistema de confianza en tres niveles (Confirmado / Deducido / Estimado por meta) integrado en Peek y Deep.
- Modo de importación manual de equipo como funcionalidad de primera clase, no como contingencia (decisión #15).

**Criterio de salida:** la pestaña de predicción de equipo deja de depender de un archivo estimado a mano y cada estimación es explicable con su cadena de evidencia.

## Fase 3 — Formalizar la separación Motor / Cliente

- Extraer explícitamente el motor de dominio como módulo independiente de Android/Kotlin (decisión #10), sin que esto implique construir todavía un segundo cliente — es preparar el terreno, no anticipar trabajo que no hace falta hoy.
- Dejar reservadas (sin implementar) las interfaces de entitlements (decisión #5) y de espacio de publicidad (decisión #4) en la capa de Presentación, verificando que ningún módulo de dominio las referencia.

**Criterio de salida:** el motor puede ejecutarse y probarse sin ningún dependencia de Android.

## Fase 4 — Memoria y análisis post-combate

- Resumen post-partida construido sobre el event log: qué acertó y qué falló el modelo, qué información se reveló de más.
- Modo serie (Bo3) con persistencia de creencias confirmadas entre juegos (decisión #9).
- Soporte para Open Team Sheets como un tipo de evento más (colapsa hipótesis a certeza desde el inicio del combate) — sin requerir ningún cambio en el motor de inferencia.

**Criterio de salida:** un jugador puede repasar una serie completa y entender qué patrones propios está repitiendo.

## Fase 5 en adelante — Ver `future.md`

Todo lo que depende de una decisión de negocio no tomada todavía (licencias, publicidad activa, sincronización multi-dispositivo, análisis de hábitos a largo plazo, multi-idioma completo, clientes en otras plataformas) vive documentado en [`future.md`](./future.md) y se aborda cuando corresponda, sin condicionar las fases anteriores.

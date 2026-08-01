# Roadmap

Fases en orden. No se pasa a la siguiente sin cumplir el criterio de salida de la actual — esto es deliberado: el proyecto ya pagó el costo de construir features nuevas sobre una base con deuda técnica (ver `audit.md`).

## Alcance realista de una sesión corta (horas)

Para que una sesión con Claude Code termine con una app **completamente funcional**, sin bugs conocidos, el objetivo alcanzable en horas es **cerrar la Fase 0 entera**: son correcciones puntuales y acotadas, no diseño nuevo. Los checklists de cada hallazgo abajo están ordenados por dependencia — seguirlos en orden evita retrabajo.

El pipeline de datos de meta real (Fase 2) es un trabajo más grande (inspeccionar un esquema de API no documentado, escribir y probar un scraper con manejo de rate limits, construir el índice de combinaciones). Se incluye igual en el roadmap con el primer hito accionable marcado, para que si sobra tiempo en la sesión se pueda arrancar sin rediseñar nada — pero no es razonable esperar terminarlo completo en la misma sesión que la Fase 0.

## Fase 0 — Estabilización (completa, 2026-07-31)

Sin features nuevas. Objetivo: que la auditoría, si se re-ejecutara hoy, no encuentre nada en rojo. Cada ítem referencia el hallazgo correspondiente en `audit.md` y su verificación.

**Actualizado 2026-07-31 tras re-auditoría completa** (ver `audit.md` §10, registro de cambios). El ítem que antes ocupaba el puesto 1 (mismatch `predict()`/`vPre()`) se retiró: ya no reproduce en el código actual, ver `audit.md` §5.1.

**Actualizado de nuevo el mismo día tras la decisión #17** (`decisions.md`): el HUD tiene selector de idioma explícito (inglés/español al menos), no español fijo. Esto fusiona lo que eran los ítems 1 y 5 por separado — no tiene sentido migrar a slugs canónicos sin resolver a la vez cómo se traduce lo que se muestra.

1. ~~**Unificar a slugs canónicos en inglés + construir la capa i18n con selector de idioma**~~ — **Hecho, 2026-07-31.** `ABIL_I18N`/`abilName()` (generado desde PokeAPI, no a mano) cubren ahora lo que `mvName`/`itName` ya cubrían para movimientos/ítems. `calc()`, `ROLE_AB`, `loadDex()` y la UI comparan por slug. Ver `audit.md` §5.2/§5.5. Pendiente aparte, no bloqueante: el texto de la interfaz (labels, mensajes) sigue en español fijo — el selector traduce datos del juego, no el chrome de la UI.
2. ~~**Regenerar `meta.json`**~~ — **Hecho, 2026-07-31.** Podadas 14 especies no legales, corregidos ítems/habilidades inválidos, sumadas 10 especies con evidencia real de capturas de Angel. Ver `audit.md` §5.3.
3. ~~**Resolver el orden de dependencia en `hud.html`**~~ — **Hecho, 2026-07-31.** `DEX COMPLETO` (con `loadDex()`/`learnable()`) movido antes de `PREDICCIÓN`, que los usa. Ver `audit.md` §5.4.
4. ~~**Partir `hud.html` en módulos**~~ — **Decidido que NO se hace, 2026-07-31 (decisión #18).** Investigado a fondo: `OverlayService.kt` carga el HUD vía `file:///android_asset/` sin `allowFileAccessFromFileURLs`, así que módulos ES probablemente no carguen en el WebView real. La alternativa sin ese riesgo (archivos separados + build que concatena, como `build_dex.py`) se le presentó a Angel explícitamente — la rechazó porque agrega fricción al ciclo editar-probar-ver que hoy es la principal ventaja del proyecto. `hud.html` se mantiene como archivo único a propósito, no por falta de tiempo. Ver `decisions.md` #18.
5. ~~**Escribir el script de validación de datos en build**~~ — **Hecho, 2026-07-31.** `validate_data.py` en la raíz del repo — cruza `meta.json`, `dex.json`, `sprite_index.json` y las tablas embebidas de `hud.html`. Probado inyectando un error a propósito. Ver `architecture.md` §6.
6. ~~**Suite de pruebas mínima**~~ — **Hecho, 2026-07-31.** `tests/run.js` — extrae el motor de daño de `hud.html` (sin depender de la modularización del punto 4, que sigue pendiente) y lo corre en un sandbox de Node; cubre el bug de habilidades ya resuelto en los dos idiomas, más `validate_data.py` como parte de la suite. Ver `audit.md` §5.7.
7. ~~**Investigar la reconexión de permiso de captura**~~ — **Hecho, 2026-07-31.** No hay reconexión automática, pero el fallo es explícito: `dead=true` produce un mensaje claro que llega hasta el panel (`ScreenCapture.kt` → `OverlayService.scan()` → `window.onScan()`). No es un bug, es degradación aceptable y ruidosa. Ver `audit.md` §5.8. Automatizar la re-solicitud de permiso queda como mejora de UX para Fase 1, no como corrección.
8. ~~**Limpieza menor: dependencia sin uso**~~ — **Hecho, 2026-07-31.** `kotlinx-coroutines-android` removida de `app/build.gradle.kts` (`audit.md` §5.6).

**Criterio de salida: cumplido, 2026-07-31.** Los 8 ítems están cerrados (7 resueltos con código, 1 — la modularización — cerrado como decisión explícita de no hacerlo, `decisions.md` #18). Todos los hallazgos de `audit.md` §5 que describían comportamiento incorrecto están resueltos, y hay pruebas (`tests/run.js`, `validate_data.py`) que impedirían que se reintroduzcan en silencio. **Fase 0 completa — el proyecto pasa a Fase 1.**

## Fase 1 — Reducir la fricción crítica de uso (fase actual)

**Reformulada el 2026-07-31** tras revisar el primer intento con Angel: la importación de equipo por texto no era lo que esperaba — quiere captura automática (OCR) de la pantalla "View Details" del juego, como ya funciona para el rival en team preview. Se replanteó el alcance con él en cuatro partes, en el orden que eligió: **A. equipos guardados, B. Previa, C. Campo, D. OCR del equipo propio — las cuatro hechas.** Ninguna se probó todavía en dispositivo real (ver aviso al final de la sección).

- ~~**A. Equipos guardados**~~ — **Hecho, 2026-07-31.** Guardar, nombrar, elegir, duplicar y borrar equipos completos (antes solo existía un único equipo sin nombre). Formato de persistencia v1→v2 con migración automática, sin tocar Kotlin. El importador de texto (`parseTeamText()`) queda como estaba — sigue siendo la forma rápida de cargar/corregir un equipo sin usar los selectores uno por uno, y ahora también sirve para corregir lo que la OCR de la Parte D lea mal.
- ~~**B. Previa: orden de velocidad completo + mayores amenazas**~~ — **Hecho, 2026-07-31.** `fullSpeedOrder()` (los 12 Pokémon, propios exactos y rivales en rango — nunca un número solo para el rival) y `topThreats()` (el mejor golpe de cada rival contra tu peor respuesta). Información sobre el rival, no una recomendación — no viola `decisions.md` #1/#19.
- ~~**C. Campo: quién entra + matriz de daño**~~ — **Hecho, 2026-07-31.** Panel nuevo (`vBrought()`) para marcar qué rivales están confirmados en la partida y qué 4 propios se llevaron — reemplaza la fricción de los selectores sueltos que ya existían (que siguen ahí, pero ahora acotados a los marcados). La matriz de daño reemplaza las listas "Les hacés"/"Te hacen" (que solo cubrían activo-contra-activo) por una grilla completa (hasta 4×4, activos y banca, las dos direcciones por celda).
- ~~**D. OCR del equipo propio**~~ — **Hecho, 2026-07-31, primer intento sin verificar contra el juego real.** Dos capturas de "View Details" (Moves & More, después Stats) arman un equipo nuevo automáticamente. Dependencia nueva: `com.google.mlkit:text-recognition:16.0.1` (variante *bundled*, offline). Decisión de arquitectura: `TeamOCR.kt` no interpreta nada — solo corre ML Kit y devuelve texto crudo con posición; toda la lógica de a qué Pokémon pertenece cada línea y qué campo es (`clusterCards()`, `parseMovesCard()`, `parseStatsCard()`, `finishOwnScan()`) vive en `hud.html`, para poder corregirla sin recompilar cuando el layout real no se comporte como se asumió mirando 2 capturas estáticas. Reusa `findSpecies()`/`findAbility()`/`findItem()`/`findMove()` de la Parte A, cero matching nuevo. Crea un equipo nuevo, no pisa ninguno guardado.
- ~~Corrección de reconocimiento en 2 taps, sin teclado, en cualquier punto del flujo.~~ — **Hecho, 2026-07-31.** La especie del rival en team preview no tenía ninguna forma de corregirse manualmente (solo objeto/habilidad/movimientos la tenían). Agregado con el mismo patrón de selector de 2 taps que ya usaba el equipo propio.
- ~~Ajustar Glance para dejar de mostrar contadores de campo que el juego ya muestra~~ — **Verificado, 2026-07-31: el supuesto no se sostenía.** Glance (`vCompact()`) nunca mostró esos contadores — viven en `vField()` (Peek), que además es el mecanismo de entrada con el que el usuario le informa el estado a la app. En cambio se encontró y corrigió algo más grave en el mismo lugar: Glance seguía rankeando movimientos con la etiqueta "MEJOR", el modo `suggest()` que `decisions.md` #1 daba por descartado. Corregido y matizado en `decisions.md` #19 (mostrar el resultado calculado no es recomendar; ordenar o etiquetar "mejor" sí).
- Rediseño de Presentación hacia una vista contextual única (según fase del combate) en vez de pestañas fijas, alineado con `product.md`. **Sin abordar todavía.**

**Primera pasada por dispositivo real, 2026-08-01.** Angel compiló y probó. Dos errores de compilación reales (confirman que hacía falta probarlo, no se podían haber encontrado leyendo código): `TextRecognizerOptions` vive en `com.google.mlkit.vision.text.latin`, no en `com.google.mlkit.vision.text` — corregido. La versión `16.0.0` de ML Kit no tenía sus librerías nativas alineadas a páginas de 16 KB (warning de Android Studio, no bloqueante hoy) — actualizada a `16.0.1`, que sí lo soluciona según el changelog oficial. Feedback de uso real, todo corregido el mismo día:
- Captura OCR del equipo propio: **no funcionó** — sin logs del dispositivo no se pudo encontrar la causa exacta al principio. Se endureció en dos frentes: match difuso (`closestMatch()`/`editDistance()`) para que un carácter mal leído no tire la lectura entera a la basura, y diagnóstico visible (cuántas líneas leyó ML Kit, sample crudo por tarjeta) para que el próximo intento deje información real en vez de fallar en silencio. **Revisando el código de nuevo (sin logs, por lectura), apareció un bug real que explica exactamente el síntoma reportado ("tocás el botón y no pasa nada"):** `Bridge.scanOwnTeam()` (el método que JS llama) y el método privado de `OverlayService` que hacía la captura real tenían el mismo nombre, `scanOwnTeam()`. Como `Bridge` es una clase interna, la llamada sin calificar adentro de `Bridge.scanOwnTeam()` se resolvía a sí misma en vez de al método externo — quedaba reencolando el mismo post en el hilo principal para siempre, sin llegar nunca a sacar el bitmap ni correr OCR. Se corrigió renombrando el método privado a `doScanOwnTeam()`. No se puede confirmar al 100% sin volver a probar en el dispositivo, pero es un bug real confirmado por lectura de código (no una hipótesis) y coincide exactamente con el síntoma. Además se corrigió un bug propio en `parseStatsCard()` (agrupaba líneas por Y antes de separar por columna, mezclando filas de tarjetas distintas — encontrado por un test que empezó a fallar) y se endureció `parseMovesCard()` para exigir al menos una letra en cada línea. Sigue sin verificarse contra el juego real.
- Panel "Quién entra" en Campo se compactaba apenas se tocaba el primer Pokémon — correguido para esperar los 2 rivales y los 4 propios.
- Velocidad post-megaevolución: `fullSpeedOrder()` ahora también muestra la velocidad que tendría un Pokémon con piedra de mega puesta si megaevoluciona este turno.
- Panel del HUD agrandado ~60% en horizontal (con el límite de no tapar el panel nativo de equipo rival en team preview).
- La predicción de "quién va a sacar" (`predict()`) resultó poco fiable en uso real — bajada al fondo de Previa, sin estorbar; rediseñar el algoritmo queda documentado en `future.md` para más adelante, no es una corrección rápida.

**Sigue pendiente de verificar en dispositivo real:** el resto de la captura OCR (si `clusterCards()` agrupa bien contra el layout real más allá de las 2 capturas de referencia, si el regex de `parseStatsCard()` matchea lo que ML Kit realmente devuelve), y todos los cambios de esta segunda vuelta (panel más grande, "Quién entra" corregido, velocidad post-mega). La lógica está testeada con datos sintéticos (`tests/run.js`, 46 casos), pero eso no reemplaza probarlo contra el juego.

**Tercera vuelta, mismo día (2026-08-01), sesión larga sin supervisión mientras Angel dormía — QA propio, sin nuevos reportes de Angel:** con los 6 ítems de la segunda vuelta ya corregidos, se dedicó el resto de la sesión a revisar el código de las Partes A/B/C/D en busca de bugs latentes (nada de esto vino de un reporte nuevo, es revisión propia):
- Encontrado y corregido el bug de colisión de nombres `scanOwnTeam()` descripto arriba — probablemente la causa real de que el botón de captura no hiciera nada.
- Encontrado y corregido un bug propio en `parseStatsCard()`: agrupaba por Y antes de separar columnas (mezclaba filas de tarjetas distintas).
- Endurecido `parseMovesCard()` para exigir al menos una letra por línea.
- `parseStatsCard()`: el corte entre columna izquierda/derecha pasó de "por mediana de X" a "por el mayor salto entre valores de X consecutivos" — la mediana fallaba si ML Kit fragmentaba más líneas de un lado que del otro.
- Revisado el resto de `wire()`, `vField()`/`vBrought()`, `vPre()`, `expandNow()`/`collapseNow()`, y el pipeline completo de `ScreenCapture.kt` (compartido entre el escaneo del rival, que ya funciona, y la captura propia nueva) — sin hallazgos adicionales.
- Ningún cambio de esta tercera vuelta es una feature nueva ni un cambio de comportamiento pedido — todo es corrección de bugs encontrados por lectura de código y refuerzo de casos ya cubiertos por tests.

### Checklist para probar en el dispositivo real (lo que dejó esta sesión)

En orden, de lo más rápido a lo que más tiempo lleva:

1. **Botón de captura del equipo propio** (el bug principal de esta vuelta): abrí "View Details" de un Pokémon propio en la pestaña Moves & More, tocá "Capturar equipo" en MÍO. Si el fix fue correcto, ahora debería pasar algo (mostrar cuántas líneas leyó, aunque la lectura salga mal) en vez de no hacer nada.
2. Si el paso 1 muestra texto reconocido pero mal agrupado en las 6 tarjetas: es el layout asumido por `clusterCards()` (grilla 2×3 por posición relativa) el que puede no coincidir con la pantalla real — avisame qué agrupó mal y lo ajusto en `hud.html` sin recompilar.
3. Segunda pasada: cambiá a la pestaña Stats en el juego y volvé a tocar el botón (ahora dice "Ahora tocá Stats..."). Fijate si arma un equipo nuevo razonable en MÍO, o si `parseStatsCard()` no matchea el formato real de los números.
4. **Campo → "Quién entra":** marcá los 2 rivales y tus 4 elegidos en orden. Debería quedarse arriba hasta completar los 6 toques, no bajar después del primero.
5. **Previa → orden de velocidad:** si algún propio lleva piedra de mega y no mega-evolucionó, debería aparecer la velocidad hipotética post-mega al lado del nombre.
6. **Tamaño del panel:** confirmá que no tapa el panel nativo de equipo rival en team preview, y que ahora entra más info sin cortarse.
7. **Previa → "Va a sacar"/"Sacá vos"/"Por qué":** deberían estar al fondo de la pestaña, marcados como predicción poco fiable, sin estorbar el resto.

Si algo de los pasos 1–3 sigue sin andar bien, lo más útil que podés mandar son capturas de pantalla del resultado (el mensaje de diagnóstico que muestra cuántas líneas leyó y qué texto crudo salió por tarjeta) — con eso alcanza para corregir sin que compiles de nuevo, salvo que el problema esté del lado de Kotlin.

**Fuera de esta fase todavía:** detección de naturaleza por color en la captura de Stats (por ahora queda neutral, corrección manual); rediseño de Presentación a vista contextual única (ítem sin abordar, arriba).

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

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
- ~~Rediseño de Presentación hacia una vista contextual única (según fase del combate) en vez de pestañas fijas~~ — **Movido fuera del alcance de esta fase, ver más abajo.** No estaba entre las 4 partes (A/B/C/D) que Angel pidió al reformular Fase 1; queda como mejora de UX para más adelante, no bloquea el criterio de salida de esta fase.

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

**Cuarta vuelta, mismo día (2026-08-01), con capturas reales de Angel de "Quién entra" y de la captura de equipo:**
- **"Quién entra" no cambiaba el campo:** marcar rivales/propios en el panel de arriba no actualizaba los selectores "Tus activos"/"Rivales" — se quedaban en el default (índices 0/1). Nuevas `syncActiveFoe()`/`syncActiveMine()`: al marcar, si el slot activo correspondiente todavía no apunta a alguien confirmado, se completa solo con lo recién marcado — pero nunca pisa un activo que ya era un rival/propio confirmado (para no revertir un cambio real de en medio del combate cuando se revela un cuarto/quinto Pokémon más adelante).
- **Captura de equipo: leyó 2 de 6 y mal.** Causa encontrada por lectura de la captura que mandó Angel: `clusterCards()` asumía que la grilla de 6 tarjetas ocupa toda la altura de la imagen, pero el nombre de equipo/entrenador (`"Team 9"` / su nombre de entrenador) y las pestañas "Moves & More"/"Stats" viven arriba de la grilla — ese header caía en el primer tercio y se leía como si fuera la especie de las tarjetas 1 y 2. Corregido: ahora se busca el texto de las pestañas (siempre presente, texto fijo del juego) y se usa su posición como corte real de dónde empieza la grilla, en vez de una fracción fija de toda la imagen. Si no se reconocen las pestañas, cae al comportamiento anterior en vez de romper.
- **"O Protect" / "T Choice Scarf":** Angel identificó la causa exacta — el ícono de tipo Normal (un círculo liso) y el ícono de objeto se leen como una letra suelta pegada adelante del nombre real. `findMove()`/`findItem()` ahora reintentan sin ese prefijo como último recurso (solo si nada más matcheó — ningún movimiento u objeto real empieza con una letra sola seguida de espacio).
- **"Importar equipo" (pegar texto)** bajó al final de la pestaña MÍO — sigue disponible, pero ya no compite por atención con la captura automática, que es el flujo principal ahora.
- 9 tests nuevos (55 en total) cubren los tres fixes de arriba con datos sintéticos que reproducen los casos reales que mandó Angel.

**Quinta vuelta, 2026-08-03, con diagnóstico real en pantalla — la causa de fondo de la captura, encontrada por fin:**
- **La captura del equipo propio fallaba por un supuesto equivocado sobre el layout, no por OCR.** El diagnóstico visible que se había agregado en la tercera vuelta hizo exactamente su trabajo: mostró que Aegislash salía con habilidad `"9 Iron Head"` (un movimiento con el número de tarjeta pegado), ítem `"Stance Change"` (la habilidad) y movimiento `"5 Spell Tag"` (el ítem). Ese corrimiento de un lugar en cada campo es la firma inconfundible de **dos columnas intercaladas**: cada tarjeta tiene especie/habilidad/ítem a la izquierda y hasta 4 movimientos a la derecha, **compartiendo las mismas alturas**, y `parseMovesCard()` ordenaba todo por Y asumiendo lectura secuencial. Corregido con `splitColumns()` (corte por el mayor salto en X, el mismo criterio que ya usaba `parseStatsCard()`, ahora compartido por las dos). Los fixes anteriores (header del nombre de equipo, match difuso, prefijos de ícono) eran correctos pero atacaban síntomas de segundo orden — este era el bug de fondo.
- `stripIconPrefix()` ahora también saca un **dígito** suelto, no solo una letra: el número grande de orden de la tarjeta (1–6) se pega a la línea (`"9 Iron Head"`, `"5 Spell Tag"`).
- **Elegir dónde va lo escaneado.** Cada captura creaba un equipo nuevo, y reintentar una lectura fallida dejaba la lista llena (Angel llegó a 5 guardados). Ahora hay un selector en MÍO — *un equipo nuevo* / *actualizar el activo* — persistido, porque quien reescanea para corregir quiere lo mismo varias veces seguidas.
- **"Mayores amenazas" mostraba Electro Shot en todos los rivales** (Blaziken, Mimikyu, Ditto, Sneasler), incluso en especies que no lo aprenden. Causa: `best()` caía **en silencio** a la lista global de todos los movimientos del juego cuando no había datos del rival, y elegía el más fuerte que existiera. Es el patrón de fallo silencioso de `audit.md` §8 otra vez. Corregido en dos capas: `best()` con pool vacío devuelve `null` en vez de la lista global, y el nuevo `foeMovePool()` resuelve los movimientos del rival en orden de confianza (**visto** › **común en meta** › **posible por learnset**) y **etiqueta cuál usó** — antes los tres niveles se leían igual y "solo posible" parecía una amenaza confirmada.
- **Tamaño del panel: confirmado correcto por Angel**, no tapa el equipo rival en team preview. Cierra ese ítem de la segunda vuelta.
- 9 tests nuevos (64 en total), incluido uno que reproduce literalmente el caso Aegislash del diagnóstico.

**Deuda técnica reportada, explícitamente pospuesta — no para el próximo sprint:**
- El HUD consume aproximadamente **3 veces más batería** que el propio juego de Pokémon Champions corriendo solo. No investigado todavía; sospechosos razonables para cuando se retome: el WebView redibujando aunque no haya cambios, la resolución de la captura de pantalla, o el polling de conexión con el overlay — nada de esto se confirmó, es punto de partida para una futura sesión dedicada a perfilar batería.
- El permiso de captura de pantalla (`MediaProjection`) se pierde solo después de un rato sin usarlo — aproximadamente entre 1 y 2 combates de inactividad. Ya hay manejo explícito del caso (`ScreenCapture.kt`: `dead=true` da un mensaje claro en vez de fallar en silencio, `audit.md` §5.8), pero no hay renovación automática del permiso; el usuario tiene que volver a `MainActivity` y autorizar de nuevo. Automatizar esa re-solicitud queda pendiente.

### Checklist para probar en el dispositivo real (lo que dejó esta sesión)

En orden, de lo más rápido a lo que más tiempo lleva:

1. **Botón de captura del equipo propio:** abrí "View Details" de un Pokémon propio en la pestaña Moves & More, tocá "Capturar equipo" en MÍO. Debería agrupar bien las 6 tarjetas ahora (antes leía el nombre de equipo/entrenador como si fuera una especie).
2. Si sigue agrupando mal: mandame el mensaje de diagnóstico (cuántas líneas leyó, sample por tarjeta) — con eso alcanza para ajustar sin que compiles de nuevo.
3. Segunda pasada: cambiá a Stats, volvé a tocar. Fijate si "O Protect"/"T [objeto]" ya se leen bien como "Protect"/"[objeto]".
4. **Campo → "Quién entra":** marcá los 2 rivales y tus 4 elegidos en orden. Debería quedarse arriba hasta completar los 6 toques, y ahora "Tus activos"/"Rivales" deberían mostrar justo lo que marcaste, no el default.
5. **Previa → orden de velocidad:** velocidad post-mega al lado del nombre si corresponde.
6. **Tamaño del panel** y **Previa → predicción al fondo** (ya confirmados en la vuelta anterior, revalidar si tocás algo cerca).

Si algo sigue sin andar bien, lo más útil que podés mandar son capturas de pantalla del resultado — con eso alcanza para corregir sin que compiles de nuevo, salvo que el problema esté del lado de Kotlin.

**Fuera de esta fase todavía:** detección de naturaleza por color en la captura de Stats (por ahora queda neutral, corrección manual); rediseño de Presentación a vista contextual única; batería y renovación automática del permiso de captura (ver deuda técnica arriba). Ninguno de estos tres bloquea el criterio de salida de abajo — quedan para Fase 1.5 o más adelante, según lo que Angel priorice cuando retome.

**Criterio de salida:** un combate completo se juega con el presupuesto de interacción manual definido en `product.md`, salvo fallos puntuales de reconocimiento.

**Estado, 2026-08-01: código completo y revisado (4 vueltas de QA, 55 tests), pendiente del único paso que no se puede dar sin el teléfono de Angel — jugar un combate real de punta a punta sin que nada rompa el flujo.** No hay ningún bug conocido sin corregir en este momento. El bloqueo real para cerrar la fase es de verificación, no de código: cada vuelta de feedback encontró bugs nuevos que ninguna lectura de código adelantó (la colisión de nombres en `scanOwnTeam()`, el header contaminando `clusterCards()`), así que declarar la fase cerrada sin ese combate real sería exactamente el patrón que `audit.md` viene señalando como el error repetido del proyecto — degradar en silencio la confianza de un resultado. En cuanto Angel confirme un combate completo sin bugs nuevos (o reporte los que aparezcan y se corrijan), la Fase 1 cierra formalmente y el proyecto pasa de lleno a Fase 2 — cuyo primer hito ya se adelantó más abajo, dado que no depende del teléfono.

## Fase 2 — Datos de meta reales y motor de inferencia por eliminación

Diseño completo en `architecture.md` §10. No es una fase de una sola sesión; se lista en pasos para poder retomarla sin releer todo el diseño cada vez.

**Primer hito accionable (el que tiene sentido arrancar si sobra tiempo tras la Fase 0):**
1. ~~Resolver el ID de formato de la Reg M-B vigente con `GET /games` contra la API de Limitless.~~ — **Hecho, 2026-08-01.** El formato es literalmente `"M-B"` en la API (`{"M-B":"Regulation Set M-B"}`) — coincide exacto con el `regulation` que ya usa `meta.json`, sin mapeo de por medio.
2. ~~Traer standings de un torneo real e inspeccionar el subesquema real del campo `decklist`.~~ — **Hecho, 2026-08-01.** Verificado contra 2 jugadores de un torneo real (Reg M-B, 42 jugadores). Esquema documentado en `architecture.md` §10.1.1. Hallazgo importante que cambia lo que se conjeturaba: **no hay reparto de stats/EVs en ninguna muestra** — el `decklist` cubre especie/ítem/habilidad/movimientos/naturaleza, nunca el spread numérico, ni siquiera en torneos con teamlist abierto.
3. ~~Decidir el modelo de datos exacto de `MetaSnapshot`~~ — **Resuelto, 2026-08-03.** El índice de combinaciones parciales (§10.3) nunca estuvo bloqueado porque no depende del spread. Para "Repartos habituales" se había verificado que **ninguna fuente da una distribución real de repartos** (Limitless no trae ninguno; Pikalytics solo una mención suelta del build más usado). Le presenté a Angel dos salidas — degradar la sección, o dejarla como estimación marcada — y eligió una tercera mejor: usar el **contexto de equipo**, que las fuentes sí dan en abundancia, para derivar una estimación fundamentada. Nuevo campo `spreadEstimate` en `architecture.md` §10.6: combina el único reparto conocido de Pikalytics + el rol que la especie cumple en los equipos donde aparece + sus movimientos comunes. Se muestra siempre como ○ Estimado con su razonamiento inspeccionable, y como todo prior **ordena hipótesis pero nunca las descarta** — en cuanto haya un daño observado, la deducción de `solveBulk()` le gana.

### Plan por sprints (definido 2026-08-03, `decisions.md` #21/#22/#23)

**El reencuadre que ordena todo esto:** revisando el código real se confirmó que el proyecto **ya tiene dos reglas de inferencia funcionando** (`solveBulk()` descarta repartos defensivos incompatibles con un daño observado; `observeOrder()` acota velocidad y deduce Pañuelo Elección solo). Lo que falta no es el motor — es el sustrato: ambas tiran la evidencia que produjo su conclusión, y por eso hoy no se puede explicar una inferencia, deshacerla, ni arrastrarla a un Bo3. Fase 2 construye ese sustrato debajo de lo que ya anda. Especificación completa en [`inference.md`](./inference.md).

**Regla de secuencia, no negociable:** nada se construye encima del sustrato hasta que el sustrato reproduzca el comportamiento actual sin regresiones.

**Prerrequisito — cerrar Fase 1.** Un combate real de punta a punta con la build actual. No es trabajo de código, es la verificación pendiente descrita arriba.

---

**Sprint 2.1 — Event log en paralelo** · *obligatorio*
- **Objetivo:** registrar todos los hechos de la partida en un log append-only que corre **junto a** `B`, sin reemplazarlo. Riesgo cero por diseño: si el log está mal, nada se rompe todavía.
- **Archivos:** `hud.html` (sección `ESTADO`), `tests/run.js`.
- **Datos:** ninguno nuevo. Los tipos de evento del MVP están en `inference.md` §2.
- **Tests:** cada acción del usuario que hoy muta `B` genera el evento correspondiente; el log sobrevive el ciclo de guardado/carga; `userCorrection` se registra como evento en vez de mutar en silencio.
- **Aceptación:** para una partida sintética completa, el fold del log reproduce **exactamente** el `B` que produce el código actual. Verificable con un test de igualdad estructural.
- **Riesgos:** que algún camino de mutación de `B` quede sin instrumentar y el log salga incompleto sin que nadie lo note — mitigación: el test de igualdad de arriba lo detecta.
- **Terminado:** el test de equivalencia pasa y el log persiste entre sesiones.

**Sprint 2.2 — Espacio de hipótesis + migrar R1/R2** · *obligatorio*
- **Objetivo:** el primer beneficio visible. Conjuntos de hipótesis con evidencia adjunta (`inference.md` §3), y las dos reglas existentes migradas **sin cambiar su lógica** — solo pasan a declarar qué descartaron y por qué.
- **Archivos:** `hud.html` (`solveBulk`, `observeOrder`, `vFoe`), `tests/run.js`.
- **Datos:** ninguno nuevo.
- **Tests:** los casos actuales de `solveBulk`/`observeOrder` siguen dando el mismo resultado; cada descarte trae su `byEvent`; los tres niveles de confianza se derivan del tamaño del conjunto; deshacer un evento restituye las hipótesis que había descartado.
- **Aceptación:** en Peek se puede tocar "Pañuelo Elección — Deducido" y ver *"porque se movió antes que tu Sinistcha en el turno 3"*. Y el nivel de confianza sale del conjunto, no de una etiqueta a mano.
- **Riesgos:** la migración cambia el comportamiento sin querer — mitigación: los tests actuales son la red, se corren antes y después.
- **Terminado:** cero regresiones, "¿por qué?" contestable para las dos reglas, deshacer funciona.

**Sprint 2.3 — `MetaSnapshot` + adaptador de Limitless** · *obligatorio*
- **Objetivo:** reemplazar `meta.json` estimado a mano por datos reales de torneo. Es el corazón declarado de esta fase.
- **Archivos:** `build_meta.py` (hoy un stub, `audit.md` §5.9), `validate_data.py`, `assets/meta.json`.
- **Datos:** API de Limitless, esquema ya verificado (`architecture.md` §10.1.1). Incluye `roleInCore` y `speedControlMajority` (§10.6) desde el diseño inicial, no como parche.
- **Tests:** el adaptador produce `MetaSnapshot` válido desde una respuesta real guardada como fixture; `partial: true` cuando una fuente falla; `validate_data.py` cruza el snapshot generado contra las tablas canónicas.
- **Aceptación:** `meta.json` se genera desde torneos reales, con `regulation`/`generatedAt`/`sourceCounts`, y la app arranca con él sin cambios de código.
- **Riesgos:** rate limits (mitigación: batch semanal con backoff, ya diseñado en §10.4); que la API cambie de forma (mitigación: fixture + validación que falla ruidosamente).
- **Terminado:** un comando regenera el dataset completo y la validación pasa.

**Sprint 2.4 — Motor de prioridad** · *obligatorio* (habilita `decisions.md` #21, parte 1)
- **Objetivo:** que el HUD decida qué información sube a Glance según qué es más probable que cambie la decisión del turno (`inference.md` §10).
- **Archivos:** `hud.html` (`vCompact`, `vField`), `tests/run.js`.
- **Datos:** los conjuntos de hipótesis de 2.2 (para saber qué es incierto) y la tabla de peso base de `decisions.md` #20.
- **Tests:** un rango de daño que abarca KO y no-KO puntúa más alto que uno que da 20%; un orden de velocidad que depende de un solo escenario sube; la fórmula es determinista y auditable.
- **Aceptación:** Glance muestra primero lo que cruza una frontera de decisión. **Sin ranking de movimientos propios ni etiqueta "MEJOR"** — se ordena información, nunca opciones de juego (#19 sigue vigente).
- **Riesgos:** repetir el error de `predict()` — un puntaje opaco ajustado a mano que no acierta (ver `future.md`). Mitigación: la fórmula es dos factores, ambos inspeccionables, sin pesos finos.
- **Terminado:** tests de prioridad pasan y Angel confirma en uso real que el orden le ahorra buscar.

**Sprint 2.5 — Reglas nuevas y datos que faltan** · *recomendable*
- **Objetivo:** R3 (movimiento visto), R4 (habilidad que no se activó), R5 (objeto activado) — `inference.md` §5. Más PP **de todos los movimientos** (`architecture.md` §11.2 — decidido con Angel el 2026-08-03: se muestra el PP completo en Peek, y el ruido en Glance lo resuelve el motor de prioridad del Sprint 2.4, no recortando el dato en origen) y descripción de habilidad (§11.1, ya investigada, solo falta escribirla).
- **Archivos:** `hud.html` (tabla `MV` para PP, registro de reglas), script de datos para PP, `tests/run.js`.
- **Tests:** una por regla, aisladas, sin DOM ni Android.
- **Aceptación:** entrar con Intimidate y no ver la bajada descarta las habilidades incompatibles, con su evidencia.
- **Riesgos:** agregar PP a `MV` toca ~150 entradas — mitigación: script generado + validación, nunca a mano.
- **Terminado:** las tres reglas con tests, PP visible en Peek.

**Sprint 2.6 — Descripción de riesgo y consecuencia** · *recomendable* (habilita `decisions.md` #21, parte 2)
- **Objetivo:** enunciar la posición: *"el escenario más peligroso es X"*, *"no mata en 3 de 16 tiradas"*, *"si cambia a X, tu Y queda expuesto"*.
- **Dependencia dura:** **no se empieza antes de 2.2.** Una descripción de riesgo sin cadena de evidencia inspeccionable es exactamente la caja negra que #21 condiciona explícitamente.
- **Tests:** cada afirmación de riesgo trae los eventos que la sostienen; ninguna se emite sin evidencia.
- **Aceptación:** toda frase de riesgo contesta "¿por qué me mostrás esto?".
- **Riesgos:** que el lenguaje se deslice de describir a sugerir — mitigación: la prueba de #21 (¿enuncia un hecho o un imperativo?) se aplica a cada string nuevo.
- **Terminado:** descripciones activas, todas explicables, ninguna que diga qué hacer.

---

**Clasificación del resto:**
- *Futuro (Fase 4)*: memoria de serie Bo3 y Open Team Sheets (R6). El event log de 2.1 los deja casi listos — `inference.md` §9.
- *Futuro (Fase 4+)*: aprendizaje sobre las partidas propias del usuario, como consumidor del log guardado.
- *Experimental, sin fecha*: rediseño del algoritmo de predicción de team preview (`future.md`) — depende de tener datos reales de 2.3 antes de volver a tocar sus pesos.
- *Descartado con justificación*: Evidence Graph explícito, enumeración de repartos de 6 stats, ML, probabilidades numéricas sobre hipótesis — `inference.md` §11.

**Criterio de salida de Fase 2:** la predicción de equipo deja de depender de un archivo estimado a mano, y cada estimación mostrada es explicable con su cadena de evidencia concreta.

**Sesión de asesoría VGC, 2026-08-01/02 (`decisions.md` #20) — análisis y plan, sin código todavía (preferencia explícita de Angel: analizar → documentar → planear → recién después programar).** Investigación externa sobre qué distingue a un jugador de VGC profesional + una sesión larga de preguntas a Angel como jugador real, para no diseñar Fase 2 a ciegas. Conclusiones ya documentadas, listas para retomar cuando se pase a código:
- `architecture.md` §10.6 — dos campos nuevos requeridos del `MetaSnapshot` (arriba).
- `architecture.md` §11.1 — descripción de habilidad expandible en Peek. Fuente y método ya verificados end-to-end (PokeAPI, 201/201 habilidades encontradas, incluidas las propias de Champions) — falta solo escribir el código, no falta investigar nada más.
- `architecture.md` §11.2 — seguimiento de PP en movimientos clave. Confirmado como brecha real (`product.md` lo prometía desde el principio y nunca se construyó). Necesita agregar PP máximo a la tabla `MV` primero (dato nuevo, ~150+ movimientos) antes de tocar la UI — plan completo en la sección, no se arrancó por el tamaño de esa migración de datos.

## Fase 3 — Formalizar la separación Motor / Cliente

- Extraer explícitamente el motor de dominio como módulo independiente de Android/Kotlin (decisión #10), sin que esto implique construir todavía un segundo cliente — es preparar el terreno, no anticipar trabajo que no hace falta hoy.
- Dejar reservadas (sin implementar) las interfaces de entitlements (decisión #5) y de espacio de publicidad (decisión #4) en la capa de Presentación, verificando que ningún módulo de dominio las referencia.

**Criterio de salida:** el motor puede ejecutarse y probarse sin ningún dependencia de Android.

## Fase 4 — Memoria y análisis post-combate

- Resumen post-partida construido sobre el event log: qué acertó y qué falló el modelo, qué información se reveló de más.
- Modo serie (Bo3) con persistencia de creencias confirmadas entre juegos (decisión #9). **El event log del Sprint 2.1 lo deja casi listo:** al empezar el juego 2 se inyectan como eventos iniciales las hipótesis `confirmed` del juego 1; lo que solo estaba "vivo" no se arrastra, porque el rival puede traer otros 4. Esa distinción — arrastrar hechos, no suposiciones — es exactamente lo que el modelo de tres niveles permite expresar y el estado mutable de hoy no (`inference.md` §9).
- Soporte para Open Team Sheets como un tipo de evento más (regla R6 en `inference.md` §5: colapsa hipótesis a certeza desde el inicio del combate) — sin requerir ningún cambio en el motor de inferencia.

**Criterio de salida:** un jugador puede repasar una serie completa y entender qué patrones propios está repitiendo.

## Fase 5 en adelante — Ver `future.md`

Todo lo que depende de una decisión de negocio no tomada todavía (licencias, publicidad activa, sincronización multi-dispositivo, análisis de hábitos a largo plazo, multi-idioma completo, clientes en otras plataformas) vive documentado en [`future.md`](./future.md) y se aborda cuando corresponda, sin condicionar las fases anteriores.

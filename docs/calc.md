# CALC — calculadora de daño a mano

Análisis y diseño de la pestaña CALC, hecho a pedido de Angel el 2026-08-06. Complementa (no reemplaza) el resto del HUD: `topThreats()`, la matriz de daño de Campo y `previewMatrix()` ya dan daño automatizado sin que el jugador tenga que tocar nada — CALC es la herramienta libre para cualquier pregunta que esas vistas no cubren ("¿y si tuviera Vida Sana en vez de Pañuelo?", "¿le gana a esto con -1?").

## 1. Por qué esto no es "clonar la calculadora de Showdown"

`vision.md` ya lo dice para el resto del producto: el HUD informa, no reemplaza al jugador pensando. Acá aplica distinto — CALC es explícitamente una herramienta manual — pero el principio de fondo se mantiene: **no se agrega superficie nueva sin que resuelva algo que el resto del HUD no resuelve ya**. La calculadora de Showdown es exhaustiva porque su único trabajo es cubrir cada mecánica del juego para cualquier formato; la de acá tiene un trabajo más chico: completar los huecos que quedan cuando el resto del HUD (que ya sabe tu equipo, el rival escaneado, el clima y el campo actuales) no alcanza.

## 2. Auditoría de la calculadora de Showdown (calc.pokemonshowdown.com)

**Fortalezas — por qué es el estándar de la comunidad:**
- Cobertura mecánica completa y confiable: cada objeto, habilidad, interacción de clima/terreno/pantallas, movimiento múltiple, daño repartido en dobles, Teraestallar — todo modelado y mantenido contra el juego real.
- Estado completamente explícito en la URL: un cálculo se puede compartir con un link, sin ambigüedad de qué se configuró.
- Una vez aprendida, es rápida: alguien que ya sabe dónde está cada campo arma un cálculo en segundos.

**Debilidades — todas relevantes acá, porque CALC vive en un teléfono, en medio de un combate real, no en un escritorio con tiempo de sobra:**
1. **Pensada para mouse + teclado.** Los menúes desplegables son chicos, pensados para clickear con precisión, no para el dedo. En un teléfono, mientras el juego sigue corriendo abajo, cada toque que falla cuesta un timer que no vuelve.
2. **EVs/IVs se cargan tecleando 5-6 números por Pokémon**, uno por stat. Es el punto de fricción más grande de la herramienta entera — típear "252" seis veces por cálculo no es razonable bajo presión de tiempo.
3. **El buscador de especie es la lista completa del juego** (1000+ entradas). Cuando ya se sabe que el Pokémon en cuestión es uno de los 12 que están en la partida — 6 propios ya cargados, 6 rivales ya escaneados — buscarlo en una lista de mil es trabajo de más que la app ya podría ahorrar.
4. **Cero memoria de contexto.** Cada cálculo arranca de cero: hay que volver a decir el clima, las pantallas activas, qué objeto lleva el rival — todo dato que, en Champions HUD, YA está registrado en el event log de la partida en curso.
5. **Habilidad/objeto son campos de texto/dropdown independientes**, sin relación con "qué Pokémon es este" — no autocompleta con lo que el jugador ya confirmó ver.
6. **Sin historial.** Si querés comparar "con Vida Sana" contra "con Pañuelo Elección" hay que rehacer todo el cálculo de nuevo, no hay un "duplicar y cambiar un campo".

## 3. Principio de diseño para la versión de Champions HUD

**Todo lo que el HUD ya sabe, lo completa solo. Todo lo que no sabe, se toca, no se tipea.**

Concretamente:
- **Atacante/Defensor por defecto salen de los 12 Pokémon de la partida** (tus 6 + los 6 del rival, escaneados o cargados), como chips para tocar — no un buscador de la Pokédex completa. Buscar en la lista completa sigue existiendo, pero como escape hatch explícito ("Otro Pokémon…"), no como el camino por defecto.
- **Si el Pokémon elegido es uno ya conocido, objeto/habilidad se autocompletan** con lo que el jugador ya confirmó (`m.item`/`m.abil` del lado propio, `f.item`/`f.abil` si están confirmados del lado rival) — con un toggle para override manual, nunca bloqueado.
- **Clima/terreno/pantallas/dobles se heredan de `B` (el estado de campo actual)**, igual que ya hace `calc()` internamente vía `ctxFor()` — esto YA estaba hecho antes de esta sesión, solo no se comunicaba en la UI que es automático.
- **Reparto de EVs por slider de toque, no tecleado** — ya existe el patrón (`vMine()` usa sliders para repartir los 66 puntos), se reutiliza acá en vez de inventar un campo de texto nuevo.
- **Botón ⇄ para invertir atacante/defensor** de un toque — el caso de uso más común ("¿quién le gana la carrera de daño a quién?") hoy exige rearmar los dos lados a mano.

## 4. Qué se implementó (2026-08-06, dos pasadas)

- **Chips de selección rápida**, tus 6 + los 6 del rival, para Atacante y Defensor — con la lista completa de la Pokédex disponible aparte, para el caso "quiero probar con un Pokémon que no está en la partida".
- **Autocompletado de objeto/habilidad** desde el Pokémon real cuando se elige uno de los 12 de la partida, con override manual explícito.
- **Botón ⇄** para invertir atacante/defensor sin rearmar los dos lados.
- **Estado alterado del atacante, autocompletado si está ACTIVO ahora mismo.** `calc()` ya sabía aplicar quemadura al daño físico (`o.aSta`) desde antes de esta sesión — otro caso del mismo patrón que objeto/habilidad: el motor sabía, la UI nunca preguntaba. `calcActiveStatus(dex)` busca en `B.act` (m0/m1/f0/f1, los únicos slots con estado real — un Pokémon en banca no tiene, se curó al salir) y autocompleta cuando aplica, con override manual. No hay campo "dSta" — ninguna mecánica de este motor cambia el daño *recibido* por el estado del defensor, así que no se agregó uno que no haría nada.
- **Daño repartido en dobles, visible.** `calc()` ya aplicaba el ×0.75 (`o.doubles&&m.sp`) desde antes de esta sesión, pero no había ninguna indicación en pantalla de que ya estaba aplicado — con Individual seleccionado en Ajustes, el mismo cálculo daba un número distinto sin explicación visible. Ahora, cuando el formato es Dobles y el movimiento elegido pega a los dos rivales, el Resultado muestra una nota explícita.
- **Reparto de SP por slider de toque**, reusando el widget visual que "Reparto de puntos" (TUYO) ya tenía (`.sp`/`.bar`/`.bg`/`.fl`) en vez de la lista `sel()` numérica que obligaba a abrir una hoja de 33 opciones para mover un solo número. `calcSlider()` genera el mismo widget apuntando a `window.__c` en vez de al Pokémon en edición — con cuidado explícito de no colisionar con el slider real de TUYO, que comparte las mismas clases CSS (`inp.dataset.sp` vs `inp.dataset.cev` se distinguen en el handler compartido).

## 4.1 Uso fuera de combate (2026-08-06)

Angel preguntó si CALC servía también **fuera de batalla**, para armar equipo. Se probó antes de responder, y la respuesta era "corre, pero no es confiable": heredaba **siempre** el clima, terreno y pantallas de `B` (el estado de la partida) sin ninguna indicación en pantalla. Medido: con una lluvia que quedó de un combate anterior, un Acua Jet pasaba de 36 a 54 de daño (+50%); con una pantalla rival vieja, bajaba de 36 a 24. El número cambiaba y no había forma de saber por qué — la degradación silenciosa que `vision.md` prohíbe, en la única pantalla del HUD que es puro cálculo manual.

**Resuelto con un control explícito de efectos de campo**, no con un "modo fuera de combate" separado (que hubiera duplicado la pantalla entera para un solo eje de diferencia):
- **"Los del combate"** (default): comportamiento de siempre, y ahora **muestra cuáles** están activos (`calcFieldLabel()` → "lluvia · pantalla rival", o "sin efectos" cuando no hay ninguno — nunca vacío, para que se pueda confirmar de un vistazo que el número no trae nada escondido).
- **"Ninguno"**: cuenta limpia para armar equipo. Limpia **solo lo transitorio** (clima/terreno/pantallas). El formato dobles/individual **no** se toca: es una preferencia de Ajustes, no un residuo de combate.

También se etiquetaron las dos filas de chips ("Tuyos" / "Rivales"), que eran visualmente idénticas — importa más fuera de combate, donde el "rival" puede ser el equipo de ejemplo por defecto y no uno escaneado de verdad.

**Nota de método:** la primera verificación de esto casi da un falso negativo. El escenario de prueba tenía lluvia *y* pantalla a la vez, y en dobles la pantalla es ×2/3 — que contra el ×1.5 de la lluvia da exactamente ×1.0, así que el daño salía idéntico en los dos modos y parecía que el toggle no hacía nada. Se aisló cada efecto por separado (36 → 54 con lluvia sola, 36 → 24 con pantalla sola) antes de concluir nada. Vale como recordatorio: un test que da "sin diferencia" puede estar midiendo dos efectos que se cancelan, no la ausencia de efecto.

## 5. Lo que queda para una próxima sesión

- **Duplicar un cálculo** para comparar variantes (objeto A vs. objeto B) sin rearmar todo — necesita decidir dónde vive el historial (¿por turno? ¿por sesión?) antes de escribir código, no es una decisión técnica menor. Es lo único que queda de esta lista: el resto de los puntos identificados en el análisis original ya está resuelto.

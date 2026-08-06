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

## 4. Qué se implementó en esta sesión (2026-08-06)

- **Chips de selección rápida**, tus 6 + los 6 del rival, para Atacante y Defensor — con la lista completa de la Pokédex disponible aparte, para el caso "quiero probar con un Pokémon que no está en la partida".
- **Autocompletado de objeto/habilidad** desde el Pokémon real cuando se elige uno de los 12 de la partida, con override manual explícito.
- **Botón ⇄** para invertir atacante/defensor sin rearmar los dos lados.
- Reparto de EVs por slider — pendiente, ver sección 5.

## 5. Lo que queda para una próxima sesión

- **Reparto de EVs/naturaleza por slider de toque** en vez de la lista `sel()` numérica actual (que ya es más táctil que un input de texto, pero no reusa el widget de reparto que `vMine()` ya tiene).
- **Duplicar un cálculo** para comparar variantes (objeto A vs. objeto B) sin rearmar todo — necesita decidir dónde vive el historial (¿por turno? ¿por sesión?) antes de escribir código, no es una decisión técnica menor.
- **Multi-hit / daño repartido en dobles más visible** — `calc()` ya lo soporta (`o.doubles&&m.sp` aplica el ×0.75), pero la UI no lo muestra como una opción explícita, así que hoy es invisible incluso cuando aplica.
- **Estado alterado (quemado/paralizado/veneno) del atacante o defensor** — el motor no lo modela todavía en `calc()`; agregar el campo antes tiene que pasar por decidir cómo interactúa con lo que Campo ya registra en `B.act`.

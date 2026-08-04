# Modelo de conocimiento e inferencia

Especificación del sustrato que sostiene lo que el copiloto *sabe* sobre una partida: cómo entra la evidencia, cómo se derivan las conclusiones, y cómo se explica cada una. Es la base técnica de la Fase 2 (`roadmap.md`) y el lugar donde viven los detalles que `architecture.md` solo referencia.

Este documento nace de la sesión de asesoría VGC de 2026-08-01/02 (`decisions.md` #20) y de la revisión de arquitectura del 2026-08-03 (`decisions.md` #21, #22, #23).

## 0. El hallazgo que reencuadra todo el trabajo

**El proyecto ya tiene dos motores de inferencia funcionando.** Antes de diseñar nada nuevo se revisó el código real, y lo que se encontró cambia el tamaño del problema:

- **`solveBulk()`** (`hud.html`) ya enumera todos los repartos defensivos `(PS, Def, naturaleza)` compatibles con un porcentaje de daño observado y descarta los incompatibles. Eso *es* "el calculador de daño como fuente de evidencia" — ya existe.
- **`observeOrder()`** ya acota `spdMin`/`spdMax` a partir de un orden de acción observado, y **deduce Pañuelo Elección por sí solo** cuando la velocidad mínima necesaria supera lo que la especie puede alcanzar sin objeto (`f.item="Pañuelo Elección"; f.itemSure=true`). Eso *es* una cadena evidencia → hipótesis → conclusión sobre objeto — ya existe.

Lo que **no** existe es el sustrato debajo de esas reglas. Ambas escriben su conclusión directo sobre el objeto mutable del rival (`f.spdMin`, `f.bulk`, `f.itemSure`) y **descartan la evidencia que la produjo**. Las consecuencias son concretas, no teóricas:

- No se puede responder *"¿por qué creés que tiene Pañuelo?"* — el `true` no recuerda de dónde salió.
- No se puede deshacer una inferencia si el usuario corrige un dato mal cargado; hay que resetear el combate.
- No se puede llevar nada al juego 2 de un Bo3: no hay forma de distinguir lo confirmado de lo supuesto.
- Las reglas no se encadenan: acotar la velocidad no informa al cálculo de resistencia ni viceversa.

**Por eso el trabajo de Fase 2 no es "construir un motor de inferencia". Es poner el event log y el espacio de hipótesis debajo de las reglas que ya funcionan, y recién después agregar reglas nuevas.** Este encuadre es deliberadamente más chico que el ambicioso, y es el que hace la diferencia entre un sistema que una persona sola puede sostener durante meses y uno que se abandona a mitad.

## 1. Los tres niveles de conocimiento, que nunca se mezclan

Toda la arquitectura de abajo se apoya en distinguir tres cosas que hoy el código trata como si fueran la misma:

| Nivel | Qué es | Ejemplo | Se guarda en |
|---|---|---|---|
| **Hecho observado** | Ocurrió en pantalla. No se discute, no caduca, no se recalcula. | "Kingambit usó Protect en el turno 3." "Este ataque hizo 43%." "El rival se movió primero." | Event Log (§2) |
| **Inferencia** | Se derivó de hechos + reglas. Siempre reversible, siempre con su evidencia adjunta. | "Los repartos lentos quedan descartados." "Probablemente lleva Pañuelo." | Espacio de hipótesis (§3), derivado |
| **Prior de meta** | Lo que suele pasar en el formato. No dice nada de *esta* partida. | "El 62% de los Whimsicott traen Tailwind." | `MetaSnapshot` (§7), externo |

**Regla dura:** un prior de meta nunca descarta una hipótesis. Solo ordena las que siguen vivas. Confundir esto es exactamente el patrón de bug que `audit.md` §8 identifica como el recurrente del proyecto — presentar como confiable algo que se degradó en silencio.

## 2. Event Log

Registro append-only, la única fuente de verdad de la partida. Todo lo demás se deriva.

```js
// Un evento nunca se edita ni se borra. Corregir = agregar un evento de corrección.
{
  id: 17,            // monotónico, es la referencia que usan las hipótesis
  turn: 3,
  kind: "damage",
  ...payload         // según kind
}
```

Tipos de evento del MVP (los que el HUD ya puede capturar o el usuario ya marca a mano hoy):

| `kind` | Payload | De dónde sale hoy |
|---|---|---|
| `teamPreview` | los 6 del rival, confianza por especie | `SpriteMatcher` (ya existe) |
| `brought` | quiénes entraron de cada lado | panel "Quién entra" (ya existe) |
| `move` | quién, cuál, sobre quién | manual, 2 taps |
| `damage` | atacante, defensor, movimiento, % observado | manual (`vFoe()` "Confirmar por daño", ya existe) |
| `order` | A actuó antes que B | manual ("Se movió antes/después", ya existe) |
| `switch` / `ko` | entrada, salida, debilitado | manual |
| `itemRevealed` | objeto activado o revelado | manual |
| `abilityNoTrigger` | habilidad esperada que **no** se activó | nuevo (§5, regla R4) |
| `fieldChange` | clima, terreno, pantallas, Tailwind, Espacio Raro | manual (ya existe) |
| `otsImport` | listas abiertas | nuevo (Fase 4) |
| `userCorrection` | el usuario corrigió un dato | reemplaza la mutación directa de hoy |

**`userCorrection` es la pieza que hace todo lo demás reversible.** Hoy, si el usuario se equivoca al marcar una especie, la inferencia derivada de ese error queda incrustada sin forma de limpiarla. Con el log, la corrección es un evento más y el estado se re-deriva desde cero.

### 2.1 Qué deriva del log y qué no — alcance ajustado, 2026-08-03

El diseño original decía que `B` (el objeto de estado actual) pasaría a ser **una vista derivada del log**, con el criterio de aceptación "el fold del log reproduce `B` exactamente". **Al ir a implementarlo se ajustó, y conviene dejar escrito por qué**, porque suena a recorte y no lo es.

`B` mezcla dos cosas de naturaleza muy distinta:

| En `B` | Ejemplos | ¿Alimenta inferencia? |
|---|---|---|
| **Estado de campo y de UI** | turno, clima, terreno, Tailwind, pantallas, PS, etapas, quién está activo, pestaña abierta | No |
| **Evidencia sobre el rival** | daño observado, orden de acción observado, movimiento visto, ítem revelado, habilidad confirmada | Sí |

Derivar lo primero desde un log significa re-implementar toda la lógica de mutación de la app dentro de un reductor — trabajo grande, duplicación de lógica, y riesgo alto de regresión — **a cambio de nada para el objetivo de esta fase**, que es que las inferencias sean explicables, reversibles y arrastrables a un Bo3. Ninguna de esas tres cosas necesita que el clima venga del log.

**Alcance vigente:** el event log registra los **hechos que producen o corrigen inferencia**, que es el subconjunto de §2 marcado como MVP. El estado de campo sigue viviendo en `B` y persistiéndose como hasta ahora. El log viaja dentro de `B`, así que se guarda y se restaura con el mismo mecanismo, sin tocar Kotlin.

**Qué queda abierto, a propósito:** el formato de evento no asume nada sobre este recorte. Cuando la Fase 4 (resumen post-combate) necesite reconstruir la partida turno a turno, se agregan los tipos de evento de estado de campo al mismo log, sin migrar lo ya guardado. La puerta queda abierta; simplemente no se paga hoy por atravesarla.

```
Event Log (evidencia)  ──(reglas)──►  Hipótesis  ──┐
                                                    ├──►  vistas
B (estado de campo)  ─────────────────────────────┘
```

**Costo a vigilar:** re-derivar todo el estado en cada evento es O(eventos × reglas). Una partida de VGC son decenas de eventos, no miles — es despreciable. Si alguna vez deja de serlo (análisis batch de cientos de partidas, §9), se cachea el fold incremental. No optimizar antes de tener el problema.

## 3. Espacio de hipótesis

Cada Pokémon rival mantiene, por cada dimensión desconocida, un conjunto de candidatos vivos:

```js
HypothesisSet = {
  alive:     [...],                                  // todavía posibles
  ruledOut:  [{ value, byEvent: 17, rule: "speedFloor" }],  // descartados, con por qué
  confirmed: { value, byEvent: 12 } | null           // observado directamente
}
```

Dimensiones: `item`, `ability`, `moves`, `speed`, `bulk`. (Sobre por qué no hay una dimensión `spread` completa, ver §3.2.)

### 3.1 El sistema de confianza cae solo del tamaño del conjunto

`product.md` ya define tres niveles de confianza para el usuario. Con este modelo **no hay que mantenerlos a mano** — se derivan:

| Estado del conjunto | Nivel mostrado |
|---|---|
| `confirmed !== null` | ✔ **Confirmado** |
| `alive.length === 1` | ◆ **Deducido** (único sobreviviente) |
| `alive.length > 1` | ○ **Estimado por meta** (se ordenan los vivos por prior) |
| `alive.length === 0` | ⚠ **Contradicción** — fallo ruidoso, ver §3.3 |

Que el vocabulario de producto salga como consecuencia del modelo de datos, y no como una etiqueta paralela que hay que acordarse de actualizar, es exactamente el tipo de propiedad que evita la familia de bugs de `audit.md` §8.

### 3.1.1 Implementado (sprint 2.2, 2026-08-03): `item`/`ability` sin `alive` enumerado todavía

Al construir R1/R2 se aplicó el mismo argumento de §3.2 (combinatoria) a la dimensión `item`: hoy **una sola regla** (`speedFloor`, R2) concluye algo sobre el ítem del rival, así que enumerar "todos los ítems del juego menos los descartados" no tiene con qué llenarse todavía — sería una lista de un elemento disfrazada de conjunto general. Se implementaron tres niveles (`confirmed`/`deduced`/`unknown`) en vez del `HypothesisSet` completo de arriba. `ability` quedó igual, con un único nivel posible además de `unknown` (`confirmed`) porque R4 (la regla que deduciría habilidades por eliminación) todavía no existe — llega en el sprint 2.5.

**Cuándo generalizar a `alive`/`ruledOut` de verdad:** cuando R3-R5 aporten señales que reduzcan un universo real de candidatos (por ejemplo, un `MetaSnapshot` con la lista de ítems típicos de una especie, sprint 2.3+). Construirlo antes sería la misma trampa que ya se evitó con el reparto de stats — una estructura general sin un caso real que la necesite.

### 3.2 Por qué NO se enumeran repartos completos

La tentación es representar el reparto de stats como un conjunto de hipótesis sobre las 6 estadísticas. **No se hace**, por dos razones:

1. **Combinatoria.** Con 0–32 por stat y un pool de 66 repartidos entre 6 stats, el espacio es de cientos de miles de combinaciones. Enumerarlo por cada evento, en un WebView, dentro de un turno con reloj, no es viable.
2. **No hace falta.** El daño observado solo restringe el eje defensivo; el orden observado solo restringe el eje de velocidad. `solveBulk()` ya explota exactamente eso — enumera `(PS, Def, naturaleza)` con paso 2 (~450 combinaciones, instantáneo) y nada más.

**Decisión:** se mantienen **rangos por eje** (`speed: {min, max}`, `bulk: {hpRange, defRange}`), no un producto cartesiano de repartos. Es lo que el código ya hace y funciona; lo único que se agrega es la evidencia adjunta. Si alguna vez aparece una regla que de verdad necesite correlacionar ejes, se revisa — pero no antes de tener el caso concreto.

### 3.3 Contradicción = fallo ruidoso

Si un conjunto queda vacío, algo está mal: el usuario cargó un dato erróneo, el juego tiene una mecánica que el motor no modela, o una regla es incorrecta. **Nunca se "arregla" solo relajando el filtro en silencio** — ese es literalmente el anti-patrón fundacional del proyecto (`decisions.md` #8).

El comportamiento correcto: mostrarlo explícitamente ("*el daño observado no es compatible con ningún reparto normal — sospechá de baya de resistencia, pantalla o crítico*"), ofrecer deshacer el evento que produjo el conflicto, y seguir funcionando con el conjunto anterior. `solveBulk()` ya hace la primera mitad de esto (`{ok:false}` → mensaje al usuario); falta la segunda (poder deshacer).

## 4. Sin Evidence Graph explícito — y por qué

El prompt de diseño original proponía un **Evidence Graph** como entidad de primera clase: nodos de evento, nodos de hipótesis, aristas de "afecta a". **Se evaluó y se descarta.**

**Qué resolvería:** poder responder "¿por qué?" y navegar la cadena causal hacia atrás.

**Por qué no hace falta una estructura nueva:** el campo `byEvent` de cada entrada en `ruledOut`/`confirmed` (§3) ya apunta al evento que la causó, y el evento vive en un log indexado por `id`. Eso *ya es* el grafo — expresado como referencias, no como una estructura paralela que hay que mantener sincronizada. Reconstruir la cadena es seguir `byEvent` hacia atrás; mostrar "por qué" es leer esa lista.

**Qué se pierde:** consultas tipo "mostrame todas las hipótesis que dependen del evento 17" requieren un barrido en vez de una arista directa. Con decenas de eventos por partida, es irrelevante.

**Regla de oro aplicada:** una estructura de grafo explícita es más sofisticada; dos campos y un índice son más robustos, más explicables y mantenibles por una persona sola. Se elige lo segundo. Si aparece un caso de uso real que lo necesite (por ejemplo, análisis batch cruzando cientos de partidas en Fase 4+), se revisa esta decisión con ese caso en la mano.

## 5. Reglas de inferencia como datos, no como `if` desparramados

Hoy las dos reglas existentes están incrustadas en funciones específicas. Se migran a un registro declarativo, uniforme:

```js
{
  id: "speedFloor",
  on: "order",                       // tipo de evento que la dispara
  apply(event, knowledge) {
    // devuelve efectos, NO muta nada
    return [{ target, dim: "speed", action: "ruleOut", values: [...], why: "..." }];
  }
}
```

Que las reglas sean datos uniformes da tres cosas concretas: se testean una por una sin DOM ni Android (el patrón que `tests/run.js` ya usa), se agregan sin tocar el motor, y la explicación al usuario sale del mismo `why` que la regla declaró — no de un texto duplicado en la vista que se desincroniza.

### Reglas del MVP

| # | Regla | Dispara con | Efecto | Estado |
|---|---|---|---|---|
| R1 | `bulkFromDamage` | `damage` | Descarta repartos defensivos incompatibles | **Ya existe** (`solveBulk`), falta adjuntar evidencia |
| R2 | `speedFloor` | `order` | Acota `speed`; confirma Pañuelo si el piso supera el máximo sin objeto | **Ya existe** (`observeOrder`), ídem |
| R3 | `moveSeen` | `move` | Confirma el movimiento; descarta sets incompatibles | Nueva, trivial |
| R4 | `abilityNoTrigger` | `abilityNoTrigger` | Descarta una habilidad que debería haberse activado y no lo hizo | Nueva — el caso Intimidate |
| R5 | `itemActivated` | `itemRevealed` | Confirma objeto | Nueva, trivial |
| R6 | `otsKnown` | `otsImport` | Confirma todo lo que la lista abierta declare | Fase 4 |

**R4 merece una nota**, porque es el patrón que el resto de las reglas futuras va a imitar: *evento → condición esperada bajo una hipótesis → resultado observado → si no coinciden, la hipótesis se cae*. Ejemplo concreto: entra un Pokémon propio con Intimidate; bajo la hipótesis "el rival tiene Cuerpo Puro / Fuerza Mental" no debería verse la bajada de Ataque, pero se ve — esa habilidad queda descartada, con el evento como evidencia. Este esquema *expresa* la lógica en vez de codificarla suelta, que es lo que se pidió.

## 6. Velocidad como entidad de primera clase

La velocidad ya es lo que más trabajo hace en el HUD y es donde Angel identificó su mayor cuello de botella junto con el daño (`decisions.md` #20). Se formaliza:

**Composición** (ya implementada, se documenta): base → naturaleza/inversión → objeto → etapas → Tailwind → parálisis → Espacio Raro (invierte el orden). `effSpd()` y `spdRange()` cubren esto.

**Como evidencia** (parcial): cada enfrentamiento observado es un dato duro. R2 ya lo explota.

**Lo que falta: "orden probable este turno"** — no solo el orden ordenado por número, sino *qué escenarios lo invertirían*. Esto es información sobre la posición, no una recomendación de jugada, así que entra sin conflicto con `decisions.md` #21:

> Tu Sinistcha (81) actúa después de su Whimsicott (rango 90–134).
> **Se invierte si:** Espacio Raro · tu Pañuelo · su parálisis.
> **Seguro:** ninguno de tus 4 supera 134 sin ayuda.

No duplica el contador de Tailwind que el juego ya muestra (`vision.md`, principio 4) — cruza esa duración con el rango oculto del rival, que es justamente lo que el juego no da.

## 7. Datos de meta: `MetaSnapshot` y adaptadores

El motor **nunca** consume Limitless ni Pikalytics directamente. Consume un único formato interno; cada fuente externa es un adaptador que produce ese formato. Ver `architecture.md` §10 para el detalle del pipeline, el esquema real ya verificado de cada fuente, y §10.6 para los campos derivados (`roleInCore`, `speedControlMajority`).

```
Limitless Adapter  ─┐
Pikalytics Adapter ─┼──►  MetaSnapshot  ──►  Motor
Fuente futura      ─┘
```

**Uso dentro de la inferencia:** un `MetaSnapshot` **solo ordena hipótesis vivas** (§1, regla dura). Nunca descarta. Que un ítem sea raro en el formato no lo hace imposible en esta partida — tratarlo como imposible sería fabricar certeza, y es la falla que `vision.md` (principio 3, confianza calibrada) prohíbe explícitamente.

## 8. Inferencia del back y equipos similares

Con el índice de cores del `MetaSnapshot` (`architecture.md` §10.3), al ver los 6 del team preview se pueden buscar equipos de torneo muy parecidos y, con eso, estimar qué suele quedar atrás.

**Esto es un prior, no una deducción.** Cae en ○ Estimado por meta, siempre — nunca sube a ◆ Deducido por más equipos que coincidan. La única forma de subir de nivel es evidencia de *esta* partida.

**Sin porcentajes falsamente precisos.** Si tres equipos similares traen cierto Pokémon atrás, eso no es "75% de probabilidad": es "aparece en equipos parecidos". El vocabulario de `product.md` (Confirmado/Deducido/Estimado) alcanza; agregar una escala numérica sobre una muestra chica sería precisamente la falsa precisión que el producto rechaza.

## 9. Memoria de serie (Bo3) y aprendizaje del usuario

**Bo3** — el event log hace esto casi gratis, que es la razón por la que se elige esta arquitectura y no otra:

```
Series { games: [EventLog, EventLog, EventLog], carried: {...} }
```

Al empezar el juego 2, lo `confirmed` del juego 1 se inyecta como eventos iniciales del log nuevo (con su procedencia marcada). Lo meramente `alive` **no** se arrastra: el rival puede traer otros 4. Esa distinción — arrastrar hechos, no suposiciones — es exactamente lo que el modelo de tres niveles (§1) permite expresar y el estado mutable de hoy no.

**Aprendizaje del usuario** (Fase 4+, `future.md`): con event logs guardados, el análisis de patrones propios es un consumidor más del log, no un subsistema nuevo. Sobre si usar ML: **no hace falta y no se va a usar** para esto. Las preguntas reales ("¿cuántas veces subestimé un daño?", "¿qué matchups pierdo seguido?") son consultas de agregación sobre datos ya estructurados. ML aportaría opacidad justo donde el producto exige explicabilidad (`vision.md`, principio 7). Se descarta salvo que aparezca un problema concreto que las reglas y la estadística no puedan resolver.

## 10. Motor de prioridad: qué información importa más ahora

Habilitado por `decisions.md` #21. **Jerarquiza información; no elige jugadas.**

El criterio no es "qué dato es más importante en abstracto" sino **qué dato es más probable que cambie la decisión de este turno**. Un cálculo de daño que da 20% es información; uno que da 47–52% contra un rival al 50% de vida es *decisivo* — el mismo tipo de dato, muy distinta relevancia.

Formulación deliberadamente simple y auditable (nada de puntajes opacos ajustados a mano — ese error ya se cometió con `predict()`, ver `future.md`):

```
relevancia = pesoBase(tipo) × multiplicadorDeUmbral
```

- **`pesoBase`** — tabla fija y corta, editable a mano, en el orden que salió de la asesoría VGC (`decisions.md` #20): orden de velocidad crítico > rango de KO > amenaza entrante > posibilidad de Protect/prioridad > back probable > el resto.
- **`multiplicadorDeUmbral`** — se dispara cuando el dato *cruza una frontera de decisión*: un rango de daño que abarca el KO y el no-KO, un orden de velocidad que depende de un solo escenario, un rival cuyo rango de velocidad cruza el de un propio. Fuera de esos casos, vale 1.

Lo que sale de acá alimenta qué va en **Glance** (lo más relevante) y qué queda en **Peek**/**Deep** (`product.md`), sin cambiar esas tres capas. Sigue sin haber ranking de movimientos ni etiqueta "MEJOR" (`decisions.md` #19): se ordena *información*, nunca *opciones de juego*.

## 11. Qué queda explícitamente fuera

Para que el alcance no se desborde, y con la justificación de cada exclusión:

| Fuera de alcance | Por qué |
|---|---|
| Evidence Graph como estructura propia | §4 — `byEvent` + índice del log ya lo cubren |
| Enumeración de repartos de 6 stats | §3.2 — combinatoria inviable, y las reglas reales solo necesitan ejes |
| ML de cualquier tipo | §9 — opacidad donde el producto exige explicabilidad |
| Probabilidades numéricas sobre hipótesis | §8 — falsa precisión sobre muestras chicas |
| Recomendación de jugada | `decisions.md` #21 — se puede describir riesgo y consecuencia, nunca elegir la acción |
| Sincronización online del log | El log es local; sincronizarlo es Fase 5+ (`future.md`) |
| Perfilado del jugador rival | `architecture.md` — no se construyen perfiles personales, no hay identificación del rival |
| Telemetría | No se agrega "por si sirve después" |

## 12. Orden de construcción

El detalle por sprint, con criterios de aceptación, vive en `roadmap.md` (Fase 2). El orden de dependencia es:

1. **Event log en paralelo** a `B`, sin reemplazarlo — riesgo cero, se puede verificar que reproduce el estado actual antes de confiar en él.
2. **Espacio de hipótesis + migración de R1/R2** — las dos reglas que ya funcionan, ahora con evidencia adjunta. Primer beneficio visible: "¿por qué?" contestable.
3. **`MetaSnapshot` + adaptador de Limitless** — datos reales reemplazando `meta.json` estimado a mano.
4. **Motor de prioridad** — necesita que los conjuntos de hipótesis existan para saber qué es incierto.
5. **Reglas nuevas (R3–R5), PP, back** — encima de un sustrato ya probado.
6. **Bo3 / OTS (R6)** — Fase 4, ya sin trabajo de arquitectura pendiente.

La regla que ordena todo esto: **nada se construye encima del sustrato hasta que el sustrato reproduzca el comportamiento actual sin regresiones.**

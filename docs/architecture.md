# Arquitectura

Este documento traduce `vision.md` y `product.md` en estructura técnica. Las decisiones que fundamentan cada elección están numeradas en [`decisions.md`](./decisions.md); acá se explica el *cómo*, ahí el *por qué*.

## 0. Principio rector

**El motor (engine) es independiente de la plataforma. El overlay Android es el primer cliente del motor, no el motor mismo.**

Esto no es una aspiración a futuro: es la forma correcta de resolver, hoy, la instrucción de que el overlay en tiempo real es una funcionalidad principal y permanente que no debe sacrificarse por prolijidad arquitectónica. La manera de tener ambas cosas — overlay como diferencial central *y* arquitectura sana — es no mezclarlas: toda la lógica de dominio (lectura de estado, inferencia, cálculo, memoria del combate) vive en un motor portable; el overlay es la superficie de percepción y presentación sobre ese motor. Si en el futuro existe otro cliente (otra plataforma, una vista de escritorio para preparar series, lo que sea), consume el mismo motor sin reescribirlo. El overlay no se deprecia ni se relega: es y sigue siendo el cliente principal para uso personal y comunitario.

## 1. Arquitectura lógica

```
                    ┌─────────────────────┐
                    │   Meta Data Service   │  (snapshots versionados,
                    │                       │   actualización semanal)
                    └──────────┬───────────┘
                               │
[Percepción] ──eventos──▶ ┌──────────────┐
 (captura o entrada        │  EVENT LOG    │  ← fuente única de verdad,
  manual, por cliente)     │ (inmutable)   │    inmutable, con timestamp
                            └──────┬───────┘    y origen de cada evento
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            [Motor de Estado] [Motor de      [Meta Data Service]
             (HP, campo,       Inferencia]    (priors por especie)
             contadores,       (belief state:
             PP)               sets candidatos,
                                confianza)
                    │              │
                    └──────┬───────┘
                           ▼
                  [Motor de Cálculo]
                  (daño, velocidad —
                   sobre estado + hipótesis)
                           │
                           ▼
                  [Motor de Insights]
                  (traduce a las 5 preguntas
                   del jugador; decide qué
                   amerita alerta y qué no)
                           │
                           ▼
                    [Presentación]
                 Glance / Peek / Deep
                  (por cliente: Android
                   overlay hoy, otros
                   clientes a futuro)
```

El flujo es estrictamente unidireccional: Percepción → Event Log → (Estado + Inferencia) → Cálculo → Insights → Presentación. Las correcciones manuales del usuario entran por Percepción como eventos nuevos de máxima confianza; todo lo que está río abajo se recalcula a partir de ahí. Nada escribe "hacia atrás".

## 2. Módulos y responsabilidades

| Módulo | Responsabilidad | No hace |
|---|---|---|
| **Percepción** | Convertir observaciones (frames de captura o eventos de entrada manual) en eventos candidatos, con su nivel de confianza | No decide verdad; propone |
| **Event Log** | Registrar hechos inmutables, ordenados, con origen (captura/manual/corrección) | No interpreta nada |
| **Motor de Estado** | Estado determinista derivado de hechos: HP visibles, campo activo, contadores, PP | No especula |
| **Motor de Inferencia** | Mantener, por Pokémon rival, el conjunto de sets/ítems/habilidades/movimientos aún compatibles con la evidencia (eliminación, no ajuste estadístico continuo) | No calcula daño ni decide qué mostrar |
| **Motor de Cálculo** | Daño y velocidad exactos dado un estado y un set (hipotético o confirmado); agrega sobre el conjunto de hipótesis vigentes | No opina sobre qué set es más probable |
| **Motor de Insights** | Traducir cambios de estado/creencias a las cinco preguntas del jugador; **jerarquizar** qué información sube a Glance según relevancia para la decisión del turno; describir riesgos y consecuencias; decidir qué amerita una alerta y qué se queda en silencio | No elige la jugada, nunca (`decisions.md` #21): ordena información y describe la posición, no la acción |
| **Meta Data Service** | Empaquetar, versionar (por reglamento) y actualizar (semanalmente) los datasets de uso y sets del meta, combinando fuentes externas detrás de un adaptador por fuente (ver §10) | No se consulta en tiempo real durante el combate — todo lo que el motor usa en combate ya está local |
| **Presentación** | Glance/Peek/Deep, corrección de errores en 1-2 taps, por cliente | No contiene lógica de dominio |
| **Persistencia** | Guardar event logs de combates y snapshots del meta localmente | No requiere red para operar |

**Estado real vs. diseñado (verificado 2026-08-03).** Esta tabla describe el diseño objetivo. En el código actual, las capas **Event Log**, **Motor de Estado** y **Motor de Inferencia** no están separadas: el estado vive en un objeto mutable (`B` en `hud.html`) y las dos reglas de inferencia que sí existen y funcionan (`solveBulk()` y `observeOrder()`) escriben su conclusión directo sobre el objeto del rival, descartando la evidencia que la produjo. Construir ese sustrato — no reescribir las reglas, que ya andan — es el trabajo central de la Fase 2. La especificación completa está en [`inference.md`](./inference.md); el plan por sprints, en `roadmap.md`.

## 3. Modelo de datos de alto nivel

- **Species / Move / Item / Ability** — datos estáticos del juego, versionados por reglamento/parche. Identificados internamente por **slug canónico en inglés** (ver sección 5), nunca por su nombre en un idioma particular.
- **MetaSnapshot** — versión fechada de datos de uso y sets del meta, empaquetada para uso offline. Se actualiza con cadencia semanal (ver sección 4). Incluye probabilidades condicionales útiles para el motor de inferencia (ítem dado especie, compañeros frecuentes, tasa de selección en preview), un índice de combinaciones parciales (pares/tríos → equipos compatibles), y metadatos obligatorios: `regulation` (p. ej. `regMB`), `generatedAt`, `sourceCounts` y `partial` (booleano, ver §10.4). El motor elige el snapshot correspondiente a la regulación activa y puede conservar el anterior para partidas en formatos viejos.
- **Battle** — id, fecha, formato/reglamento, equipo propio, event log completo, resultado.
- **Event** — tipo, turno, payload, origen (captura/manual/corrección), confianza, timestamp.
- **BeliefState** — derivable en cualquier momento a partir del event log, pero se puede snapshotear por turno para navegar el post-combate sin recomputar todo.
- **Series** — agrupa Battles de un mismo Bo3/torneo y hereda creencias confirmadas entre juegos.
- **UserTeam** — sets propios completos, conocidos de antemano, importados una sola vez.

## 4. Persistencia y estrategia offline-first

**El producto tiene que funcionar completo sin conexión.** Esto no es una degradación aceptable, es un requisito:

- Todo lo necesario para jugar un combate vive en el dispositivo: datos estáticos del juego, el `MetaSnapshot` más reciente disponible localmente, y los equipos propios.
- El `MetaSnapshot` se actualiza en segundo plano cuando hay red disponible, con **cadencia semanal** como expectativa por defecto (el meta de un juego reciente no cambia con frecuencia horaria; sincronizar más seguido no agrega valor y sí agrega superficie de fallo). Si el snapshot local supera esa antigüedad, se lo indica de forma discreta fuera del combate — nunca durante.
- Los combates se guardan localmente como event logs (livianos: son una secuencia de eventos, no un blob de estado). La sincronización a la nube (multi-dispositivo, respaldo) es una capa opcional posterior que consume este mismo formato; no es un requisito de la Fase 0-1.
- Ningún módulo del pipeline de combate (Percepción → Insights) depende de una llamada de red para responder. Un fallo de conectividad nunca debe degradar la experiencia dentro de un combate.

## 5. Idioma e identificadores canónicos

Fuente de un bug real y grave detectado en la auditoría: el motor de daño comparaba habilidades contra literales en español mientras la fuente de datos (Pokémon Showdown) las entrega en inglés, rompiendo en silencio todos los modificadores de habilidad.

**Regla de arquitectura:** todo identificador de dominio (especie, movimiento, ítem, habilidad) usa un **slug canónico en inglés** internamente (por ejemplo `intimidate`, no `"Intimidación"` ni `"Intimidate"` como string de comparación). El español — y cualquier idioma futuro — vive exclusivamente en la capa de presentación, resuelto por una función de traducción (`t(clave)`) que nunca participa de ninguna comparación de lógica de dominio. La adopción de esta capa debe ser total, no parcial: un i18n adoptado a medias es peor que no tenerlo, porque aparenta estar resuelto sin estarlo (ver `audit.md`).

## 6. Validación de datos en build

Un script de validación corre antes de empaquetar cualquier build y verifica que los datasets (`meta.json`, `dex.json`, `sprite_index.json`, tablas embebidas) son mutuamente consistentes: que los ítems y habilidades referenciados existen en las tablas canónicas, que los slugs resuelven, que la versión de formato de cada archivo es la esperada. Este módulo no es opcional ni de "buena práctica" — es la respuesta directa a que tres de los hallazgos de la auditoría fueron exactamente este tipo de inconsistencia, no detectada hasta que un humano leyó el código línea por línea.

## 7. Puntos de extensión reservados (sin implementar todavía)

Estos puntos existen en el diseño de la arquitectura **para que agregarlos en el futuro no requiera reescribir el dominio**, pero hoy no tienen implementación ni afectan el comportamiento del producto, que se distribuye completo.

### 7.1 Entitlements (licencia / modo pro-free)

El producto se desarrolla y distribuye hoy como una versión completa, sin ninguna función bloqueada. Cuando en el futuro exista una versión con capacidades limitadas y desbloqueo por clave, esa lógica va a vivir en un módulo de **entitlements** consultado únicamente por la capa de Presentación (qué se muestra, qué panel está disponible) — nunca por el Motor. El Motor de Inferencia, de Cálculo o de Insights no debe conocer la existencia de un plan pro o free bajo ninguna circunstancia: no recibe ni evalúa ningún flag de licencia. Esto garantiza que agregar el sistema de licencias en el futuro sea un cambio aislado a Presentación, sin tocar dominio.

### 7.2 Publicidad

No se implementa ninguna forma de publicidad por ahora. Si en el futuro se agrega, la arquitectura debe poder alojarla sin cambios estructurales: un espacio de anuncio es, en el peor de los casos, un componente más de la capa de Presentación en superficies frías (pantalla de resumen post-combate, biblioteca de historial) — nunca en Glance/Peek durante el combate, y nunca con acceso a datos del Motor más allá de lo que ya es público en pantalla. No se reserva ningún gancho dentro del Motor para esto: no hace falta, porque publicidad es puramente presentación.

### 7.3 Multi-cliente / multi-plataforma

Si en el futuro existe otra plataforma o cliente (otro sistema operativo, una vista de escritorio, lo que sea), ese cliente implementa su propia capa de Percepción y Presentación y consume el mismo Motor descrito en la sección 1-2. El requisito para que esto sea así de simple es que el Motor no tenga, hoy, ninguna dependencia de Android/Kotlin en su lógica de dominio — algo que el proyecto ya viene haciendo bien al concentrar la lógica en JS y usar Kotlin solo como cascarón de plataforma (captura de pantalla, ventana, permisos). Esa separación se mantiene y se refuerza, no se relaja.

## 8. Testing y contratos

- Todo objeto que cruza entre módulos (por ejemplo, lo que devuelve el Motor de Inferencia y lo que consume Presentación) debe tener una forma documentada (JSDoc `@typedef` como mínimo) para que un cambio de forma en un lado sea detectable sin depender de una lectura manual línea por línea — esto es exactamente lo que faltó en el mismatch `predict()`/`vPre()` documentado en `audit.md`.
- Una suite de pruebas mínima vive en el repositorio (no en scripts ad-hoc descartados sesión a sesión). Cubre como mínimo: el pipeline evento → estado → inferencia → cálculo con casos conocidos, y el validador de datos de la sección 6.
- Ningún módulo del pipeline de combate degrada su salida en silencio. Ante datos inconsistentes o ausentes, reporta explícitamente en vez de producir un resultado plausible pero incorrecto (principio de fallo ruidoso, ver `vision.md`).

## 9. Riesgos técnicos a considerar en decisiones futuras

- El juego recibe reglamentos y parches nuevos con cierta frecuencia: todo dato de especies/movimientos/sets necesita versionado por reglamento desde el modelo de datos, no como un agregado posterior.
- La capa de Percepción por captura de pantalla depende de la UI del juego; cualquier cambio de esa UI puede romperla. El Motor de Inferencia debe seguir funcionando con entrada manual aunque la Percepción automática falle — esto ya es un requisito de diseño (degradación elegante, ver `vision.md`), no solo una contingencia.
- El bus de conocimiento del proyecto no debe vivir únicamente en el historial de conversaciones de desarrollo: por eso esta documentación existe y se mantiene versionada junto con el código.

## 10. Pipeline de datos de meta

Diseño concreto del `Meta Data Service`, resultado de la investigación de fuentes. Reemplaza al stub actual `build_meta.py` (`fetch_usage()` devuelve `{}` siempre — ver `audit.md` §5). Corre en la PC del desarrollador, no en el teléfono; el artefacto que produce se copia a `assets/` y/o se sube a la URL de actualización remota que la app ya soporta (`Android.updateMeta(url)`).

### 10.1 Fuentes, en orden de prioridad

- **Primaria — API pública de Limitless TCG** (`https://play.limitlesstcg.com/api`). Sin clave para los endpoints de torneos (`/tournaments`, `/tournaments/{id}/standings`, `/tournaments/{id}/pairings`). Devuelve equipos crudos (campo `decklist` en standings) de torneos reales. Es la fuente raíz de la que beben casi todos los agregadores de terceros — usarla directo evita depender de que un tercero siga existiendo. Los movimientos/habilidad/nature solo están presentes cuando el torneo usó envío de teamlist abierto — la cobertura de "qué 6 Pokémon" va a ser mayor que la de "sets completos", y el pipeline debe tolerar esa asimetría sin fallar. Esquema real verificado el 2026-08-01, ver 10.1.1.
- **Secundaria — rutas AI de Pikalytics** (`/ai/pokedex/<formato>/<pokemon>`, Markdown estructurado vía `llms.txt`/`llms-full.txt`). Da agregados ya calculados (uso %, win rate, ítems/habilidades/movimientos/spreads/naturalezas/compañeros) para no tener que recalcular todo desde cero. Cadencia de actualización mensual para varios agregados — si se necesita frescura semanal real, esos agregados puntuales se recalculan directo desde los equipos crudos de Limitless en vez de esperar a Pikalytics.
- **Descartadas para scraping automatizado — Pokémon Zone y Champions Hub.** Sus términos de servicio lo prohíben explícitamente. Se pueden usar como referencia conceptual/visual manual, nunca como fuente automatizada del pipeline.
- **No usadas por ahora, quedan documentadas como alternativas de respaldo:** Champions Lab y championshub.gg (agregadores sin API pública documentada), Smogon/Showdown usage stats (secundarias, formato oficial es in-game), pokedata.ovh (VGC presencial, sin cobertura de esta regulación al momento de relevarlo).

### 10.1.1 Esquema real confirmado (verificado 2026-08-01, Fase 2 hito 1)

Inspeccionado contra respuestas reales de la API, no contra documentación (no existe documentación formal de este esquema):

- **`GET /games`** → el juego es `"VGC"` (`Pokémon VGC`), y sus `formats` incluyen exactamente `"M-B": "Regulation Set M-B"` — coincide letra por letra con el `regulation:"M-B"` que ya usa `meta.json`. No hace falta ningún mapeo de traducción entre el nombre de regulación del proyecto y el de Limitless.
- **`GET /tournaments?game=VGC&format=M-B&limit=N`** → array de `{id, name, date, players}`. El `id` (string hex, no numérico) es el que hace falta para pedir standings.
- **`GET /tournaments/{id}/standings`** → array de entradas de jugador:
  ```json
  {
    "name": "KST | KAMPFI",
    "country": "DE",
    "decklist": [
      {
        "id": "sinistcha",
        "name": "Sinistcha",
        "item": "Kasib Berry",
        "ability": "Hospitality",
        "attacks": ["Matcha Gotcha", "Life Dew", "Rage Powder", "Trick Room"],
        "nature": "Calm",
        "tera": null
      }
    ],
    "placing": null,
    "player": "die_kampfstube",
    "record": {"wins": 4, "losses": 1, "ties": 0},
    "deck": {},
    "drop": 5
  }
  ```
  `decklist[].id` es un slug en inglés (`"sinistcha"`, `"floette-eternal"`) — mapea directo a los slugs canónicos que el proyecto ya usa (decisión #7), sin traducción. `item`/`ability`/`attacks` vienen en inglés, nombre de display (no slug) — pasan por `findItem()`/`findAbility()`/`findMove()` igual que cualquier otro texto en inglés que ya entra al motor. **No hay campo de reparto de stats/EVs** en las respuestas inspeccionadas (ni siquiera en torneos con `decklist` completo) — el subesquema real es más angosto de lo que `§10.1` conjeturaba: cubre especie/ítem/habilidad/movimientos/naturaleza, nunca el spread numérico. Esto no bloquea el índice de combinaciones parciales (§10.3, que no depende de spreads).
  `tera` está presente en el esquema pero salió `null` en todas las muestras revisadas — esperable, ya que Champions reemplaza Terastalización por Megaevolución (`decisions.md`); no se puede descartar todavía que el campo tenga otro uso en algún torneo, pero no es una señal a la que este proyecto deba prestarle atención.
  `placing` salió `null` en torneos sin terminar de completar el cálculo de posiciones — el generador tiene que tolerar ese caso, no asumir que siempre viene poblado.

**Repartos habituales, verificado también contra Pikalytics (2026-08-01):** se probó `GET /ai/pokedex/battledataregmbs3/<especie>` (formato real: `battledataregmbs3`, resuelto vía `llms.txt` — confirma además que Pikalytics ya llama al juego "Pokemon Champions" internamente, no VGC genérico). Los movimientos/ítems/habilidades/compañeros sí vienen con distribución completa de porcentajes, y sí usan la escala real de Champions (0–32 por stat, no el 0–252 de los juegos principales — confirmado con un ejemplo real: `32/32/0/0/2/0`). Pero el reparto solo aparece como **una mención suelta del build más usado** (una oración tipo FAQ, sin tabla ni desglose de alternativas), no como una distribución completa por porcentaje igual que el resto de los campos. Conclusión: ni Limitless ni Pikalytics dan hoy una base de datos real de repartos con la misma cobertura que items/habilidades/movimientos. `vFoe()` → "Repartos habituales" sigue dependiendo de `meta.json` estimado a mano hasta que aparezca una fuente mejor, o hasta que se decida explícitamente con Angel degradar esa sección a "top 1 reparto conocido, sin desglose" en vez de la lista completa actual — **decisión de producto pendiente, no se resuelve acá.**

### 10.2 Formato de almacenamiento y umbral de migración

Se mantiene **JSON plano**, consistente con el resto del proyecto (sin SQLite, sin Room) mientras se cumplan estas condiciones:
- El índice de combinaciones parciales (pares/tríos → equipos + agregados condicionados) se mantiene por debajo de **~5–8 MB**.
- El parseo del JSON en el arranque del WebView no supera **~1–2 segundos**.

**Migrar a SQLite** (vía `sql.js`/`wa-sqlite` dentro del WebView, o un puente nativo con Room) únicamente si el índice supera **~10 MB**, si aparecen consultas que requieren joins en tiempo de ejecución, o si el arranque se degrada más allá del umbral anterior. Hasta que eso ocurra, JSON gana por simplicidad — no migrar preventivamente.

### 10.3 Índice de combinaciones parciales

Viable y ya validado como concepto por productos de terceros (Pokémon Zone publica "team cores" de 2-4 Pokémon con sus completions más probables). Se construye desde los equipos crudos de Limitless:
- Se indexan pares y tríos de especies que aparecen en al menos un umbral mínimo de equipos observados (referencia: ~1% de las listas, o un piso absoluto de 3–5 equipos — el que sea más restrictivo evita ruido de combinaciones anecdóticas).
- Cada entrada del índice mapea a una lista de IDs de equipo (no duplica los sets completos) más agregados precomputados: Pokémon restantes más probables con frecuencia, ítems/habilidades/leads condicionados a esa combinación.
- Este índice es el que alimenta la predicción de Team Preview (`predict()`) con datos reales en vez del `meta.json` estimado a mano actual.

### 10.4 Generación, versionado y degradación

- **Script generador** (Python, en línea con el resto del pipeline de datos del proyecto): (a) descarga de Limitless respetando las cabeceras de rate limit con backoff — es un proceso batch semanal, no en tiempo real, así que el riesgo de límite de tasa es bajo; (b) enriquece opcionalmente con Pikalytics; (c) filtra a las especies legales de la regulación activa; (d) precompone agregados e índice parcial; (e) emite un único artefacto versionado con los metadatos descritos en §3 (`regulation`, `generatedAt`, `sourceCounts`, `partial`).
- **Degradación elegante, no negociable:** si una fuente falla durante la generación, el script igual emite el dataset con lo que sí pudo obtener y marca `partial: true` — nunca rompe la generación entera por la caída de una fuente. La app, a su vez, funciona con el último dataset empaquetado si la descarga remota falla, consistente con el requisito de offline-first (§4).
- **Modo de importación manual como funcionalidad de primera clase**, no como contingencia menor: pegar un teamlist o importar un JSON de equipo cubre tanto el caso de que una fuente externa desaparezca como el de formatos/regulaciones nuevas que todavía no tienen datos agregados.
- Cada fuente externa vive detrás de un adaptador propio dentro del Meta Data Service, para poder sustituir o agregar fuentes sin tocar el resto del pipeline ni el modelo de datos consumido por el Motor.

### 10.5 Umbrales que ameritan revisar esta sección

- Si Limitless cerrara o limitara su API de forma significativa → caer a datos manuales/importados y a los agregados de Pikalytics mientras exista otra fuente viable.
- Si el índice de tríos superara ~10 MB o el arranque del WebView pasara de ~2s → migrar el índice a SQLite (§10.2).
- Si Pikalytics dejara de exponer sus rutas `/ai/` → recalcular agregados directo desde los equipos crudos de Limitless, que ya se tienen igual.

### 10.6 Campos del `MetaSnapshot` confirmados por la sesión de asesoría VGC (2026-08-01/02, `decisions.md` #20)

Además de uso%/win rate/3-cores (§10.3), el generador tiene que emitir, por especie, dos campos derivados que salieron directamente de la sesión de investigación + preguntas a Angel — ninguno de los dos necesita una fuente nueva, ambos se calculan sobre el mismo `decklist` crudo de Limitless (§10.1.1):

- **`roleInCore`** (texto corto, ej. `"suele setear Tailwind"`, `"suele liderar"`, `"suele quedarse en banca"`) — el rol que una especie cumple habitualmente dentro de los equipos/cores donde aparece. Angel, pregunta 5: quiere ver "el rol que suelen ser esas especies en ese equipo en específico", no solo el ítem/habilidad más común. Se deriva contando, para cada especie, en qué proporción de sus decklists aparece con un movimiento de control de velocidad, o en qué proporción aparece entre los primeros 2 de la selección declarada (si el torneo trae esa señal) — no es un cálculo nuevo de dominio, es un agregado más sobre los mismos datos crudos.
- **`speedControlMajority`** (booleano + %, ej. `{tool:"tailwind", pct:0.8}`) — si una proporción mayoritaria (umbral a definir, ~60-70%) de los sets observados de esa especie trae Tailwind/Trick Room/un movimiento que inflige parálisis, se marca. Angel, pregunta 7: "generalmente lo detecto solo... pero no estaría de más una ayuda visual cuando la mayoría de los pokemon de esa especie traiga un control de velocidad o mecánica en específico" — pidió explícitamente que **no** sea una inferencia trivial ("si es algo que yo pueda saber con mucha facilidad, no aporta mucho", pregunta 8): el umbral de mayoría real sobre datos de torneo es justamente el tipo de señal que no se puede estimar a ojo mirando una sola partida.

- **`spreadEstimate`** — estimación de reparto derivada, con su razonamiento adjunto. **Resuelve la decisión que quedó pendiente el 2026-08-01** ("¿'Repartos habituales' se degrada o sigue estimado?"). Angel eligió una tercera opción mejor que las dos que le presenté: *"No dará el reparto habitual de stats, pero sí da variedad de equipo, que use los stats de los principales equipos donde aparece para crear su propia estimación."* O sea: ninguna fuente da una distribución real de repartos (verificado en §10.1.1), pero sí dan **contexto de equipo**, y de ahí se puede derivar una estimación fundamentada en vez de una inventada. Composición:
  1. El único reparto conocido que publica Pikalytics para esa especie, si existe (ej. Kingambit `32/32/0/0/2/0`, 13.7% de los sets).
  2. El rol que cumple en los equipos donde aparece (`roleInCore`, arriba): un Pokémon que aparece seteando Tailwind sugiere inversión en velocidad; uno que aparece como respuesta defensiva, en resistencia.
  3. Los movimientos comunes de esa especie, que acotan qué inversión tiene sentido (un set físico no invierte en Ataque Especial).

  **Se muestra siempre como ○ Estimado, nunca como ◆ Deducido**, con su razonamiento inspeccionable ("estimado desde el reparto más usado + rol en los equipos donde aparece"). Y como todo prior (decisión #23): **ordena hipótesis, nunca las descarta.** En cuanto haya un daño observado, `solveBulk()` descarta repartos por evidencia real y esa deducción le gana a la estimación — el orden de precedencia lo fija `inference.md` §1.

Estos tres campos se muestran en Rival/Previa como **tags informativos con su nivel de confianza** (Confirmado/Deducido/Estimado, `product.md` §"Sistema de confianza") — nunca como recomendación, consistente con decisión #1/#19: informan que una especie *suele* tener ese rol, no sugieren jugarla de una forma.

**No implementado todavía** — depende del script generador completo de §10.4, que todavía no existe. Documentado acá para que cuando se construya el generador, estos campos salgan desde el diseño inicial y no como un parche after-the-fact.

## 11. Dos features chicas, independientes del pipeline de meta — planeadas, no implementadas

Salieron de la misma sesión (`decisions.md` #20), pero a diferencia de §10.6 no dependen del script generador de Fase 2: se pueden construir en cualquier momento, con datos que ya están disponibles hoy. Quedan documentadas y no implementadas a propósito — Angel prefiere separar la etapa de análisis/documentación/plan de la de escribir código, para no quemar ventana de contexto en cambios que todavía no se decidió hacer ahora mismo.

### 11.1 Descripción de habilidad expandible (Peek)

**Qué falta:** una tabla `ABIL_DESC` (slug → texto en inglés) en `hud.html`, al lado de `ABIL_I18N` (línea ~485). Se muestra en Peek (`vFoe()`) como texto secundario/expandible, nunca en Glance (`product.md`, regla de qué entra en el primer vistazo) — Angel: "no es información primordial, pero sería genial que la pueda dar si la necesito" (pregunta 5).

**Fuente y método, ya verificados end-to-end (2026-08-02) — no hace falta re-investigar, solo re-ejecutar:**
- PokeAPI (`https://pokeapi.co/api/v2/ability/<slug-con-guiones>`) — mismo origen que ya generó `ABIL_I18N` (decisión #7).
- El slug de la API se arma a partir del **nombre en inglés ya guardado en `ABIL_I18N[x].en`** (ej. `"Armor Tail"` → `armor-tail`), no del slug interno de una palabra (`armortail`) — el slug interno no tiene los espacios que hacían falta para reconstruir el separador, es un callejón sin salida para este propósito.
- Campo a extraer: `effect_entries` con `language.name === "en"`, tomar `short_effect`.
- **Cobertura confirmada: 201/201 habilidades encontradas**, incluidas las propias de Champions que no existen en los juegos principales (`eelevate`, `firemane`, `dragonize`, `megasol`, `hungerswitch`, `spicyspray`, `supersweetsyrup`, `supremeoverlord`, `piercingdrill`) — PokeAPI ya tiene estos datos cargados. No hay que prever un fallback de "sin descripción", el caso no aparece hoy (sí conviene que el código lo tolere igual, por las dudas de que la cobertura cambie).
- Solo en inglés — no se tradujo a español porque no es información primordial (Angel) y la cobertura de `effect_entries` en español de PokeAPI es más floja para habilidades nuevas; mostrarla en inglés siempre es consistente con cómo ya se maneja el resto de los datos crudos del juego (decisión #7).

### 11.2 Seguimiento de PP en movimientos clave (Peek/Campo)

**Qué falta:** `product.md` ya prometía esto en la definición original de Peek y nunca se construyó (brecha real, confirmada por Angel: "muy pocas veces lo cuento... o cuando ya estamos en late game y no puedo recordar con precisión", preguntas 3 y 4).

**Por qué no se hizo en la misma sesión que 11.1:** a diferencia de la descripción de habilidad, esto necesita un dato nuevo que hoy no existe en ningún lado del proyecto — PP máximo por movimiento. La tabla `MV` (`hud.html`, línea ~364) no tiene ese campo (`mv(k)` expone `p,t,c,sp,self,pri,acc,note` — nunca PP). Antes de escribir código hace falta:
1. Conseguir el PP máximo real de cada movimiento (PokeAPI `/move/<slug>` trae `pp`, mismo patrón de fuente que 11.1) y agregarlo como un nuevo índice a cada entrada de `MV` — esto es una migración de datos sobre una tabla que ya tiene ~150+ movimientos, no una tabla nueva chica; conviene un script dedicado con verificación (`validate_data.py`), no una edición a mano.
2. Diseñar el estado: PP no se puede leer por OCR ni por texto en pantalla — es manual, igual que hoy es manual marcar qué movimientos ya se vieron (`f.moves`). Propuesta: `f.ppUsed = {}` (mapa `movimiento → veces usado`, inicializado vacío por Pokémon rival), con un botón "+1 usado" al lado de cada movimiento ya revelado en Peek, mostrando `PPmax - usado / PPmax`. Mismo patrón de interacción que ya existe (2 taps, sin teclado), no una UI nueva.
3. ~~Decidir con Angel si esto se muestra para **todos** los movimientos revelados o solo para los "clave"~~ — **Resuelto 2026-08-03: se muestra el PP de todos los movimientos.** Angel: *"Sería bueno que muestre el pp de todos los ataques, si vamos a hacer las cosas hagámosla bien. Es info importante en algunos contextos."* La preocupación por el ruido en Glance se resuelve por otra vía y ya está cubierta: el motor de prioridad (`inference.md` §10) decide qué sube a Glance; el PP completo vive en Peek, que es la capa donde el detalle es bienvenido. No hace falta recortar el dato en origen — recortar por las dudas hubiera sido decidir por el usuario algo que él ya decidió.

Queda como el próximo candidato claro para retomar cuando se pase de "documentar y planear" a "escribir código" — el plan de arriba ya resuelve el cómo, falta solo ejecutarlo (Sprint 2.5, `roadmap.md`).

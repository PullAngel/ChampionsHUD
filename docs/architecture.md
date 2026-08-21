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

### 7.4 Fork de diseño (mismo Motor, Presentación nueva desde cero) — `decisions.md` #26

Distinto del §7.3: no es "el mismo diseño en otra plataforma", es **el mismo Motor con una Presentación pensada desde cero**, sin heredar ninguna decisión de interfaz ya tomada (Glance/Peek/Deep, el sistema de confianza visual de la decisión #24, la disposición de paneles) — planeado por Angel para más adelante, como una segunda versión del producto diseñada en Claude Design, para comparar contra la actual y quedarse con la más simple de usar.

**Qué ya hace que esto sea viable sin reescribir nada, verificado, no aspiracional:**
- **La frontera Motor/Presentación existe de hecho, no solo en el diagrama.** Todo lo que vive en `hud.html` antes de `function vPre(){` es el Motor: se extrae y corre en un sandbox de Node sin DOM ni Android, y es exactamente lo que `tests/run.js` ejecuta en sus 223 casos. Todo lo que viene después (`vPre()`, `vFoe()`, `vCalc()`, `wire()`…) es Presentación: arma HTML como texto y engancha eventos del DOM real. Un fork de diseño **no toca nada antes de ese corte** — importa el Motor tal cual y construye su propia capa de vistas encima.
- **El adaptador `IO`** (`hud.html`, junto a la guarda `has`): las 8 llamadas de entrada/salida que el Motor necesita del entorno (`loadDex`, `haptic`, `keepOpen`, `saveBattle`, `loadTeam`, `saveTeam`, `loadMeta`, `loadBattle`) viven agrupadas en un único objeto con nombre, no sueltas por el archivo. Un cliente nuevo que corra en otro contexto (por ejemplo, un fork que persista en `localStorage` de navegador en vez del puente `Android` del WebView) reimplementa `IO` una sola vez — el resto del Motor no sabe ni le importa qué hay detrás. Un test permanente (`tests/run.js`) falla si aparece una llamada a `Android.*` fuera de ese objeto.

**Qué queda deliberadamente sin resolver hasta que el fork sea un trabajo real, no una intención:** cómo se empaqueta el Motor para dos Presentaciones a la vez (¿el mismo `hud.html` recortado, un archivo separado, un paquete?) es una decisión de packaging que no vale la pena tomar antes de tener un segundo consumidor real — resolverla ahora sería sobre-construir sin caso de uso (mismo criterio que ya aplica el proyecto en `future.md`). Lo que sí se sostiene ya es la propiedad que hace esa decisión futura barata: el Motor no sabe que existe una Presentación, y punto.

## 8. Testing y contratos

- Todo objeto que cruza entre módulos (por ejemplo, lo que devuelve el Motor de Inferencia y lo que consume Presentación) debe tener una forma documentada (JSDoc `@typedef` como mínimo) para que un cambio de forma en un lado sea detectable sin depender de una lectura manual línea por línea — esto es exactamente lo que faltó en el mismatch `predict()`/`vPre()` documentado en `audit.md`.
- Una suite de pruebas mínima vive en el repositorio (no en scripts ad-hoc descartados sesión a sesión). Cubre como mínimo: el pipeline evento → estado → inferencia → cálculo con casos conocidos, y el validador de datos de la sección 6.
- Ningún módulo del pipeline de combate degrada su salida en silencio. Ante datos inconsistentes o ausentes, reporta explícitamente en vez de producir un resultado plausible pero incorrecto (principio de fallo ruidoso, ver `vision.md`).

## 9. Riesgos técnicos a considerar en decisiones futuras

- El juego recibe reglamentos y parches nuevos con cierta frecuencia: todo dato de especies/movimientos/sets necesita versionado por reglamento desde el modelo de datos, no como un agregado posterior.
- La capa de Percepción por captura de pantalla depende de la UI del juego; cualquier cambio de esa UI puede romperla. El Motor de Inferencia debe seguir funcionando con entrada manual aunque la Percepción automática falle — esto ya es un requisito de diseño (degradación elegante, ver `vision.md`), no solo una contingencia.
- El bus de conocimiento del proyecto no debe vivir únicamente en el historial de conversaciones de desarrollo: por eso esta documentación existe y se mantiene versionada junto con el código.

## 10. Pipeline de datos de meta

Diseño concreto del `Meta Data Service`, resultado de la investigación de fuentes. `build_meta.py` implementa este diseño desde el 2026-08-03 (Fase 2, sprint 2.3 — ver `roadmap.md`) y ya se corrió contra la API real (`audit.md` §5.9). Corre en la PC del desarrollador, no en el teléfono; el artefacto que produce se copia a `assets/` y/o se sube a la URL de actualización remota que la app ya soporta (`Android.updateMeta(url)`).

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

**Repartos habituales, verificado también contra Pikalytics (2026-08-01):** se probó `GET /ai/pokedex/battledataregmbs3/<especie>` (formato real: `battledataregmbs3`, resuelto vía `llms.txt` — confirma además que Pikalytics ya llama al juego "Pokemon Champions" internamente, no VGC genérico). Los movimientos/ítems/habilidades/compañeros sí vienen con distribución completa de porcentajes, y sí usan la escala real de Champions (0–32 por stat, no el 0–252 de los juegos principales — confirmado con un ejemplo real: `32/32/0/0/2/0`). Pero el reparto solo aparece como **una mención suelta del build más usado** (una oración tipo FAQ, sin tabla ni desglose de alternativas), no como una distribución completa por porcentaje igual que el resto de los campos. Conclusión: ni Limitless ni Pikalytics dan hoy una base de datos real de repartos con la misma cobertura que items/habilidades/movimientos.

**Resuelto (sprint 2.7, 2026-08-04): `championsbattledata.com/api` sí da esto.** Investigado a pedido de Angel junto con el resto de fuentes candidatas (Champions Battle Data, Limitless, Pikalytics, Showdown, OP.GG, MunchStats, Victory Road) — verificado contra la API real, no contra su documentación. Da reparto de EVs (escala 0–32) y naturaleza real, cada uno con % de uso propio, con la misma cobertura que items/movimientos/habilidades. Verificado que refleja la misma regulación que Limitless (los % de movimientos/ítems de Kingambit coinciden de forma muy cercana entre las dos fuentes) antes de instalar nada. `build_meta_v2.py` lo cruza contra el `meta.json` de Limitless (sin reemplazarlo, sets/cores siguen siendo solo de Limitless — CBD no da combos de 4 movimientos) y `vFoe()` → "Repartos habituales" ya no depende de un archivo estimado a mano — ver `roadmap.md`, Sprint 2.7.

### 10.2 Formato de almacenamiento y umbral de migración

Se mantiene **JSON plano**, consistente con el resto del proyecto (sin SQLite, sin Room) mientras se cumplan estas condiciones:
- El índice de combinaciones parciales (pares/tríos → equipos + agregados condicionados) se mantiene por debajo de **~5–8 MB**.
- El parseo del JSON en el arranque del WebView no supera **~1–2 segundos**.

**Migrar a SQLite** (vía `sql.js`/`wa-sqlite` dentro del WebView, o un puente nativo con Room) únicamente si el índice supera **~10 MB**, si aparecen consultas que requieren joins en tiempo de ejecución, o si el arranque se degrada más allá del umbral anterior. Hasta que eso ocurra, JSON gana por simplicidad — no migrar preventivamente.

#### Contrato de esquema: los cambios son aditivos (2026-08-21)

Los tres archivos de datos declaran su versión de esquema: `meta.json` en `schema`, `dex.json` y `sprite_index.json` en `v`. **Esa versión describe el FORMATO, no el contenido** — el contenido lo fecha `updated`/`generatedAt`.

La regla que hace escalable agregar capas de datos nuevas:

- **Agregar un campo NO sube la versión.** El motor lee todo con `?.`/`||`, así que ignora lo que no conoce. Un `meta.json` con una dimensión nueva funciona sin cambios en una app vieja, y un `meta.json` viejo funciona en una app nueva (el campo simplemente no está y la vista que lo usa no se muestra). Esto es lo que permite publicar datos por internet sin coordinar la actualización de la app (§10.7).
- **Solo se sube la versión al RENOMBRAR o QUITAR un campo**, que es lo único capaz de romper a un lector viejo. Si eso pasa, el lector nuevo tiene que soportar los dos formatos durante una transición, o negarse explícitamente a leer un esquema que no entiende — nunca leerlo a medias.

**Esto no es una convención escrita y nada más: es un test.** `tests/run.js` → "contrato de esquema de meta.json" alimenta al motor con (a) campos desconocidos arriba y por especie, (b) una especie sin ningún campo opcional, (c) un `meta.json` completamente vacío, y verifica que todas las funciones que consumen META sigan funcionando. Se probó rompiéndolo a propósito (sacándole la lectura defensiva a `probableMoves()`): falla y nombra el problema.

El caso (b) no es hipotético — hoy hay **48 especies así** en el `meta.json` instalado: aparecen en Champions Battle Data pero no en la muestra de torneos de Limitless, así que llegan sin `usage`, sin `moves` y sin `sets`.

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

- **`sets`** (sprint 2.5, `roadmap.md` R3) — combos de 4 movimientos que aparecieron **completos, de verdad, en el mismo Pokémon** dentro de un decklist real, no una combinación artificial armada a partir de los `moves` top por separado (que solo dice frecuencia individual, no qué va junto). Cada entrada: `{moves:[4 nombres],count,pct}`, más `setsSample` al nivel de la especie — el denominador real (equipos con los 4 movimientos resueltos), casi siempre más chico que `usage×tc` porque un decklist con un solo movimiento sin resolver se descarta entero en vez de guardar un set trunco de 3 (`build_meta.py`, principio de "fallo ruidoso"). Es lo que permite `compatibleSets()` en `hud.html`: de los sets conocidos, cuáles siguen siendo compatibles con lo que ya se le vio usar al rival — un set que no incluye un movimiento ya confirmado queda descartado. Prior de meta, nunca certeza: no dice qué trae seguro, angosta el espacio de hipótesis con evidencia (`inference.md` §3/§5).

Estos campos se muestran en Rival/Previa como **tags informativos con su nivel de confianza** (Confirmado/Deducido/Estimado, `product.md` §"Sistema de confianza") — nunca como recomendación, consistente con decisión #1/#19: informan que una especie *suele* tener ese rol, no sugieren jugarla de una forma.

**Estado:** `roleInCore`/`speedControlMajority`/`sets` — **HECHOS** (sprints 2.3 y 2.5, generados de verdad contra Limitless). `spreadEstimate` — **HECHO** (sprint 2.7, 2026-08-04) — no terminó siendo una estimación heurística compuesta como preveía el diseño original de este párrafo (Pikalytics + rol + movimientos), sino datos reales de reparto/naturaleza de Champions Battle Data. Los cuatro campos de esta lista están hoy instalados en `assets/meta.json` y consumidos por `vFoe()`.

### 10.7 Generación periódica y distribución (2026-08-21)

#### Un comando, tres niveles

`update_data.py` reemplaza el proceso anterior de correr cuatro scripts a mano en orden, recordando cuál dependía de cuál y copiando archivos a `assets/` con `cp`. Los niveles salen de la **frecuencia real de cambio de cada fuente**, no de una división arbitraria:

| Comando | Cuándo | Qué corre | Costo |
|---|---|---|---|
| `python update_data.py meta` | semanal | meta de Limitless + cruce con Champions Battle Data | ~2-3 min |
| `python update_data.py dex` | parche de balance (nerfeos/bufeos) | lo anterior + dex de Showdown | +1 min |
| `python update_data.py completo` | Pokémon u objetos **nuevos** en Champions | lo anterior + índice de sprites | +2-4 min |

La cadena de dependencias es real, no una convención: `sprites → dex → meta → meta+CBD`. `sprite_index.json` es la fuente de verdad de **qué especies existen** en Champions (sale de la categoría de sprites del propio juego), así que es el único paso capaz de descubrir especies nuevas — y el único lento. Por eso no se corre siempre.

#### Staging → validar → promover

Nada pisa `app/src/main/assets/` hasta que `validate_data.py` da OK sobre lo recién generado. Se genera en `_staging/`, se valida ahí (`validate_data.py --datos`), y solo entonces se promueve. Si falla, lo instalado sigue intacto y los archivos quedan en `_staging/` para inspeccionarlos.

No es celo de más: la app corre offline y confía en que estos tres archivos son mutuamente consistentes. Un `meta.json` que nombre un movimiento que el dex no conoce no rompe con una excepción — **degrada en silencio**, que es el patrón de bug recurrente de este proyecto (`audit.md` §8). **La red se probó sola:** la primera corrida real falló (un torneo de Limitless con un emoji en el nombre reventaba la consola cp1252 de Windows) y no instaló nada.

#### Distribución sin APK nuevo

El requisito: que un usuario con la app instalada reciba datos nuevos sin reinstalar, y que eso escale a miles de usuarios.

**Lo que había, y su hueco.** `updateMeta(url)` existía desde antes pero **solo actualizaba `meta.json`** — `dex.json` y `sprite_index.json` se leían directo de `assets/`, sin ninguna vía de actualización. O sea: con Pokémon nuevos, hacía falta APK nuevo sí o sí, que es justo el caso que más importa. Además pedía **tipear una URL a mano** en el celular, algo que no escala más allá del propio desarrollador.

**Lo que hay ahora.** `DataRepository` (Storage.kt) generaliza el patrón que `MetaRepository` ya usaba —*lo descargado gana sobre lo empaquetado, con caída automática al APK si lo descargado está roto*— a los tres archivos. `loadDex()` y `SpriteMatcher` pasan por ahí en vez de leer `assets/` directo.

`build_data_manifest.py` arma la carpeta `dist/` que se sube a cualquier hosting estático (GitHub Pages, un bucket, un CDN — **no hace falta servidor**). El `manifest.json` pesa <1 KB y lista versión, tamaño, `sha256` y `schema` de cada archivo. La app lo baja, compara contra lo que tiene, y **descarga solo lo que cambió**.

Eso último no es un detalle con muchos usuarios: los tres archivos pesan ~1.7 MB juntos y el que más cambia (`meta.json`, 279 KB) es el más chico. Bajar todo cada semana sería servir 6 veces más datos de lo necesario.

**Garantías de la descarga**, en orden de lo que cada una tapa:
- **`sha256` por archivo** — una descarga cortada es JSON inválido y se detecta igual; una corrupta *y parseable* no se detecta de otra forma.
- **Validación de cordura antes de reemplazar** — un `dex.json` sin especies o un `sprite_index.json` de formato viejo se rechazan y se conserva el que funcionaba.
- **Escritura atómica** (`.tmp` + rename) — nunca queda un archivo a medias.
- **`minAppVersion`** — el freno de mano. Si unos datos nuevos necesitan código que las apps viejas no tienen, se marca en el manifiesto y esas apps los ignoran en vez de romperse.
- **Un archivo que la app no conoce se ignora en silencio, a propósito** — es lo que permite publicar una capa de datos nueva sin romper a las apps viejas (junto con el contrato aditivo de §10.2).

**Lo que falta decidir, y por qué no se inventó:** dónde se hospeda. `DATA_URL` en `hud.html` está **vacía a propósito** — poner una URL inventada sería peor que ninguna, porque la app intentaría bajar de un lugar inexistente y el error no diría nada útil. Mientras esté vacía, el campo manual funciona igual que siempre. Cuando se decida, es **cambiar esa línea y nada más**.

**Compatibilidad hacia atrás:** `updateMeta` distingue por el contenido de lo que baja. Un `manifest.json` dispara el flujo de tres archivos; un `meta.json` suelto sigue funcionando como antes, para no romper una URL que alguien ya tenga guardada.

**Sin verificar en dispositivo:** todo el lado Kotlin de esta sección se escribió sin poder compilar ni correr. Lo que sí se verificó acá: los generadores corrieron de verdad, el manifiesto se generó y se inspeccionó, y las dos variantes de la vista de Ajustes se renderizaron en un sandbox con DOM simulado.

## 11. Dos features chicas, independientes del pipeline de meta — ~~planeadas~~ **HECHAS, 2026-08-03**

Salieron de la sesión de asesoría VGC (`decisions.md` #20). Documentadas primero y no implementadas a propósito (Angel prefiere separar análisis/documentación/plan de escribir código); implementadas después, en la sesión de Fase 2 (sprint 2.5), una vez que ya había plan aprobado y tokens para ejecutarlo.

### 11.1 Descripción de habilidad expandible (Peek) — **HECHO**

**Implementado tal cual estaba planeado**, sin sorpresas: `ABIL_DESC` (slug → texto en inglés, 201/201 habilidades incluidas las propias de Champions) vive al lado de `ABIL_I18N` en `hud.html`. Se muestra en la fila "Habilidad" de `vFoe()` (Peek) al tocarla — mismo mecanismo `whyRow()` que ya mostraba la cadena de evidencia (sprint 2.2), extendido para combinar evidencia **y** descripción estática cuando hay las dos, o mostrar solo la que corresponda. No aparece en Glance.

**Fuente y método real, usado tal cual estaba verificado desde el 2026-08-02:**
- PokeAPI (`https://pokeapi.co/api/v2/ability/<slug-con-guiones>`) — mismo origen que ya generó `ABIL_I18N` (decisión #7).
- El slug de la API se arma a partir del **nombre en inglés ya guardado en `ABIL_I18N[x].en`** (ej. `"Armor Tail"` → `armor-tail`), no del slug interno de una palabra (`armortail`) — el slug interno no tiene los espacios que hacían falta para reconstruir el separador, es un callejón sin salida para este propósito.
- Campo a extraer: `effect_entries` con `language.name === "en"`, tomar `short_effect`.
- **Cobertura confirmada: 201/201 habilidades encontradas**, incluidas las propias de Champions que no existen en los juegos principales (`eelevate`, `firemane`, `dragonize`, `megasol`, `hungerswitch`, `spicyspray`, `supersweetsyrup`, `supremeoverlord`, `piercingdrill`) — PokeAPI ya tiene estos datos cargados. No hay que prever un fallback de "sin descripción", el caso no aparece hoy (sí conviene que el código lo tolere igual, por las dudas de que la cobertura cambie).
- Solo en inglés — no se tradujo a español porque no es información primordial (Angel) y la cobertura de `effect_entries` en español de PokeAPI es más floja para habilidades nuevas; mostrarla en inglés siempre es consistente con cómo ya se maneja el resto de los datos crudos del juego (decisión #7).

### 11.2 Seguimiento de PP de todos los movimientos (Peek/Campo) — **HECHO**

`product.md` ya prometía esto en la definición original de Peek y nunca se había construido (brecha real, confirmada por Angel: "muy pocas veces lo cuento... o cuando ya estamos en late game y no puedo recordar con precisión"). El dato que faltaba (PP máximo por movimiento) salió de `build_dex.py` — Showdown's `moves.json` ya trae el campo `pp` directo, así que fue agregar un índice a `mv()` y a `MV[m.n]` en `loadDex()`, sin necesidad de una fuente nueva.

**Implementado tal cual el plan preveía:** `mv(k).pp` (`null` si no hay dex.json cargado — "no sabemos" y "no tiene PP" son estados distintos, mismo criterio de `Fase 1` para la naturaleza sin determinar). `f.ppUsed = {}` por Pokémon rival, un botón "−1 usado"/"+1" junto a cada movimiento visto en Peek, mostrando `restante/máximo`. **Se muestra para todos los movimientos vistos, no solo los "clave"** — decisión de Angel del 2026-08-03: *"Sería bueno que muestre el pp de todos los ataques, si vamos a hacer las cosas hagámosla bien."* El ruido en Glance lo resuelve el motor de prioridad (`inference.md` §10), no un recorte del dato en origen.

La misma fila de cada movimiento es tocable para ver su efecto (`d`/`note` de `dex.json`, la descripción real de Showdown) — mismo mecanismo `whyRow()` de §11.1.

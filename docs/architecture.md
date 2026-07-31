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
| **Motor de Insights** | Traducir cambios de estado/creencias a las cinco preguntas del jugador; decidir qué amerita una alerta y qué se queda en silencio | No genera recomendaciones de jugada, nunca |
| **Meta Data Service** | Empaquetar, versionar (por reglamento) y actualizar (semanalmente) los datasets de uso y sets del meta, combinando fuentes externas detrás de un adaptador por fuente (ver §10) | No se consulta en tiempo real durante el combate — todo lo que el motor usa en combate ya está local |
| **Presentación** | Glance/Peek/Deep, corrección de errores en 1-2 taps, por cliente | No contiene lógica de dominio |
| **Persistencia** | Guardar event logs de combates y snapshots del meta localmente | No requiere red para operar |

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

- **Primaria — API pública de Limitless TCG** (`https://play.limitlesstcg.com/api`). Sin clave para los endpoints de torneos (`/tournaments`, `/tournaments/{id}/standings`, `/tournaments/{id}/pairings`). Devuelve equipos crudos (campo `decklist` en standings) de torneos reales. Es la fuente raíz de la que beben casi todos los agregadores de terceros — usarla directo evita depender de que un tercero siga existiendo. El subesquema exacto del `decklist` VGC (ítems/movimientos/habilidad/spread) no está documentado formalmente y debe inspeccionarse contra una respuesta real antes de fijar el modelo de datos. Los movimientos/habilidad/spread solo están presentes cuando el torneo usó envío de teamlist abierto — la cobertura de "qué 6 Pokémon" va a ser mayor que la de "sets completos", y el pipeline debe tolerar esa asimetría sin fallar.
- **Secundaria — rutas AI de Pikalytics** (`/ai/pokedex/<formato>/<pokemon>`, Markdown estructurado vía `llms.txt`/`llms-full.txt`). Da agregados ya calculados (uso %, win rate, ítems/habilidades/movimientos/spreads/naturalezas/compañeros) para no tener que recalcular todo desde cero. Cadencia de actualización mensual para varios agregados — si se necesita frescura semanal real, esos agregados puntuales se recalculan directo desde los equipos crudos de Limitless en vez de esperar a Pikalytics.
- **Descartadas para scraping automatizado — Pokémon Zone y Champions Hub.** Sus términos de servicio lo prohíben explícitamente. Se pueden usar como referencia conceptual/visual manual, nunca como fuente automatizada del pipeline.
- **No usadas por ahora, quedan documentadas como alternativas de respaldo:** Champions Lab y championshub.gg (agregadores sin API pública documentada), Smogon/Showdown usage stats (secundarias, formato oficial es in-game), pokedata.ovh (VGC presencial, sin cobertura de esta regulación al momento de relevarlo).

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

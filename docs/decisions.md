# Registro de decisiones

Formato: contexto → decisión → consecuencias → estado. Cuando un documento parezca contradecir algo listado acá, este documento gana. Las decisiones marcadas como **supersede** anulan explícitamente un diseño anterior mencionado en el propio historial del proyecto.

---

### 1. El copiloto nunca recomienda una jugada
**Contexto:** un diseño anterior incluía un modo "compacto" que ordenaba los cuatro movimientos propios por conveniencia — funcionalmente un recomendador, en contradicción directa con la filosofía de "nunca jugar por el usuario".
**Decisión:** el producto informa (hechos, estimaciones, eliminación de hipótesis, consecuencias de una acción hipotética si se pide explícitamente) pero jamás rankea, sugiere o resalta una jugada como mejor que otra.
**Consecuencias:** cualquier feature futura que se parezca a un ranking de acciones se descarta en revisión de diseño, no se implementa "a modo de prueba".
**Estado:** Aceptada, **refinada dos veces — leer junto con #19 y #21, que son la forma vigente.** El núcleo (no rankear ni sugerir una jugada) nunca se revirtió. #19 aclaró que mostrar el resultado calculado de cada opción es información, no recomendación. #21 amplió a jerarquizar información y describir riesgos/consecuencias, manteniendo prohibido elegir la acción. **Supersede** el diseño previo de modo compacto/`suggest()`.

---

### 2. El HUD no duplica información que el juego ya muestra
**Contexto:** Pokémon Champions ya muestra correctamente la duración restante de Tailwind, clima, pantallas y otros efectos de campo.
**Decisión:** el HUD no repite esos contadores salvo que aporte un valor adicional que el juego no da (cruzar esa información con una estimación oculta, señalar una interacción no obvia entre efectos simultáneos).
**Consecuencias:** la capa Glance se diseña alrededor de lo que el juego *no* muestra (orden de velocidad bajo incertidumbre, rangos de daño, estimaciones de lo oculto), no como un espejo del HUD nativo del juego.
**Estado:** Aceptada. **Supersede** el diseño previo de `product.md` que incluía contadores de campo en Glance.

---

### 3. El overlay en tiempo real es una funcionalidad principal y permanente
**Contexto:** una revisión crítica previa del proyecto (ver `audit.md` / historial) cuestionó la viabilidad comercial y de distribución del overlay y sugirió considerar un pivot que lo dejara de lado a favor de un producto sin captura de pantalla.
**Decisión:** el overlay con lectura automática no se elimina ni se relega por conveniencia arquitectónica ni por incertidumbre comercial. Es, junto con la memoria de combate, el diferencial central del producto para uso personal y comunitario. La forma de sostenerlo sin comprometer la arquitectura es la separación Motor/Cliente (ver `architecture.md` §0): si en el futuro surge otro cliente o plataforma, se suma como consumidor adicional del mismo motor — el overlay no se reemplaza ni se depreca.
**Consecuencias:** ninguna decisión técnica futura puede plantearse como "sacar el overlay para simplificar"; la simplificación correcta es aislar el motor, no recortar el producto.
**Estado:** Aceptada. **Supersede** la sugerencia de pivot de la revisión crítica anterior.

---

### 4. Sin publicidad por ahora, arquitectura compatible con publicidad a futuro
**Contexto:** el diseño original contemplaba ads como parte del modelo de negocio; una revisión posterior recomendó eliminarlas del todo por riesgo de distribución y de experiencia.
**Decisión:** no se implementa ninguna forma de publicidad en esta etapa. La arquitectura se mantiene compatible: si en el futuro se agrega, es un componente de la capa de Presentación en superficies frías (post-combate, historial), sin ningún gancho especial dentro del Motor.
**Consecuencias:** cero trabajo de monetización ahora; cero deuda técnica para agregarla después, porque no requiere tocar dominio.
**Estado:** Diferida (no implementada), arquitectura reservada. Ver `architecture.md` §7.2 y `future.md`.

---

### 5. Producto completo ahora; licencia pro/free reservada para el futuro
**Contexto:** el negocio a futuro podría requerir una versión limitada gratuita y una versión completa desbloqueable por clave.
**Decisión:** hoy el producto se distribuye completo, sin funciones bloqueadas. La lógica de entitlements (qué está disponible según licencia) se reserva como módulo de Presentación, explícitamente separado del dominio: el Motor nunca evalúa ni conoce ningún flag de plan.
**Consecuencias:** agregar el sistema de licencias en el futuro es un cambio acotado a Presentación. El dominio no se contamina con condicionales de "si es pro, mostrar esto".
**Estado:** Diferida (no implementada), arquitectura reservada. Ver `architecture.md` §7.1 y `future.md`.

---

### 6. Offline-first como requisito, no como degradación aceptable
**Contexto:** la lectura de meta y las inferencias dependen de datos que, si se consultaran en vivo, introducirían una dependencia de red dentro del combate.
**Decisión:** todo el pipeline de combate opera 100% local. Los datos de meta se actualizan en segundo plano con cadencia semanal por defecto.
**Consecuencias:** ningún fallo de conectividad puede degradar la experiencia dentro de un combate. La sincronización a la nube (si existe en el futuro) es una capa opcional sobre este mismo diseño, no un requisito.
**Estado:** Aceptada. Ver `architecture.md` §4.

---

### 7. Identificadores canónicos en inglés; idioma solo en presentación
**Contexto:** bug real y grave detectado en auditoría — el motor de daño comparaba habilidades en español contra datos que la fuente (Pokémon Showdown) entrega en inglés, rompiendo en silencio los modificadores de habilidad.
**Decisión:** todo identificador de dominio usa slug canónico en inglés internamente. El español (y cualquier idioma futuro) vive exclusivamente en la capa de presentación vía una función de traducción, adoptada al 100%, nunca de forma parcial.
**Consecuencias:** elimina de raíz la clase de bug más grave encontrada en la auditoría. Habilita agregar idiomas nuevos sin tocar el dominio.
**Estado:** Aceptada. Ver `architecture.md` §5.

---

### 8. Fallo ruidoso, nunca silencioso
**Contexto:** al menos tres hallazgos distintos de la auditoría (regex de sprites shiny, `meta.json` desincronizado, mismatch de campos `predict()`/`vPre()`) comparten el mismo patrón: el sistema seguía funcionando y reportando éxito mientras producía resultados incorrectos.
**Decisión:** ningún módulo del pipeline puede degradar su salida en silencio. Ante datos inconsistentes, ausentes o de versión no reconocida, el sistema reporta explícitamente el problema en lugar de producir un resultado plausible pero incorrecto.
**Consecuencias:** exige validación explícita en los bordes de cada módulo (ver `architecture.md` §6 y §8), no solo manejo de errores genérico.
**Estado:** Aceptada como principio transversal de todo el proyecto.

---

### 9. El event log es la fuente única de verdad
**Contexto:** para sostener memoria de combate, análisis post-partida, series Bo3 y una futura sincronización sin reescribir el dominio cada vez.
**Decisión:** todo lo observado en un combate se registra como una secuencia inmutable de eventos con timestamp, origen y confianza. Estado, creencias, cálculos y vistas se derivan de ese log; nunca se edita retroactivamente (una corrección es un evento nuevo).
**Consecuencias:** historial, Bo3, análisis de hábitos y sync futuros son todos consumidores del mismo formato — se agregan sin reescribir el núcleo.
**Estado:** Aceptada. Ver `architecture.md` §1 y §3.

---

### 10. Separación Motor (Engine Core) / Cliente
**Contexto:** necesidad de sostener el overlay como diferencial permanente (decisión #3) sin acoplar todo el dominio a Android/Kotlin, y de dejar la puerta abierta a futuros clientes sin reescritura.
**Decisión:** toda la lógica de dominio (percepción interpretada, estado, inferencia, cálculo, insights) vive en un motor agnóstico de plataforma. Cada plataforma (Android hoy, lo que exista después) implementa solo su capa de Percepción (captura/entrada) y Presentación, y consume el motor.
**Consecuencias:** el overlay Android sigue siendo el cliente principal sin que eso implique que el dominio dependa de Android. Refuerza una decisión de diseño que el proyecto ya venía tomando bien (lógica en JS, Kotlin como cascarón).
**Estado:** Aceptada. Ver `architecture.md` §0.

---

### 11. Estabilización antes que features nuevas
**Contexto:** la auditoría técnica encontró bugs confirmados en producción y deuda técnica que multiplica su costo con cada feature nueva construida encima.
**Decisión:** no se agregan funcionalidades nuevas hasta resolver los hallazgos de `audit.md` y dejar en el repo una suite de pruebas mínima reproducible.
**Consecuencias:** define el contenido de la Fase 0 del roadmap.
**Estado:** Aceptada. Ver `roadmap.md`.

---

### 12. Limitless como fuente primaria de meta, Pikalytics como secundaria
**Contexto:** investigación de fuentes de datos completada. `build_meta.py` es hoy un stub sin implementar (ver `audit.md`).
**Decisión:** el pipeline usa la API pública de Limitless TCG (sin clave, equipos crudos de torneo) como fuente primaria, y las rutas AI/Markdown de Pikalytics como fuente secundaria para agregados ya calculados. Se descarta explícitamente el scraping de Pokémon Zone y Champions Hub por prohibición expresa en sus términos de servicio.
**Consecuencias:** el motor de inferencia deja de depender de un `meta.json` estimado a mano y pasa a alimentarse de datos de torneo reales. Ver diseño completo en `architecture.md` §10.
**Estado:** Aceptada.

---

### 13. JSON como formato de meta, con umbral explícito de migración a SQLite
**Contexto:** el índice de combinaciones parciales (pares/tríos de especies → equipos) podría crecer lo suficiente como para justificar una base embebida.
**Decisión:** se mantiene JSON plano mientras el índice esté por debajo de ~5–8 MB y el parseo en arranque no supere ~1–2 segundos. Migrar a SQLite (`sql.js`/`wa-sqlite` o puente Room) solo si se superan esos umbrales o aparecen consultas que requieren joins en tiempo de ejecución.
**Consecuencias:** no se migra preventivamente. Se evita una dependencia nueva (SQLite embebido) mientras JSON siga resolviendo el caso de uso con la simplicidad que el proyecto viene priorizando.
**Estado:** Aceptada. Ver `architecture.md` §10.2.

---

### 14. Datos de meta versionados por reglamento, no solo por fecha
**Contexto:** Pokémon Champions cambia el pool de especies legales por reglamento (Reg M-A, Reg M-B, y las que sigan), y ese cambio invalida sets y agregados de golpe.
**Decisión:** todo `MetaSnapshot` incluye un campo `regulation` obligatorio además de `generatedAt`. El motor selecciona el snapshot correspondiente a la regulación activa y puede conservar snapshots anteriores para partidas en formatos viejos.
**Consecuencias:** un cambio de reglamento no requiere ningún cambio de código, solo la generación y distribución de un nuevo snapshot versionado.
**Estado:** Aceptada. Ver `architecture.md` §3 y §10.4.

---

### 15. Importación manual de equipo como funcionalidad de primera clase
**Contexto:** ninguna fuente externa de datos es 100% confiable a largo plazo (términos de servicio, disponibilidad, cambios de formato), y siempre va a haber una ventana entre un reglamento nuevo y la existencia de datos agregados para ese reglamento.
**Decisión:** pegar un teamlist o importar un equipo manualmente no es un plan de contingencia secundario — es un modo soportado desde el diseño, con el mismo nivel de cuidado de UX que la carga automática.
**Consecuencias:** el producto nunca queda inutilizable por la caída o el retraso de una fuente externa, consistente con el principio de degradación elegante (`vision.md`).
**Estado:** Aceptada. Ver `architecture.md` §10.4.

---

### 16. La estrategia comercial no condiciona la arquitectura actual
**Contexto:** existe incertidumbre real sobre distribución, monetización y modelo de negocio a futuro.
**Decisión:** esas definiciones quedan explícitamente pospuestas y documentadas como abiertas en `future.md`, sin bloquear ni orientar prematuramente decisiones de arquitectura o de producto de hoy. Las decisiones #4, #5 y #10 ya dejan los puntos de extensión necesarios para cuando se resuelva.
**Consecuencias:** el equipo (Angel + Claude Code) puede avanzar en producto y arquitectura sin esperar una definición de negocio.
**Estado:** Abierta — a revisar más adelante.

---

### 17. Idioma del HUD: selector explícito al abrir la app, no fijo en español
**Contexto:** la re-auditoría de 2026-07-31 encontró que la capa i18n (`decisions.md` #7, `architecture.md` §5) nunca se construyó — `hud.html` tiene texto hardcodeado en español en todas las vistas. Al revisar capturas reales del juego (Pokémon Champions en un dispositivo con el juego configurado en **inglés** — "Trick Room", "Colbur Berry", "Light Screen", etc.), quedó claro que fijar el HUD en español asumía un idioma de juego que no es el que Angel usa hoy, y que tampoco sería el correcto para otro jugador que use el juego en español.
**Decisión:** el HUD tiene un selector de idioma explícito al abrir la app (persistido, no se pregunta cada vez). Todo dato de dominio (especie, movimiento, ítem, habilidad) se identifica internamente por su **slug canónico en inglés** (ya decidido en #7) — eso no cambia. Lo nuevo es que el texto mostrado al usuario sale de una tabla de traducción con, como mínimo, entradas en **inglés y español**, resuelta por `t(clave, idioma)`. El idioma por defecto al primer uso se puede sugerir según el idioma del sistema Android, pero el usuario lo puede cambiar en cualquier momento desde un ajuste — no se infiere del texto en pantalla ni se fuerza.
**Consecuencias:** el trabajo de unificar `calc()` a slugs canónicos (`audit.md` §5.2) y el de construir la capa i18n (`audit.md` §5.5) pasan a ser **el mismo esfuerzo**, no dos separados — no tendría sentido migrar a slugs sin resolver al mismo tiempo cómo se muestran. Agregar un tercer idioma en el futuro es solo agregar una columna a la tabla de traducción, no tocar dominio ni lógica (consistente con `future.md`, "Multi-idioma completo").
**Estado:** Aceptada. Reemplaza cualquier lectura anterior de la decisión #7 como "el HUD habla español fijo". Ver `roadmap.md` Fase 0, ítem 1, y `audit.md` §5.5.

---

### 18. `hud.html` se mantiene como archivo único — no se modulariza con ES modules
**Contexto:** el roadmap Fase 0 (ítem 4) preveía partir `hud.html` en módulos con contratos `@typedef` entre capas (Percepción/Estado/Inferencia/Cálculo/Insights/Presentación), siguiendo `architecture.md` §8. Al investigarlo se confirmó un riesgo concreto, no teórico: `OverlayService.kt` carga el HUD con `loadUrl("file:///android_asset/hud.html")` y nunca habilita `allowFileAccessFromFileURLs`/`allowUniversalAccessFromFileURLs` (desactivados por default desde Android 11) — `<script type="module">` con `import`/`export` entre archivos probablemente no cargue nada en el WebView real por las restricciones de CORS que Chromium aplica a módulos servidos desde origen `file://`.
La alternativa sin ese riesgo — mantener el código fuente dividido en archivos y agregar un script de build que los concatene en un único `hud.html` final, como ya hacen `build_dex.py`/`build_sprite_index.py` con sus datos — se le presentó a Angel explícitamente. La rechazó: agregar un paso de build al ciclo de edición rompe exactamente lo que hace valioso a este proyecto hoy (editar `hud.html`, recargar el WebView, ver el resultado, sin recompilar nada) a cambio de un beneficio (contratos tipados entre secciones) que es preventivo, no un bug activo.
**Decisión:** `hud.html` se mantiene como un único archivo con un solo scope global. No se introduce ninguna forma de módulos ni de paso de build intermedio para la lógica de combate.
**Consecuencias:** el ítem 4 de la Fase 0 queda cerrado como "no se hace", no como pendiente. La protección contra mismatches de forma entre funciones (el tipo de bug que fue el §5.1, ya resuelto de otra forma) sigue dependiendo de disciplina manual y de la suite de tests (`tests/run.js`) en vez de contratos verificables en build. Si el archivo sigue creciendo y esto se vuelve un problema real y recurrente (no solo preventivo), esta decisión se puede revisar — pero no antes de que haya evidencia concreta de que hace falta.
**Estado:** Aceptada. Ver `roadmap.md` Fase 0, ítem 4, y `audit.md` §7.

---

### 19. Matiz a la decisión #1: mostrar el resultado calculado de cada movimiento no es "recomendar"
**Contexto:** al trabajar el ajuste de Glance en la Fase 1 se encontró que `vCompact()` seguía llamando a `suggest()` y mostrando los cuatro movimientos propios ordenados por un puntaje interno, con la etiqueta `"MEJOR"` en el primero — exactamente el modo "compacto"/`suggest()` que la decisión #1 dice que quedó descartado, no pospuesto. Al consultarlo, Angel aclaró que la regla como estaba escrita era más estricta de lo que quería: mostrar cuánto daño hace cada movimiento en el contexto actual es información útil para decidir, y sacarla del todo no ayuda. Lo que rechaza no es la información, es que el HUD elija y lo marque como "la mejor opción".
**Decisión:** la decisión #1 se mantiene en su forma fuerte — **el HUD no rankea, no ordena por conveniencia ni resalta un movimiento como mejor que otro** — pero se aclara explícitamente que **mostrar el resultado calculado de cada opción disponible (daño, KO/no KO) no es una recomendación, es un hecho**, igual que mostrar un rango de daño contra el rival ya lo era para el resto del HUD. La distinción operativa: cero ranking, cero orden por puntaje, cero etiqueta tipo "MEJOR"/"1"/"2" que implique jerarquía — los movimientos se muestran en el orden real que tienen en el set del Pokémon (el orden en que el jugador los cargó), cada uno con su resultado, y el jugador arma su propia conclusión mirando los números.
**Consecuencias:** `suggest()`/`vCompact()` se corrigen para dejar de ordenar por `v` y de aplicar la etiqueta `"MEJOR"` — pasan a listar todas las combinaciones movimiento×objetivo en orden de set/turno, sin recortar a un top-4 por puntaje (ese recorte era en sí mismo una forma de decidir qué mostrar). Cualquier feature futura que muestre información de movimientos debe seguir este mismo criterio: números y hechos sí, jerarquía o etiqueta de "mejor" no.
**Estado:** Aceptada. Ajusta (no revierte) la decisión #1. Ver `roadmap.md` Fase 1.

---

### 20. Prioridades de datos/UI para Fase 2, confirmadas contra investigación externa + a Angel como asesor de VGC
**Contexto:** antes de tocar el pipeline de datos de meta (Fase 2) se hizo una investigación dedicada (agente separado, con fuentes citadas) sobre qué distingue a un jugador de VGC profesional de uno promedio, y después una sesión de preguntas completa (no el widget de 3 preguntas — una tanda larga en el chat, opción múltiple + desarrollo) donde Angel respondió como jugador real. El objetivo: no adivinar qué datos/gráficas importan, contrastarlo contra literatura real y contra la experiencia de Angel, y que ambas fuentes coincidan o se corrijan entre sí antes de diseñar nada.
**Hallazgos que confirman lo que ya estaba construido** (sin cambios de diseño, solo evidencia a favor): el sistema de confianza en 3 niveles (`product.md`) coincide con cómo la investigación describe la diferencia entre top jugadores y el resto en "team preview" (leer certeza vs. incertidumbre, no fingir precisión). Angel confirmó que sigue sin contar PP mentalmente en late-game ("se me pierde") y que el mayor cuello de botella hoy es cálculo de daño/velocidad impreciso en momentos decisivos (ej.: necesitar bajar exactamente el % de vida justo para asegurar un KO al turno siguiente, con margen de error de ~10% en la estimación mental) — confirma que el Motor de Cálculo ya construido es la parte de mayor apalancamiento del proyecto, no una más entre varias.
**Hallazgos nuevos, priorizados para Fase 2 y cercanías:**
1. **Descripción de habilidad expandible en Peek** — Angel: "no es información primordial, pero sería genial que la pueda dar si la necesito". Se implementa ahora (no depende del pipeline de meta): tabla `ABIL_DESC` generada desde PokeAPI (mismo método que `ABIL_I18N`, decisión #7), en inglés, mostrada como texto secundario/expandible, nunca en el primer vistazo de Glance (`product.md`, regla de qué entra en Glance).
2. **Rol habitual de una especie dentro de un equipo/core específico** y **bandera de "control de velocidad mayoritario"** (ej. "el 80% de los Whimsicott de la meta traen Tailwind") pasan a ser campos requeridos del `MetaSnapshot` de Fase 2 (`architecture.md` §10), no solo uso%/win rate — Angel: en metas cerrados detecta el control de velocidad solo, pero pide ayuda visual justo en el caso borde (mayoría, no totalidad, de una especie trayendo la misma herramienta). Coincide con lo que la investigación externa marca como near-mandatory: control de velocidad como infraestructura de equipo, no bonus.
3. **PP de los movimientos** — confirmado como brecha real (`audit.md`/`product.md` ya lo prometían en Peek, nunca se construyó). Requiere una tabla de PP por movimiento que hoy no existe en `MV` — se documenta como ítem de roadmap con el diseño ya resuelto, no se improvisa en la misma sesión que el resto de estos cambios (ver `roadmap.md`, Sprint 2.5). **Alcance ampliado el 2026-08-03:** la duda de si mostrarlo solo para los movimientos "clave" (Protect, redirección) o para todos la resolvió Angel a favor de **todos** — *"si vamos a hacer las cosas hagámoslas bien, es info importante en algunos contextos"*. El riesgo de ruido que motivaba recortarlo se resuelve por otra vía y ya está cubierto: el motor de prioridad (#21) decide qué sube a Glance, y el detalle completo vive en Peek, que es la capa donde corresponde.
4. **Jerarquía y ubicación consistente de la información** — Angel remarcó que perder tiempo buscando un dato que "a veces está en una parte y después en otra" es un costo real, más que el formato en sí (pidió números/porcentajes crudos, no solo texto cualitativo). Esto es evidencia concreta a favor del ítem ya diferido "rediseño de Presentación a vista contextual única" (`roadmap.md` Fase 1) — no cambia su prioridad todavía, pero deja de ser una intuición de diseño y pasa a tener un caso de uso real documentado.
5. **Notas de comportamiento del rival (estilo de juego, foco excesivo a un Pokémon) no se automatizan** — es lectura subjetiva del jugador, no un dato que el Motor pueda calcular u observar de forma confiable; queda fuera de alcance, no por descuido sino porque automatizarlo mal violaría "fallo ruidoso, nunca silencioso" (inventaría una lectura que no está fundamentada).
6. **Resumen post-combate (Fase 4) puede esperar**, confirmado por Angel, pero con una nota de contexto que vale la pena preservar: incluso jugadores profesionales siguen prefiriendo Pokémon Showdown antes que el juego oficial en parte porque ahí la información es más fácil de acceder — valida el objetivo central de `vision.md` (el HUD existe para cerrar esa brecha de acceso a información dentro del juego real), no es una prioridad de feature en sí misma.
**Decisión:** Fase 2 (`architecture.md` §10, `roadmap.md`) incorpora los campos de rol-por-core y bandera de control de velocidad mayoritario como parte del `MetaSnapshot`, no como extensión posterior. La descripción de habilidad se construye ya, fuera del pipeline de meta. El PP por movimiento queda especificado pero no construido en esta sesión.
**Estado:** Aceptada. Ver `product.md` (Peek), `architecture.md` §10, `roadmap.md` Fase 1/Fase 2.

---

### 21. Segundo matiz a la decisión #1: el copiloto describe la posición, nunca elige la acción
**Contexto:** Angel trajo una propuesta de diseño (elaborada con ayuda de ChatGPT, que no conocía la historia del proyecto) para una capa avanzada de datos e inferencia. Un punto de esa propuesta decía explícitamente *"NO existe una prohibición absoluta de recomendar"*, y habilitaba al HUD a "sugerir una línea de juego" o marcar la "opción más segura". Eso contradice frontalmente la sección más enfática de `vision.md`, la lista de principios no negociables de `CLAUDE.md`, y las decisiones #1/#19. No se aplicó por defecto: se le presentó a Angel la contradicción con tres opciones concretas y eligió la intermedia.
**Decisión:** se amplía el alcance del copiloto en dos direcciones, y solo esas dos:
1. **Jerarquizar información.** El HUD decide *qué mostrar primero* según qué dato es más probable que cambie la decisión del turno. Ordenar información no es recomendar una jugada.
2. **Describir riesgo y consecuencia.** El HUD puede enunciar el estado y a dónde lleva cada escenario: *"el escenario más peligroso es que lleve Pañuelo"*, *"este ataque no mata en 3 de 16 tiradas"*, *"si cambia a X, tu Y queda expuesto"*.

Lo que **sigue prohibido, sin excepción**: elegir o sugerir la acción a tomar (*"la opción más segura es Protect"*, *"conviene sacar a X"*), rankear los movimientos propios, o cualquier etiqueta de jerarquía tipo "MEJOR" (esto último ya lo fijaba #19 y no se toca).

**La línea operativa, en una frase: describir la posición sí, elegir la acción no.** Ante un caso dudoso, la pregunta es si la frase enuncia un hecho sobre el estado del juego o un imperativo sobre qué hacer.

**Condición inseparable:** toda descripción de riesgo tiene que ser inspeccionable. Si el HUD dice "el escenario más peligroso es X", tiene que poder contestar "¿por qué?" con la evidencia concreta. Sin eso, esta ampliación se convierte en la caja negra que #1 existía para evitar — la explicabilidad no es un extra de esta decisión, es lo que la hace admisible. Técnicamente esto depende del sustrato de `inference.md` (#22): **no se implementa ninguna descripción de riesgo antes de que exista la cadena de evidencia que la sostenga.**
**Consecuencias:** `vision.md` cambia de título y contenido en su sección central (de "nunca recomienda una jugada" a "describe la posición; la jugada la elegís vos"). `product.md` incorpora el motor de prioridad como el criterio de qué entra en Glance/Peek/Deep. `architecture.md` §2 amplía la responsabilidad del Motor de Insights. Las decisiones #1 y #19 se mantienen vigentes en todo lo demás — esta las ajusta, no las revierte, igual que hizo #19 en su momento.
**Estado:** Aceptada, 2026-08-03, con elección explícita de Angel entre tres alcances posibles. Ver `vision.md`, `product.md`, `inference.md` §10.

---

### 22. El trabajo de inferencia es construir el sustrato, no el motor — y sin Evidence Graph explícito
**Contexto:** la propuesta de diseño asumía que había que construir un sistema de inferencia desde cero, e incluía un *Evidence Graph* (nodos de evento, nodos de hipótesis, aristas) como entidad de primera clase. Antes de aceptar nada se revisó el código real, y el diagnóstico resultó distinto: **el proyecto ya tiene dos reglas de inferencia funcionando.** `solveBulk()` enumera repartos defensivos compatibles con un daño observado y descarta el resto; `observeOrder()` acota velocidad por orden observado y deduce Pañuelo Elección por sí solo cuando el piso de velocidad supera el máximo alcanzable sin objeto. Lo que falta no son las reglas: es el sustrato debajo. Ambas escriben su conclusión directo sobre el objeto mutable del rival (`f.spdMin`, `f.itemSure=true`) y **tiran la evidencia**, por lo que hoy es imposible explicar una inferencia, deshacerla si el usuario cargó mal un dato, o arrastrarla al juego 2 de un Bo3.
**Decisión:** el trabajo de Fase 2 se define como **construir el event log y el espacio de hipótesis debajo de las reglas que ya funcionan**, migrarlas sin cambiar su comportamiento, y recién después agregar reglas nuevas. Tres definiciones concretas:
1. **Event log append-only como fuente de verdad**, con `B` pasando a ser una vista derivada. Migración en paralelo: el log corre junto a `B` sin reemplazarlo hasta que se verifique que reproduce el estado actual sin regresiones.
2. **Sin Evidence Graph como estructura propia.** Un campo `byEvent` en cada hipótesis descartada/confirmada, más el log indexado por `id`, ya *son* el grafo — expresado como referencias en vez de una estructura paralela que hay que mantener sincronizada. Se pierde la consulta inversa directa ("qué depende del evento 17"), que con decenas de eventos por partida se resuelve con un barrido irrelevante en costo. Regla de oro del proyecto: más robusto y mantenible le gana a más sofisticado.
3. **Conjuntos de hipótesis por eje, no repartos completos.** No se enumera el producto cartesiano de las 6 estadísticas (cientos de miles de combinaciones, inviable en un WebView bajo reloj); se mantienen rangos por eje (velocidad, resistencia), que es lo que las reglas reales necesitan y lo que el código ya hace.

**Beneficio de diseño no buscado pero valioso:** los tres niveles de confianza de `product.md` dejan de ser etiquetas mantenidas a mano y pasan a derivarse del tamaño del conjunto de hipótesis vivas (uno solo → Deducido, varios → Estimado, ninguno → Contradicción). Eso elimina por construcción una instancia de la familia de bugs de `audit.md` §8 (dos representaciones de lo mismo que se desincronizan).
**Consecuencias:** se crea `docs/inference.md` como especificación detallada. `architecture.md` §2 documenta explícitamente la brecha entre las capas diseñadas y el código real. La Fase 2 del roadmap se reestructura en sprints con el sustrato primero. No se reescribe `solveBulk()` ni `observeOrder()`: se migran conservando su lógica.
**Estado:** Aceptada, 2026-08-03. Ver `inference.md` (completo), `architecture.md` §2, `roadmap.md` Fase 2.

---

### 23. El Motor consume `MetaSnapshot` y nada más — cada fuente externa vive detrás de su adaptador
**Contexto:** ya estaba implícito en `architecture.md` §10.4, pero nunca se fijó como decisión. Con Fase 2 a punto de traer datos reales de Limitless y Pikalytics, conviene explicitarlo antes de que aparezca el primer atajo que acople el dominio a una fuente concreta.
**Decisión:** ningún módulo del Motor conoce Limitless, Pikalytics ni ninguna fuente futura. Todas producen el mismo formato interno (`MetaSnapshot`, `architecture.md` §3 y §10.6) a través de un adaptador por fuente, y el Motor consume únicamente ese formato. Corolario que vale la pena escribir porque es el que se viola primero bajo presión: **un prior de meta nunca descarta una hipótesis, solo ordena las que siguen vivas.** Que un ítem sea raro en el formato no lo hace imposible en esta partida; tratarlo como imposible sería fabricar certeza — exactamente lo que prohíbe el principio de confianza calibrada de `vision.md`.
**Consecuencias:** agregar o reemplazar una fuente es escribir un adaptador, sin tocar dominio ni modelo de datos. Si una fuente desaparece (riesgo real y ya identificado en `architecture.md` §10.5), el impacto queda contenido. La separación de los tres niveles de conocimiento — hecho observado / inferencia / prior de meta — es la que hace que esto sea verificable y no solo una intención (`inference.md` §1).
**Estado:** Aceptada, 2026-08-03. Formaliza lo que `architecture.md` §10.4 ya describía. Ver `inference.md` §7.

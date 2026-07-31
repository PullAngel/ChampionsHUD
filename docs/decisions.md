# Registro de decisiones

Formato: contexto → decisión → consecuencias → estado. Cuando un documento parezca contradecir algo listado acá, este documento gana. Las decisiones marcadas como **supersede** anulan explícitamente un diseño anterior mencionado en el propio historial del proyecto.

---

### 1. El copiloto nunca recomienda una jugada
**Contexto:** un diseño anterior incluía un modo "compacto" que ordenaba los cuatro movimientos propios por conveniencia — funcionalmente un recomendador, en contradicción directa con la filosofía de "nunca jugar por el usuario".
**Decisión:** el producto informa (hechos, estimaciones, eliminación de hipótesis, consecuencias de una acción hipotética si se pide explícitamente) pero jamás rankea, sugiere o resalta una jugada como mejor que otra.
**Consecuencias:** cualquier feature futura que se parezca a un ranking de acciones se descarta en revisión de diseño, no se implementa "a modo de prueba".
**Estado:** Aceptada. **Supersede** el diseño previo de modo compacto/`suggest()`.

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

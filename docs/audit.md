# Auditoría técnica

Estado del código relevado archivo por archivo. Este documento es un punto en el tiempo, no un reporte vivo — cuando la Fase 0 del roadmap se complete, debería re-ejecutarse la auditoría y actualizar este archivo.

**Re-auditado el 2026-07-31** contra el HEAD subido a GitHub. Varios hallazgos de la versión anterior de este documento ya no coincidían con el código real (algunos se resolvieron, uno directamente desapareció con el archivo que describía). Cada sección de abajo indica su estado verificado a esa fecha. Ver también el registro de cambios al final del documento.

Cada hallazgo de la sección 5 tiene su ítem correspondiente, con verificación concreta, en el checklist de [`roadmap.md` — Fase 0](./roadmap.md#fase-0--estabilización-fase-actual). Ese es el orden de ejecución recomendado para Claude Code.

## 1. Arquitectura general (re-verificado 2026-07-31)

El proyecto son dos mitades acopladas por un puente angosto:

```
Android/Kotlin (5 archivos, ~1251 líneas)      hud.html (1 archivo, 1503 líneas)
────────────────────────────────────      ─────────────────────────
MainActivity      → onboarding             Motor de daño, inferencia,
OverlayService     → ventana + puente       predicción, estado, vistas,
ScreenCapture      → MediaProjection        eventos — todo vive acá
SpriteMatcher      → visión por computadora
Storage            → persistencia + red
```

El puente son **13** métodos `@JavascriptInterface` (Kotlin→JS) y **2** callbacks `window.onX` (JS→Kotlin) — `onScan` y `onMetaUpdate`. La decisión de fondo — mover casi toda la lógica de combate a JS plano dentro de un WebView — es deliberada y correcta: permite iterar (editar-probar-ver) en segundos con Node, sin recompilar Kotlin. Esta decisión se mantiene y se refuerza en `architecture.md` (separación Motor/Cliente).

**Nota:** la versión anterior de esta auditoría listaba un sexto archivo, `ReconnectActivity` (recuperación de permiso de captura), y lo elogiaba en la sección "qué funciona bien". Ese archivo no existe en ningún lugar del repositorio actual — ni la clase, ni la palabra "reconnect" en ningún `.kt`. No hay evidencia de qué reemplazó ese mecanismo, si es que algo lo hizo. Ver hallazgo 5.8.

## 2. Flujo de la app (al momento de la auditoría)

1. `MainActivity` pide permisos secuenciales (overlay, notificaciones, captura) y lanza `OverlayService` como foreground service.
2. `OverlayService.onCreate()` construye un único WebView que carga `hud.html` una sola vez y vive mientras el servicio viva.
3. Al escanear, el servicio oculta burbuja y panel, captura, pasa el bitmap a `SpriteMatcher` en un hilo de IO, y emite el resultado al WebView.
4. Todo lo demás (equipo, daño, predicción, campo) ocurre en JS: mutación de estado → render → vista nueva.
5. Persistencia: combate y equipos como JSON en `filesDir` con debounce; `meta.json` vive en `assets/` y puede reemplazarse por descarga bajo pedido explícito del usuario.

## 3. Flujo de datos: qué es local, qué viene de internet

**Local, empaquetado en el APK:** `hud.html` completo, `meta.json` (datos de uso *estimados*, no medidos), tablas embebidas (~42 especies, 11 megas, ~85 movimientos, ítems, colores de tipo) como *fallback* si no hay `dex.json`.

**Local, generado por el desarrollador y copiado a mano a `assets/`:** `sprite_index.json` (huellas de ~718 sprites, vía `build_sprite_index.py` contra Bulbagarden Archives), `dex.json` (especies/movimientos/learnsets, vía `build_dex.py` contra la API pública de Pokémon Showdown).

**Red en tiempo real, solo si el usuario lo pide explícitamente:** `Android.updateMeta(url)` descarga un `meta.json` alternativo de una URL provista por el usuario. Es el único tráfico de red que la app inicia por sí sola en producción.

**No implementado:** integración con fuentes de meta de torneos reales (Limitless/Pikalytics). `build_meta.py` es un stub: `fetch_usage()` devuelve `{}` siempre.

## 4. Reconocimiento del equipo rival

`SpriteMatcher.readTeamPreview()`, en tres pasos:

1. **Encontrar la pila de tarjetas:** en vez de asumir "el color más común" (que en la práctica es el fondo del estadio), prueba ~20 colores candidatos y se queda con el que produce bandas horizontales regulares (validado contra capturas reales: 0.997 el color correcto vs. 0.615 el segundo).
2. **Recortar cada sprite:** el fondo de cada tarjeta se estima fila por fila con la franja izquierda; el sprite se aísla por densidad de "no-fondo".
3. **Identificar:** la silueta se normaliza a su caja envolvente y se compara contra las 718 referencias en dos pasadas — primero por forma, después por color (para desambiguar shiny vs. normal).

Esta es la parte más sofisticada y mejor iterada de todo el proyecto — reescrita varias veces contra evidencia real, no por intuición. El enfoque de hipótesis-y-verificación generaliza mejor que asumir un color fijo y es el patrón a imitar en el resto del sistema.

## 5. Hallazgos confirmados

### 5.1 ~~Bug de producción — mismatch de campos `predict()` ↔ `vPre()`~~ — **RESUELTO, verificado 2026-07-31**
La versión anterior de este documento reportaba que `predict()` devolvía `{cover, survive, mode, score}` mientras `vPre()` leía `{role, off, surv, def}`, y que por eso el subtítulo de rol en la pestaña PREVIA siempre mostraba "apoyo". **Esto ya no es así.** En el código actual (`hud.html:713` y `hud.html:1039`), `predict()` devuelve objetos con `{off, def, role, score}` (rivales) y `{off, surv, role, score}` (propios), y `vPre()` lee exactamente esos campos (`x.role`, `x.off`, `x.surv||x.def`, `x.score`). El subtítulo varía correctamente según el Pokémon: "control de ritmo" / "amenaza directa" / "aguanta" / "apoyo".
No queda claro si esto se corrigió en una sesión de la que no quedó registro en `decisions.md`, o si el hallazgo original ya estaba desactualizado al escribirse. En cualquier caso, **no requiere trabajo** — se mantiene la entrada acá para no perder la razón detrás del principio de "fallo ruidoso" en `decisions.md` #8, que sigue siendo válido como principio aunque este ejemplo puntual ya no aplique.

### 5.2 Bug silencioso crítico — idioma de habilidades — **CONFIRMADO VIGENTE, 2026-07-31**
`build_dex.py` extrae habilidades en inglés desde Pokémon Showdown (`p.get("abilities", {}).values()`); el motor de daño (`calc()`, `hud.html:552`) las compara contra literales hardcodeados en español (`"Escama Especial"`, `"Piel Feérica"`, `"Levitación"`, `"Absorbe Fuego"`, etc. — más de 15 solo en esa función). No existe ninguna capa de traducción intermedia ni tabla de slugs. El flujo que el propio proyecto recomienda para tener el roster completo (`loadDex()`, que sobreescribe `ABIL[key]` con los nombres en inglés de `dex.json`) rompe en silencio todos los modificadores de habilidad del motor de daño, sin ningún error visible. Este es el hallazgo más grave del documento — sigue intacto.

### 5.3 `meta.json` desincronizado — **CONFIRMADO VIGENTE, 2026-07-31, con evidencia concreta**
Cruzando `meta.json` contra las tablas canónicas `IT` y `ABIL` de `hud.html`:
- **Ítems en `meta.json` que no existen en la tabla `IT`:** Baya Occa, Mental Herb, Refuerzo, Charizardita Y, Banda Focus, Bota Gruesa, Anteojos Elección, Cinta Elección, Gafas Aisladoras, Tyranitarita, Roca Humedad, Chaleco Asalto, Semilla Hierba, Blastoisita, Charizardita X.
- **Habilidades en `meta.json` que no existen en la tabla `ABIL`:** Guts, Fuerza Interior, Ovación Fúnebre, Chorro Potente, Impulso Químico.

Nota aparte: `meta.json` trae metadatos honestos (`"source": "estimado"`, con una nota explícita de que son datos de arranque, no de uso real) — el problema no es que sea estimado, es que ni siquiera coincide internamente con las tablas del propio HUD. No hay ningún mecanismo que detecte esta desincronización.

### 5.4 Orden de dependencia invertido — **CONFIRMADO VIGENTE, 2026-07-31**
`PREDICCIÓN` (`hud.html:684`) usa `learnable()`, definida más abajo en `DEX COMPLETO` (`hud.html:835`), con la sección `ESTADO` empezando aún más abajo (`hud.html:907`). Funciona en runtime porque son *declaraciones* de función que se resuelven antes de ser *invocadas* — pero contradice el orden de capas documentado en `architecture.md`, y hace que leer el archivo de arriba a abajo lleve a conclusiones equivocadas sobre qué depende de qué. Las líneas cambiaron respecto al reporte anterior pero el problema es idéntico.

### 5.5 i18n — **PEOR DE LO REPORTADO: no existe, no "parcialmente adoptado"**
El reporte anterior decía que de 146 claves de texto definidas en una tabla `STRINGS`, `vMine()` usaba `t()` de forma consistente y el resto tenía literales hardcodeados. **Verificado 2026-07-31: no existe ninguna tabla `STRINGS` ni función `t()` en todo `hud.html`.** Cero ocurrencias de ambas cadenas en el archivo completo, incluida `vMine()`. La capa de presentación/i18n que exige la decisión #7 (`decisions.md`) y la sección 5 de `architecture.md` no está construida — no es una adopción parcial, es una ausencia total. Todo el texto visible está hardcodeado en español directamente en las funciones `vX()`.

**Actualización de la misma fecha (decisión #17):** al revisar capturas reales del juego se confirmó que el juego de Angel corre en inglés, no en español — fijar el HUD en español asumía un idioma que no coincide con la pantalla real. Se decidió que el HUD tiene selector de idioma explícito (inglés/español como mínimo), y que este hallazgo se resuelve junto con §5.2 como un solo trabajo: slugs canónicos + tabla de traducción. Ver `decisions.md` #17 y `roadmap.md` Fase 0, ítem 1.

### 5.6 Dependencia declarada sin uso — **CONFIRMADO VIGENTE, 2026-07-31**
`kotlinx-coroutines-android:1.8.1` sigue en `app/build.gradle.kts`; cero imports de `kotlinx.coroutines` en cualquier archivo `.kt`. El proyecto sigue usando `HandlerThread`/`Handler` para el hilo secundario (ver `ScreenCapture.kt`).

### 5.7 Sin tests automatizados — **CONFIRMADO VIGENTE, 2026-07-31**
No existe `app/src/test` ni `app/src/androidTest`, ni ningún otro directorio de pruebas en el repositorio.

### 5.8 `ReconnectActivity` no existe — **HALLAZGO NUEVO, 2026-07-31**
La versión anterior de este documento describía `ReconnectActivity` como uno de los 6 archivos Kotlin del proyecto y la elogiaba en la sección "qué funciona bien" por resolver la recuperación de permiso de captura en Android 14+. Ese archivo, esa clase y cualquier referencia a "reconnect" **no existen en el código actual** — ni en los 5 archivos `.kt` que sí existen, ni en ningún otro lugar del repositorio.
`ScreenCapture.kt` sí registra un callback (`projection.registerCallback { onStop() { dead = true } }`) que marca la captura como muerta cuando el sistema revoca el permiso, pero no hay evidencia en el código de qué pasa después — si algo dispara automáticamente un nuevo flujo de permiso o si el usuario queda sin captura hasta reabrir la app manualmente. **Esto es un hallazgo abierto, no verificado en profundidad**: haría falta trazar qué consume `dead` en `OverlayService.kt` para saber si la recuperación de permiso sigue funcionando de otra forma o si genuinamente se perdió. Se marca como pendiente de investigar, no como bug confirmado — a diferencia de 5.2, 5.3, 5.4, 5.6 y 5.7, no se verificó el comportamiento en runtime, solo la ausencia del archivo.

### 5.9 `build_meta.py` sigue siendo un stub — **CONFIRMADO VIGENTE, 2026-07-31**
`fetch_usage()` (línea 37) sigue devolviendo `{}` incondicionalmente. Consistente con el diseño de Fase 2 en `architecture.md` §10 — no es un hallazgo de Fase 0, se mantiene documentado acá por completitud ya que `meta.json` trae la nota explícita "Corré build_meta.py para reemplazarlos".

## 6. Qué funciona bien y por qué vale la pena preservarlo

- **Lógica de combate en HTML/JS, cascarón en Kotlin.** La decisión más importante del proyecto y bien tomada — permite iterar en segundos sin recompilar. Se formaliza y refuerza en `architecture.md` como separación Motor/Cliente.
- **Captura persistente con un solo `VirtualDisplay` por permiso.** Verificado en `ScreenCapture.kt`. **La reconexión automática ya no está confirmada** (ver §5.8) — se retira esa parte de la afirmación hasta investigarlo.
- **`render()` con manejo de errores** — un error en una vista ya no congela toda la interfaz. Re-verificado en `hud.html:1015`.
- **Selectores propios en vez de `<select>` nativo**, justificado por la ventana `FLAG_NOT_FOCUSABLE` (no robarle foco al juego).
- **Detección de sprites por hipótesis-y-verificación** en vez de asumir un color fijo — el patrón más sólido del proyecto. Re-verificado línea por línea en `SpriteMatcher.kt` contra esta descripción: coincide en los tres pasos y en los umbrales.
- **WebView único y persistente** — no se pierde el estado del combate al abrir/cerrar el panel.
- **Persistencia atómica y tolerante a fallos:** escritura atómica, versionado por campo `v`, degradación a `{}` si el archivo está corrupto en vez de crashear.

## 7. Deuda técnica, en orden de severidad (actualizado 2026-07-31)

1. Idioma de habilidades entre `build_dex.py` y `calc()` (§5.2) — el más grave porque degrada silenciosamente todo el motor de daño. **Vigente.**
2. `meta.json` desincronizado de las tablas canónicas (§5.3) — ahora con la lista exacta de ítems/habilidades huérfanos. **Vigente.**
3. i18n inexistente, no parcial (§5.5) — más grave de lo reportado antes. **Vigente, empeorado.**
4. `build_meta.py` sin implementar pese a presentarse como una de las fuentes de datos del sistema (§5.9). **Vigente, es trabajo de Fase 2.**
5. Dependencia declarada sin uso (§5.6). **Vigente.**
6. Un único archivo de 1503 líneas sin módulos ni contratos tipados entre secciones — la causa raíz que permitió que 5.2 y 5.3 ocurrieran sin que nada las detectara. **Vigente.**
7. ~~Mismatch de campos `predict()` ↔ `vPre()`~~ — **retirado de la lista, resuelto (§5.1).**
8. `ReconnectActivity` desaparecido sin reemplazo documentado (§5.8) — severidad sin determinar, requiere investigación antes de poder priorizarlo.

## 8. Patrón transversal

Los hallazgos 5.2 y 5.3 comparten la misma forma: el sistema sigue funcionando y reportando éxito mientras produce un resultado incorrecto. No es una coincidencia — es la consecuencia directa de no tener contratos de forma ni validación en los bordes entre módulos. Este patrón es el origen directo del principio de "fallo ruidoso, nunca silencioso" adoptado en `decisions.md` #8, y de los requisitos de validación en build y contratos tipados en `architecture.md` §6 y §8. (La re-auditoría de 2026-07-31 retiró a 5.1 de este patrón porque ya no reproduce, pero el principio se mantiene por 5.2 y 5.3, que sí siguen vigentes.)

## 9. Preguntas frecuentes sobre el estado del código

**¿Qué hace bien la aplicación hoy?** El reconocimiento de sprites es genuinamente sólido y validado contra evidencia real. La captura de pantalla resuelve correctamente una restricción real del sistema operativo. El motor de daño implementa una fórmula verificada contra la pantalla de stats del juego. La persistencia es prolija.

**¿Qué componentes son más difíciles de mantener?** `hud.html` completo, por tamaño y por compartir un único scope global sin tipos. En particular, la relación `meta.json`/tablas canónicas, y la coexistencia de tablas embebidas en español con `dex.json` en inglés tratadas como intercambiables cuando no lo son.

**¿Qué partes generan más fricción en un combate real?** Cargar el equipo propio a mano (sin lectura automática todavía). El escaneo del rival depende de que la burbuja esté fuera de cierta zona de pantalla. La predicción es tan buena como el `meta.json` estimado que la alimenta hoy.

**¿Qué funcionalidades están declaradas pero incompletas?** Lectura automática del equipo propio. Pipeline real de datos de meta (`build_meta.py` es un placeholder). Seguimiento de objetos consumidos (baya usada, banda gastada). Aplicación automática de Intimidate al entrar (hoy manual). El sistema de idiomas — no construido en absoluto, no solo desconectado (ver §5.5).

## 10. Registro de cambios de esta auditoría

- **2026-07-31 — re-auditoría completa contra el HEAD en GitHub.** Motivo: la versión anterior de este documento no coincidía con el código real en varios puntos — se detectó al contrastar la documentación recién migrada contra el código de captura de team preview. Cambios:
  - §5.1 (mismatch `predict()`/`vPre()`): **cerrado**, ya no reproduce.
  - §5.2, §5.3, §5.4, §5.6, §5.7: **re-confirmados vigentes**, con evidencia actualizada (números de línea, listas concretas).
  - §5.5 (i18n): **corregido el diagnóstico** — no es adopción parcial, es ausencia total de `STRINGS`/`t()`.
  - §5.8 (`ReconnectActivity`): **hallazgo nuevo**, el archivo que la auditoría anterior describía ya no existe y no se identificó reemplazo.
  - §5.9 (`build_meta.py` stub): agregado por completitud, ya estaba implícito en la versión anterior.
  - Roadmap Fase 0: ver `roadmap.md` — el ítem 1 (antes ligado a §5.1) se retiró del checklist.

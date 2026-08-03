# Auditoría técnica

Estado del código relevado archivo por archivo. Este documento es un punto en el tiempo, no un reporte vivo — cuando la Fase 0 del roadmap se complete, debería re-ejecutarse la auditoría y actualizar este archivo.

**Re-auditado el 2026-07-31** contra el HEAD subido a GitHub. Varios hallazgos de la versión anterior de este documento ya no coincidían con el código real (algunos se resolvieron, uno directamente desapareció con el archivo que describía). Cada sección de abajo indica su estado verificado a esa fecha. Ver también el registro de cambios al final del documento.

Cada hallazgo de la sección 5 tiene su ítem correspondiente, con verificación concreta, en el checklist de [`roadmap.md` — Fase 0](./roadmap.md#fase-0--estabilización-fase-actual). Ese es el orden de ejecución recomendado para Claude Code.

## 1. Arquitectura general (re-verificado 2026-07-31)

El proyecto son dos mitades acopladas por un puente angosto:

```
Android/Kotlin (6 archivos, ~1226 líneas)      hud.html (1 archivo, ~2310 líneas)
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

### 5.2 ~~Bug silencioso crítico — idioma de habilidades~~ — **RESUELTO, 2026-07-31**
`build_dex.py` extrae habilidades en inglés desde Pokémon Showdown; el motor de daño (`calc()`) comparaba contra literales hardcodeados en español, rompiendo en silencio al cargar `dex.json`. Corregido: se introdujo `ABIL_I18N` (tabla slug → `{en, es}`, generada desde PokeAPI, no a mano) y `abilName()`; `calc()`, `ROLE_AB`, `loadDex()` y la UI de habilidades ahora comparan y guardan por slug canónico. La tabla de especies embebida (`ABIL`) se regeneró desde `dex.json` real en vez de mantenerse a mano — de paso corrigió datos ya desactualizados (ej. Gengar figuraba con Levitación, retirada desde la gen 8). Quedaron marcadas con TODO en el código dos habilidades que no se pudieron identificar contra Showdown/PokeAPI (`Barrera Férrea`, `Sartén Vudú` — posibles mecánicas propias de Champions) y un hallazgo nuevo: el efecto que el código le atribuye a `Robustez`/Sturdy no es el real de Sturdy (sobrevivir un OHKO) — parece una confusión de diseño previa a esta sesión, sin tocar (requiere decisión de producto, no es parte de este fix de idioma).

### 5.3 ~~`meta.json` desincronizado~~ — **RESUELTO, 2026-07-31**
Además de la desincronización de ítems/habilidades, se encontró algo más grave al regenerar: **14 de las 34 entradas eran de especies ya no legales** en la regulación actual (Mewtwo, Salamence, Togekiss, Landorus-T, Rillaboom, Indeedee, Urshifu, Ursaluna, Kingambit, Flutter Mane, Iron Hands, Baxcalibur, Chi-Yu, Iron Valiant, Amoonguss, Ferrothorn, Magnezone) — la predicción de team preview podía estar considerando Pokémon que ni siquiera pueden aparecer en pantalla. Se podaron esas 14, se corrigieron ítems inexistentes en Champions (Chaleco Asalto, Cinta/Anteojos Elección no existen en este juego; varios nombres estaban directamente mal escritos) y habilidades que no correspondían a la especie real según `dex.json` (Corviknight con Magic Bounce en vez de Mirror Armor, Grimmsnarl con Shadow Tag, Basculegion con Unnerve, Talonflame con Static, Blastoise con Water Bubble, Farigiraf con Thick Fat — ninguna de esas seis es una habilidad real de esa especie). Se sumaron 10 especies con evidencia real de capturas de pantalla de Angel (4 con set exacto observado, 6 estimadas) en vez de rellenar a ciegas. Total: 30 especies, 0 ítems/habilidades huérfanos verificado por validación cruzada contra las tablas canónicas.

### 5.4 Orden de dependencia invertido — **CONFIRMADO VIGENTE, 2026-07-31**
`PREDICCIÓN` (`hud.html:684`) usa `learnable()`, definida más abajo en `DEX COMPLETO` (`hud.html:835`), con la sección `ESTADO` empezando aún más abajo (`hud.html:907`). Funciona en runtime porque son *declaraciones* de función que se resuelven antes de ser *invocadas* — pero contradice el orden de capas documentado en `architecture.md`, y hace que leer el archivo de arriba a abajo lleve a conclusiones equivocadas sobre qué depende de qué. Las líneas cambiaron respecto al reporte anterior pero el problema es idéntico.

### 5.5 ~~i18n~~ — **CORREGIDO EL DIAGNÓSTICO Y RESUELTO, 2026-07-31**
El reporte anterior decía que no existía ninguna tabla `STRINGS` ni función `t()` en `hud.html`. **Ese diagnóstico estaba mal** — la búsqueda solo cubrió esos dos nombres literales. En realidad ya existía un sistema de i18n parcial con otros nombres: `LANG` (persistido en `localStorage` como `hudLang`, default `"en"` — con un comentario del propio código explicando que el juego de Angel está en inglés), `mvName()`/`itName()` (resuelven nombre de movimiento/ítem según `LANG`), `ES_ALT` (tabla de overrides al español para movimientos nuevos), y un selector de idioma ya funcionando en la UI (botones English/Español, `hud.html` ~1318). Lo que sí faltaba por completo era el equivalente para **habilidades** — cero cobertura, ni parcial.
Corregido junto con §5.2: se agregó `ABIL_I18N`/`abilName()` siguiendo el mismo patrón que `mvName`/`itName`, así que ahora movimientos, ítems y habilidades respetan el selector de idioma de forma consistente. **Sigue pendiente, fuera de este alcance:** el texto de la interfaz en sí (etiquetas como "Habilidad", "Objeto", mensajes de las vistas `vX()`) sigue hardcodeado en español — el selector hoy traduce los *datos* del juego (nombres de Pokémon/movimientos/ítems/habilidades), no el *chrome* de la UI. Completar eso es un trabajo bastante más grande (recorrer las ~1500 líneas de `hud.html`) que no se justificaba para cerrar el bug de §5.2.

### 5.6 Dependencia declarada sin uso — **CONFIRMADO VIGENTE, 2026-07-31**
`kotlinx-coroutines-android:1.8.1` sigue en `app/build.gradle.kts`; cero imports de `kotlinx.coroutines` en cualquier archivo `.kt`. El proyecto sigue usando `HandlerThread`/`Handler` para el hilo secundario (ver `ScreenCapture.kt`).

### 5.7 Sin tests automatizados — **CONFIRMADO VIGENTE, 2026-07-31**
No existe `app/src/test` ni `app/src/androidTest`, ni ningún otro directorio de pruebas en el repositorio.

### 5.8 `ReconnectActivity` no existe — **INVESTIGADO Y CERRADO, 2026-07-31**
La versión anterior de este documento describía `ReconnectActivity` como uno de los 6 archivos Kotlin del proyecto y la elogiaba por resolver la recuperación de permiso de captura en Android 14+. Ese archivo no existe en el código actual.
**Se trazó el flujo completo:** cuando Android revoca el permiso (`SecurityException` en `ScreenCapture.ensure()`, `ScreenCapture.kt:99-101`, o el callback `projection.registerCallback{onStop()}`), se marca `dead=true` y `ensure()` devuelve el string `"Android revocó el permiso de captura. Cerrá el HUD y volvé a abrirlo."`. Ese mensaje viaja por `grab()` → `OverlayService.scan()` (`OverlayService.kt:301-311`, que lo empaqueta como `{"error": ...}`) → `emit("onScan", json)` → `window.onScan()` en `hud.html:1523-1526`, que lo muestra explícitamente en el panel.
**Conclusión:** no hay reconexión automática (a diferencia de lo que `ReconnectActivity` presumiblemente hacía) — el usuario tiene que cerrar y reabrir la burbuja a mano. Pero el fallo es explícito y accionable, no silencioso: consistente con el principio de "fallo ruidoso, nunca silencioso" (`decisions.md` #8). No se considera un bug — es una degradación aceptable dado que ya es ruidosa. Si en el futuro se quiere automatizar la re-solicitud del permiso, es una mejora de UX de Fase 1, no una corrección de bug.

### 5.10 Tabla `MEGA` incompleta y desalineada con `SPD` — **PARCIALMENTE RESUELTO, 2026-08-03**
Encontrado al depurar la captura del equipo propio (el equipo real de Angel lleva Venusaurite y Swampertite).
**Lo resuelto:** `MEGA` no tenía **ninguna** entrada de Venusaur, así que "Venusaurite" era irreconocible. Peor: tres entradas que sí existían (`Swampertite`, `Sablenita`, `Mawilita`) apuntaban a claves de forma mega **inexistentes en `SPD`** — tocar "Megaevolucionado" en un Swampert con su piedra hacía que `S()` devolviera `null` y `myStat()` tirara una excepción. Agregadas las cuatro formas con stats sacadas de `dex.json`. Hay un test (`tests/run.js`) que recorre `MEGA` entera y falla si alguna entrada apunta a una forma que no existe, para que no vuelva a pasar en silencio.
**Lo que sigue vigente:** `dex.json` trae **76 formas mega** y `MEGA` cubre **15**. Las 61 restantes no se pueden completar de memoria: los nombres de las piedras son irregulares (Blastoise → *Blastoisinite*, Sableye → *Sablenite*, Heracross → *Heracronite*) y Champions agrega megas nuevas (Raichu, Meganium, Feraligatr, Eelektross, Greninja, Falinks, Scovillain, Glimmora…) cuyos nombres de piedra no están en ninguna fuente ya relevada. **Es una tarea de datos, no de código** — completarla adivinando produciría exactamente la clase de error silencioso que este proyecto viene arrastrando. Queda para cuando haya una fuente confiable de nombres de objeto de Champions (candidato natural: el mismo pipeline de Fase 2).
**Deuda relacionada, sin tocar:** las claves de `MEGA` mezclan español (`Blastoisita`, `Gengarita`) e inglés (`Swampertite`) sin criterio. Se mitigó con una conversión `-ite`↔`-ita` en `findItem()`, pero la tabla debería unificarse a slugs canónicos cuando se regenere (decisión #7).

### 5.11 `loadDex()` asigna claves de formas alternativas de forma frágil — **VIGENTE, no corregido**
`loadDex()` (`hud.html`) asigna a cada forma alternativa la clave `900000+num*10+(Object.keys(byNum).length%10)`. El último dígito depende de **cuántas especies se procesaron antes**, no de la forma en sí, así que la clave que le toca a una mega concreta es esencialmente arbitraria y puede colisionar con otra forma del mismo Pokémon (una mega y una Gmax del mismo `num` compiten por el mismo rango de 10 claves). Además el chequeo `byNum[sp.num]` consulta una clave distinta de la que después escribe (`byNum[key]=1`), así que la detección de "ya vi este número" no hace lo que aparenta.
Consecuencia práctica: las claves de forma mega que `MEGA` referencia (`900061`, `901261`, …) pueden no coincidir con las que `loadDex()` genera cuando hay `dex.json` cargado. Hoy no rompe porque las entradas de `MEGA` apuntan a las formas embebidas, que `loadDex()` no borra. **Por eso la entrada nueva de Venusaur usa una clave en el rango `99xxxx`**, fuera del alcance de lo que `loadDex()` puede generar. No se corrigió el generador de claves en sí: es un cambio de riesgo medio en código que hoy funciona, y conviene hacerlo junto con la regeneración de `MEGA` (§5.10), no antes.

### 5.12 La captura puede devolver un fotograma viejo en pantallas estáticas — **VIGENTE, no corregido**
`ScreenCapture.grab()` intenta primero `take(r)`, que devuelve el fotograma más reciente **ya encolado**. El `ImageReader` tiene `maxImages=3` y, en una pantalla que no cambia, esos tres buffers se llenan y el productor se frena — por lo que el "más reciente encolado" puede ser de antes de que el HUD se ocultara, es decir, con el panel tapando lo que se quiere leer.
El escaneo del rival no lo sufre porque el team preview está animado (llegan fotogramas nuevos todo el tiempo). La captura del equipo propio sí es una pantalla estática, así que es justo el caso de riesgo. En las pruebas reales hasta ahora **no se manifestó** — la escalera de reintentos (250/600/1200/2000 ms) parece cubrirlo — por eso no se tocó: es código Kotlin que no se puede compilar ni probar en el entorno de desarrollo actual, y romperlo dejaría a Angel sin poder buildear. **El arreglo, si hiciera falta:** vaciar los buffers encolados (`acquireLatestImage()` en bucle, descartando) **antes** de ocultar el panel, y recién después capturar — así cualquier fotograma en cola es necesariamente posterior. Si aparece una lectura que muestra el panel del HUD tapando las tarjetas, esta es la causa.

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

## 7. Deuda técnica, en orden de severidad (actualizado 2026-08-03, tercera pasada)

1. `build_meta.py` sin implementar pese a presentarse como una de las fuentes de datos del sistema (§5.9). **Vigente, es el corazón de la Fase 2.**
2. Tabla `MEGA` con 15 de las 76 formas mega que trae `dex.json` (§5.10). **Vigente**, y es la que más se nota en uso real: cualquier Pokémon con una piedra fuera de esas 15 no se reconoce al capturar el equipo. Es trabajo de datos, no de código.
3. `loadDex()` genera claves de formas alternativas de forma frágil y colisionable (§5.11). **Vigente.** Hoy no rompe, pero es una trampa puesta para el futuro; conviene resolverlo junto con el punto 2.
4. Un único archivo de ~2300 líneas sin módulos ni contratos tipados entre secciones — la causa raíz que permitió que 5.2 y 5.3 (ya resueltos) ocurrieran sin que nada las detectara. **Vigente**, y creciendo: el archivo casi duplicó su tamaño. La decisión de no modularizar (#18) sigue en pie, pero el contrapeso acordado ahí era la suite de tests — que sí creció en proporción (de 0 a 65 casos), así que el trato se está cumpliendo.
5. Captura potencialmente estancada en un fotograma viejo en pantallas estáticas (§5.12). **Vigente, sin manifestarse todavía**; documentado el arreglo por si aparece.
6. Dependencia declarada sin uso (§5.6). **Vigente, trivial.**
7. Texto de interfaz (labels, mensajes de las vistas `vX()`) sigue hardcodeado en español pese a que el selector de idioma ya cubre los datos del juego (§5.5) — inconsistencia menor, no un bug.
8. Tres comparaciones de habilidad sin resolver del todo, marcadas con TODO en el código tras la migración a slugs (§5.2): `Barrera Férrea` y `Sartén Vudú` sin poder identificarse contra Showdown/PokeAPI, y el efecto atribuido a `Robustez`/Sturdy que no es el real de esa habilidad.

**Retirado de esta lista:** `ReconnectActivity` (§5.8) figuraba como "severidad sin determinar, requiere investigación" cuando §5.8 ya lo había investigado y cerrado como no-bug en la misma pasada — contradicción interna del documento, corregida el 2026-08-03.

**Resueltos:** idioma de habilidades (§5.2), `meta.json` desincronizado (§5.3), mismatch `predict()`/`vPre()` (§5.1), piedras mega apuntando a formas inexistentes (§5.10, parte crítica).

## 8. Patrón transversal

Los hallazgos 5.2 y 5.3 (ya resueltos) compartían la misma forma: el sistema seguía funcionando y reportando éxito mientras producía un resultado incorrecto. No fue una coincidencia — es la consecuencia directa de no tener contratos de forma ni validación en los bordes entre módulos. Este patrón sigue siendo el origen del principio de "fallo ruidoso, nunca silencioso" adoptado en `decisions.md` #8, y de los requisitos de validación en build y contratos tipados en `architecture.md` §6 y §8 (deuda técnica #3 de la sección anterior, todavía pendiente) — resolver estos dos casos puntuales no resuelve la causa raíz que permitió que existieran.

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

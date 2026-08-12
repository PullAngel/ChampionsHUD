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

**Corrección importante, 2026-08-06** — esta valoración era demasiado generosa y hay que leerla con el hallazgo de abajo (§5.14): los pasos 1 y 3 son sólidos, pero **el paso 2 (recortar) es el eslabón débil y es el que causa los errores reales de identificación** que Angel viene reportando. Además, la confianza que el sistema reportaba estaba estructuralmente rota y no servía para detectar esos errores.

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

### 5.6 Dependencia declarada sin uso — ~~**RESUELTO**~~ (verificado 2026-08-06)
`kotlinx-coroutines-android:1.8.1` estaba en `app/build.gradle.kts` sin un solo import de `kotlinx.coroutines` en ningún `.kt`; el proyecto usa `HandlerThread`/`Handler` para el hilo secundario (ver `ScreenCapture.kt`). **Se removió en la Fase 0 (ítem 8), pero este documento siguió diciendo "CONFIRMADO VIGENTE" hasta el 2026-08-06** — contradicción interna encontrada revisando la deuda técnica contra el código real: `build.gradle.kts` no tiene ninguna referencia a coroutines. Corregido acá y en §7.

### 5.7 Sin tests automatizados — **CONFIRMADO VIGENTE, 2026-07-31**
No existe `app/src/test` ni `app/src/androidTest`, ni ningún otro directorio de pruebas en el repositorio.

### 5.8 `ReconnectActivity` no existe — **INVESTIGADO Y CERRADO, 2026-07-31**
La versión anterior de este documento describía `ReconnectActivity` como uno de los 6 archivos Kotlin del proyecto y la elogiaba por resolver la recuperación de permiso de captura en Android 14+. Ese archivo no existe en el código actual.
**Se trazó el flujo completo:** cuando Android revoca el permiso (`SecurityException` en `ScreenCapture.ensure()`, `ScreenCapture.kt:99-101`, o el callback `projection.registerCallback{onStop()}`), se marca `dead=true` y `ensure()` devuelve el string `"Android revocó el permiso de captura. Cerrá el HUD y volvé a abrirlo."`. Ese mensaje viaja por `grab()` → `OverlayService.scan()` (`OverlayService.kt:301-311`, que lo empaqueta como `{"error": ...}`) → `emit("onScan", json)` → `window.onScan()` en `hud.html:1523-1526`, que lo muestra explícitamente en el panel.
**Conclusión:** no hay reconexión automática (a diferencia de lo que `ReconnectActivity` presumiblemente hacía) — el usuario tiene que cerrar y reabrir la burbuja a mano. Pero el fallo es explícito y accionable, no silencioso: consistente con el principio de "fallo ruidoso, nunca silencioso" (`decisions.md` #8). No se considera un bug — es una degradación aceptable dado que ya es ruidosa. Si en el futuro se quiere automatizar la re-solicitud del permiso, es una mejora de UX de Fase 1, no una corrección de bug.

### 5.10 Tabla `MEGA` incompleta y desalineada con `SPD` — **CASI RESUELTO, 2026-08-03 (segunda pasada, sprint 2.3)**
Encontrado al depurar la captura del equipo propio (el equipo real de Angel lleva Venusaurite y Swampertite).
**Primera pasada, mismo día:** `MEGA` no tenía **ninguna** entrada de Venusaur; peor, tres entradas que sí existían (`Swampertite`, `Sablenita`, `Mawilita`) apuntaban a claves de forma mega **inexistentes en `SPD`** — tocar "Megaevolucionado" en un Swampert con su piedra hacía que `S()` devolviera `null` y `myStat()` tirara una excepción. Agregadas las cuatro formas con stats de `dex.json`. Cobertura en ese momento: 13 especies de 76.
**Segunda pasada (sprint 2.3, con acceso real a `items.js` de Pokémon Showdown):** se cruzó cada piedra mega real (campo `megaStone`) contra las 76 formas de `dex.json`, y se agregaron **27 especies más** con stats reales, no inventadas — ver `roadmap.md` Fase 2, sprint 2.3, para la lista completa. Cobertura: **40 de 76**. Hay un test (`tests/run.js`) que recorre `MEGA` entera y falla si alguna entrada apunta a una forma que no existe.
**Lo que sigue vigente, y por qué no se puede cerrar del todo:** las **36 formas restantes son megas exclusivas de Champions** (Staraptor, Delphox, Floette, Raichu, Froslass, Scovillain, Glimmora, Dragonair, Meowstic, Malamar, Pyroar, Greninja, Chesnaught, Emboar, Eelektross, Chandelure, Golurk, Falinks, Crabominable, Hawlucha, Dragalge, Barbaracle…) que nunca existieron en los juegos principales, así que **ninguna fuente real tiene el nombre de su piedra** — ni Showdown, ni PokeAPI. Adivinarlos (ej. "Staraptite" por patrón regular) produciría exactamente la clase de error silencioso que este proyecto viene evitando: se probó y se descartó a propósito, con un test que confirma que el generador NO resuelve estos casos a ciegas (`tests/test_build_meta.py`). Queda cerrado hasta que aparezca una fuente real específica de Champions (el mismo pipeline del sprint 2.3 ya sabe automáticamente incorporar más si se encuentra una).
**Deuda relacionada, sin tocar:** las claves de `MEGA` mezclan español (`Blastoisita`, `Gengarita`) e inglés (`Swampertite`) sin criterio. Se mitiga con una conversión `-ite`↔`-ita` en `findItem()` (y ahora también en `build_meta.py`), pero la tabla debería unificarse a slugs canónicos cuando se regenere (decisión #7).

### 5.13 La naturaleza no se puede leer con OCR: el juego la indica con flechas de color — ~~**RESUELTO, 2026-08-06**~~ (por aritmética, no por imagen)

> **Este hallazgo se resolvió de una forma que este mismo documento había descartado.** Lo de abajo se conserva porque el diagnóstico del problema sigue siendo correcto y explica por qué importa; lo que estaba equivocado era la conclusión sobre *cómo* resolverlo.
>
> **La naturaleza no hace falta verla: se deduce.** El juego muestra, por cada stat, el valor **ya calculado** y la **inversión** — los dos los lee el OCR hoy. La base sale de `dex.json`. Con esos tres datos el multiplicador de naturaleza es la única incógnita, y solo puede valer ×1.1, ×1 o ×0.9: se prueban los tres y gana el que reproduce exactamente el número que el juego mostró.
>
> **Por qué nunca es ambiguo:** ×1.1 solo podría empatar con ×1 si el valor previo a multiplicar fuera menor a 10 (`floor(v*1.1)===v` exige `v*0.1<1`). El mínimo real en `dex.json` es 35. Medido sobre las 134 bases distintas × las 33 inversiones posibles: **0 casos ambiguos de 4422**.
>
> Implementado como `natureFromStats(dex, sp, val)` en `hud.html`, más `statPair()` para que `parseStatsCard()` conserve el valor calculado (antes lo descartaba y se quedaba solo con la inversión). Verificado contra las capturas reales de Angel: acierta Grimmsnarl (sube DefEsp, baja AtqEsp) y Aegislash (sube Vel, baja AtqEsp), y distingue una naturaleza genuinamente neutra de una que no se pudo leer.
>
> Es estricto a propósito: una naturaleza real sube exactamente una stat y baja exactamente otra distinta, o no toca ninguna. Si sale cualquier otra combinación, o si un valor no cuadra con ninguno de los tres multiplicadores, devuelve `ok:false` con el motivo y la naturaleza queda sin definir — nunca media naturaleza, que sesgaría todos los cálculos en silencio.
>
> **Lección de método:** el documento afirmaba "análisis de color y forma sobre el bitmap... vive en Kotlin, que no se puede compilar". Era una conclusión razonable —la información *es* gráfica— pero se saltó preguntar si el dato era **recuperable por otra vía**. Conviene desconfiar de un "esto requiere X" cuando X justo coincide con lo que no se puede hacer: es cuando menos se revisa el supuesto.

**Diagnóstico original (2026-08-03), conservado:**
Angel lo señaló el 2026-08-03: en la pantalla de Stats el juego **no escribe la naturaleza**. Dibuja una **flecha roja hacia arriba** en la estadística que sube un 10% y una **azul hacia abajo** en la que baja; en las naturalezas neutras no dibuja nada. Es información gráfica, y ML Kit Text Recognition reconoce texto, no formas ni colores — no hay ninguna garantía de que devuelva un carácter por esas flechas.
**Por qué importa más de lo que parece:** la naturaleza multiplica ±10% una estadística. Sin ella, todo el cálculo de daño y todo el orden de velocidad quedan sesgados, que es justamente el núcleo de valor del producto (`decisions.md` #20: el cuello de botella real de Angel es la precisión del cálculo en el momento decisivo).
**Mitigación implementada:** (a) `natMul()` ahora acepta `0` como "sin naturaleza" y devuelve ×1 — antes cualquier equipo capturado heredaba el default del `slot()` (sube Ataque / baja Ataque Especial), o sea **una naturaleza inventada presentada como si fuera leída**, el patrón de fallo silencioso de §8; (b) `parseStatsCard()` intenta igual leer flechas por si el motor emite `▲`/`▼`, ubicándolas en su celda por fila y sub-columna; (c) si no las encuentra, la deja sin definir y **el resumen de la captura lo dice explícitamente**, nombrando a los Pokémon afectados; (d) los selectores *Sube*/*Baja* de MÍO incorporan la opción "— ninguna" para poder representar ese estado.
**Cómo resolverlo de verdad:** análisis de color y forma sobre el bitmap, exactamente lo que ya hace `SpriteMatcher` con los sprites — buscar dos triángulos pequeños de color saturado (rojo/azul) y quedarse con su posición relativa a las seis celdas de la tarjeta. Es un problema bien acotado y de la misma familia que el reconocimiento de sprites, que es la parte mejor resuelta del proyecto (§4). Pero vive en Kotlin, que **no se puede compilar ni probar en el entorno de desarrollo actual**, así que hacerlo a ciegas arriesga dejar la app sin buildear. Queda como el primer candidato para cuando haya un ciclo de compilación disponible.

### 5.11 `loadDex()` asigna claves de formas alternativas de forma frágil — **VIGENTE, no corregido**
`loadDex()` (`hud.html`) asigna a cada forma alternativa la clave `900000+num*10+(Object.keys(byNum).length%10)`. El último dígito depende de **cuántas especies se procesaron antes**, no de la forma en sí, así que la clave que le toca a una mega concreta es esencialmente arbitraria y puede colisionar con otra forma del mismo Pokémon (una mega y una Gmax del mismo `num` compiten por el mismo rango de 10 claves). Además el chequeo `byNum[sp.num]` consulta una clave distinta de la que después escribe (`byNum[key]=1`), así que la detección de "ya vi este número" no hace lo que aparenta.
Consecuencia práctica: las claves de forma mega que `MEGA` referencia (`900061`, `901261`, …) pueden no coincidir con las que `loadDex()` genera cuando hay `dex.json` cargado. Hoy no rompe porque las entradas de `MEGA` apuntan a las formas embebidas, que `loadDex()` no borra. **Por eso la entrada nueva de Venusaur usa una clave en el rango `99xxxx`**, fuera del alcance de lo que `loadDex()` puede generar. No se corrigió el generador de claves en sí: es un cambio de riesgo medio en código que hoy funciona, y conviene hacerlo junto con la regeneración de `MEGA` (§5.10), no antes.

### 5.12 La captura puede devolver un fotograma viejo en pantallas estáticas — **VIGENTE, no corregido**
`ScreenCapture.grab()` intenta primero `take(r)`, que devuelve el fotograma más reciente **ya encolado**. El `ImageReader` tiene `maxImages=3` y, en una pantalla que no cambia, esos tres buffers se llenan y el productor se frena — por lo que el "más reciente encolado" puede ser de antes de que el HUD se ocultara, es decir, con el panel tapando lo que se quiere leer.
El escaneo del rival no lo sufre porque el team preview está animado (llegan fotogramas nuevos todo el tiempo). La captura del equipo propio sí es una pantalla estática, así que es justo el caso de riesgo. En las pruebas reales hasta ahora **no se manifestó** — la escalera de reintentos (250/600/1200/2000 ms) parece cubrirlo — por eso no se tocó: es código Kotlin que no se puede compilar ni probar en el entorno de desarrollo actual, y romperlo dejaría a Angel sin poder buildear. **El arreglo, si hiciera falta:** vaciar los buffers encolados (`acquireLatestImage()` en bucle, descartando) **antes** de ocultar el panel, y recién después capturar — así cualquier fotograma en cola es necesariamente posterior. Si aparece una lectura que muestra el panel del HUD tapando las tarjetas, esta es la causa.

### 5.9 `build_meta.py` sigue siendo un stub — **RESUELTO, 2026-08-03 (Fase 2, sprint 2.3)**
Reescrito por completo: descarga torneos reales de Limitless TCG, agrega equipos en especies/ítems/movimientos/habilidades/cores, y escribe `meta.json` con metadatos (`generatedAt`, `sourceCounts`, `partial`). Corrido de verdad contra la API — no solo escrito y sin probar — y `assets/meta.json` ya es la salida real de esa corrida (1838 equipos, 169 especies, 60 cores). Detalle completo en `roadmap.md`, Fase 2 sprint 2.3.

### 5.14 La confianza del reconocimiento de sprites estaba rota de raíz — **RESUELTO, 2026-08-06**

Angel reportó, con capturas: *"me dice 'calidad 98%' pero coloca a Aegislash en vez de Floette y mimikyu en vez de milotic. 2 errores de 6. Y pasa seguido"*. Se auditó simulando `identify()` en Node contra el `sprite_index.json` real (209 especies / 718 entradas), en vez de por lectura de código. Tres fallas encadenadas:

1. **La confianza se medía contra el segundo mejor de TODO el índice.** Como el índice guarda normal y variocolor de cada especie, y el variocolor tiene silueta casi idéntica, el segundo mejor era **la misma especie el 100% de las veces medidas**. `(second-best)/second` daba ~0 hasta en lecturas perfectas: **el 99% de las lecturas correctas quedaban marcadas como dudosas**. Con el aviso encendido en todas, no distinguía nada — y como `flojos` nunca bajaba del umbral, el HUD caía **siempre** en el cartel "Lectura dudosa (calidad 98%)". Corregido: el rival es la mejor **otra especie**. Medido: falsas alarmas 99% → 0%, manteniendo 359/359 aciertos.
2. **La confianza describía al ganador de la pasada 1, pero se devolvía el de la pasada 2** (la de color reasigna el ganador en 114–160 de 359 casos medidos). El número informado no correspondía al Pokémon mostrado.
3. **La pasada 2 no aplicaba el filtro de proporción de la pasada 1**, así que podía resucitar por color una referencia descartada por forma imposible. Corregido; los errores que pasaban *sin aviso* ante un recorte roto bajaron de 12 a 3.

**Dónde está el error de verdad:** los pares que Angel reportó están **lejos** en forma (Aegislash↔Floette 0.244, Mimikyu↔Milotic 0.131, contra un umbral de 0.055). El comparador nunca los confundiría con un recorte sano — **el que falla es el recorte** (paso 2 de §4: partes finas del sprite caen bajo el umbral y el "tramo más ancho de columnas" se queda con un pedazo). Se agregó validación de cordura del recorte con límites medidos sobre el índice real, que hace fallar la tarjeta de forma visible en vez de devolver una especie inventada.

**Qué queda:** el recorte en sí sigue sin rediseñarse — solo se le agregó una red de contención. Rediseñarlo requiere capturas reales del juego y un ciclo de compilación de Kotlin, ninguno de los dos disponible en el entorno de desarrollo. Con la confianza ya arreglada, el sistema al menos **avisa cuáles** revisar en vez de presentar los seis como igual de confiables.

### 5.15 Cuánto se pierde de verdad cuando falta `dex.json` — **MEDIDO, 2026-08-06**

La app ya avisa cuando `dex.json` no está (`DATA-02`, "Faltan los datos del juego, así que cada Pokémon ofrece todos los ataques en vez de solo los suyos"), pero nadie había medido el impacto real. Sin `dex.json`, `MV` es solo la tabla embebida: **el 45% de los movimientos que `meta.json` cita (582 de 1279) no resuelve**, así que desaparecen en silencio de "Ataques que suele llevar", de la estimación de amenazas y de los roles de partida. Con `dex.json` cargado, resuelven los 1279.

No es un bug — es la degradación esperada de un modo degradado, y el aviso ya existe. Se documenta porque el aviso actual sugiere que solo se pierde el *filtrado* de movimientos por especie, cuando en realidad también se pierde casi la mitad de la información de meta sobre el rival. Si algún día se reescribe ese mensaje, este es el número real.

## 6. Qué funciona bien y por qué vale la pena preservarlo

- **Lógica de combate en HTML/JS, cascarón en Kotlin.** La decisión más importante del proyecto y bien tomada — permite iterar en segundos sin recompilar. Se formaliza y refuerza en `architecture.md` como separación Motor/Cliente.
- **Captura persistente con un solo `VirtualDisplay` por permiso.** Verificado en `ScreenCapture.kt`. **La reconexión automática ya no está confirmada** (ver §5.8) — se retira esa parte de la afirmación hasta investigarlo.
- **`render()` con manejo de errores** — un error en una vista ya no congela toda la interfaz. Re-verificado en `hud.html:1015`.
- **Selectores propios en vez de `<select>` nativo**, justificado por la ventana `FLAG_NOT_FOCUSABLE` (no robarle foco al juego).
- **Detección de la pila de tarjetas por hipótesis-y-verificación** en vez de asumir un color fijo — sigue siendo un patrón sólido y vale la pena imitarlo. **Acotado el 2026-08-06:** esto vale para el paso 1 (encontrar la pila) y el 3 (comparar contra el índice), no para el 2 (recortar el sprite), que es el que falla en uso real — ver §5.14.
- **WebView único y persistente** — no se pierde el estado del combate al abrir/cerrar el panel.
- **Persistencia atómica y tolerante a fallos:** escritura atómica, versionado por campo `v`, degradación a `{}` si el archivo está corrupto en vez de crashear.

## 7. Deuda técnica, en orden de severidad (actualizado 2026-08-06, quinta pasada)

0. **El recorte del sprite (`readCard()` paso 2) es el que falla en uso real** (§5.14). **Vigente**, con red de contención puesta (validación de cordura + confianza ya arreglada, así que ahora avisa cuáles revisar). Rediseñarlo de verdad necesita capturas reales del juego y un ciclo de compilación de Kotlin — ninguno disponible hoy. Es la causa directa de los errores de identificación que Angel reporta seguido, así que va primero.
0.b. **Comparaciones inglés/español sin pasar por `findMove()`** — misma familia de bug encontrada **tres veces** (`ROLE_MV_EN` sprint 2.9; `foeMovePool()` y `compatibleSets()` el 2026-08-06). `meta.json` guarda movimientos en inglés, `MV` está keyeado en español. Las tres instancias conocidas están corregidas y con test, y se auditaron `items`/`abilities` (limpios). **Mitigado el 2026-08-06 con un contrato ejecutable en el borde** (`tests/run.js`, "contrato meta.json ↔ motor"): verifica que **todo** nombre que `meta.json` entrega — movimientos, sets, ítems, habilidades — el motor lo sepa resolver. Medido con `dex.json` cargado: **0 fallos sobre 1279 movimientos, 1563 movimientos de sets, 564 ítems y 307 habilidades**. Probado inyectando un nombre inválido a propósito: falla y lo nombra. Sigue siendo un contrato de *datos*, no de *tipos*: no impide que código nuevo compare mal, pero sí garantiza que los datos nunca sean la causa.

1. ~~La naturaleza no se captura: es gráfica, no texto (§5.13).~~ **RESUELTO, 2026-08-06** — no hacía falta análisis de imagen: se **deduce por aritmética** del valor calculado + la inversión + la base (`natureFromStats()`). 0 casos ambiguos sobre 4422 combinaciones medidas; verificado contra las capturas reales de Angel. Era el ítem de mayor impacto sobre la calidad del cálculo y ya no está.
2. Tabla `MEGA`: de 15 a 40 de las 76 formas mega que trae `dex.json` (§5.10). **Casi resuelto** — las 36 que quedan son megas exclusivas de Champions sin ninguna fuente real de su nombre; no es trabajo pendiente por hacer, es un límite real de los datos disponibles hoy.
3. `loadDex()` genera claves de formas alternativas de forma frágil y colisionable (§5.11). **Vigente.** Hoy no rompe, pero es una trampa puesta para el futuro.
4. Un único archivo de ~2300 líneas sin módulos ni contratos tipados entre secciones — la causa raíz que permitió que 5.2 y 5.3 (ya resueltos) ocurrieran sin que nada las detectara. **Vigente**, y creciendo. La decisión de no modularizar (#18) sigue en pie, pero el contrapeso acordado ahí era la suite de tests — que sí creció en proporción (de 0 a 218 casos al 2026-08-06), así que el trato se está cumpliendo.
5. Captura potencialmente estancada en un fotograma viejo en pantallas estáticas (§5.12). **Vigente, sin manifestarse todavía**; documentado el arreglo por si aparece.
6. ~~Dependencia declarada sin uso (§5.6).~~ **RESUELTO** — se removió en la Fase 0 (ítem 8); este documento lo seguía listando como vigente por error, corregido el 2026-08-06 verificando `build.gradle.kts` contra el código real.
7. Texto de interfaz (labels, mensajes de las vistas `vX()`) sigue hardcodeado en español pese a que el selector de idioma ya cubre los datos del juego (§5.5) — inconsistencia menor, no un bug.
8. Dos comparaciones de habilidad sin resolver del todo, marcadas con TODO en el código tras la migración a slugs (§5.2): `Barrera Férrea` y `Sartén Vudú` sin poder identificarse contra Showdown/PokeAPI. **Confirmado, 2026-08-11: son código muerto.** Ningún dato real (`dex.json`, `meta.json`) ni ningún otro punto del código contiene esos literales — toda habilidad real que puede llegar a `calc()` sale de `ABIL[dex]` (slugs en inglés, la misma migración que resolvió el resto de este punto), nunca de un string en español. No degradan nada hoy (nunca se activan), pero tampoco documentan una mecánica real: se quedan hasta que alguien reconozca, por el efecto que el código intentaba modelar, a qué habilidad real corresponden — recién ahí conviene decidir si se restauran bajo el slug correcto o se borran. ~~El efecto atribuido a `Robustez`/Sturdy que no es el real de esa habilidad~~ — **RESUELTO, 2026-08-11**: `calc()` tenía una reducción de daño del 25% en golpes súper efectivos (la cifra real de Filtro/Roca Sólida/Coraza Prisma, no de Robustez). Robustez real no reduce daño: a PS llenos, sobrevive con 1 PS cualquier golpe que la dejaría en 0. Modelado como un tope sobre el resultado de cada tirada (`Math.min(dmg,maxHP-1)` cuando `dAb==="sturdy"` y el defensor está a 100% de PS), no como un multiplicador — es la forma correcta de representar la mecánica real. 4 tests nuevos.

**Retirado de esta lista, resuelto:** `build_meta.py` sin implementar (§5.9) — reescrito y corrido contra la API real, ver `roadmap.md` Fase 2 sprint 2.3.
**Retirado antes:** `ReconnectActivity` (§5.8) figuraba como "severidad sin determinar, requiere investigación" cuando §5.8 ya lo había investigado y cerrado como no-bug en la misma pasada — contradicción interna del documento, corregida el 2026-08-03.

**Resueltos:** idioma de habilidades (§5.2), `meta.json` desincronizado (§5.3), mismatch `predict()`/`vPre()` (§5.1), piedras mega apuntando a formas inexistentes (§5.10, parte crítica).

## 8. Patrón transversal

Los hallazgos 5.2 y 5.3 (ya resueltos) compartían la misma forma: el sistema seguía funcionando y reportando éxito mientras producía un resultado incorrecto. No fue una coincidencia — es la consecuencia directa de no tener contratos de forma ni validación en los bordes entre módulos. Este patrón sigue siendo el origen del principio de "fallo ruidoso, nunca silencioso" adoptado en `decisions.md` #8, y de los requisitos de validación en build y contratos tipados en `architecture.md` §6 y §8 (deuda técnica #3 de la sección anterior, todavía pendiente) — resolver estos dos casos puntuales no resuelve la causa raíz que permitió que existieran.

## 9. Preguntas frecuentes sobre el estado del código

**¿Qué hace bien la aplicación hoy?** La captura de pantalla resuelve correctamente una restricción real del sistema operativo. **La fórmula de stats está verificada contra la pantalla real del juego, y desde el 2026-08-06 esa verificación es un test permanente** (12 comparaciones exactas — los 6 stats de Grimmsnarl y de Aegislash, tomados de capturas de Angel — que fallan si alguien toca `hpOf`/`stOf`/`natMul` o si Champions cambia la fórmula en un parche). La persistencia es prolija. El reconocimiento de sprites tiene una base sólida (§4) pero **no la etapa de recorte**, que es la que falla en uso real — ver §5.14.

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

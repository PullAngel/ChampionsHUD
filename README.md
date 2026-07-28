# Champions HUD

Overlay de batalla para Pokémon Champions en Android. Lee el equipo rival desde
la vista previa, deduce sus objetos y velocidad a medida que avanza el combate,
y se sale del camino.

Pensado para un Samsung A55 5G con Android 16 / One UI 8.5: `targetSdk 36`,
`minSdk 29`, WebView con capa por hardware para los 120 Hz del panel, negros
profundos para el AMOLED, y vibracion via `VibrationEffect.EFFECT_TICK` para que
se sienta como un control nativo de One UI y no como un zumbido.

## Compilar

1. Abrir la carpeta en Android Studio. Baja el wrapper de Gradle y el SDK solo.
2. `Build > Build Bundle(s) / APK(s) > Build APK(s)`, o `./gradlew assembleDebug`.
3. El APK queda en `app/build/outputs/apk/debug/`.

## Antes de que el escaneo sirva

El matcher necesita el índice de sprites, que no viene incluido:

```
pip install requests pillow numpy
python build_sprite_index.py
cp sprite_index.json app/src/main/assets/
```

Sin ese archivo la app arranca igual y todo lo demás funciona; solo el escaneo
avisa que falta el índice.

## Cómo se usa

Una burbuja queda flotando sobre el juego. Arrastrala donde no moleste, se pega
al borde. Tocarla abre el panel del lado donde esté, ocupando como mucho el 46%
del ancho.

| Control | Qué hace |
|---|---|
| `▸` | Avanza el turno y baja todos los contadores de campo |
| `⇱` | Fija el panel: deja de cerrarse solo |
| `↻` | Escanea la vista previa |
| `×` | Cierra el panel |
| mantener la burbuja | Cierra la app |

El panel se cierra solo a los 16 segundos sin uso, salvo que esté fijado.

### Diseño horizontal

Champions se juega siempre en horizontal, así que el panel es más ancho que
alto (unos 382 × 338 px CSS en el A55). La navegación va en un **riel vertical a
la izquierda** en vez de una barra inferior — el alto es el recurso escaso — y
las tarjetas se acomodan en dos columnas.

### Las pestañas

**PREVIA** — el predictor de team preview. Con tu equipo cargado y el rival
escaneado, estima qué 4 va a sacar y en qué orden, y te recomienda tus 4 con
leads y back. No es solo daño: pesa control de velocidad (Tailwind vs Espacio
Raro), clima propio, megas duplicadas que ocupan un solo cupo, y choques de
habilidad como Bromista contra tipos siniestro. Y muestra el razonamiento, para
que puedas discutirlo en vez de obedecerlo.

Es una heurística, no un oráculo: sirve para no pasar por alto un eje obvio con
el reloj corriendo, no para elegir por vos.

**CAMPO** — lo que necesitás sin tocar nada: qué le hace cada uno de los tuyos a
cada uno de ellos, qué te hacen a vos, el orden de velocidad y el estado del
campo con contadores.

**RIVAL** — por cada Pokémon del rival: objetos, movimientos y repartos más
probables según el meta, más lo que se fue confirmando durante la partida.

**CALC** — calculadora manual para cuando querés forzar valores.

**⚙** — formato, actualización del meta y reinicio del combate.

## Lo que deduce solo

- **Pañuelo Elección**: si marcás "se movió antes" y la velocidad que necesitó
  supera lo que su base permite, el Pañuelo queda confirmado.
- **Rango de velocidad**: arranca en el máximo teórico y se va achicando con
  cada observación de orden.
- **Resistencia**: en RIVAL, "Confirmar por daño" toma el porcentaje real que le
  bajaste y descarta todos los repartos defensivos incompatibles.
- **Movimientos**: los que marcás como vistos reemplazan a los estimados, y el
  cálculo de amenaza pasa a usar solo esos.

### Estados y etapas

Cada activo tiene su propio estado y sus propias etapas, no un interruptor
global. En CAMPO elegís el Pokémon y le ponés estado (quemado, paralizado,
envenenado, dormido, congelado) y etapas de −6 a +6 en las cinco stats.

Entran donde corresponde: la **quemadura** baja solo el daño físico del que la
tiene, la **parálisis** parte su velocidad al medio en el orden de turno, y las
etapas se aplican a la stat correcta según si el movimiento es físico o
especial. En crítico se ignoran las etapas que perjudican al atacante.

Tailwind, Espacio Raro, clima, campos y pantallas también entran en los cálculos
de daño y de orden en cuanto los marcás.

## Si se cae a mitad de un combate

El estado se guarda en disco en cada cambio. Al reabrir la app vuelve tal cual
estaba: turno, revelados, campo y equipo. Se descarta solo si pasaron más de
tres horas, porque un combate viejo confunde más de lo que ayuda.

## Actualizar el meta

`assets/meta.json` viene con datos **estimados**, no de uso real — el HUD lo
avisa en ⚙ hasta que lo reemplaces. Dos formas:

- Regenerarlo con `build_meta.py` y copiarlo a `assets/`.
- Servirlo por HTTP y pegar la URL en ⚙ → se descarga y reemplaza sin recompilar.

La descarga se valida antes de guardar: si viene rota, el HUD sigue con lo que
tenía.

## Por qué la captura es persistente

Desde Android 14, un permiso de captura permite crear **un solo** display
virtual. La versión anterior lo creaba y destruía en cada escaneo: el primero
andaba y el segundo tiraba `SecurityException`, dejando la proyección muerta.

Ahora el display se crea una vez y vive lo que viva el HUD. Cada escaneo solo
pide el último fotograma. No gasta batería porque entre escaneos no consumimos
nada y el productor se frena solo.

Detalle que parecía cosmético y no lo era: el HUD **se oculta** justo antes de
capturar. En una pantalla estática no llegan fotogramas nuevos, así que ese
ocultamiento es lo que provoca el cambio que dispara uno fresco.

## Variocolor (shiny)

Bulbagarden publica los sprites variocolor en su propia categoría, así que ahora
entran al índice como entradas propias y el matcher los identifica igual que a
cualquier otro. El match va en dos pasadas:

1. **Silueta**, que es identica entre shiny y normal. Si el ganador le saca
   diferencia clara al segundo, se cierra ahi y el color no se mira nunca.
2. **Color**, solo entre candidatos que empataron en silueta — las formas que se
   distinguen unicamente por color, como Shellos o los patrones de Vivillon.

Y el color pasa a ser dato util: silueta impecable con paleta lejos es
exactamente la firma de un shiny, y el HUD lo marca con `✦` en la pestaña RIVAL.

Pasar todo a escala de grises **no** habria servido: un recoloreo shiny cambia
tambien la luminancia, asi que el gris no es invariante. La silueta si lo es.

## Tu equipo

En la pestaña **MÍO** cargas los seis: especie, objeto, alineacion (que stat
sube y cual baja) y los 66 Stat Points repartidos con barras. Al lado de cada
barra ves el valor final de la stat mientras la movés.

Sin esto el HUD asumia el peor caso para todo. Con el equipo cargado, los daños
que hacés y recibís salen de tus numeros reales.

Nota: en Champions **no hay IVs** que cargar — todos los Pokemon cuentan como 31
en las seis stats. Lo unico que define tu reparto son los Stat Points.

## Barras de PS

Las barras de PS del CAMPO se arrastran con el dedo y tienen un tick de
vibracion por cada punto de porcentaje, mas un click al soltar. La idea es poder
ajustarlas sin mirar y sin abrir el teclado, en medio del turno.

## Por qué los selectores son propios y no del sistema

La ventana del overlay es `FLAG_NOT_FOCUSABLE` a propósito: si tuviera foco le
robaría el teclado y el botón atrás al juego. Pero un `<select>` nativo necesita
foco para abrir su popup, así que simplemente no se abría.

Por eso todos los desplegables están dibujados dentro del panel: al tocarlos se
despliega una lista a pantalla completa del panel, con las opciones en dos
columnas. Nada depende del foco de ventana.

## De dónde salen los datos

Tres archivos en `assets/`, todos generados por scripts y reemplazables sin
tocar el código:

| Archivo | Lo genera | Para qué |
|---|---|---|
| `sprite_index.json` | `build_sprite_index.py` | reconocer al rival en la vista previa |
| `dex.json` | `build_dex.py` | stats, tipos, habilidades, movimientos y **learnsets** |
| `meta.json` | `build_meta.py` | porcentajes de uso para estimar al rival |

`build_dex.py` toma los datos de Pokémon Showdown y los recorta a las especies
que existen en Champions — que deduce del `sprite_index.json`, o sea de los
sprites del propio juego. El resultado son unos 400 KB.

Los learnsets son lo que hace que el selector de movimientos de cada Pokémon
muestre solo lo que ese Pokémon aprende. Sin `dex.json` la app sigue andando con
tablas mínimas embebidas, pero ofrece todos los movimientos a todos.

## Los datos del meta

`assets/meta.json` guarda, por especie, los porcentajes de uso de objetos,
movimientos, habilidades y repartos. El HUD los usa para estimar al rival antes
de que revele nada.

Los que vienen de fábrica son criterio propio, **no datos medidos** — por eso el
HUD los marca como «estimados» en ⚙. Si conseguís un archivo con datos reales y
lo servís por HTTP, pegás la URL en ⚙ y se reemplaza sin recompilar. Se valida
antes de guardar: si viene roto, sigue con el anterior.

## Modo compacto

El botón `◱` colapsa el HUD a tres bloques: qué tirar, qué te hacen y el orden
de velocidad. Es para los últimos segundos del turno, cuando no hay tiempo de
leer nada más.

Ahí vive el **recomendador**: ordena tus cuatro movimientos y explica cada uno
en una línea. No es una flecha que obedecés — dice *por qué*, para que aprendas
a leer la posición. Pesa daño, KO, precisión real, prioridad, si pega a los dos,
y si el rival te mata primero.

## Megaevolución: decisión, no suposición

Llevar la piedra no es haberla usado. Tyranitar espera para reinstalar arena,
y hay equipos que traen la piedra y nunca megaevolucionan.

Por eso en MÍO hay un botón aparte, **Sin megaevolucionar / Megaevolucionado**.
Hasta que lo marcás, el HUD calcula con la forma base. Al marcarlo cambian las
stats, los tipos y todos los números.

## Habilidades y megas

Cada slot propio lleva su habilidad, elegida de la lista real de esa especie.
El motor modela las que cambian el daño:

| Atacante | Defensor |
|---|---|
| Poder Solar, Chorro Potente, Sartén Vudú | Multiescamas, Levitación |
| Piel Feérica, Adaptable | Filtro / Solidez / Coraza Filtro, Robustez |
| Torrente / Mar Llamas / Espesura / Enjambre (bajo 1/3 de PS) | Absorbe Fuego / Agua, Pararrayos, Motor Eléctrico |

Las demás figuran en el equipo pero no alteran el cálculo.

Las piedras mega resuelven a la forma megaevolucionada: elegís Charizardita Y y
el HUD pasa a usar los 159 de AtqEsp base de la Mega Y, no los 109 del normal.
Se resuelve automáticamente en cuanto la piedra está equipada — en la práctica
megaevolucionás el primer turno, pero si querés el cálculo con la forma base
está la pestaña CALC.

## Lo que falta

- `SPD` en `hud.html` tiene ~42 especies y 11 megas; falta el roster legal completo.
- `MV` no modela efectos secundarios, precisión, golpes múltiples ni PP.
- Intimidación no se aplica sola: marcá la etapa −1 a mano en CAMPO.
- Sin Teratipos.
- Sin seguimiento de Protección (por ahora se cuenta mentalmente).
- Sin objetos consumidos (Baya Zidra usada, Banda Focus gastada).
- Sin Terastalización: todavía no está en el juego. El motor está armado para
  poder sumarla sin rehacerlo.
- El recorte de tarjetas en `SpriteMatcher` está calibrado a ojo; puede necesitar
  ajuste según el teléfono.

## La fórmula, verificada

Champions no usa IVs: todos los Pokémon cuentan como 31 en las seis stats. Lo
único que define tu reparto son los Stat Points, y **1 SP = +1 punto de stat a
nivel 50, sumado antes de la alineación**.

Verificado contra la pantalla de stats del juego con 10 valores de 6 Pokémon
distintos. Ejemplo: Gholdengo, AtqEsp base 133, con 32 SP y alineación que sube
da 203 en el juego. `floor((153+32)*1.1) = 203`. Si el SP se sumara después
daría 200.

El HUD reproduce exactamente los números de esa pantalla, así que podés
contrastarlo cuando quieras.

Sprites: Bulbagarden Archives, CC BY-NC-SA 2.5. Proyecto personal, no comercial.

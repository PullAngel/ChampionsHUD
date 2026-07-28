# Guía: de este ZIP a la app andando en tu A55

Escrita asumiendo que nunca compilaste una app Android. Seguila en orden.
Tiempo real: unos 40–60 minutos, casi todo esperando descargas.

---

## Paso 1 — Instalar Android Studio (~20 min, casi todo descarga)

1. Entrá a **https://developer.android.com/studio** y bajá la versión para tu
   sistema (Windows / macOS / Linux). Son unos 1,2 GB.
2. Instalalo con las opciones por defecto. No hace falta instalar Java aparte:
   Android Studio trae el suyo.
3. La primera vez que lo abrís aparece un asistente de configuración.
   Elegí **Standard** y aceptá las licencias. Va a descargar el SDK de Android
   (otros ~2 GB). Dejalo terminar.

> Si te pregunta por importar configuración de una instalación previa, elegí
> "Do not import settings".

---

## Paso 2 — Los sprites (~10 min)

Sin este paso la app abre y todo funciona, pero el botón de escanear avisa que
falta el índice. Es lo que le permite reconocer al equipo rival.

1. Instalá Python desde **https://www.python.org/downloads/**.
   En Windows, **tildá "Add Python to PATH"** en la primera pantalla del
   instalador. Es fácil pasarlo por alto y después nada funciona.
2. Descomprimí `ChampionsHUD.zip` en algún lado fácil de encontrar,
   por ejemplo `C:\Users\TuUsuario\ChampionsHUD` o `~/ChampionsHUD`.
3. Abrí una terminal:
   - **Windows**: tecla Windows → escribí `cmd` → Enter.
   - **macOS**: Cmd+Espacio → `Terminal` → Enter.
4. Movete a la carpeta del proyecto:
   ```
   cd ChampionsHUD
   ```
   (Si la pusiste en otro lado, escribí `cd ` y arrastrá la carpeta a la
   terminal: pega la ruta sola.)
5. Instalá lo que necesita el script:
   ```
   pip install requests pillow numpy
   ```
   Si dice que `pip` no existe, probá `python -m pip install requests pillow numpy`
   o, en Mac/Linux, `pip3`.
6. Corré el script:
   ```
   python build_sprite_index.py
   ```
   Va a bajar 359 sprites de Bulbagarden, de a uno con pausa para no maltratar
   el servidor. Tarda unos minutos. Al terminar dice cuántos procesó.
7. Copiá el archivo generado a la carpeta de la app:
   - **Windows**: `copy sprite_index.json app\src\main\assets\`
   - **macOS/Linux**: `cp sprite_index.json app/src/main/assets/`

Verificá que `app/src/main/assets/` tenga ahora tres archivos: `hud.html`,
`meta.json` y `sprite_index.json`.

---

## Paso 2b — Los datos del juego (~3 min)

Esto es lo que hace que cada Pokémon ofrezca solo **sus** movimientos, en vez de
los 900 del juego mezclados. Sin este paso la app funciona, pero cargar el
equipo es un suplicio.

En la misma terminal, parado en `ChampionsHUD`:

```
python build_dex.py
```

Baja los datos de Pokémon Showdown (unos 4 MB) y los filtra a las especies que
existen en Champions — que las saca del `sprite_index.json` del paso anterior,
así que ese tiene que estar hecho primero.

Copiá el resultado:
- **Windows**: `copy dex.json app\src\main\assets\`
- **macOS/Linux**: `cp dex.json app/src/main/assets/`

En `app/src/main/assets/` tienen que quedar cuatro archivos: `hud.html`,
`meta.json`, `sprite_index.json` y `dex.json`.

Podés confirmar que cargó desde la app: **⚙ → Datos** te dice cuántas especies
y si los learnsets están activos.

---

## Paso 3 — Abrir el proyecto (~5 min)

1. En Android Studio: **Open** (o File → Open).
2. Elegí la carpeta **`ChampionsHUD`** — la que contiene `settings.gradle.kts`.
   No entres a `app/`: hay que abrir la carpeta de arriba.
3. Abajo a la derecha va a aparecer una barra de progreso: **Gradle sync**.
   La primera vez descarga Gradle y las dependencias. Puede tardar 5–15 minutos.
   Esperá a que diga *"Gradle sync finished"*.

**Si aparece un error sobre el Gradle wrapper**: es esperable, el ZIP no puede
traer ese archivo (es un binario). Android Studio normalmente lo regenera solo.
Si no lo hace, andá a **File → Settings → Build → Build Tools → Gradle**
(en Mac: Android Studio → Settings) y en *"Use Gradle from"* elegí
**"'wrapper' task in Gradle build script"**, o bien la distribución local que
trae Android Studio. Después **File → Sync Project with Gradle Files**.

**Si pide instalar algún componente del SDK** (por ejemplo "Android SDK
Platform 35"), aceptá y dejá que lo baje.

---

## Paso 4 — Preparar el teléfono (~5 min)

En tu A55:

1. **Ajustes → Información del teléfono → Información de software** y tocá
   **siete veces** sobre *Número de compilación*. Te va a decir "Ya eres
   desarrollador".
2. Volvé a **Ajustes → Opciones de desarrollador** y activá:
   - **Depuración USB**
   - **Instalar vía USB** (si aparece)
3. **Importante en Samsung**: andá a
   **Ajustes → Seguridad y privacidad → Auto Blocker** y **desactivalo**.
   Auto Blocker bloquea la instalación de apps que no vienen de la tienda, y es
   la causa número uno de que un APK "no se instale" sin explicar por qué.

---

## Paso 5 — Instalar la app

Hay dos caminos. **El primero es más simple y te sirve para seguir probando
cambios**, así que empezá por ahí.

### Camino A — Directo por cable (recomendado)

1. Conectá el teléfono a la computadora por USB.
2. En el teléfono va a aparecer un cartel: **"¿Permitir depuración USB?"**.
   Tildá *"Permitir siempre desde este equipo"* y aceptá.
   Si no aparece, deslizá la barra de notificaciones, tocá la notificación de
   USB y elegí **"Transferencia de archivos"**.
3. En Android Studio, arriba al centro, donde dice *"No devices"*, debería
   aparecer ahora **SM-A556** (o similar). Seleccionalo.
4. Tocá el botón **▶ Run** (triángulo verde) o `Shift+F10`.
5. Compila e instala solo. La primera compilación tarda unos minutos; las
   siguientes son mucho más rápidas.

### Camino B — Generar un APK para vos y para pasar a amigos

Este camino produce un archivo único que se instala en cualquier teléfono
Android, sin cables ni Android Studio del otro lado.

**B.1 — Crear la firma (una sola vez).** Android exige que todo APK esté
firmado. En la terminal, parado en la carpeta `ChampionsHUD`, pegá esto en una
sola línea:

```
keytool -genkeypair -v -keystore app/championshud.jks -alias champions -keyalg RSA -keysize 2048 -validity 10000 -storepass champions -keypass champions -dname "CN=Champions HUD"
```

Si dice que `keytool` no existe, usá el que trae Android Studio:
- **Windows**: `"C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"` y después el resto igual.
- **macOS**: `/Applications/Android\ Studio.app/Contents/jbr/Contents/Home/bin/keytool`

Eso genera `app/championshud.jks`. **Guardalo**: si lo perdés, las
actualizaciones futuras no van a poder instalarse encima de la versión vieja.

**B.2 — Compilar.** En Android Studio: **Build → Generate Signed Bundle / APK**
→ elegí **APK** → *Next* → en *Key store path* buscá el `.jks` que creaste,
contraseña `champions`, alias `champions`, contraseña de clave `champions` →
*Next* → variante **release** → *Create*.

Más rápido por terminal:
```
./gradlew assembleRelease
```
(en Windows: `gradlew.bat assembleRelease`)

**B.3 — Encontrar el archivo.** Queda en
`app/build/outputs/apk/release/app-release.apk`. Ese es el archivo que mandás.

**B.4 — Pasarlo.** Por WhatsApp o Telegram el APK suele llegar renombrado; es
más confiable subirlo a Google Drive y compartir el link, o pasarlo por cable.

**B.5 — Instalarlo (vos o quien lo reciba).** Abrir **Mis archivos**, tocar el
APK, permitir la instalación desde esa app cuando lo pida. En Samsung hay que
tener **Auto Blocker desactivado** (paso 4.3).

> Avisale a quien se lo pases que la app pide permiso para dibujar sobre otras
> apps y para capturar pantalla, y que eso es lo que necesita para funcionar.
> Nada sale del teléfono.

### Camino C — Solo el APK de prueba

1. **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
2. Cuando termina, aparece un aviso abajo a la derecha con un link **"locate"**.
   Tocalo: te abre la carpeta con el archivo `app-debug.apk`.
   (La ruta es `app/build/outputs/apk/debug/app-debug.apk`.)
3. Pasá ese archivo al teléfono: por cable, por Google Drive, o mandándotelo
   por Telegram a vos mismo.
4. En el teléfono, abrí **Mis archivos**, buscá el APK y tocalo.
5. Va a decir que esa app no tiene permiso para instalar. Tocá **Ajustes**,
   activá el permiso para *Mis archivos*, volvé atrás e instalá.

---

## Paso 6 — Primer arranque

Abrí **Champions HUD**. Te va a pedir tres permisos, uno por vez:

1. **Dibujar sobre otras apps** — te manda a una pantalla de Ajustes. Activalo
   y volvé con el botón atrás.
2. **Notificaciones** — Android las exige para mantener viva la captura de
   pantalla. Aceptá.
3. **Captura de pantalla** — aparece un cartel del sistema. Tocá *Iniciar*.

Cuando aceptás el tercero, la app se va al fondo sola y queda **una burbuja
flotando**. Ya está andando.

- Arrastrala donde no moleste; se pega al borde.
- Tocala para abrir el panel.
- **Mantenela presionada para cerrar la app.**

---

## Paso 7 — Antes del primer combate

1. Abrí el panel → pestaña **MÍO** y cargá tus seis: especie, objeto,
   habilidad, alineación, Stat Points y movimientos.
2. Entrá a un combate. En la pantalla de vista previa (donde elegís 4), tocá
   la burbuja y después **↻**.
3. Debería leer los seis del rival y saltar sola a **PREVIA** con la predicción.

**Si el escaneo falla**, sacá una captura de esa pantalla y mandámela: el
recorte de las tarjetas está calibrado a ojo y lo ajusto con tu resolución real.

---

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| "Gradle sync failed" con un error de red | Firewall o proxy. Probá con otra red. |
| Pide un JDK | File → Settings → Build → Gradle → *Gradle JDK* → elegí el **jbr** que trae Android Studio. |
| El teléfono no aparece en la lista | Cable de solo carga (probá otro), o falta aceptar el cartel de depuración USB, o el modo USB no está en "Transferencia de archivos". |
| El APK "no se instaló" sin más explicación | **Auto Blocker** de Samsung, paso 4.3. |
| La burbuja no aparece | Falta el permiso de dibujar sobre otras apps. Reabrí la app. |
| El escaneo dice que falta `sprite_index.json` | No copiaste el archivo del paso 2.7 a `app/src/main/assets/`. |
| Escanea pero identifica cualquier cosa | Recorte descalibrado: mandame una captura. |
| Los números no coinciden con el juego | Revisá `SP_AFTER_NAT` en `hud.html` (está explicado en el README). |

---

## Para seguir haciendo cambios

Casi toda la lógica vive en **`app/src/main/assets/hud.html`**. Es un archivo de
texto: lo editás, tocás ▶ Run de nuevo y en menos de un minuto lo tenés en el
teléfono. No hace falta tocar Kotlin para cambiar la interfaz, agregar especies
o ajustar el motor de daño.

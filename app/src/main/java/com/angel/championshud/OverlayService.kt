package com.angel.championshud

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.min

/**
 * El HUD.
 *
 *   burbuja  — 56dp, arrastrable, se pega al borde. Es lo unico que ocupa
 *              pantalla mientras jugas.
 *   panel    — se abre del lado donde este la burbuja. Nunca pasa del 46% del
 *              ancho, asi el campo de batalla queda a la vista.
 *
 * El WebView se crea UNA sola vez y se reusa. Eso hace que abrir el panel sea
 * instantaneo y, sobre todo, que el estado del combate no se pierda al cerrarlo
 * y volver a abrirlo entre turno y turno.
 */
class OverlayService : Service() {

    companion object {
        const val EXTRA_RESULT_CODE = "code"
        const val EXTRA_RESULT_DATA = "data"
        private const val CHANNEL = "hud"
        private const val IDLE_MS = 16_000L
    }

    private lateinit var wm: WindowManager
    private lateinit var matcher: SpriteMatcher
    private lateinit var teamOcr: TeamOCR
    private lateinit var meta: MetaRepository
    private lateinit var battle: BattleStore
    private lateinit var team: TeamStore
    private lateinit var haptics: Haptics
    private var capture: ScreenCapture? = null

    private lateinit var bubble: FrameLayout
    private lateinit var bubbleLp: WindowManager.LayoutParams
    private lateinit var badge: TextView

    private var panel: FrameLayout? = null
    private var panelLp: WindowManager.LayoutParams? = null
    private var web: WebView? = null
    private var ready = false          // el HTML ya cargo
    private var expanded = false
    private var pinned = false         // fijado por el usuario: no se auto-cierra
    private var scanning = false       // evita escaneos superpuestos

    private val ui = Handler(Looper.getMainLooper())
    private val io = HandlerThread("hud-io").apply { start() }
    private val ioHandler by lazy { Handler(io.looper) }
    private val autoClose = Runnable { if (expanded && !pinned) collapseNow() }

    private val dp get() = resources.displayMetrics.density

    override fun onBind(p: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        matcher = SpriteMatcher(this)
        teamOcr = TeamOCR()
        meta = MetaRepository(this)
        battle = BattleStore(this)
        team = TeamStore(this)
        haptics = Haptics(this)
        startForeground(1, notification())
        buildWebView()
        addBubble()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val code = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        @Suppress("DEPRECATION")
        val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        if (code != 0 && data != null && capture == null) {
            val mgr = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            runCatching { mgr.getMediaProjection(code, data) }
                .onSuccess { capture = ScreenCapture(this, it) }
        }
        return START_STICKY
    }

    // ─────────────────────── WebView persistente ───────────────────────

    private fun buildWebView() {
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            setBackgroundColor(Color.TRANSPARENT)
            overScrollMode = View.OVER_SCROLL_NEVER
            setLayerType(View.LAYER_TYPE_HARDWARE, null)
            addJavascriptInterface(Bridge(), "Android")
            webViewClient = object : android.webkit.WebViewClient() {
                override fun onPageFinished(v: WebView?, url: String?) { ready = true }
            }
            loadUrl("file:///android_asset/hud.html")
        }
    }

    // ─────────────────────────── burbuja ───────────────────────────

    private fun addBubble() {
        val size = (56 * dp).toInt()

        bubble = FrameLayout(this).apply {
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.parseColor("#E60D0B18"))
                setStroke((2 * dp).toInt(), Color.parseColor("#B8FF3C"))
            }
            alpha = 0.72f
        }
        badge = TextView(this).apply {
            text = "HUD"
            setTextColor(Color.parseColor("#B8FF3C"))
            textSize = 11f
            letterSpacing = 0.12f
            gravity = Gravity.CENTER
        }
        bubble.addView(badge, FrameLayout.LayoutParams(size, size))

        bubbleLp = WindowManager.LayoutParams(
            size, size, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 0; y = (140 * dp).toInt()
        }

        bubble.setOnTouchListener(DragHandler())
        runCatching { wm.addView(bubble, bubbleLp) }
    }

    private inner class DragHandler : View.OnTouchListener {
        private var downX = 0f; private var downY = 0f
        private var startX = 0; private var startY = 0
        private var downAt = 0L; private var moved = false

        override fun onTouch(v: View, e: MotionEvent): Boolean {
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY
                    startX = bubbleLp.x; startY = bubbleLp.y
                    downAt = System.currentTimeMillis(); moved = false
                    bubble.animate().alpha(1f).scaleX(1.1f).scaleY(1.1f).setDuration(90).start()
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX; val dy = e.rawY - downY
                    if (!moved && (abs(dx) > 8 * dp || abs(dy) > 8 * dp)) {
                        moved = true
                        if (expanded) collapseNow()
                    }
                    if (moved) {
                        bubbleLp.x = startX + dx.toInt()
                        bubbleLp.y = startY + dy.toInt()
                        runCatching { wm.updateViewLayout(bubble, bubbleLp) }
                    }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    val held = System.currentTimeMillis() - downAt
                    bubble.animate().alpha(if (expanded) 1f else 0.72f)
                        .scaleX(1f).scaleY(1f).setDuration(140).start()
                    when {
                        moved -> snapToEdge()
                        held > 650 -> stopSelf()
                        else -> if (expanded) collapseNow() else expandNow()
                    }
                }
            }
            return true
        }
    }

    private fun snapToEdge() {
        val (w, h) = metrics()
        val margin = (8 * dp).toInt()
        bubbleLp.x = if (bubbleLp.x + bubble.width / 2 < w / 2) margin else w - bubble.width - margin
        bubbleLp.y = bubbleLp.y.coerceIn(margin, (h - bubble.height - margin).coerceAtLeast(margin))
        runCatching { wm.updateViewLayout(bubble, bubbleLp) }
    }

    // ─────────────────────────── panel ───────────────────────────

    private fun expandNow() {
        if (expanded) return
        val wv = web ?: return
        val (sw, sh) = metrics()
        val onLeft = bubbleLp.x + bubble.width / 2 < sw / 2

        // En horizontal el alto es el recurso escaso: lo usamos casi entero y
        // dejamos el centro del campo libre.
        val land = sw > sh
        // ~60% más ancho que antes (0.42 -> 0.67) — pedido explícito de Angel
        // después de probarlo, con el límite de no tapar el panel de equipo
        // rival nativo del juego en team preview (vive a la derecha de la
        // pantalla; 0.67 deja ~33% libre, que en las capturas que mandó
        // alcanza de sobra). Sin verificar en pantalla real todavía.
        val panelW = min((sw * (if (land) 0.67f else 0.62f)).toInt(), (740 * dp).toInt())
        val panelH = (sh * (if (land) 0.94f else 0.80f)).toInt()
        val gap = (8 * dp).toInt()

        val container = FrameLayout(this).apply {
            background = GradientDrawable().apply {
                cornerRadius = 20 * dp
                setColor(Color.parseColor("#4D0D0B18"))
                setStroke((1 * dp).toInt(), Color.parseColor("#3A2A55"))
            }
            clipToOutline = true
            alpha = 0f
            translationX = if (onLeft) -20 * dp else 20 * dp
        }

        (wv.parent as? ViewGroup)?.removeView(wv)
        container.addView(wv, FrameLayout.LayoutParams(-1, -1))

        val lp = WindowManager.LayoutParams(
            panelW, panelH, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (if (onLeft) bubbleLp.x + bubble.width + gap else bubbleLp.x - panelW - gap)
                .coerceIn(gap, (sw - panelW - gap).coerceAtLeast(gap))
            y = (sh - panelH) / 2
        }

        runCatching { wm.addView(container, lp) }.onFailure {
            (wv.parent as? ViewGroup)?.removeView(wv)
            return
        }
        container.animate().alpha(1f).translationX(0f).setDuration(160).start()

        panel = container; panelLp = lp; expanded = true
        badge.text = "•"; bubble.alpha = 1f
        resetIdle()
    }

    private fun collapseNow() {
        val p = panel ?: run { expanded = false; return }
        panel = null; panelLp = null; expanded = false
        badge.text = "HUD"; bubble.alpha = 0.72f
        ui.removeCallbacks(autoClose)
        // El WebView sale del contenedor pero sigue vivo: no se pierde el estado.
        p.animate().alpha(0f).setDuration(120).withEndAction {
            (web?.parent as? ViewGroup)?.removeView(web)
            runCatching { wm.removeView(p) }
        }.start()
    }

    private fun resetIdle() {
        ui.removeCallbacks(autoClose)
        if (!pinned) ui.postDelayed(autoClose, IDLE_MS)
    }

    /** Al rotar cambian las medidas: reubicamos en vez de quedar fuera de pantalla. */
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        val wasOpen = expanded
        if (expanded) collapseNow()
        ui.postDelayed({
            snapToEdge()
            if (wasOpen) expandNow()
        }, 240)
    }

    // ─────────────────────────── escaneo ───────────────────────────

    private fun scan() {
        if (scanning) return
        val cap = capture ?: run {
            emit("onScan", """{"error":"Falta autorizar la captura. Abrí Champions HUD."}""")
            return
        }
        scanning = true
        bubble.visibility = View.INVISIBLE
        panel?.visibility = View.INVISIBLE

        ui.postDelayed({
            cap.grab { bmp, err ->
                // El matching es pesado: fuera del hilo de UI.
                ioHandler.post {
                    val json = when {
                        bmp == null -> org.json.JSONObject()
                            .put("error", err ?: "No se pudo leer la pantalla.").toString()
                        else -> runCatching { matcher.readTeamPreview(bmp) }
                            .getOrElse { e ->
                                org.json.JSONObject().put("error",
                                    "Falló el reconocimiento: ${e.javaClass.simpleName}").toString()
                            }.also { bmp.recycle() }
                    }
                    ui.post {
                        bubble.visibility = View.VISIBLE
                        panel?.visibility = View.VISIBLE
                        scanning = false
                        emit("onScan", json)
                    }
                }
            }
        }, 120)
    }

    /**
     * Captura de equipo propio ("View Details" del juego, en dos pasadas —
     * Moves & More y Stats). A diferencia de scan(), acá Kotlin no interpreta
     * nada del texto que lee — TeamOCR.readText() devuelve líneas crudas con
     * posición, y toda la lógica de a qué Pokémon pertenece cada línea vive
     * en hud.html (ver decisions.md: así se puede corregir editando el HTML
     * sin recompilar, si el layout real no coincide con lo asumido).
     */
    private fun scanOwnTeam() {
        if (scanning) return
        val cap = capture ?: run {
            emit("onOwnScan", """{"error":"Falta autorizar la captura. Abrí Champions HUD."}""")
            return
        }
        scanning = true
        bubble.visibility = View.INVISIBLE
        panel?.visibility = View.INVISIBLE

        ui.postDelayed({
            cap.grab { bmp, err ->
                ioHandler.post {
                    val json = when {
                        bmp == null -> org.json.JSONObject()
                            .put("error", err ?: "No se pudo leer la pantalla.").toString()
                        else -> runCatching { teamOcr.readText(bmp) }
                            .getOrElse { e ->
                                org.json.JSONObject().put("error",
                                    "Falló el reconocimiento de texto: ${e.javaClass.simpleName}").toString()
                            }.also { bmp.recycle() }
                    }
                    ui.post {
                        bubble.visibility = View.VISIBLE
                        panel?.visibility = View.VISIBLE
                        scanning = false
                        emit("onOwnScan", json)
                    }
                }
            }
        }, 120)
    }

    private fun emit(fn: String, json: String) {
        if (!ready) { ui.postDelayed({ emit(fn, json) }, 150); return }
        val payload = JSONObject.quote(json)
        web?.evaluateJavascript("window.$fn && window.$fn($payload)", null)
    }

    // ─────────────────────── puente con el HUD ───────────────────────

    inner class Bridge {
        @JavascriptInterface fun rescan() { ui.post { scan(); resetIdle() } }
        @JavascriptInterface fun scanOwnTeam() { ui.post { scanOwnTeam(); resetIdle() } }
        @JavascriptInterface fun keepOpen() { ui.post { resetIdle() } }
        @JavascriptInterface fun close() { ui.post { collapseNow() } }

        /** Fijar el panel: deja de auto-cerrarse mientras dura el combate. */
        @JavascriptInterface fun pin(on: Boolean) {
            ui.post { pinned = on; if (on) ui.removeCallbacks(autoClose) else resetIdle() }
        }

        @JavascriptInterface fun loadMeta(): String = meta.load()

        /** Dex completo generado por build_dex.py. Puede pesar cientos de KB. */
        @JavascriptInterface fun loadDex(): String = runCatching {
            assets.open("dex.json").bufferedReader().use { it.readText() }
        }.getOrElse { "" }
        @JavascriptInterface fun loadBattle(): String = battle.load()
        @JavascriptInterface fun saveBattle(json: String) { ioHandler.post { battle.save(json) } }
        @JavascriptInterface fun clearBattle() { ioHandler.post { battle.clear() } }

        @JavascriptInterface fun loadTeam(): String = team.load()
        @JavascriptInterface fun saveTeam(json: String) { ioHandler.post { team.save(json) } }

        /** kind: 0 = tick al arrastrar la barra, 1 = click de confirmacion. */
        @JavascriptInterface fun haptic(kind: Int) { haptics.pulse(kind) }

        @JavascriptInterface fun updateMeta(url: String) {
            ioHandler.post {
                val r = meta.update(url)
                ui.post { emit("onMetaUpdate", r) }
            }
        }

        /**
         * El panel tiene FLAG_NOT_FOCUSABLE por diseño (no le roba foco al
         * juego). Un campo de texto real (pegar equipo, URL de meta) necesita
         * foco de ventana para que el teclado aparezca — si no, el usuario
         * toca el campo y no pasa nada. hud.html llama a esto en focus/blur
         * de cualquier <input>/<textarea>. Fuera de esos momentos (que solo
         * ocurren en pantallas de preparación, no durante el combate) el
         * panel vuelve a no robar foco.
         */
        @JavascriptInterface fun needsKeyboard(on: Boolean) {
            ui.post {
                val p = panel ?: return@post
                val lp = panelLp ?: return@post
                lp.flags = if (on) lp.flags and WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE.inv()
                           else lp.flags or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                lp.softInputMode = if (on) WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
                                   else WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING
                runCatching { wm.updateViewLayout(p, lp) }
            }
        }
    }

    // ─────────────────────────── varios ───────────────────────────

    private fun overlayType() =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE

    private fun metrics(): Pair<Int, Int> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val b = wm.currentWindowMetrics.bounds
            b.width() to b.height()
        } else {
            val m = android.util.DisplayMetrics()
            @Suppress("DEPRECATION") wm.defaultDisplay.getRealMetrics(m)
            m.widthPixels to m.heightPixels
        }

    private fun notification(): android.app.Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(CHANNEL, "HUD activo", NotificationManager.IMPORTANCE_MIN)
            )
        }
        return NotificationCompat.Builder(this, CHANNEL)
            .setContentTitle("Champions HUD")
            .setContentText("Mantené presionada la burbuja para cerrar")
            .setSmallIcon(R.drawable.ic_hud)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .build()
    }

    override fun onDestroy() {
        super.onDestroy()
        ui.removeCallbacksAndMessages(null)
        collapseNow()
        web?.let { (it.parent as? ViewGroup)?.removeView(it); it.destroy() }
        web = null
        runCatching { wm.removeView(bubble) }
        capture?.release()
        io.quitSafely()
    }
}

package com.angel.championshud

import android.content.Context
import android.graphics.Bitmap
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.util.DisplayMetrics
import android.view.WindowManager

/**
 * Captura de pantalla persistente.
 *
 * ── POR QUE PERSISTENTE ──
 * Desde Android 14, un permiso de captura permite crear UN SOLO display virtual.
 * La version anterior lo creaba y destruia en cada escaneo: el primero andaba y
 * el segundo tiraba SecurityException, y despues la proyeccion quedaba muerta.
 *
 * Asi que ahora el display se crea una vez y vive todo lo que viva el HUD. Cada
 * escaneo simplemente pide el ultimo fotograma disponible.
 *
 * ── POR QUE NO GASTA BATERIA ──
 * El display virtual solo empuja fotogramas cuando la pantalla cambia, y
 * nosotros no consumimos nada entre escaneos: los buffers se llenan y el
 * productor se frena solo. No hay procesamiento continuo.
 *
 * ── EL TRUCO DE LA PANTALLA QUIETA ──
 * En una pantalla estatica no llegan fotogramas nuevos. Pero el HUD se oculta
 * justo antes de capturar, y ESO cambia la pantalla, lo que fuerza un fotograma
 * fresco. El ocultamiento no era solo cosmetico: es lo que dispara la captura.
 */
class ScreenCapture(private val ctx: Context, private val projection: MediaProjection) {

    private val thread = HandlerThread("capture").apply { start() }
    private val handler = Handler(thread.looper)

    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    private var w = 0
    private var h = 0
    private var dead = false

    init {
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { dead = true }
        }, handler)
    }

    private fun metrics(): Triple<Int, Int, Int> {
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dpi = ctx.resources.displayMetrics.densityDpi
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val b = wm.currentWindowMetrics.bounds
            Triple(b.width(), b.height(), dpi)
        } else {
            val m = DisplayMetrics()
            @Suppress("DEPRECATION") wm.defaultDisplay.getRealMetrics(m)
            Triple(m.widthPixels, m.heightPixels, m.densityDpi)
        }
    }

    /**
     * Crea el display la primera vez. Si la pantalla roto, NO recrea el display
     * — eso volveria a chocar con la restriccion — sino que lo redimensiona, que
     * es la via soportada.
     */
    private fun ensure(): String? {
        if (dead) return "El permiso de captura se cerró. Cerrá el HUD (mantené la burbuja) y abrilo de nuevo."

        val (nw, nh, dpi) = metrics()
        if (nw < 100 || nh < 100) return "Medidas de pantalla inválidas ($nw×$nh)."

        if (display != null && nw == w && nh == h) return null   // ya está listo

        return try {
            if (display == null) {
                val r = ImageReader.newInstance(nw, nh, android.graphics.PixelFormat.RGBA_8888, 3)
                display = projection.createVirtualDisplay(
                    "hud", nw, nh, dpi,
                    DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                    r.surface, null, handler
                ) ?: return "Android no devolvió el display de captura."
                reader = r
            } else {
                // Rotacion: redimensionar y colgarle un lector nuevo.
                val r = ImageReader.newInstance(nw, nh, android.graphics.PixelFormat.RGBA_8888, 3)
                display?.resize(nw, nh, dpi)
                display?.surface = r.surface
                runCatching { reader?.close() }
                reader = r
            }
            w = nw; h = nh
            null
        } catch (e: SecurityException) {
            dead = true
            "Android revocó el permiso de captura. Cerrá el HUD y volvé a abrirlo."
        } catch (e: Exception) {
            "No se pudo iniciar la captura: ${e.javaClass.simpleName}"
        }
    }

    /** onResult(bitmap, motivo). Uno de los dos siempre viene null. */
    fun grab(onResult: (Bitmap?, String?) -> Unit) {
        handler.post {
            ensure()?.let { onResult(null, it); return@post }
            val r = reader ?: run { onResult(null, "Lector de pantalla no disponible."); return@post }

            var done = false
            val finish = { b: Bitmap?, e: String? ->
                if (!done) { done = true; r.setOnImageAvailableListener(null, handler); onResult(b, e) }
            }

            // Si ya hay un fotograma esperando, lo usamos y listo.
            take(r)?.let { finish(it, null); return@post }

            // Si no, esperamos al proximo. El HUD acaba de ocultarse, asi que la
            // pantalla cambio y deberia llegar uno enseguida.
            r.setOnImageAvailableListener({ rd ->
                if (!done) take(rd)?.let { finish(it, null) }
            }, handler)

            for (d in longArrayOf(250, 600, 1200, 2000)) {
                handler.postDelayed({ if (!done) take(r)?.let { finish(it, null) } }, d)
            }
            handler.postDelayed({
                if (!done) finish(null, "La pantalla no devolvió ninguna imagen. " +
                    "Probá de nuevo; si insiste, cerrá y reabrí el HUD.")
            }, 2800)
        }
    }

    /** Toma el fotograma mas reciente y lo convierte. Devuelve null si no hay. */
    private fun take(r: ImageReader): Bitmap? {
        val img = runCatching { r.acquireLatestImage() }.getOrNull() ?: return null
        val bmp = runCatching { img.toBitmap() }.getOrNull()
        runCatching { img.close() }
        return bmp
    }

    /** Se arma con las medidas de la propia imagen, no con las que asumimos. */
    private fun Image.toBitmap(): Bitmap {
        val plane = planes[0]
        val padded = plane.rowStride / plane.pixelStride
        val bmp = Bitmap.createBitmap(padded, height, Bitmap.Config.ARGB_8888)
        bmp.copyPixelsFromBuffer(plane.buffer)
        return if (padded == width) bmp
        else Bitmap.createBitmap(bmp, 0, 0, width, height).also { bmp.recycle() }
    }

    fun release() {
        runCatching { reader?.setOnImageAvailableListener(null, null) }
        runCatching { display?.release() }; display = null
        runCatching { reader?.close() }; reader = null
        runCatching { projection.stop() }
        thread.quitSafely()
    }
}

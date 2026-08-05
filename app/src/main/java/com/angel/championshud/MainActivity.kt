package com.angel.championshud

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

/**
 * Unica pantalla de la app. Pide los dos permisos que el HUD necesita y se sale
 * del camino: a partir de ahi todo pasa sobre el juego.
 *
 * El rediseno completo de esta pantalla (onboarding real, modo demo, ayuda de
 * primera vez) esta diferido a proposito y anotado en docs/future.md — esto es
 * solo la pasada de presentacion que pidio Angel: misma logica exacta, mejor
 * jerarquia visual y textos que expliquen POR QUE se pide cada permiso, en vez
 * de "Paso 2 de 3".
 */
class MainActivity : AppCompatActivity() {

    private lateinit var status: TextView
    private lateinit var launch: Button
    private lateinit var hint: TextView

    private val bg = Color.parseColor("#0B0A14")
    private val card = Color.parseColor("#171331")
    private val accent = Color.parseColor("#C7F03F")
    private val cream = Color.parseColor("#FFF6E6")
    private val muted = Color.parseColor("#9A93B8")
    private val faint = Color.parseColor("#5A5480")

    private val projection = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startOverlay(result.resultCode, result.data!!)
            moveTaskToBack(true)
        } else {
            status.text = "Sin permiso para leer la pantalla, el HUD no puede reconocer al rival. " +
                "Podes intentarlo de nuevo cuando quieras."
        }
    }

    private val notifications = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { refresh() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // El juego se juega en horizontal, y la captura toma sus medidas de la
        // pantalla actual: si esta activity fuera vertical, el display virtual
        // nacia con las medidas al reves.
        val d = resources.displayMetrics.density
        val pad = (22 * d).toInt()
        val gap = (10 * d).toInt()

        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            // Centra sus hijos verticalmente cuando sobra alto; junto con
            // isFillViewport del ScrollView hace el centrado sin necesitar
            // LayoutParams propios (un ScrollView es un FrameLayout: pasarle
            // LinearLayout.LayoutParams es un ClassCastException esperando).
            gravity = Gravity.CENTER_VERTICAL
            setPadding(pad, pad, pad, pad)
        }

        // ── marca ──
        col.addView(TextView(this).apply {
            text = "CHAMPIONS HUD"
            setTextColor(accent)
            textSize = 11f
            letterSpacing = 0.28f
            typeface = Typeface.DEFAULT_BOLD
        })

        col.addView(TextView(this).apply {
            text = "Tu copiloto de combate"
            setTextColor(cream)
            textSize = 27f
            typeface = Typeface.DEFAULT_BOLD
            setPadding(0, (6 * d).toInt(), 0, 0)
        })

        col.addView(TextView(this).apply {
            text = "Lee el equipo rival desde la pantalla, calcula el dano real y recuerda " +
                "todo lo que se fue revelando. La jugada la elegis vos."
            setTextColor(muted)
            textSize = 14f
            setLineSpacing(0f, 1.4f)
            setPadding(0, (10 * d).toInt(), 0, 0)
        })

        // ── tarjeta de estado: que falta y por que ──
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(gap + (4 * d).toInt(), gap + (2 * d).toInt(), gap + (4 * d).toInt(), gap + (2 * d).toInt())
            background = GradientDrawable().apply {
                setColor(card)
                cornerRadius = 16 * d
            }
        }
        panel.addView(TextView(this).apply {
            text = "PARA EMPEZAR"
            setTextColor(faint)
            textSize = 9f
            letterSpacing = 0.18f
            typeface = Typeface.DEFAULT_BOLD
        })
        status = TextView(this).apply {
            setTextColor(cream)
            textSize = 14f
            setLineSpacing(0f, 1.42f)
            setPadding(0, (7 * d).toInt(), 0, 0)
        }
        panel.addView(status)
        col.addView(panel, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply {
            topMargin = (18 * d).toInt()
        })

        // ── accion ──
        launch = Button(this).apply {
            setTextColor(bg)
            textSize = 15f
            typeface = Typeface.DEFAULT_BOLD
            letterSpacing = 0.04f
            isAllCaps = false
            stateListAnimator = null
            background = GradientDrawable().apply {
                setColor(accent)
                cornerRadius = 999 * d
            }
            setPadding(0, (13 * d).toInt(), 0, (13 * d).toInt())
            setOnClickListener { next() }
        }
        col.addView(launch, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply {
            topMargin = (14 * d).toInt()
        })

        hint = TextView(this).apply {
            setTextColor(faint)
            textSize = 12f
            setLineSpacing(0f, 1.35f)
            setPadding(0, (14 * d).toInt(), 0, 0)
        }
        col.addView(hint)

        // En horizontal sobra ancho pero falta alto: sin scroll, el boton queda
        // fuera de pantalla en telefonos chicos.
        val root = ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            addView(col)
        }
        setContentView(root)
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun canOverlay() = Settings.canDrawOverlays(this)

    private fun canNotify() = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
        android.content.pm.PackageManager.PERMISSION_GRANTED

    /**
     * Cada permiso se explica por lo que habilita, no por su numero de paso:
     * "Paso 2 de 3 — permitir notificaciones" no le dice a nadie por que hace
     * falta. El marcador (listo / pendiente) da el progreso sin numerar.
     */
    private fun refresh() {
        val overlay = canOverlay()
        val notify = canNotify()

        fun line(done: Boolean, title: String, why: String) =
            (if (done) "  ✓  " else "  •  ") + title + "\n       " + why

        status.text = listOf(
            line(overlay, "Dibujar sobre el juego",
                "Es como el HUD aparece encima del combate."),
            line(notify, "Mostrar una notificacion",
                "Android la exige para no cortar la lectura de pantalla."),
            line(false, "Leer la pantalla",
                "Solo para reconocer los equipos. No sale nada del telefono.")
        ).joinToString("\n\n")

        launch.text = when {
            !overlay -> "Permitir dibujar sobre el juego"
            !notify -> "Permitir la notificacion"
            else -> "Activar el HUD"
        }
        hint.text = if (overlay && notify)
            "Al activarlo, el HUD queda flotando sobre el juego.\nPara cerrarlo, manten presionada la burbuja."
        else
            "Te va a llevar a los ajustes de Android y volves solo."
    }

    private fun next() {
        when {
            !canOverlay() -> startActivity(
                Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
            )
            !canNotify() -> notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            else -> {
                val mgr = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                projection.launch(mgr.createScreenCaptureIntent())
            }
        }
    }

    private fun startOverlay(code: Int, data: Intent) {
        val i = Intent(this, OverlayService::class.java).apply {
            putExtra(OverlayService.EXTRA_RESULT_CODE, code)
            putExtra(OverlayService.EXTRA_RESULT_DATA, data)
        }
        ContextCompat.startForegroundService(this, i)
    }
}

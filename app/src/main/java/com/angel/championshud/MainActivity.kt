package com.angel.championshud

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
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
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

/**
 * Unica pantalla de la app. Pide los dos permisos que el HUD necesita y se sale
 * del camino: a partir de ahi todo pasa sobre el juego.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var status: TextView
    private lateinit var launch: Button

    private val projection = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            startOverlay(result.resultCode, result.data!!)
            moveTaskToBack(true)
        } else {
            status.text = "Falta el permiso de captura. Sin el, el HUD no puede leer el equipo rival."
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
        val pad = (20 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(Color.parseColor("#0B0A14"))
            setPadding(pad, pad, pad, pad)
        }

        root.addView(TextView(this).apply {
            text = "CHAMPIONS HUD"
            setTextColor(Color.parseColor("#B8FF3C"))
            textSize = 13f
            letterSpacing = 0.22f
        })

        root.addView(TextView(this).apply {
            text = "Lee el equipo rival y calcula daño sin salir del combate."
            setTextColor(Color.parseColor("#EFEDF8"))
            textSize = 24f
            setPadding(0, pad / 2, 0, pad)
        })

        status = TextView(this).apply {
            setTextColor(Color.parseColor("#7E7AA6"))
            textSize = 14f
            setLineSpacing(0f, 1.35f)
        }
        root.addView(status)

        launch = Button(this).apply {
            text = "Activar HUD"
            setPadding(0, pad / 2, 0, pad / 2)
            setOnClickListener { next() }
        }
        root.addView(launch, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply {
            topMargin = pad
        })

        root.addView(TextView(this).apply {
            text = "Para cerrarlo, mantené presionada la burbuja."
            setTextColor(Color.parseColor("#4A4770"))
            textSize = 12f
            setPadding(0, pad, 0, 0)
        })

        setContentView(root)
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun canOverlay() = Settings.canDrawOverlays(this)

    private fun canNotify() = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
        android.content.pm.PackageManager.PERMISSION_GRANTED

    private fun refresh() {
        status.text = when {
            !canOverlay() -> "Paso 1 de 3 — permitir que la app se dibuje sobre otras apps."
            !canNotify() -> "Paso 2 de 3 — permitir notificaciones. Android las exige para " +
                "mantener viva la captura de pantalla."
            else -> "Paso 3 de 3 — autorizar la captura de pantalla. El HUD la usa solo para " +
                "leer la vista previa del rival; nada sale del teléfono."
        }
        launch.text = if (canOverlay() && canNotify()) "Activar HUD" else "Dar permiso"
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

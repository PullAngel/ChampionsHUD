package com.angel.championshud

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Archivo JSON en filesDir con escritura atomica y validacion al leer. */
open class JsonFile(
    ctx: Context,
    private val name: String,          // val: se usa dentro de save(), no solo al inicializar
    private val maxAgeMs: Long = 0L
) {

    protected val file = File(ctx.filesDir, name)
    private val tmp = File(ctx.filesDir, "$name.tmp")

    fun save(json: String) {
        runCatching {
            tmp.writeText(json)
            if (!tmp.renameTo(file)) { tmp.delete(); file.writeText(json) }
        }.onFailure { Log.w("Store", "no pude guardar $name", it) }
    }

    fun load(): String = runCatching {
        if (!file.exists()) return@runCatching "{}"
        if (maxAgeMs > 0 && System.currentTimeMillis() - file.lastModified() > maxAgeMs) {
            file.delete(); return@runCatching "{}"
        }
        file.readText().also { JSONObject(it) }   // valida antes de devolver
    }.getOrElse {
        runCatching { file.delete() }
        "{}"
    }

    fun clear() { runCatching { file.delete() } }
}

/**
 * Estado del combate. Se guarda en cada cambio; si la app muere a mitad de una
 * partida, al reabrir vuelve tal cual estaba. Se descarta a las 3 horas porque
 * un combate viejo confunde mas de lo que ayuda.
 */
class BattleStore(ctx: Context) : JsonFile(ctx, "battle.json", 3 * 60 * 60 * 1000L)

/** El equipo propio: especies, SP, alineaciones, objetos y movimientos. Sin vencimiento. */
class TeamStore(ctx: Context) : JsonFile(ctx, "team.json")

/**
 * El meta cambia regulacion a regulacion, asi que no puede vivir hardcodeado.
 * Busca primero lo descargado en filesDir y cae al que vino en el APK.
 */
class MetaRepository(private val ctx: Context) {

    private val local = File(ctx.filesDir, "meta.json")

    fun load(): String = runCatching {
        if (local.exists()) local.readText().also { JSONObject(it) } else bundled()
    }.getOrElse {
        runCatching { local.delete() }
        bundled()
    }

    private fun bundled(): String = runCatching {
        ctx.assets.open("meta.json").bufferedReader().use { it.readText() }
    }.getOrElse { """{"species":{},"source":"vacio","regulation":"?"}""" }

    /** Descarga y reemplaza. Valida antes de pisar lo que ya funcionaba. */
    fun update(url: String): String = try {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000; readTimeout = 12000
            setRequestProperty("User-Agent", "ChampionsHUD/0.3")
        }
        val body = conn.inputStream.bufferedReader().use { it.readText() }
        conn.disconnect()

        val parsed = JSONObject(body)
        val count = parsed.optJSONObject("species")?.length() ?: 0
        if (count == 0) err("El archivo no trae especies.")
        else {
            val tmp = File(ctx.filesDir, "meta.json.tmp")
            tmp.writeText(body)
            if (!tmp.renameTo(local)) { tmp.delete(); err("No se pudo guardar.") }
            else JSONObject().apply {
                put("ok", true); put("count", count)
                put("regulation", parsed.optString("regulation", "?"))
                put("updated", parsed.optString("updated", ""))
            }.toString()
        }
    } catch (e: Exception) {
        err(e.message ?: "Falló la descarga.")
    }

    private fun err(m: String) = JSONObject().put("ok", false).put("error", m).toString()
}

/**
 * Vibracion corta para las barras de PS. El A55 tiene motor decente, asi que
 * conviene el efecto TICK del sistema antes que un pulso crudo: se siente como
 * un click de One UI y no como un zumbido.
 */
class Haptics(ctx: Context) {

    private val vib: Vibrator? = runCatching {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val mgr = ctx.getSystemService(VibratorManager::class.java)
            mgr?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            ctx.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }.getOrNull()

    private var last = 0L

    /** kind: 0 = tick de arrastre, 1 = click de confirmacion. */
    fun pulse(kind: Int) {
        val v = vib ?: return
        if (!v.hasVibrator()) return
        val now = System.currentTimeMillis()
        if (kind == 0 && now - last < 22) return   // techo de frecuencia al deslizar
        last = now
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val id = if (kind == 0) VibrationEffect.EFFECT_TICK
                else VibrationEffect.EFFECT_CLICK
                v.vibrate(VibrationEffect.createPredefined(id))
            } else {
                @Suppress("DEPRECATION") v.vibrate(if (kind == 0) 8L else 18L)
            }
        }
    }
}

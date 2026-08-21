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
import java.security.MessageDigest

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
 * Un archivo de datos del juego que puede venir del APK o haberse actualizado
 * por internet. Lo descargado (filesDir) gana sobre lo empaquetado (assets).
 *
 * Antes esto existia solo para meta.json (`MetaRepository`). dex.json y
 * sprite_index.json se leian DIRECTO de assets, sin ninguna via de
 * actualizacion — o sea que cuando Champions agrega Pokemon u objetos nuevos,
 * hacia falta un APK nuevo si o si. Generalizarlo es lo que permite que no.
 *
 * `vacio` es lo que devuelve si no hay ni descargado ni empaquetado: un JSON
 * valido y obviamente vacio, para que el motor degrade en vez de recibir "" y
 * tirar una excepcion de parseo en el arranque.
 */
class DataRepository(
    private val ctx: Context,
    private val nombre: String,
    private val vacio: String,
    /**
     * Chequeo de cordura ANTES de pisar lo que ya funcionaba. Devuelve null si
     * el archivo esta bien, o el motivo si no.
     *
     * No es opcional ni un lujo: un dex.json corrupto pero parseable deja al
     * HUD sin reconocer una sola especie, y el usuario no tiene forma de saber
     * por que. Mejor rechazar la descarga y seguir con lo de antes.
     */
    private val validar: (JSONObject) -> String? = { null }
) {

    private val local = File(ctx.filesDir, nombre)

    fun load(): String = runCatching {
        if (local.exists()) local.readText().also { JSONObject(it) } else bundled()
    }.getOrElse {
        runCatching { local.delete() }   // descargado ilegible: se descarta y se cae al del APK
        bundled()
    }

    private fun bundled(): String = runCatching {
        ctx.assets.open(nombre).bufferedReader().use { it.readText() }
    }.getOrElse { vacio }

    /** Version del CONTENIDO instalado, para comparar contra el manifiesto. */
    fun version(): String = runCatching {
        val o = JSONObject(load())
        o.optString("updated").ifEmpty { o.optString("generatedAt") }
    }.getOrElse { "" }

    /**
     * Guarda un contenido ya descargado. Valida primero; si no pasa, no toca
     * nada y devuelve el motivo. Escritura atomica via .tmp + rename.
     */
    fun instalar(body: String): String? {
        val parsed = runCatching { JSONObject(body) }.getOrNull()
            ?: return "no es un JSON valido"
        validar(parsed)?.let { return it }
        val tmp = File(ctx.filesDir, "$nombre.tmp")
        return runCatching {
            tmp.writeText(body)
            if (!tmp.renameTo(local)) { tmp.delete(); "no se pudo guardar" } else null
        }.getOrElse { tmp.delete(); it.message ?: "no se pudo guardar" }
    }

    /** Vuelve a lo que vino en el APK, descartando lo descargado. */
    fun resetear() { runCatching { local.delete() } }

    companion object {
        /**
         * Los tres archivos que la app consume, con su chequeo de cordura.
         * El de meta es el que ya tenia MetaRepository; los otros dos replican
         * lo que sus consumidores ya verificaban por su cuenta (SpriteMatcher
         * exige `v` >= 2 y una lista de sprites; loadDex() exige species+moves).
         */
        fun meta(ctx: Context) = DataRepository(
            ctx, "meta.json", """{"species":{},"source":"vacio","regulation":"?"}"""
        ) { o -> if ((o.optJSONObject("species")?.length() ?: 0) == 0) "no trae especies" else null }

        fun dex(ctx: Context) = DataRepository(
            ctx, "dex.json", """{"species":{},"moves":{},"learnsets":{}}"""
        ) { o ->
            when {
                (o.optJSONObject("species")?.length() ?: 0) == 0 -> "no trae especies"
                (o.optJSONObject("moves")?.length() ?: 0) == 0 -> "no trae movimientos"
                else -> null
            }
        }

        fun sprites(ctx: Context) = DataRepository(
            ctx, "sprite_index.json", """{"v":2,"count":0,"sprites":[]}"""
        ) { o ->
            when {
                o.optInt("v", 1) < 2 -> "es de un formato anterior (v${o.optInt("v", 1)})"
                (o.optJSONArray("sprites")?.length() ?: 0) == 0 -> "no trae sprites"
                else -> null
            }
        }
    }
}

/**
 * Actualizacion de datos por internet, sin APK nuevo.
 *
 * Acepta dos formas de URL, a proposito:
 *
 *   · un manifest.json (build_data_manifest.py) — baja el manifiesto, compara
 *     versiones, y descarga SOLO los archivos que cambiaron. Es el camino
 *     bueno: el manifiesto pesa <1 KB contra 1.7 MB de bajar todo.
 *   · un meta.json suelto — el comportamiento que ya existia. Se conserva
 *     para no romper una URL vieja que alguien ya tenga guardada.
 *
 * Cada archivo se valida antes de reemplazar al que funciona (ver
 * DataRepository.instalar), y ademas se compara su sha256 contra el del
 * manifiesto: una descarga corrupta pero parseable no se detecta de otra forma.
 */
class DataUpdater(private val ctx: Context) {

    private val repos by lazy {
        mapOf(
            "meta.json" to DataRepository.meta(ctx),
            "dex.json" to DataRepository.dex(ctx),
            "sprite_index.json" to DataRepository.sprites(ctx),
        )
    }

    /** Version del APK, para respetar `minAppVersion` del manifiesto. */
    private val appVersion: Int = runCatching {
        @Suppress("DEPRECATION")
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionCode
    }.getOrElse { 1 }

    fun update(url: String): String = try {
        val body = bajar(url)
        val raiz = JSONObject(body)
        if (raiz.has("manifestSchema")) desdeManifiesto(url, raiz)
        else soloMeta(body, raiz)
    } catch (e: Exception) {
        err(e.message ?: "Falló la descarga.")
    }

    /** Compatibilidad hacia atras: la URL apunta a un meta.json pelado. */
    private fun soloMeta(body: String, parsed: JSONObject): String {
        val repo = repos.getValue("meta.json")
        repo.instalar(body)?.let { return err("meta.json $it") }
        return JSONObject().apply {
            put("ok", true)
            put("actualizados", 1)
            put("detalle", "meta.json (${parsed.optString("updated", "?")})")
            put("regulation", parsed.optString("regulation", "?"))
            put("updated", parsed.optString("updated", ""))
        }.toString()
    }

    private fun desdeManifiesto(url: String, man: JSONObject): String {
        val minApp = man.optInt("minAppVersion", 1)
        if (appVersion < minApp) return err(
            "Estos datos necesitan una versión más nueva de la app " +
            "(pide la $minApp, tenés la $appVersion)."
        )
        val files = man.optJSONObject("files") ?: return err("El manifiesto no lista archivos.")
        val base = url.substringBeforeLast('/', "")

        val hechos = mutableListOf<String>()
        val fallos = mutableListOf<String>()
        var alDia = 0

        // OJO: nada de `continue` adentro de un lambda inline (getOrElse, let).
        // Kotlin no permite ese salto no-local y no compila. Por eso el cuerpo
        // del bucle es if/else plano en vez de encadenar `?.let { ... }`.
        for (nombre in files.keys()) {
            val repo = repos[nombre]
            val info = files.optJSONObject(nombre)
            // Un archivo que esta version de la app no usa: se ignora en
            // silencio a proposito. Es lo que permite publicar un manifiesto
            // con datos nuevos sin romper a las apps viejas.
            if (repo == null || info == null) continue

            val remota = info.optString("version", "")
            if (remota.isNotEmpty() && remota == repo.version()) {
                alDia++
                continue
            }

            val cuerpo = runCatching { bajar("$base/$nombre") }.getOrNull()
            if (cuerpo == null) {
                fallos.add("$nombre: no se pudo bajar")
                continue
            }
            val esperado = info.optString("sha256", "")
            if (esperado.isNotEmpty() && sha256(cuerpo) != esperado) {
                fallos.add("$nombre: la descarga no coincide con el manifiesto")
                continue
            }
            val motivo = repo.instalar(cuerpo)
            if (motivo != null) fallos.add("$nombre: $motivo") else hechos.add("$nombre ($remota)")
        }

        return JSONObject().apply {
            put("ok", fallos.isEmpty())
            put("actualizados", hechos.size)
            put("alDia", alDia)
            put("detalle", when {
                hechos.isNotEmpty() -> hechos.joinToString(", ")
                fallos.isEmpty() -> "ya estaba todo al día"
                else -> ""
            })
            if (fallos.isNotEmpty()) put("error", fallos.joinToString(" · "))
        }.toString()
    }

    private fun bajar(url: String): String {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            // dex.json y sprite_index.json pesan cientos de KB; 12s alcanzaba
            // para meta.json pero cortaba una descarga sana de los otros dos
            // en una conexion movil lenta.
            readTimeout = 30000
            setRequestProperty("User-Agent", "ChampionsHUD/0.6")
        }
        return try {
            conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    private fun sha256(s: String): String =
        MessageDigest.getInstance("SHA-256").digest(s.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

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

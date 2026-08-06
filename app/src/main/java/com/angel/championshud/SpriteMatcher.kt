package com.angel.championshud

import android.graphics.Bitmap
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Reconoce Pokemon en pantalla a partir de sus menu sprites.
 *
 * ── LOS TRES ERRORES QUE ESTA VERSION CORRIGE ──
 *
 * 1. BUSCAR "EL COLOR MAS COMUN" NO SIRVE.
 *    En la vista previa el fondo del estadio ocupa cuatro veces mas pixeles que
 *    las tarjetas del rival: el color dominante era negro, no el carmesi de las
 *    tarjetas, y el recorte salia de cualquier lado. Ahora se prueban varios
 *    colores candidatos y gana el que forme una PILA REGULAR de tarjetas —
 *    misma altura, mismo espaciado. Medido sobre una captura real: el color
 *    correcto puntuo 0.997 y el siguiente 0.615.
 *
 * 2. LA TARJETA TIENE DEGRADADO.
 *    Un unico color de fondo con tolerancia fija recortaba mal. El borde
 *    izquierdo de la tarjeta siempre es fondo, asi que se usa como referencia
 *    FILA POR FILA y el degradado deja de importar.
 *
 * 3. LAS HUELLAS NO ERAN COMPARABLES.
 *    Las de referencia salian del lienzo completo de 128x128; en pantalla el
 *    sprite ocupa una caja mas chica y corrida. Comparar celda contra celda no
 *    significaba nada. Ahora los dos lados se recortan a su caja envolvente y
 *    se reescalan igual, asi que la comparacion es invariante a escala y
 *    posicion.
 *
 * Requiere sprite_index.json v2 (build_sprite_index.py). Con un indice viejo
 * avisa en vez de dar resultados sin sentido.
 */
class SpriteMatcher(context: Context) {

    private class Ref(
        @JvmField val dex: Int, @JvmField val form: String, @JvmField val shiny: Boolean,
        @JvmField val sil: FloatArray, @JvmField val col: FloatArray,
        @JvmField val ratio: Float
    )

    private var grid = 16
    private var cgrid = 8
    private var refs: Array<Ref> = emptyArray()
    private var indexError: String? = null

    private companion object {
        /** Cuantos colores candidatos se prueban como posible fondo de tarjeta. */
        const val CANDIDATES = 20
        /** Puntaje minimo de regularidad para aceptar una pila de tarjetas. */
        const val MIN_SCORE = 0.50f
        /** Distancia a la que dejamos de confiar en la forma. */
        const val GOOD_SIL = 0.055f
        /** Cuanto puede diferir la proporcion ancho/alto para seguir siendo
            candidata. Se aplica en LAS DOS pasadas: si la pasada 1 descarto una
            referencia por forma imposible, la pasada 2 no puede resucitarla por
            color. */
        const val RATIO_TOL = 0.55f

        // ── limites de cordura del recorte ──
        // Medidos sobre sprite_index.json (359 especies), no inventados:
        //   llenado de la caja envolvente: 0.204 a 0.774
        //   proporcion ancho/alto:         0.44  a 2.38
        // Las bandas de abajo son deliberadamente MAS anchas que esos rangos:
        // el objetivo es descartar un recorte degenerado (mascara casi vacia, o
        // un bloque solido porque se estimo mal el fondo), nunca rechazar un
        // sprite legitimo. En pantalla la mascara sale de diferencia de color,
        // asi que llena menos que la referencia con alfa — de ahi el margen.
        const val MIN_FILL = 0.08f
        const val MAX_FILL = 0.92f
        const val MIN_AR = 0.25f
        const val MAX_AR = 3.50f
    }

    init {
        val raw = runCatching {
            context.assets.open("sprite_index.json").bufferedReader().use { it.readText() }
        }.getOrNull()

        if (raw == null) {
            indexError = "Falta sprite_index.json en assets. Corré build_sprite_index.py."
        } else {
            val root = runCatching { JSONObject(raw) }.getOrNull()
            when {
                root == null -> indexError = "sprite_index.json ilegible."
                root.optInt("v", 1) < 2 -> indexError =
                    "El índice es de una versión anterior. Volvé a correr build_sprite_index.py " +
                    "(no descarga nada de nuevo, solo recalcula) y copiá el archivo a assets."
                else -> {
                    grid = root.optInt("grid", 16)
                    cgrid = root.optInt("cgrid", 8)
                    val arr = root.optJSONArray("sprites") ?: JSONArray()
                    refs = Array(arr.length()) { i ->
                        val o = arr.getJSONObject(i)
                        Ref(
                            o.optInt("dex"), o.optString("form", ""), o.optBoolean("shiny", false),
                            o.getJSONArray("sil").hundredths(),
                            o.getJSONArray("col").hundredths(),
                            o.optDouble("ratio", 1.0).toFloat()
                        )
                    }
                    if (refs.isEmpty()) indexError = "El índice está vacío."
                }
            }
        }
    }

    private fun JSONArray.hundredths() = FloatArray(length()) { getInt(it) / 100f }

    // ══════════════════ entrada publica ══════════════════

    fun readTeamPreview(shot: Bitmap): String {
        indexError?.let { return JSONObject().put("error", it).toString() }

        val w = shot.width
        val h = shot.height
        if (w < 400 || h < 200)
            return JSONObject().put("error", "Captura demasiado chica (${w}×${h}).").toString()

        // El panel del rival vive en la mitad derecha. Tomamos generoso: la
        // columna exacta la encuentra el detector.
        val from = (w * 0.50f).toInt()
        val sw = w - from
        val px = IntArray(sw * h)
        runCatching { shot.getPixels(px, 0, sw, from, 0, sw, h) }
            .onFailure { return JSONObject().put("error", "No se pudo leer la captura.").toString() }

        val stack = findStack(px, sw, h)
            ?: return JSONObject().put("error",
                "No encuentro el panel del rival. Escaneá en la pantalla de elegir 4, " +
                "con la burbuja del HUD fuera de la franja derecha.").toString()

        val out = JSONArray()
        for (band in stack.bands) {
            val m = readCard(px, sw, stack.x0, band[0], band[1])
            out.put(JSONObject().apply {
                put("dex", m?.dex ?: 0)
                put("form", m?.form ?: "")
                put("shiny", m?.shiny ?: false)
                put("confidence", m?.conf ?: 0f)
            })
        }
        return JSONObject()
            .put("team", out)
            .put("found", stack.bands.size)
            .put("quality", stack.score)
            .toString()
    }

    // ══════════════════ 1. encontrar la pila de tarjetas ══════════════════

    private class Stack(val x0: Int, val x1: Int, val bands: List<IntArray>, val score: Float)

    /**
     * Prueba varios colores candidatos y se queda con el que produzca la pila
     * mas regular. La regularidad —tarjetas de igual alto, equiespaciadas— es
     * una firma mucho mas fuerte que "este color aparece mucho".
     */
    private fun findStack(px: IntArray, w: Int, h: Int): Stack? {
        var best: Stack? = null
        for (color in candidates(px, w, h)) {
            val s = evaluate(px, w, h, color) ?: continue
            if (best == null || s.score > best!!.score) best = s
        }
        return best?.takeIf { it.score >= MIN_SCORE }
    }

    /** Colores mas frecuentes, descartando los casi negros (son fondo del estadio). */
    private fun candidates(px: IntArray, w: Int, h: Int): List<Int> {
        val hist = IntArray(4096)
        var y = 0
        while (y < h) {
            val row = y * w
            var x = 0
            while (x < w) {
                val p = px[row + x]
                hist[(p shr 20 and 0xF shl 8) or (p shr 12 and 0xF shl 4) or (p shr 4 and 0xF)]++
                x += 4
            }
            y += 3
        }
        val idx = (0 until 4096).sortedByDescending { hist[it] }
        val out = ArrayList<Int>(CANDIDATES)
        for (k in idx) {
            if (hist[k] == 0) break
            val r = (k shr 8 and 0xF) * 16 + 8
            val g = (k shr 4 and 0xF) * 16 + 8
            val b = (k and 0xF) * 16 + 8
            if (max(r, max(g, b)) < 40) continue     // negro: fondo, no tarjeta
            out.add((0xFF shl 24) or (r shl 16) or (g shl 8) or b)
            if (out.size >= CANDIDATES) break
        }
        return out
    }

    private fun near(a: Int, b: Int, tol: Int): Boolean =
        abs((a shr 16 and 0xFF) - (b shr 16 and 0xFF)) < tol &&
        abs((a shr 8 and 0xFF) - (b shr 8 and 0xFF)) < tol &&
        abs((a and 0xFF) - (b and 0xFF)) < tol

    /** Para un color dado: columna, bandas y que tan regular es la pila. */
    private fun evaluate(px: IntArray, w: Int, h: Int, color: Int): Stack? {
        // densidad por columna
        val dens = IntArray(w)
        var y = 0
        while (y < h) {
            val row = y * w
            for (x in 0 until w) if (near(px[row + x], color, 46)) dens[x]++
            y += 4
        }
        val peak = dens.max()
        if (peak < h / 4 * 0.05f) return null
        val thr = (peak * 0.5f).toInt()

        var bestS = -1; var bestLen = 0; var s = -1
        for (x in 0 until w) {
            if (dens[x] >= thr && s < 0) s = x
            if ((dens[x] < thr || x == w - 1) && s >= 0) {
                if (x - s > bestLen) { bestLen = x - s; bestS = s }
                s = -1
            }
        }
        if (bestS < 0 || bestLen < 12) return null

        // bandas horizontales dentro de esa columna
        val on = BooleanArray(h)
        for (yy in 0 until h) {
            val row = yy * w
            var n = 0
            var x = bestS
            while (x < bestS + bestLen) { if (near(px[row + x], color, 46)) n++; x += 2 }
            on[yy] = n * 2 > bestLen * 0.5f
        }
        val bands = ArrayList<IntArray>(10)
        val minH = (h * 0.03f).toInt()
        var b = -1
        for (yy in 0 until h) {
            if (on[yy] && b < 0) b = yy
            if ((!on[yy] || yy == h - 1) && b >= 0) {
                if (yy - b > minH) bands.add(intArrayOf(b, yy))
                b = -1
            }
        }
        if (bands.size < 3) return null

        return Stack(bestS, bestS + bestLen, bands, regularity(bands))
    }

    /** 6 tarjetas de igual alto y equiespaciadas = 1.0 */
    private fun regularity(bands: List<IntArray>): Float {
        val n = bands.size
        val hs = FloatArray(n) { (bands[it][1] - bands[it][0]).toFloat() }
        val hMean = hs.average().toFloat()
        val hSd = kotlin.math.sqrt(hs.map { (it - hMean) * (it - hMean) }.average()).toFloat()
        val uniH = 1f - min(1f, hSd / max(hMean, 1f))

        var uniG = 1f
        if (n > 2) {
            val gs = FloatArray(n - 1) { (bands[it + 1][0] - bands[it][0]).toFloat() }
            val gMean = gs.average().toFloat()
            val gSd = kotlin.math.sqrt(gs.map { (it - gMean) * (it - gMean) }.average()).toFloat()
            uniG = 1f - min(1f, gSd / max(gMean, 1f))
        }
        val cnt = max(0f, 1f - abs(n - 6) / 6f)
        return cnt * 0.45f + uniH * 0.30f + uniG * 0.25f
    }

    // ══════════════════ 2. leer una tarjeta ══════════════════

    class Match(val dex: Int, val form: String, val shiny: Boolean, val conf: Float)

    /**
     * Recorta el sprite y lo identifica.
     *
     * El fondo se estima FILA POR FILA con la franja izquierda de la tarjeta,
     * que nunca tiene dibujo. Asi el degradado del panel no arruina la mascara.
     */
    private fun readCard(px: IntArray, w: Int, cardLeft: Int, top: Int, bottom: Int): Match? {
        val ch = bottom - top
        if (ch < 12) return null

        val inTop = top + ch / 10
        val inBot = bottom - ch / 10
        val ih = inBot - inTop
        if (ih < 8) return null

        // Hasta 1.8 veces el alto de la tarjeta: cubre el sprite y deja afuera
        // los iconos de tipo, que viven mas a la derecha.
        val left = cardLeft + max(2, ch / 20)
        val right = min(w - 1, cardLeft + (ch * 1.8f).toInt())
        if (right - left < 10) return null

        val refW = max(3, (right - left) / 10)
        val mask = Array(ih) { BooleanArray(right - left) }
        for (r in 0 until ih) {
            val row = (inTop + r) * w
            // mediana aproximada de la franja izquierda = fondo de ESTA fila
            var sr = 0; var sg = 0; var sb = 0
            for (c in 0 until refW) {
                val p = px[row + left + c]
                sr += p shr 16 and 0xFF; sg += p shr 8 and 0xFF; sb += p and 0xFF
            }
            val br = sr / refW; val bg = sg / refW; val bb = sb / refW
            for (c in 0 until (right - left)) {
                val p = px[row + left + c]
                val d = max(abs((p shr 16 and 0xFF) - br),
                        max(abs((p shr 8 and 0xFF) - bg), abs((p and 0xFF) - bb)))
                mask[r][c] = d > 55
            }
        }

        // Tramo de columnas mas ancho con senal: el sprite. Si los iconos de
        // tipo se colaran, quedan como un bloque aparte y se descartan.
        val mw = right - left
        val colOn = BooleanArray(mw)
        for (c in 0 until mw) {
            var n = 0
            for (r in 0 until ih) if (mask[r][c]) n++
            colOn[c] = n > ih * 0.06f
        }
        var cBest = -1; var cLen = 0; var run = -1
        for (c in 0 until mw) {
            if (colOn[c] && run < 0) run = c
            if ((!colOn[c] || c == mw - 1) && run >= 0) {
                if (c - run > cLen) { cLen = c - run; cBest = run }
                run = -1
            }
        }
        val cs = cBest
        if (cs < 0 || cLen < 6) return null

        var rTop = -1; var rBot = -1
        for (r in 0 until ih) {
            var n = 0
            for (c in cs until cs + cLen) if (mask[r][c]) n++
            if (n > cLen * 0.05f) { if (rTop < 0) rTop = r; rBot = r }
        }
        if (rTop < 0 || rBot - rTop < 6) return null

        val bw = cLen
        val bh = rBot - rTop + 1

        // ── cordura del recorte ──
        // Si la mascara agarro solo un pedazo del sprite (partes finas por
        // debajo del umbral: el "tramo mas ancho de columnas" se queda con un
        // bloque y descarta el resto) o al reves capturo un bloque solido
        // porque se estimo mal el fondo, la huella que sale de ahi no describe
        // a ningun Pokemon. Identificarla igual devuelve una especie cualquiera
        // con aire de certeza — que es justo el fallo que reporto Angel.
        // Devolver null hace que la tarjeta quede como no leida y el jugador la
        // corrija, en vez de recibir un dato inventado (`vision.md`, fallo
        // ruidoso nunca silencioso).
        var onPx = 0
        for (r in rTop..rBot) for (c in cs until cs + cLen) if (mask[r][c]) onPx++
        val fill = onPx.toFloat() / max(1, bw * bh)
        if (fill < MIN_FILL || fill > MAX_FILL) return null
        val ar = bw.toFloat() / max(1, bh)
        if (ar < MIN_AR || ar > MAX_AR) return null

        // huella normalizada a la caja: mismo criterio que en el indice
        val sil = FloatArray(grid * grid)
        for (gy in 0 until grid) for (gx in 0 until grid) {
            val y0 = rTop + gy * bh / grid; val y1 = rTop + (gy + 1) * bh / grid
            val x0 = cs + gx * bw / grid;  val x1 = cs + (gx + 1) * bw / grid
            var on = 0; var tot = 0
            for (r in y0 until max(y1, y0 + 1)) for (c in x0 until max(x1, x0 + 1)) {
                if (r in 0 until ih && c in 0 until mw) { tot++; if (mask[r][c]) on++ }
            }
            sil[gy * grid + gx] = if (tot > 0) on.toFloat() / tot else 0f
        }

        val col = FloatArray(cgrid * cgrid * 3)
        for (gy in 0 until cgrid) for (gx in 0 until cgrid) {
            val y0 = rTop + gy * bh / cgrid; val y1 = rTop + (gy + 1) * bh / cgrid
            val x0 = cs + gx * bw / cgrid;  val x1 = cs + (gx + 1) * bw / cgrid
            var n = 0; var rr = 0f; var gg = 0f; var bb2 = 0f
            for (r in y0 until max(y1, y0 + 1)) for (c in x0 until max(x1, x0 + 1)) {
                if (r in 0 until ih && c in 0 until mw && mask[r][c]) {
                    val p = px[(inTop + r) * w + left + c]
                    rr += p shr 16 and 0xFF; gg += p shr 8 and 0xFF; bb2 += p and 0xFF; n++
                }
            }
            val i = (gy * cgrid + gx) * 3
            if (n > 0) { col[i] = rr / n / 255f; col[i + 1] = gg / n / 255f; col[i + 2] = bb2 / n / 255f }
        }

        return identify(sil, col, bw.toFloat() / max(1, bh))
    }

    // ══════════════════ 3. identificar ══════════════════

    private fun silDist(sil: FloatArray, ref: Ref): Float {
        var d = 0f
        for (i in sil.indices) { val t = sil[i] - ref.sil[i]; d += t * t }
        return d / sil.size
    }

    /**
     * ── POR QUE LA CONFIANZA SE MIDE ASI (reescrito 2026-08-06) ──
     *
     * La version anterior comparaba al ganador contra el SEGUNDO MEJOR DE TODO
     * EL INDICE. Como el indice guarda normal y variocolor de cada especie
     * (359 + 359) y el variocolor tiene silueta casi identica, el segundo mejor
     * era **siempre la misma especie**: medido sobre las 359, el 100% de las
     * veces. La cuenta `(second - best) / second` daba entonces ~0 aun en
     * lecturas perfectas — el 99% de las lecturas CORRECTAS quedaban marcadas
     * como dudosas. Con el aviso encendido en todas, no habia forma de saber
     * cuales estaban realmente mal, y ademas el HUD caia siempre en el cartel
     * de "Lectura dudosa".
     *
     * Ahora el rival es la mejor OTRA ESPECIE (`ref.dex != ganador.dex`), que es
     * la pregunta que de verdad importa: "¿cuanto mejor encaja esta especie que
     * la siguiente candidata distinta?". Que el variocolor de la misma especie
     * empate no es una duda sobre QUIEN es — eso lo decide la pasada de color.
     *
     * Se probo tambien usar dex+forma como identidad, para que una confusion
     * entre forma base y regional (Raichu / Raichu-Alola) tambien avisara. Se
     * descarto CON MEDICION: varias formas regionales comparten silueta exacta
     * con su base, asi que subia las falsas alarmas al 11% sin detectar ni un
     * error mas (los recortes rotos ya se detectan al 100% con dex). Y no hace
     * falta: en la prueba con ruido la pasada de color acerto la forma en
     * 1077 de 1077. Avisar ahi seria volver al problema de origen — un aviso
     * encendido tan seguido que se vuelve invisible.
     *
     * Ademas la distancia del ganador se recalcula sobre el ref que REALMENTE
     * se devuelve: la pasada 2 puede cambiar el ganador de la pasada 1 (medido:
     * en 114 a 160 de 359 casos), y antes la confianza seguia describiendo al de
     * la pasada 1 — un numero que no correspondia al Pokemon informado.
     *
     * Medido con el indice real: falsas alarmas en lecturas correctas 99% -> 0%,
     * manteniendo 359/359 aciertos, y detectando el 99% de los recortes rotos.
     */
    private fun identify(sil: FloatArray, col: FloatArray, ratio: Float): Match? {
        val n = sil.size
        var best: Ref? = null
        var bestD = Float.MAX_VALUE

        // pasada 1: forma, con la proporcion como filtro barato
        for (ref in refs) {
            if (ref.sil.size != n) continue
            if (abs(ref.ratio - ratio) > RATIO_TOL) continue
            val d = silDist(sil, ref)
            if (d < bestD) { bestD = d; best = ref }
        }
        if (best == null) return null

        // pasada 2: color, solo entre los que empataron en forma. Aca se decide
        // normal contra variocolor, que comparten silueta exacta.
        // El filtro de proporcion se repite a proposito: sin el, la pasada 2
        // podia elegir por color una referencia que la pasada 1 habia descartado
        // por forma imposible. Medido: los errores que pasaban SIN aviso ante un
        // recorte roto bajan de 12 a 3.
        val cut = bestD * 1.45f + 1e-5f
        var mixBest = Float.MAX_VALUE
        for (ref in refs) {
            if (ref.sil.size != n) continue
            if (abs(ref.ratio - ratio) > RATIO_TOL) continue
            val d = silDist(sil, ref)
            if (d > cut) continue
            var dc = 0f
            val m = min(col.size, ref.col.size)
            for (i in 0 until m) { val t = col[i] - ref.col[i]; dc += t * t }
            dc /= m
            val mix = d + dc * 1.6f
            if (mix < mixBest) { mixBest = mix; best = ref }
        }

        val win = best!!
        val dWin = silDist(sil, win)
        // El rival: la mejor OTRA especie. Sin filtro de proporcion a proposito
        // — asi la distancia rival es la menor posible y la confianza queda del
        // lado conservador (nunca mas alta de lo que corresponde).
        var dRival = Float.MAX_VALUE
        for (ref in refs) {
            if (ref.sil.size != n || ref.dex == win.dex) continue
            val d = silDist(sil, ref)
            if (d < dRival) dRival = d
        }

        var conf = if (dRival == Float.MAX_VALUE || dRival <= 0f) 0.5f
        else max(0f, min(1f, (dRival - dWin) / dRival))
        if (dWin > GOOD_SIL) conf *= 0.4f
        return Match(win.dex, win.form, win.shiny, conf)
    }
}

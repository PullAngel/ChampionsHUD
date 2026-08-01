package com.angel.championshud

import android.graphics.Bitmap
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import org.json.JSONArray
import org.json.JSONObject

/**
 * Lee texto crudo de una captura de pantalla, con su posición, y nada más.
 *
 * A propósito NO interpreta nada acá — qué línea es la especie, cuál el
 * ítem, cuál un número de reparto de stats. Esa lógica vive en hud.html,
 * no en Kotlin, para poder corregirla editando el HTML si el layout real
 * de "View Details" no se comporta como se asumió mirando un par de
 * capturas (ver docs/decisions.md, la separación motor/cliente existente
 * ya sigue este mismo criterio para el resto del proyecto).
 *
 * Primer intento sin verificar contra el juego real — ver roadmap.md.
 */
class TeamOCR {
    private val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

    /** Bloqueante — llamar siempre fuera del hilo de UI, igual que SpriteMatcher. */
    fun readText(bitmap: Bitmap): String {
        val image = InputImage.fromBitmap(bitmap, 0)
        val result = Tasks.await(recognizer.process(image))

        val lines = JSONArray()
        for (block in result.textBlocks) {
            for (line in block.lines) {
                val box = line.boundingBox ?: continue
                lines.put(
                    JSONObject()
                        .put("t", line.text)
                        .put("x", box.left)
                        .put("y", box.top)
                        .put("w", box.width())
                        .put("h", box.height())
                )
            }
        }
        return JSONObject()
            .put("w", bitmap.width)
            .put("h", bitmap.height)
            .put("lines", lines)
            .toString()
    }
}

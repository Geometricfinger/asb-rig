package org.oiris.core

/** Thermal frame (degrees C) -> display pixels, same rule as oiris/ui/glasses.thermal_image
 *  (vectors: tests/vectors/thermal_render.json). Grayscale is the default; the colour overlay
 *  ramp (black -> purple -> white) avoids the alert hue families. Not a medical measurement. */
object ThermalRender {
    fun gray(celsius: DoubleArray): IntArray {
        if (celsius.isEmpty()) return IntArray(0)
        val lo = celsius.min(); val span = (celsius.max() - lo).let { if (it == 0.0) 1.0 else it }
        return IntArray(celsius.size) { (255.0 * (celsius[it] - lo) / span).toInt() }
    }

    /** Interleaved r,g,b per pixel. */
    fun rgb(celsius: DoubleArray): IntArray {
        val g = gray(celsius); val out = IntArray(g.size * 3)
        for (i in g.indices) {
            val v = g[i]
            out[3 * i] = v.coerceIn(0, 255)
            out[3 * i + 1] = ((v - 128) * 2).coerceIn(0, 255)
            out[3 * i + 2] = (255 - kotlin.math.abs(v - 128) * 2).coerceIn(0, 255)
        }
        return out
    }

    /** ARGB pixels for an Android Bitmap. */
    fun argb(celsius: DoubleArray, colour: Boolean): IntArray =
        if (!colour) gray(celsius).map { (0xFF shl 24) or (it shl 16) or (it shl 8) or it }.toIntArray()
        else rgb(celsius).let { c -> IntArray(c.size / 3) { (0xFF shl 24) or (c[3 * it] shl 16) or (c[3 * it + 1] shl 8) or c[3 * it + 2] } }
}

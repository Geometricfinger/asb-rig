package org.oiris.core

import kotlin.math.PI
import kotlin.math.sqrt

/** M-01 eye features for the phone fallback node's front camera, ported from
 *  oiris/features/eye.py (vectors: tests/vectors/eye_android.json). Report-only on the phone:
 *  the fallback node never alerts alone. */
object EyeFeatures {
    /** Blink events (startIdx, endIdx) where openness < closed for minMs..maxMs. */
    fun blinks(openness: DoubleArray, fps: Double, closed: Double = 0.2, minMs: Double = 50.0, maxMs: Double = 500.0): List<Pair<Int, Int>> {
        val out = ArrayList<Pair<Int, Int>>(); var start = -1
        for (i in openness.indices) {
            val c = openness[i] < closed
            if (c && start < 0) start = i
            else if (!c && start >= 0) {
                val dur = (i - start) / fps * 1000
                if (dur in minMs..maxMs) out.add(start to i)
                start = -1
            }
        }
        return out
    }

    private fun median(v: DoubleArray): Double {
        val s = v.sortedArray(); val n = s.size
        return if (n % 2 == 1) s[n / 2] else (s[n / 2 - 1] + s[n / 2]) / 2.0
    }

    /** Dark-pupil equivalent-circle diameter (px) and quality 0..1 for a grayscale ROI (row-major). */
    fun pupilDiameter(roi: DoubleArray, w: Int, h: Int): Pair<Double, Double> {
        if (roi.isEmpty()) return 0.0 to 0.0
        val lo = roi.min(); val med = median(roi)
        val t = lo + 0.3 * (med - lo)
        var area = 0; var minX = w; var maxX = -1; var minY = h; var maxY = -1
        for (y in 0 until h) for (x in 0 until w) if (roi[y * w + x] <= t) {
            area++; if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y
        }
        if (area < 4) return 0.0 to 0.0
        val bh = maxY - minY + 1; val bw = maxX - minX + 1
        val roundness = minOf(bh, bw).toDouble() / maxOf(bh, bw)
        val fill = area.toDouble() / (bh * bw)
        return 2 * sqrt(area / PI) to (roundness * minOf(1.0, fill / 0.7)).coerceIn(0.0, 1.0)
    }

    /** Eye-openness proxy from an eye ROI: fraction of the ROI darker than the iris band.
     *  Calibrated per session against the open-eye median (ratio, clipped to 0..1). */
    fun openness(darkFraction: Double, openMedian: Double): Double =
        if (openMedian <= 0) 0.0 else (darkFraction / openMedian).coerceIn(0.0, 1.0)
}

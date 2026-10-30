package org.oiris.core

/** Android BLE scan-start limit: Android 7+ silently stops delivering results to an app that
 *  starts scanning more than 5 times in 30 s. Enforced here, before the OS does it for us. */
class ScanRateLimiter(private val maxStarts: Int = 5, private val windowMs: Long = 30_000, private val clock: () -> Long = System::currentTimeMillis) {
    private val starts = ArrayDeque<Long>()

    /** True (and recorded) if a scan may start now. */
    @Synchronized fun tryStart(): Boolean {
        val now = clock()
        while (starts.isNotEmpty() && now - starts.first() >= windowMs) starts.removeFirst()
        if (starts.size >= maxStarts) return false
        starts.addLast(now); return true
    }

    /** Milliseconds until the next start is allowed (0 = now). */
    @Synchronized fun waitMs(): Long {
        val now = clock()
        while (starts.isNotEmpty() && now - starts.first() >= windowMs) starts.removeFirst()
        return if (starts.size < maxStarts) 0 else windowMs - (now - starts.first())
    }
}

/** GPS fix policy for sightings (D-25): a location is used only if it is fresh and accurate
 *  enough; otherwise the row says "no_fix" and coordinates are never guessed. */
object GpsPolicy {
    data class Fix(val lat: Double?, val lon: Double?, val fix: String)

    fun classify(lat: Double?, lon: Double?, accuracyM: Float?, ageMs: Long?, maxAgeMs: Long = 120_000, maxAccuracyM: Float = 100f): Fix {
        if (lat == null || lon == null || ageMs == null || ageMs < 0 || ageMs > maxAgeMs) return Fix(null, null, "no_fix")
        if (lat !in -90.0..90.0 || lon !in -180.0..180.0) return Fix(null, null, "no_fix")
        if (accuracyM == null || accuracyM > maxAccuracyM) return Fix(null, null, "no_fix")
        return Fix(lat, lon, if (accuracyM <= 25f) "gps" else "gps_coarse")
    }
}

/** Optional microphone (off by default): only a loudness level leaves the buffer; audio is never
 *  stored or sent. Returns dBFS of 16-bit PCM. */
object MicLevel {
    fun dbfs(pcm: ShortArray, n: Int = pcm.size): Double {
        if (n <= 0) return -120.0
        var s = 0.0
        for (i in 0 until n) { val v = pcm[i] / 32768.0; s += v * v }
        val rms = kotlin.math.sqrt(s / n)
        return if (rms <= 1e-6) -120.0 else 20 * kotlin.math.log10(rms)
    }
}

/** M-14 sweep timeline model: sweeps newest first, and what is new since the last review. */
data class Sweep(val id: String, val site: String, val tStart: Double, val tEnd: Double, val counts: String, val outcome: String)

object Timeline {
    fun ordered(sweeps: List<Sweep>): List<Sweep> = sweeps.sortedByDescending { it.tStart }
    fun newSince(sweeps: List<Sweep>, lastReviewed: Double): List<Sweep> = ordered(sweeps).filter { it.tEnd > lastReviewed }
    fun line(s: Sweep): String = "${s.site} · ${s.outcome} · ${s.counts}"
}

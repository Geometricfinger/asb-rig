package org.oiris.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.CancellationSignal
import android.os.SystemClock
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import org.oiris.core.GpsPolicy
import java.util.concurrent.Executors

/** M-05: device GPS through the platform LocationManager (no Google Play services, no network
 *  location requests from this app). One fresh fix per sighting; if permission is missing,
 *  GPS is off, or no fix arrives in time, the sighting is stored as "no_fix" (never guessed). */
class LocationSource(private val ctx: Context) {
    private val lm = ctx.getSystemService(LocationManager::class.java)
    private val exec = Executors.newSingleThreadExecutor()

    fun permitted(): Boolean =
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    fun enabled(): Boolean = lm != null && LocationManagerCompat.isLocationEnabled(lm) &&
        lm.isProviderEnabled(LocationManager.GPS_PROVIDER)

    private fun toFix(loc: Location?): GpsPolicy.Fix {
        if (loc == null) return GpsPolicy.classify(null, null, null, null)
        val ageMs = (SystemClock.elapsedRealtimeNanos() - loc.elapsedRealtimeNanos) / 1_000_000
        return GpsPolicy.classify(loc.latitude, loc.longitude, if (loc.hasAccuracy()) loc.accuracy else null, ageMs)
    }

    /** Calls back exactly once (on a background thread) with a fix or no_fix. */
    @SuppressLint("MissingPermission")
    fun current(timeoutMs: Long = 15_000, cb: (GpsPolicy.Fix) -> Unit) {
        if (!permitted() || lm == null || !enabled()) { cb(GpsPolicy.Fix(null, null, "no_fix")); return }
        val done = java.util.concurrent.atomic.AtomicBoolean(false)
        val cancel = CancellationSignal()
        fun finish(f: GpsPolicy.Fix) { if (done.compareAndSet(false, true)) cb(f) }
        LocationManagerCompat.getCurrentLocation(lm, LocationManager.GPS_PROVIDER, cancel, exec) { loc -> finish(toFix(loc)) }
        exec.execute {
            Thread.sleep(timeoutMs)
            if (!done.get()) {
                cancel.cancel()
                finish(toFix(lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)))   // still subject to the age/accuracy policy
            }
        }
    }
}

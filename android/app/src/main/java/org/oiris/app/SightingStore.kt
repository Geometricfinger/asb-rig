package org.oiris.app

import android.content.ContentValues
import android.content.Context
import net.zetetic.database.sqlcipher.SQLiteDatabase
import java.security.MessageDigest
import kotlin.math.roundToLong

/** M-05/M-14 on the phone: SQLCipher DB, hash-chained sighting rows, GPS "no fix" is never
 *  guessed, exports rounded to 0.01 degrees. */
class SightingStore(ctx: Context, key: ByteArray) {
    companion object { const val NAME = "oiris.db" }

    init { System.loadLibrary("sqlcipher") }

    private val db: SQLiteDatabase = SQLiteDatabase.openOrCreateDatabase(ctx.getDatabasePath(NAME), key, null, null, null).apply {
        execSQL("CREATE TABLE IF NOT EXISTS sighting(id TEXT PRIMARY KEY, t REAL, code TEXT, verdict TEXT, lat REAL, lon REAL, fix TEXT, h_prev TEXT, h_this TEXT)")
        execSQL("CREATE TABLE IF NOT EXISTS sweep(id TEXT PRIMARY KEY, site TEXT, t_start REAL, t_end REAL, counts TEXT, outcome TEXT)")
        execSQL("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
        execSQL("CREATE TABLE IF NOT EXISTS pairing(id INTEGER PRIMARY KEY CHECK (id = 1), static_priv TEXT, created REAL, peer_fp TEXT, paired_at REAL)")
    }

    private fun head(): String = db.rawQuery("SELECT h_this FROM sighting ORDER BY rowid DESC LIMIT 1", null).use {
        if (it.moveToFirst()) it.getString(0) else "0".repeat(64)
    }

    fun add(id: String, code: String, lat: Double?, lon: Double?, fix: String) {
        val prev = head()
        val la = if (fix == "no_fix") null else lat
        val lo = if (fix == "no_fix") null else lon
        val h = MessageDigest.getInstance("SHA-256").digest("$prev|$id|$code|$la|$lo".toByteArray()).toHex()
        db.insert("sighting", null, ContentValues().apply {
            put("id", id); put("t", System.currentTimeMillis() / 1000.0); put("code", code); put("verdict", "unresolved")
            if (la != null) put("lat", la); if (lo != null) put("lon", lo); put("fix", fix); put("h_prev", prev); put("h_this", h)
        })
    }

    fun setVerdict(id: String, verdict: String) {
        require(verdict in setOf("confirmed", "benign", "unresolved"))
        db.update("sighting", ContentValues().apply { put("verdict", verdict) }, "id=?", arrayOf(id))
    }

    data class Pin(val id: String, val lat: Double, val lon: Double, val code: String)

    fun pins(): List<Pin> = db.rawQuery("SELECT id, lat, lon, code FROM sighting WHERE lat IS NOT NULL", null).use { c ->
        buildList { while (c.moveToNext()) add(Pin(c.getString(0), c.getDouble(1), c.getDouble(2), c.getString(3))) }
    }

    fun exportRounded(): List<Pin> = pins().map { it.copy(lat = round2(it.lat), lon = round2(it.lon)) }

    // ---- M-14 sweep timeline ----
    fun addSweep(s: org.oiris.core.Sweep) {
        db.insertWithOnConflict("sweep", null, ContentValues().apply {
            put("id", s.id); put("site", s.site); put("t_start", s.tStart); put("t_end", s.tEnd); put("counts", s.counts); put("outcome", s.outcome)
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun sweeps(): List<org.oiris.core.Sweep> = db.rawQuery("SELECT id, site, t_start, t_end, counts, outcome FROM sweep", null).use { c ->
        buildList { while (c.moveToNext()) add(org.oiris.core.Sweep(c.getString(0), c.getString(1), c.getDouble(2), c.getDouble(3), c.getString(4), c.getString(5))) }
    }

    data class Row(val id: String, val t: Double, val code: String, val verdict: String, val fix: String)

    fun sightings(limit: Int = 200): List<Row> = db.rawQuery("SELECT id, t, code, verdict, fix FROM sighting ORDER BY t DESC LIMIT $limit", null).use { c ->
        buildList { while (c.moveToNext()) add(Row(c.getString(0), c.getDouble(1), c.getString(2), c.getString(3), c.getString(4))) }
    }

    fun lastReviewed(): Double = db.rawQuery("SELECT v FROM meta WHERE k='last_reviewed'", null).use { if (it.moveToFirst()) it.getString(0).toDouble() else 0.0 }

    fun markReviewed(t: Double = System.currentTimeMillis() / 1000.0) {
        db.insertWithOnConflict("meta", null, ContentValues().apply { put("k", "last_reviewed"); put("v", t.toString()) }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    // ---- pod pairing (Noise static key, 90-day rotation, D-22) ----
    data class Pairing(val staticPriv: ByteArray, val created: Double, val peerFp: String?)

    fun pairing(): Pairing? = db.rawQuery("SELECT static_priv, created, peer_fp FROM pairing WHERE id=1", null).use {
        if (it.moveToFirst()) Pairing(it.getString(0).hexToBytes(), it.getDouble(1), if (it.isNull(2)) null else it.getString(2)) else null
    }

    /** New static key (first pairing or 90-day rotation); the pod must be re-paired afterwards. */
    fun newStatic(): Pairing {
        val priv = ByteArray(32).also { java.security.SecureRandom().nextBytes(it) }
        val now = System.currentTimeMillis() / 1000.0
        db.insertWithOnConflict("pairing", null, ContentValues().apply {
            put("id", 1); put("static_priv", priv.toHex()); put("created", now); putNull("peer_fp"); putNull("paired_at")
        }, SQLiteDatabase.CONFLICT_REPLACE)
        return Pairing(priv, now, null)
    }

    fun setPeer(fp: String) {
        require(Regex("[0-9a-f]{32}").matches(fp)) { "pod fingerprint is 32 hex characters" }
        db.update("pairing", ContentValues().apply { put("peer_fp", fp); put("paired_at", System.currentTimeMillis() / 1000.0) }, "id=1", null)
    }

    private fun round2(x: Double) = (x * 100).roundToLong() / 100.0
}

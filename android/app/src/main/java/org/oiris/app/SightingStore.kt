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

    private fun round2(x: Double) = (x * 100).roundToLong() / 100.0
}

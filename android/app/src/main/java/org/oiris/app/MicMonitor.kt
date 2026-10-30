package org.oiris.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import org.oiris.core.MicLevel

/** M-13 optional microphone, OFF by default and started only by the user. Only a loudness level
 *  (dBFS) leaves the buffer; audio is never stored, recorded to disk or sent anywhere. */
class MicMonitor(private val ctx: Context, private val onLevel: (Double) -> Unit) {
    @Volatile private var running = false
    private var thread: Thread? = null

    fun permitted() = ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
    val active get() = running

    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (running || !permitted()) return false
        val rate = 16_000
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (min <= 0) return false
        val rec = AudioRecord(MediaRecorder.AudioSource.MIC, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 2)
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return false }
        running = true
        thread = Thread {
            val buf = ShortArray(rate / 2)
            try {
                rec.startRecording()
                while (running) {
                    val n = rec.read(buf, 0, buf.size)
                    if (n > 0) onLevel(MicLevel.dbfs(buf, n))
                    buf.fill(0)
                }
            } finally { rec.stop(); rec.release() }
        }.apply { isDaemon = true; start() }
        return true
    }

    fun stop() { running = false; thread = null }
}

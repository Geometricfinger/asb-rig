package org.oiris.app

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Handler
import android.os.Looper

/** M-13 fallback node: any Android phone becomes a detection node with two families only
 *  (optical: white-flash on/off glint differencing; RF: passive BLE scan). It can never alert
 *  alone. BLE scanning is passive-only and respects Android's 5-starts-per-30-s limit. */
class FallbackNode(private val ctx: Context, private val onScores: (List<Score>) -> Unit) {
    private val near = mutableSetOf<String>()
    private val handler = Handler(Looper.getMainLooper())
    private var lastStart = 0L

    private val cb = object : ScanCallback() {
        override fun onScanResult(type: Int, r: ScanResult) {
            if (r.rssi > -60) near.add(r.device.address.hashCode().toString())   // never stored raw
        }
    }

    @SuppressLint("MissingPermission")
    fun startBle() {
        val now = System.currentTimeMillis()
        if (now - lastStart < 6_000) return          // <=5 starts per 30 s
        lastStart = now
        val bm = ctx.getSystemService(BluetoothManager::class.java) ?: return
        val scanner = bm.adapter?.bluetoothLeScanner ?: return
        scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_POWER).build(), cb)
        handler.postDelayed({ scanner.stopScan(cb); emit() }, 10_000)
    }

    /** Glint score from a flash-on and flash-off luminance pair (same algorithm as oiris/features/optical.py). */
    fun glintScore(on: IntArray, off: IntArray, thresh: Int = 60): Double {
        var hits = 0
        for (i in on.indices) if (on[i] - off[i] > thresh) hits++
        return if (hits in 1..30) 1.0 else 0.0
    }

    var lastGlint = 0.0

    private fun emit() {
        val rf = minOf(1.0, 0.5 * near.size)
        near.clear()
        onScores(listOf(Score("S_glint", lastGlint, 0.4), Score("S_rf", rf, 0.6)))
    }
}

package org.oiris.app

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.os.Build
import android.os.ParcelUuid
import org.oiris.core.BleFraming
import org.oiris.core.Desegmenter
import org.oiris.core.ScanRateLimiter
import java.util.UUID
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit

/** Phone side of the pod/glasses BLE link: GATT client carrying Noise frames (PodLink) as
 *  segments (org.oiris.core.BleFraming, byte-compatible with oiris/link/ble.py). Passive scan
 *  for the O Iris service only, within the 5-starts-per-30-s limit. Writes are serialised (one
 *  outstanding ATT write). Everything on the air is already Noise-encrypted.
 *  NOT exercised on hardware yet: framing + Noise-over-segments are JVM-checked; radio behaviour
 *  needs the pod or glasses. */
@SuppressLint("MissingPermission")
class BleGattTransport(private val ctx: Context, private val limiter: ScanRateLimiter) : FrameTransport {
    private val svc = UUID.fromString(BleFraming.SERVICE_UUID)
    private val rxUuid = UUID.fromString(BleFraming.RX_CHAR_UUID)
    private val txUuid = UUID.fromString(BleFraming.TX_CHAR_UUID)
    private val frames = LinkedBlockingQueue<ByteArray>()
    private val deseg = Desegmenter()
    private val writeSlot = Semaphore(1)
    private val ready = Semaphore(0)
    private var gatt: BluetoothGatt? = null
    private var rx: BluetoothGattCharacteristic? = null
    @Volatile private var mtu = 23
    private var seq = 0
    @Volatile var state = "idle"; private set

    private val cb = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) { state = "connected"; g.requestMtu(BleFraming.DEFAULT_MTU) }
            else if (newState == BluetoothProfile.STATE_DISCONNECTED) { state = "disconnected"; g.close(); writeSlot.release() }
        }
        override fun onMtuChanged(g: BluetoothGatt, m: Int, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) mtu = m
            g.discoverServices()
        }
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val s = g.getService(svc) ?: run { state = "no O Iris service"; return }
            rx = s.getCharacteristic(rxUuid)
            val tx = s.getCharacteristic(txUuid) ?: run { state = "no TX characteristic"; return }
            g.setCharacteristicNotification(tx, true)
            val cccd = tx.getDescriptor(UUID.fromString(BleFraming.CCCD_UUID))
            if (Build.VERSION.SDK_INT >= 33) g.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            else @Suppress("DEPRECATION") { cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE; g.writeDescriptor(cccd) }
        }
        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) { state = "ready"; ready.release() }
        }
        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) { writeSlot.release() }
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic, value: ByteArray) {
            if (c.uuid == txUuid) deseg.feed(value)?.let(frames::put)
        }
        @Deprecated("API < 33")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION") val v = c.value ?: return
            if (Build.VERSION.SDK_INT < 33 && c.uuid == txUuid) deseg.feed(v)?.let(frames::put)
        }
    }

    /** Scan (passive, service-filtered) for up to scanMs, connect to the first pod found. */
    fun connect(scanMs: Long = 10_000): Boolean {
        if (!limiter.tryStart()) { state = "scan limit: wait ${limiter.waitMs() / 1000} s"; return false }
        val scanner = ctx.getSystemService(BluetoothManager::class.java)?.adapter?.bluetoothLeScanner ?: run { state = "bluetooth off"; return false }
        val found = LinkedBlockingQueue<BluetoothDevice>()
        val scb = object : ScanCallback() { override fun onScanResult(t: Int, r: ScanResult) { found.offer(r.device) } }
        scanner.startScan(listOf(ScanFilter.Builder().setServiceUuid(ParcelUuid(svc)).build()),
            ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), scb)
        val dev = found.poll(scanMs, TimeUnit.MILLISECONDS)
        scanner.stopScan(scb)
        if (dev == null) { state = "no pod found"; return false }
        state = "connecting"
        gatt = dev.connectGatt(ctx, false, cb, BluetoothDevice.TRANSPORT_LE)
        return ready.tryAcquire(15, TimeUnit.SECONDS)
    }

    override fun send(frame: ByteArray) {
        val g = gatt ?: error("not connected"); val c = rx ?: error("not ready")
        val segs = synchronized(this) { BleFraming.segment(frame, mtu, seq).also { seq = (seq + it.size) and 0xFF } }
        for (s in segs) {
            if (!writeSlot.tryAcquire(5, TimeUnit.SECONDS)) error("BLE write timed out")
            if (Build.VERSION.SDK_INT >= 33) g.writeCharacteristic(c, s, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
            else @Suppress("DEPRECATION") { c.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE; c.value = s; g.writeCharacteristic(c) }
        }
    }

    override fun receive(timeoutMs: Long): ByteArray? = frames.poll(timeoutMs, TimeUnit.MILLISECONDS)

    fun close() { gatt?.disconnect(); gatt = null; state = "idle" }
}

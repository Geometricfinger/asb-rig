package org.oiris.core

/** BLE GATT segmenting of Noise frames, byte-compatible with oiris/link/ble.py
 *  (vectors: tests/vectors/ble_framing.json). Segment = seq | flags(0x01 first, 0x02 last) |
 *  [u32 BE total length, first only] | payload. Carries already-encrypted frames only. */
object BleFraming {
    const val SERVICE_UUID = "6f697269-7300-4c69-6e6b-000000000001"
    const val RX_CHAR_UUID = "6f697269-7300-4c69-6e6b-000000000002"   // phone -> pod, write without response
    const val TX_CHAR_UUID = "6f697269-7300-4c69-6e6b-000000000003"   // pod -> phone, notify
    const val CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"
    const val FIRST = 0x01
    const val LAST = 0x02
    const val MAX_FRAME = 65_535 + 4
    const val DEFAULT_MTU = 247

    fun segment(frame: ByteArray, mtu: Int, seq0: Int = 0): List<ByteArray> {
        require(frame.isNotEmpty() && frame.size <= MAX_FRAME) { "frame size out of range" }
        val room = mtu - 3 - 2
        require(room >= 8) { "MTU too small" }
        val out = ArrayList<ByteArray>()
        var pos = 0; var seq = seq0
        while (pos < frame.size || out.isEmpty()) {
            val first = out.isEmpty()
            val n = if (first) room - 4 else room
            val end = minOf(frame.size, pos + n)
            val chunk = frame.copyOfRange(pos, end); pos = end
            val flags = (if (first) FIRST else 0) or (if (pos >= frame.size) LAST else 0)
            val hdr = if (first) byteArrayOf((seq and 0xFF).toByte(), flags.toByte(),
                (frame.size ushr 24).toByte(), (frame.size ushr 16).toByte(), (frame.size ushr 8).toByte(), frame.size.toByte())
            else byteArrayOf((seq and 0xFF).toByte(), flags.toByte())
            out.add(hdr + chunk); seq++
        }
        return out
    }
}

class Desegmenter {
    private var expectSeq: Int? = null
    private val buf = java.io.ByteArrayOutputStream()
    private var total = 0
    private var active = false
    var dropped = 0; private set

    private fun reset() { buf.reset(); total = 0; active = false }

    fun feed(seg: ByteArray): ByteArray? {
        if (seg.size < 2) { dropped++; reset(); return null }
        val seq = seg[0].toInt() and 0xFF; val flags = seg[1].toInt() and 0xFF
        var body = seg.copyOfRange(2, seg.size)
        if (expectSeq != null && seq != expectSeq) { if (active) dropped++; reset() }
        expectSeq = (seq + 1) and 0xFF
        if (flags and BleFraming.FIRST != 0) {
            if (active) dropped++
            reset()
            if (body.size < 4) { dropped++; return null }
            total = ((body[0].toInt() and 0xFF) shl 24) or ((body[1].toInt() and 0xFF) shl 16) or
                ((body[2].toInt() and 0xFF) shl 8) or (body[3].toInt() and 0xFF)
            if (total <= 0 || total > BleFraming.MAX_FRAME) { dropped++; return null }
            body = body.copyOfRange(4, body.size); active = true
        } else if (!active) return null
        buf.write(body)
        if (buf.size() > total) { dropped++; reset(); return null }
        if (flags and BleFraming.LAST != 0) {
            if (buf.size() != total) { dropped++; reset(); return null }
            val out = buf.toByteArray(); reset(); return out
        }
        return null
    }
}

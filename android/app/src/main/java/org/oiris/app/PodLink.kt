package org.oiris.app

import org.oiris.core.Fragments
import org.oiris.core.Reassembler
import org.oiris.core.SecureChannel

/** Phone end of the pod<->phone link: Noise_XX (org.oiris.core, byte-compatible with
 *  oiris/security/channel.py) over any byte-frame transport. The BLE GATT transport needs the pod
 *  hardware and is not built yet (docs/STATUS.md); until a transport is attached the app reports
 *  "Pod not connected" and the enrollment screen stays locked. */
interface FrameTransport {
    fun send(frame: ByteArray)
    fun receive(timeoutMs: Long): ByteArray?
}

class PodLink(private val transport: FrameTransport, staticPriv: ByteArray, podFingerprint: String) {
    private val ch = SecureChannel(initiator = true, staticPriv = staticPriv, expectedPeerFp = podFingerprint)
    private val rx = Reassembler(ch)

    fun handshake(timeoutMs: Long = 5_000) {
        transport.send(ch.writeHandshake())
        ch.readHandshake(transport.receive(timeoutMs) ?: error("pod did not answer"))
        transport.send(ch.writeHandshake())
    }

    /** One request/response (canonical JSON) through the encrypted channel. */
    @Synchronized
    fun request(json: String, timeoutMs: Long = 10_000): String {
        Fragments.split(ch, json.toByteArray()).forEach(transport::send)
        while (true) {
            val f = transport.receive(timeoutMs) ?: error("pod timed out")
            rx.feed(f)?.let { return String(it) }
        }
    }

    companion object {
        @Volatile var current: PodLink? = null   // set when a transport is paired and connected
    }
}

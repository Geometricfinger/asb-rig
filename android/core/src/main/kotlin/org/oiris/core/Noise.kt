package org.oiris.core

import org.bouncycastle.crypto.digests.Blake2sDigest
import org.bouncycastle.crypto.macs.HMac
import org.bouncycastle.crypto.modes.ChaCha20Poly1305
import org.bouncycastle.crypto.params.AEADParameters
import org.bouncycastle.crypto.params.KeyParameter
import org.bouncycastle.math.ec.rfc7748.X25519
import java.security.MessageDigest
import java.security.SecureRandom

/** Noise_XX_25519_ChaChaPoly_BLAKE2s (Noise spec rev 34), byte-compatible with the Python pod side
 *  (noiseprotocol + oiris/security/channel.py). Verified against tests/vectors/noise_xx.json. */
class NoiseException(msg: String) : Exception(msg)

object Prim {
    const val DHLEN = 32
    fun hash(vararg parts: ByteArray): ByteArray {
        val d = Blake2sDigest(256); parts.forEach { d.update(it, 0, it.size) }
        return ByteArray(32).also { d.doFinal(it, 0) }
    }
    fun hmac(key: ByteArray, vararg data: ByteArray): ByteArray {
        val m = HMac(Blake2sDigest(256)); m.init(KeyParameter(key)); data.forEach { m.update(it, 0, it.size) }
        return ByteArray(32).also { m.doFinal(it, 0) }
    }
    fun hkdf2(ck: ByteArray, ikm: ByteArray): Pair<ByteArray, ByteArray> {
        val t = hmac(ck, ikm); val o1 = hmac(t, byteArrayOf(1)); val o2 = hmac(t, o1, byteArrayOf(2))
        return o1 to o2
    }
    fun pub(priv: ByteArray): ByteArray = ByteArray(32).also { X25519.scalarMultBase(priv, 0, it, 0) }
    fun dh(priv: ByteArray, pub: ByteArray): ByteArray {
        val out = ByteArray(32)
        if (!X25519.calculateAgreement(priv, 0, pub, 0, out, 0)) throw NoiseException("bad DH (low-order point)")
        return out
    }
    fun aead(enc: Boolean, k: ByteArray, n: Long, ad: ByteArray, data: ByteArray): ByteArray {
        val nonce = ByteArray(12); for (i in 0 until 8) nonce[4 + i] = (n ushr (8 * i)).toByte()
        val c = ChaCha20Poly1305(); c.init(enc, AEADParameters(KeyParameter(k), 128, nonce, ad))
        val out = ByteArray(c.getOutputSize(data.size))
        val len = c.processBytes(data, 0, data.size, out, 0)
        try { c.doFinal(out, len) } catch (e: Exception) { throw NoiseException("decrypt failed") }
        return out
    }
}

class CipherState(var k: ByteArray? = null) {
    var n = 0L
    fun encrypt(ad: ByteArray, p: ByteArray): ByteArray { val key = k ?: return p; return Prim.aead(true, key, n, ad, p).also { n++ } }
    fun decrypt(ad: ByteArray, c: ByteArray): ByteArray { val key = k ?: return c; return Prim.aead(false, key, n, ad, c).also { n++ } }
    fun rekey() { k = Prim.aead(true, k!!, -1L /* 2^64-1 */, ByteArray(0), ByteArray(32)).copyOf(32) }
}

/** XX handshake. `ephemeral` may be fixed only by test-vector checks. */
class NoiseXX(val initiator: Boolean, private val s: ByteArray, prologue: ByteArray = ByteArray(0), ephemeral: ByteArray? = null) {
    private var h: ByteArray = "Noise_XX_25519_ChaChaPoly_BLAKE2s".toByteArray().let { if (it.size <= 32) it.copyOf(32) else Prim.hash(it) }
    private var ck = h.copyOf()
    private val cs = CipherState()
    private val e: ByteArray = ephemeral ?: ByteArray(32).also { SecureRandom().nextBytes(it) }
    private var re: ByteArray? = null
    var rs: ByteArray? = null; private set
    private var step = 0
    var finished = false; private set
    lateinit var send: CipherState; private set
    lateinit var recv: CipherState; private set
    val handshakeHash: ByteArray get() = h

    init { mixHash(prologue) }

    private fun mixHash(d: ByteArray) { h = Prim.hash(h, d) }
    private fun mixKey(ikm: ByteArray) { val (a, b) = Prim.hkdf2(ck, ikm); ck = a; cs.k = b; cs.n = 0 }
    private fun encHash(p: ByteArray) = cs.encrypt(h, p).also { mixHash(it) }
    private fun decHash(c: ByteArray) = cs.decrypt(h, c).also { mixHash(c) }
    private fun split() {
        val (a, b) = Prim.hkdf2(ck, ByteArray(0))
        val c1 = CipherState(a); val c2 = CipherState(b)
        if (initiator) { send = c1; recv = c2 } else { send = c2; recv = c1 }
        finished = true
    }

    fun writeMessage(payload: ByteArray = ByteArray(0)): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        when {
            initiator && step == 0 -> { val ep = Prim.pub(e); mixHash(ep); out.write(ep) }
            !initiator && step == 1 -> {
                val ep = Prim.pub(e); mixHash(ep); out.write(ep)
                mixKey(Prim.dh(e, re!!)); out.write(encHash(Prim.pub(s))); mixKey(Prim.dh(s, re!!))
            }
            initiator && step == 2 -> { out.write(encHash(Prim.pub(s))); mixKey(Prim.dh(s, re!!)) }
            else -> throw NoiseException("out of order write")
        }
        out.write(encHash(payload)); step++
        if (step == 3) split()
        return out.toByteArray()
    }

    fun readMessage(m: ByteArray): ByteArray {
        var off = 0
        fun take(n: Int): ByteArray { if (off + n > m.size) throw NoiseException("short message"); return m.copyOfRange(off, off + n).also { off += n } }
        when {
            !initiator && step == 0 -> { re = take(32); mixHash(re!!) }
            initiator && step == 1 -> {
                re = take(32); mixHash(re!!); mixKey(Prim.dh(e, re!!))
                rs = decHash(take(48)); mixKey(Prim.dh(e, rs!!))
            }
            !initiator && step == 2 -> { rs = decHash(take(48)); mixKey(Prim.dh(e, rs!!)) }
            else -> throw NoiseException("out of order read")
        }
        val p = decHash(m.copyOfRange(off, m.size)); step++
        if (step == 3) split()
        return p
    }
}

/** Phone side of the pod<->phone link; same framing and rekey rule as oiris/security/channel.py:
 *  frame = 4-byte big-endian rekey generation || ciphertext; rekey every 1,000 messages or 10 minutes. */
class SecureChannel(initiator: Boolean, staticPriv: ByteArray, private val expectedPeerFp: String,
                    private val rekeyMessages: Int = 1000, private val rekeyMillis: Long = 600_000,
                    private val clock: () -> Long = System::currentTimeMillis, ephemeral: ByteArray? = null) {
    val noise = NoiseXX(initiator, staticPriv, ephemeral = ephemeral)
    private var sent = 0; private var txEpoch = clock(); var rekeys = 0; private set
    private var rxGen = 0
    val ready get() = noise.finished

    fun writeHandshake(): ByteArray = noise.writeMessage().also { if (noise.finished) checkPeer() }
    fun readHandshake(m: ByteArray) { noise.readMessage(m); if (noise.rs != null) checkPeer() }

    private fun checkPeer() {
        val pub = noise.rs ?: throw NoiseException("no peer static key")
        if (!MessageDigest.isEqual(fingerprint(pub).toByteArray(), expectedPeerFp.toByteArray()))
            throw NoiseException("peer static key does not match paired fingerprint")
    }

    fun encrypt(data: ByteArray): ByteArray {
        if (!ready) throw NoiseException("handshake not finished")
        val now = clock()
        if (sent >= rekeyMessages || now - txEpoch >= rekeyMillis) { noise.send.rekey(); sent = 0; txEpoch = now; rekeys++ }
        sent++
        val g = rekeys
        return byteArrayOf((g ushr 24).toByte(), (g ushr 16).toByte(), (g ushr 8).toByte(), g.toByte()) + noise.send.encrypt(ByteArray(0), data)
    }

    fun decrypt(msg: ByteArray): ByteArray {
        if (msg.size < 4) throw NoiseException("short frame")
        val gen = ((msg[0].toInt() and 0xff) shl 24) or ((msg[1].toInt() and 0xff) shl 16) or ((msg[2].toInt() and 0xff) shl 8) or (msg[3].toInt() and 0xff)
        if (gen < rxGen) throw NoiseException("stale key generation (replay?)")
        while (rxGen < gen) { noise.recv.rekey(); rxGen++ }
        return noise.recv.decrypt(ByteArray(0), msg.copyOfRange(4, msg.size))
    }

    companion object {
        fun fingerprint(staticPub: ByteArray): String {
            val d = Blake2sDigest(128); d.update(staticPub, 0, staticPub.size)
            return ByteArray(16).also { d.doFinal(it, 0) }.joinToString("") { "%02x".format(it) }
        }
        fun newStatic(): ByteArray = ByteArray(32).also { SecureRandom().nextBytes(it) }
    }
}

/** Application messages larger than one Noise frame; same format as oiris/security/channel.py
 *  `fragment` / `Reassembler`: plaintext = 1 flag byte (1 = more, 0 = last) || chunk (<= 60,000 bytes). */
object Fragments {
    const val CHUNK = 60_000
    const val MAX_MESSAGE = 8 * 1024 * 1024
    fun split(ch: SecureChannel, data: ByteArray): List<ByteArray> {
        if (data.size > MAX_MESSAGE) throw NoiseException("message too large")
        val n = maxOf(1, (data.size + CHUNK - 1) / CHUNK)
        return (0 until n).map { k ->
            val part = data.copyOfRange(k * CHUNK, minOf(data.size, (k + 1) * CHUNK))
            ch.encrypt(byteArrayOf(if (k < n - 1) 1 else 0) + part)
        }
    }
}

class Reassembler(private val ch: SecureChannel) {
    private val buf = java.io.ByteArrayOutputStream()
    fun feed(frame: ByteArray): ByteArray? {
        val pt = ch.decrypt(frame)
        if (pt.isEmpty() || pt[0] !in byteArrayOf(0, 1)) { buf.reset(); throw NoiseException("bad fragment flag") }
        buf.write(pt, 1, pt.size - 1)
        if (buf.size() > Fragments.MAX_MESSAGE) { buf.reset(); throw NoiseException("message too large") }
        if (pt[0].toInt() == 1) return null
        return buf.toByteArray().also { buf.reset() }
    }
}

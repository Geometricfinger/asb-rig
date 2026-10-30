package org.oiris.core

import java.io.File

/** JVM checks for the pure-Kotlin core (run by Gradle `:core:check` -> `jvmChecks`, and in CI).
 *  Self-contained on purpose: no test framework dependency to licence. Exit code 1 on any failure. */
private var failures = 0
private var passed = 0
fun expect(name: String, cond: Boolean) { if (cond) passed++ else { failures++; System.err.println("FAIL: $name") } }
fun hex(b: ByteArray) = b.joinToString("") { "%02x".format(it) }
fun unhex(s: String) = ByteArray(s.length / 2) { s.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
inline fun throws(block: () -> Unit) = try { block(); false } catch (e: Exception) { true }

@Suppress("UNCHECKED_CAST")
fun main(args: Array<String>) {
    val root = File(args.getOrElse(0) { "../.." })
    val v = Json.decode(File(root, "tests/vectors/noise_xx.json").readText()) as Map<String, Any?>
    // ---- Noise vectors (bytes produced by the Python pod side) ----
    val ist = unhex(v["init_static"] as String); val rst = unhex(v["resp_static"] as String)
    expect("static pub", hex(Prim.pub(ist)) == v["init_static_pub"])
    expect("fingerprint", SecureChannel.fingerprint(Prim.pub(rst)) == v["resp_fingerprint"])
    val i = NoiseXX(true, ist, ephemeral = unhex(v["init_ephemeral"] as String))
    val r = NoiseXX(false, rst, ephemeral = unhex(v["resp_ephemeral"] as String))
    val hs = v["handshake"] as List<String>
    val m1 = i.writeMessage(); expect("msg1", hex(m1) == hs[0]); r.readMessage(m1)
    val m2 = r.writeMessage(); expect("msg2", hex(m2) == hs[1]); i.readMessage(m2)
    val m3 = i.writeMessage(); expect("msg3", hex(m3) == hs[2]); r.readMessage(m3)
    expect("handshake hash", hex(i.handshakeHash) == v["handshake_hash"] && hex(r.handshakeHash) == v["handshake_hash"])
    var rekeyed = false
    for (t in v["transport"] as List<Map<String, Any?>>) {
        val plain = (t["plain"] as String).toByteArray()
        val (tx, rx) = if (t["dir"] == "i2r") i.send to r.recv else r.send to i.recv
        if (t["gen"] == 1L && !rekeyed) { i.send.rekey(); r.recv.rekey(); rekeyed = true }
        val c = tx.encrypt(ByteArray(0), plain)
        expect("transport ${t["plain"]}", hex(c) == t["cipher"])
        expect("decrypt ${t["plain"]}", rx.decrypt(ByteArray(0), c).contentEquals(plain))
    }
    // tamper is rejected
    val c = i.send.encrypt(ByteArray(0), "x".toByteArray()); c[0] = (c[0].toInt() xor 1).toByte()
    expect("tamper rejected", throws { r.recv.decrypt(ByteArray(0), c) })

    // ---- SecureChannel: pairing check, rekey generations, fragments ----
    val pod = SecureChannel(false, rst, SecureChannel.fingerprint(Prim.pub(ist)), rekeyMessages = 3)
    val phone = SecureChannel(true, ist, SecureChannel.fingerprint(Prim.pub(rst)), rekeyMessages = 3)
    pod.readHandshake(phone.writeHandshake()); phone.readHandshake(pod.writeHandshake()); pod.readHandshake(phone.writeHandshake())
    expect("ready", pod.ready && phone.ready)
    repeat(8) { k -> expect("rekey msg $k", pod.decrypt(phone.encrypt("m$k".toByteArray())).contentEquals("m$k".toByteArray())) }
    expect("rekeyed", phone.rekeys == 2)
    val big = ByteArray(150_000) { (it % 251).toByte() }
    val ra = Reassembler(pod); var got: ByteArray? = null
    val frames = Fragments.split(phone, big); frames.forEach { got = ra.feed(it) ?: got }
    expect("fragments", frames.size == 3 && got!!.contentEquals(big))
    val wrong = SecureChannel(true, ist, "00".repeat(16))
    val pod2 = SecureChannel(false, rst, SecureChannel.fingerprint(Prim.pub(ist)))
    pod2.readHandshake(wrong.writeHandshake())
    expect("wrong pairing refused", throws { wrong.readHandshake(pod2.writeHandshake()) })

    // ---- Enrollment protocol strings (shared with Python) ----
    val req = (Json.decode(File(root, "tests/vectors/enrollment_protocol.json").readText()) as Map<String, Any?>)["requests"] as Map<String, String>
    expect("p status", EnrollmentProtocol.status() == req["status"])
    expect("p warning", EnrollmentProtocol.warning("us-other") == req["warning"])
    expect("p start", EnrollmentProtocol.startSession() == req["start_session"])
    expect("p add", EnrollmentProtocol.addPerson("S", "Alex", "c-ok", false) == req["add_person"])
    expect("p add unicode/null", EnrollmentProtocol.addPerson("S", "Mom é", null, false) == req["add_person_no_consent"])
    expect("p shot", EnrollmentProtocol.shot("P", Angle.LEFT, 2, 1, byteArrayOf(1, 2, 3, 4, 5, 6)) == req["shot"])
    expect("p finish", EnrollmentProtocol.finish("P") == req["finish"])
    expect("p end", EnrollmentProtocol.endSession("S") == req["end_session"])

    // ---- EnrollmentFlow against a scripted pod ----
    var optedIn = false; val sent = mutableListOf<Map<String, Any?>>()
    val pod3: (String) -> String = { s ->
        val m = Json.decode(s) as Map<String, Any?>; sent += m
        when (m["op"]) {
            "status" -> Json.encode(mapOf("ok" to true, "opted_in" to optedIn, "modes" to if (optedIn) listOf("personal") else listOf<String>()))
            "warning" -> Json.encode(mapOf("ok" to true, "text" to "Face matching is about to be turned on."))
            "opt_in" -> { optedIn = m["typed"] == CONFIRM_PHRASE; Json.encode(mapOf("ok" to optedIn)) }
            "start_session" -> Json.encode(mapOf("ok" to true, "session" to "S1"))
            "add_person" -> Json.encode(mapOf("ok" to true, "person" to "P${sent.size}"))
            "shot" -> { val a = m["angle"]; val ok = (m["w"] as Long) >= 64
                Json.encode(mapOf("ok" to true, "accepted" to ok, "reason" to if (ok) "ok" else "move closer", "code" to a)) }
            "finish" -> Json.encode(mapOf("ok" to true, "complete" to true, "message" to "complete"))
            else -> Json.encode(mapOf("ok" to true))
        }
    }
    val f = EnrollmentFlow(pod3)
    expect("off by default -> locked", f.open() == EnrollmentFlow.Stage.LOCKED)
    expect("no capture while locked", throws { f.startPerson("Alex", "c") })
    f.showWarning()
    expect("wrong phrase keeps it off", !f.optIn("yes") && !optedIn && f.stage == EnrollmentFlow.Stage.WARNING)
    expect("typed opt-in", f.optIn("I UNDERSTAND") && f.stage == EnrollmentFlow.Stage.READY)
    for (n in 1..12) {   // no count limit: enroll many people in one session
        f.startPerson("Person $n", "c$n")
        expect("first prompt", f.lastMessage == Angle.FRONT.prompt || n > 1)
        val small = ByteArray(10 * 10 * 3)
        expect("rejected shot reason", !f.submit(Angle.FRONT, 10, 10, small) && f.lastMessage == "move closer")
        for (a in Angle.values()) { val px = ByteArray(64 * 64 * 3) { 7 }; expect("accept $a", f.submit(a, 64, 64, px)); expect("frame wiped", px.all { it == 0.toByte() }) }
        expect("checklist all ticked", f.checklist().all { it.second } && f.nextAngle() == null)
        expect("finish", f.finish() && f.lastMessage == "Template complete for Person $n")
    }
    expect("12 enrolled, one session", f.enrolledThisSession == 12 && sent.count { it["op"] == "start_session" } == 1)
    f.end(); expect("end session sent", sent.last()["op"] == "end_session")

    // ---- Alert visuals from the C7 tokens ----
    val av = AlertVisuals.fromTokens(File(root, "oiris/ui/design_tokens.json").readText())
    expect("three distinct shapes", av.values.map { it.shape }.toSet().size == 3)
    expect("words", av["medium"]!!.word == "Medium signal" && av.values.none { "robot" in it.word.lowercase() })
    expect("engine map", AlertVisuals.forEngine("attention") == "medium" && AlertVisuals.forEngine(null) == null)
    expect("bad tokens refused", throws { AlertVisuals.fromTokens("{\"alert_levels\":{\"low\":{}},\"color\":{\"alert\":{}}}") })
    expect("json roundtrip", Json.encode(Json.decode("{\"b\":[1,2.5,\"x\\n\"],\"a\":null}")) == "{\"a\":null,\"b\":[1,2.5,\"x\\n\"]}")


    // ---- BLE GATT framing of Noise frames (shared with oiris/link/ble.py) ----
    val bv = (Json.decode(File(root, "tests/vectors/ble_framing.json").readText()) as Map<String, Any?>)["cases"] as List<Map<String, Any?>>
    for (c in bv) {
        val frame = unhex(c["frame"] as String); val mtu = (c["mtu"] as Long).toInt(); val seq0 = (c["seq0"] as Long).toInt()
        val segs = BleFraming.segment(frame, mtu, seq0)
        expect("ble segments n=${frame.size} mtu=$mtu", segs.map { hex(it) } == c["segments"] as List<String>)
        expect("ble segment fits ATT mtu=$mtu", segs.all { it.size <= mtu - 3 })
        val d = Desegmenter(); var got: ByteArray? = null
        segs.forEach { s -> d.feed(s)?.let { got = it } }
        expect("ble reassembly n=${frame.size}", got != null && got!!.contentEquals(frame))
    }
    run {   // a lost segment drops the partial frame; the next frame still arrives
        val f1 = ByteArray(1000) { 1 }; val f2 = ByteArray(700) { 2 }
        val s1 = BleFraming.segment(f1, 185, 0); val s2 = BleFraming.segment(f2, 185, s1.size)
        val d = Desegmenter(); val out = mutableListOf<ByteArray>()
        (s1.filterIndexed { i, _ -> i != 2 } + s2).forEach { s -> d.feed(s)?.let { out.add(it) } }
        expect("ble gap drops partial frame", out.size == 1 && out[0].contentEquals(f2) && d.dropped >= 1)
    }
    run {   // Noise frames over BLE segments end to end (loopback)
        val podB = SecureChannel(false, rst, SecureChannel.fingerprint(Prim.pub(ist)))
        val phoneB = SecureChannel(true, ist, SecureChannel.fingerprint(Prim.pub(rst)))
        val toPod = Desegmenter(); val toPhone = Desegmenter(); var seqA = 0; var seqB = 0
        fun p2pod(f: ByteArray): ByteArray { var r: ByteArray? = null; BleFraming.segment(f, 23, seqA).also { seqA += it.size }.forEach { s -> toPod.feed(s)?.let { r = it } }; return r!! }
        fun pod2p(f: ByteArray): ByteArray { var r: ByteArray? = null; BleFraming.segment(f, 23, seqB).also { seqB += it.size }.forEach { s -> toPhone.feed(s)?.let { r = it } }; return r!! }
        podB.readHandshake(p2pod(phoneB.writeHandshake())); phoneB.readHandshake(pod2p(podB.writeHandshake())); podB.readHandshake(p2pod(phoneB.writeHandshake()))
        expect("noise over ble handshake", podB.ready && phoneB.ready)
        val msg = ByteArray(5000) { (it % 97).toByte() }
        expect("noise over ble message", podB.decrypt(p2pod(phoneB.encrypt(msg))).contentEquals(msg))
    }

    // ---- Thermal live view pixels (shared with oiris/ui/glasses.thermal_image) ----
    val tv = (Json.decode(File(root, "tests/vectors/thermal_render.json").readText()) as Map<String, Any?>)["cases"] as List<Map<String, Any?>>
    for (c in tv) {
        val cel = (c["celsius"] as List<Any?>).map { (it as Number).toDouble() }.toDoubleArray()
        val g = (c["gray"] as List<Any?>).map { (it as Number).toInt() }
        val rgb = (c["rgb"] as List<Any?>).map { (it as Number).toInt() }
        expect("thermal gray ${c["h"]}x${c["w"]}", ThermalRender.gray(cel).toList() == g)
        expect("thermal colour ${c["h"]}x${c["w"]}", ThermalRender.rgb(cel).toList() == rgb)
        val a = ThermalRender.argb(cel, false)
        expect("thermal argb gray ${c["h"]}x${c["w"]}", a.size == g.size && a.indices.all { (a[it] and 0xFF) == g[it] && (a[it] ushr 24) == 0xFF })
    }

    // ---- Front-camera eye features (shared with oiris/features/eye.py) ----
    val ev = Json.decode(File(root, "tests/vectors/eye_android.json").readText()) as Map<String, Any?>
    for (c in ev["blinks"] as List<Map<String, Any?>>) {
        val o = (c["openness"] as List<Any?>).map { (it as Number).toDouble() }.toDoubleArray()
        val exp = (c["blinks"] as List<List<Any?>>).map { (it[0] as Number).toInt() to (it[1] as Number).toInt() }
        expect("blinks fps=${c["fps"]}", EyeFeatures.blinks(o, (c["fps"] as Number).toDouble()) == exp)
    }
    for (c in ev["pupil"] as List<Map<String, Any?>>) {
        val roi = (c["roi"] as List<Any?>).map { (it as Number).toDouble() }.toDoubleArray()
        val (d, q) = EyeFeatures.pupilDiameter(roi, (c["w"] as Number).toInt(), (c["h"] as Number).toInt())
        expect("pupil diameter ${c["diameter"]}", kotlin.math.abs(d - (c["diameter"] as Number).toDouble()) < 1e-9)
        expect("pupil quality ${c["quality"]}", kotlin.math.abs(q - (c["quality"] as Number).toDouble()) < 1e-9)
    }

    // ---- Scan-rate limit, GPS policy, mic level, timeline ----
    var now = 0L; val lim = ScanRateLimiter(clock = { now })
    val allowed = (0 until 8).count { now = it * 1000L; lim.tryStart() }
    expect("<=5 scan starts per 30 s", allowed == 5 && lim.waitMs() == 30_000L - 7_000L)
    now = 30_000L; expect("scan allowed after window", lim.tryStart())
    var burst = 0; now = 100_000L; repeat(100) { if (lim.tryStart()) burst++ }
    expect("burst capped", burst == 5)
    expect("gps ok", GpsPolicy.classify(38.25, -85.76, 8f, 1_000).fix == "gps")
    expect("gps coarse", GpsPolicy.classify(38.25, -85.76, 60f, 1_000).fix == "gps_coarse")
    expect("gps stale -> no_fix", GpsPolicy.classify(38.25, -85.76, 8f, 600_000).let { it.fix == "no_fix" && it.lat == null })
    expect("gps inaccurate -> no_fix", GpsPolicy.classify(38.25, -85.76, 500f, 1_000).fix == "no_fix")
    expect("gps none -> no_fix", GpsPolicy.classify(null, null, null, null).fix == "no_fix")
    expect("mic silence", MicLevel.dbfs(ShortArray(256)) == -120.0)
    expect("mic full scale ~0 dBFS", kotlin.math.abs(MicLevel.dbfs(ShortArray(256) { if (it % 2 == 0) 32767 else -32768 })) < 0.01)
    val sw = listOf(Sweep("a", "home", 10.0, 20.0, "0", "clear"), Sweep("b", "home", 30.0, 40.0, "2", "signatures"), Sweep("c", "shop", 50.0, 60.0, "1", "signatures"))
    expect("timeline newest first", Timeline.ordered(sw).map { it.id } == listOf("c", "b", "a"))
    expect("timeline new since review", Timeline.newSince(sw, 35.0).map { it.id } == listOf("c", "b"))

    println("core checks: $passed passed, $failures failed")
    if (failures > 0) kotlin.system.exitProcess(1)
}

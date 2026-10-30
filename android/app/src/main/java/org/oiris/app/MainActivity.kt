package org.oiris.app

import android.Manifest
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.KeyEvent
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.fragment.app.FragmentActivity
import org.oiris.core.Json
import org.oiris.core.Prim
import org.oiris.core.SecureChannel
import java.util.UUID
import java.util.concurrent.Executors

/** Screen zones follow the design bot's C6 map: P1 status strip, P2 alert panel,
 *  P3 live/thermal view (grayscale default, colour toggle), P4 voice controls, P5 tabs (map,
 *  timeline/review, face match). Threat level is shown by shape + word; colour is only a secondary cue. */
class MainActivity : FragmentActivity() {
    private lateinit var vocab: Vocabulary
    private lateinit var vault: KeyVault
    private var store: SightingStore? = null
    private lateinit var status: TextView
    private lateinit var alert: TextView
    private lateinit var thermal: ThermalView
    private lateinit var nodeInfo: TextView
    private lateinit var micBtn: Button
    private val panic = Panic { lock() }
    private lateinit var alerts: AlertUi
    private lateinit var location: LocationSource
    private var glint: GlintCamera? = null
    private var eye: FrontEyeCamera? = null
    private var mic: MicMonitor? = null
    private var node: FallbackNode? = null
    private var ble: BleGattTransport? = null
    private val io = Executors.newSingleThreadExecutor()
    @Volatile private var polling = false
    private var lastSighting = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        vocab = Vocabulary.load(this)
        vault = KeyVault(this)
        alerts = AlertUi(this)
        location = LocationSource(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 48, 32, 32) }
        status = TextView(this).apply { text = "P1 · Locked · build ${BuildConfig.COMMIT}"; textSize = 14f }
        alert = TextView(this).apply { text = "P2 · No signatures"; textSize = 20f }
        thermal = ThermalView(this)
        val thermalNote = TextView(this).apply { text = "P3 · Thermal · ${getString(R.string.not_medical)}"; setTextColor(Color.GRAY) }
        val thermalToggle = Button(this).apply { text = getString(R.string.thermal_to_colour); minHeight = 144
            setOnClickListener { thermal.colour = !thermal.colour
                text = getString(if (thermal.colour) R.string.thermal_to_gray else R.string.thermal_to_colour) } }
        val voice = TextView(this).apply { text = "P4 · Voice: offline tiers (FYI haptic, Attention, Confirmed)" }
        val tabs = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fun tab(label: String, go: () -> Unit) = Button(this).apply { text = label; minHeight = 144; setOnClickListener { go() } }
            .also { tabs.addView(it, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)) }
        tab(getString(R.string.tab_map)) { startActivity(Intent(this, MapActivity::class.java)) }
        tab(getString(R.string.tab_timeline)) { startActivity(Intent(this, TimelineActivity::class.java)) }
        tab(getString(R.string.tab_enroll)) { startActivity(Intent(this, EnrollmentActivity::class.java)) }
        val attribution = TextView(this).apply { text = "P5 · ${getString(R.string.osm_attribution)}"; setTextColor(Color.GRAY) }
        val podBtn = Button(this).apply { text = getString(R.string.pod_connect); minHeight = 144; setOnClickListener { connectPod() } }
        val nodeBtn = Button(this).apply { text = getString(R.string.node_glint); minHeight = 144; setOnClickListener { startFallbackNode() } }
        val eyeBtn = Button(this).apply { text = getString(R.string.node_eye); minHeight = 144; setOnClickListener { startEyeCamera() } }
        micBtn = Button(this).apply { text = getString(R.string.mic_off); minHeight = 144; setOnClickListener { toggleMic() } }
        nodeInfo = TextView(this).apply { text = getString(R.string.node_idle); setTextColor(Color.LTGRAY) }
        val notice = TextView(this).apply { text = getString(R.string.research_notice); setTextColor(Color.GRAY) }
        listOf(status, alert, thermal, thermalNote, thermalToggle, voice, tabs, attribution, podBtn, nodeBtn, eyeBtn, micBtn, nodeInfo, notice)
            .forEach(root::addView)
        setContentView(ScrollView(this).apply { addView(root) })
        unlock()
    }

    private fun unlock() {
        Gate(this, vault) { key ->
            store = SightingStore(this, key).also { SessionKeys.store = it }
            status.text = "P1 · Unlocked"
            if (!location.permitted()) requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), 11)
        }.prompt()
    }

    /** P2 alert: shape + "signal" word from the C7 tokens, colour as a redundant cue, level haptic. */
    fun show(result: Fusion.Result) {
        val v = alerts.forEngine(result.level?.name?.lowercase())
        if (v == null) { alert.text = "P2 · No signatures"; alert.setTextColor(Color.LTGRAY); return }
        alert.text = vocab.check("P2 · " + v.line("families: ${result.active.joinToString()}") +
            if (result.advisory) " · advisory (fallback node)" else "")
        alert.setTextColor(v.argb.toInt())
        alerts.haptic(v)
        recordSighting(result)
    }

    /** M-05: one sighting row per alert (at most every 30 s) with a fresh GPS fix or "no_fix". */
    private fun recordSighting(result: Fusion.Result) {
        val s = store ?: return
        val now = System.currentTimeMillis()
        if (now - lastSighting < 30_000) return
        lastSighting = now
        val code = (result.level?.name ?: "FYI") + ":" + result.active.sorted().joinToString("+") + if (result.advisory) ":advisory" else ""
        location.current { fix -> runOnUiThread { store?.takeIf { it === s }?.add(UUID.randomUUID().toString(), code, fix.lat, fix.lon, fix.fix) } }
    }

    private fun startFallbackNode() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), 7); return
        }
        eye?.stop(); eye = null
        if (glint != null) return
        val n = node ?: FallbackNode(this) { scores -> runOnUiThread { show(Fusion.fuse(scores, fallbackNode = true)) } }.also { node = it }
        glint = GlintCamera(this, n).also { it.start(this) }
        n.startBle()
        nodeInfo.text = getString(R.string.node_glint_on)
    }

    /** Front camera: blink + pupil features, report-only (shown here, never fused). */
    private fun startEyeCamera() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), 8); return
        }
        glint?.stop(); glint = null
        if (eye != null) return
        eye = FrontEyeCamera(this) { st -> runOnUiThread {
            nodeInfo.text = "Eye (report-only): pupil %.1f px, quality %.2f, blinks/min %s, %.0f fps"
                .format(st.pupilPx, st.quality, st.blinksPerMin?.let { "%.1f".format(it) } ?: "measuring", st.fps)
        } }.also { it.start(this) }
    }

    private fun toggleMic() {
        val m = mic
        if (m != null && m.active) { m.stop(); mic = null; micBtn.text = getString(R.string.mic_off); return }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 9); return
        }
        val mm = MicMonitor(this) { db -> runOnUiThread { micBtn.text = getString(R.string.mic_on) + " · %.0f dBFS".format(db) } }
        if (mm.start()) { mic = mm; micBtn.text = getString(R.string.mic_on) }
    }

    /** Pair (pod fingerprint typed from the pod's screen/QR text) and connect over BLE GATT. */
    private fun connectPod() {
        val s = store ?: return
        var p = s.pairing()
        if (p != null && System.currentTimeMillis() / 1000.0 - p.created >= 90 * 86400) p = null   // D-22: rotate after 90 days
        val pairing = p ?: s.newStatic()
        val myFp = SecureChannel.fingerprint(Prim.pub(pairing.staticPriv))
        if (pairing.peerFp == null) {
            val input = EditText(this).apply { hint = getString(R.string.pod_fp_hint) }
            AlertDialog.Builder(this).setTitle(R.string.pod_pair_title)
                .setMessage(getString(R.string.pod_pair_msg, myFp)).setView(input)
                .setPositiveButton(R.string.pod_pair_ok) { _, _ ->
                    runCatching { s.setPeer(input.text.toString().trim().lowercase()) }
                        .onSuccess { connectPod() }.onFailure { nodeInfo.text = it.message }
                }.setNegativeButton(android.R.string.cancel, null).show()
            return
        }
        val btPerms = if (android.os.Build.VERSION.SDK_INT >= 31) arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
            else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)        // API 29-30: BLE scan needs location permission
        if (btPerms.any { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }) { requestPermissions(btPerms, 10); return }
        nodeInfo.text = getString(R.string.pod_connecting)
        io.execute {
            val t = BleGattTransport(this, node?.limiter ?: org.oiris.core.ScanRateLimiter())
            val ok = runCatching { t.connect() && PodLink(t, pairing.staticPriv, pairing.peerFp).also { it.handshake() }.let { PodLink.current = it; true } }
                .getOrElse { false }
            runOnUiThread { nodeInfo.text = if (ok) getString(R.string.pod_connected) else "Pod: ${t.state}" }
            if (ok) { ble = t; pollThermal() }
        }
    }

    private fun pollThermal() {
        polling = true
        thermal.placeholder = getString(R.string.thermal_waiting)
        io.execute {
            while (polling) {
                val link = PodLink.current ?: break
                runCatching {
                    @Suppress("UNCHECKED_CAST")
                    val r = Json.decode(link.request("{\"op\":\"thermal\"}")) as Map<String, Any?>
                    if (r["ok"] == true && r["w"] != null) {
                        val cel = (r["celsius"] as List<Any?>).map { (it as Number).toDouble() }.toDoubleArray()
                        thermal.setFrame(cel, (r["w"] as Number).toInt(), (r["h"] as Number).toInt())
                    }
                }
                Thread.sleep(500)
            }
        }
    }

    private fun lock() {
        polling = false
        PodLink.current = null; ble?.close(); ble = null
        store = null
        SessionKeys.store = null
        glint?.stop(); glint = null
        eye?.stop(); eye = null
        mic?.stop(); mic = null; micBtn.text = getString(R.string.mic_off)
        status.text = "P1 · Locked"
        alert.text = "P2 · —"
        unlock()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) panic.volumeDown()
        return super.onKeyDown(keyCode, event)
    }

    override fun onStop() {
        super.onStop()
        lock()      // auto-lock when backgrounded (spec: 60 s; immediate is stricter)
    }
}

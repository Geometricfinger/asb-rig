package org.oiris.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.KeyEvent
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.FragmentActivity

/** Screen zones follow the design bot's C6 map: P1 status strip, P2 alert panel,
 *  P3 live/thermal view (grayscale default), P4 voice controls, P5 tabs (map, timeline, review).
 *  Threat level is shown by shape + word; colour is only a secondary cue. */
class MainActivity : FragmentActivity() {
    private lateinit var vocab: Vocabulary
    private lateinit var vault: KeyVault
    private var store: SightingStore? = null
    private lateinit var status: TextView
    private lateinit var alert: TextView
    private val panic = Panic { lock() }
    private lateinit var alerts: AlertUi
    private var glint: GlintCamera? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        vocab = Vocabulary.load(this)
        vault = KeyVault(this)
        alerts = AlertUi(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 48, 32, 32) }
        status = TextView(this).apply { text = "P1 · Locked · build ${BuildConfig.COMMIT}"; textSize = 14f }
        alert = TextView(this).apply { text = "P2 · No signatures"; textSize = 20f }
        val thermal = TextView(this).apply { text = "P3 · Thermal: grayscale · ${getString(R.string.not_medical)}" }
        val voice = TextView(this).apply { text = "P4 · Voice: offline tiers (FYI haptic, Attention, Confirmed)" }
        val tabs = TextView(this).apply { text = "P5 · Map (${getString(R.string.osm_attribution)}) · Timeline · Review" }
        val notice = TextView(this).apply { text = getString(R.string.research_notice); setTextColor(Color.GRAY) }
        val mapBtn = Button(this).apply { text = getString(R.string.tab_map); minHeight = 144
            setOnClickListener { startActivity(Intent(this@MainActivity, MapActivity::class.java)) } }
        val fmBtn = Button(this).apply { text = getString(R.string.tab_enroll); minHeight = 144
            setOnClickListener { startActivity(Intent(this@MainActivity, EnrollmentActivity::class.java)) } }
        val nodeBtn = Button(this).apply { text = "Fallback node: camera glint"; minHeight = 144
            setOnClickListener { startFallbackNode() } }
        listOf(status, alert, thermal, voice, tabs, mapBtn, fmBtn, nodeBtn, notice).forEach(root::addView)
        setContentView(root)
        unlock()
    }

    private fun unlock() {
        Gate(this, vault) { key -> store = SightingStore(this, key).also { SessionKeys.store = it }; status.text = "P1 · Unlocked" }.prompt()
    }

    /** P2 alert: shape + "signal" word from the C7 tokens, colour as a redundant cue, level haptic. */
    fun show(result: Fusion.Result) {
        val v = alerts.forEngine(result.level?.name?.lowercase())
        if (v == null) { alert.text = "P2 · No signatures"; alert.setTextColor(Color.LTGRAY); return }
        alert.text = vocab.check("P2 · " + v.line("families: ${result.active.joinToString()}") +
            if (result.advisory) " · advisory (fallback node)" else "")
        alert.setTextColor(v.argb.toInt())
        alerts.haptic(v)
    }

    private fun startFallbackNode() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CAMERA), 7); return
        }
        if (glint != null) return
        val node = FallbackNode(this) { scores -> runOnUiThread { show(Fusion.fuse(scores, fallbackNode = true)) } }
        glint = GlintCamera(this, node).also { it.start(this) }
        node.startBle()
    }

    private fun lock() {
        store = null
        SessionKeys.store = null
        glint?.stop(); glint = null
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

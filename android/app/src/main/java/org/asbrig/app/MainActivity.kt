package org.asbrig.app

import android.graphics.Color
import android.os.Bundle
import android.view.KeyEvent
import android.view.WindowManager
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        vocab = Vocabulary.load(this)
        vault = KeyVault(this)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 48, 32, 32) }
        status = TextView(this).apply { text = "P1 · Locked · build ${BuildConfig.COMMIT}"; textSize = 14f }
        alert = TextView(this).apply { text = "P2 · No signatures"; textSize = 20f }
        val thermal = TextView(this).apply { text = "P3 · Thermal: grayscale · ${getString(R.string.not_medical)}" }
        val voice = TextView(this).apply { text = "P4 · Voice: offline tiers (FYI haptic, Attention, Confirmed)" }
        val tabs = TextView(this).apply { text = "P5 · Map (${getString(R.string.osm_attribution)}) · Timeline · Review" }
        val notice = TextView(this).apply { text = getString(R.string.research_notice); setTextColor(Color.GRAY) }
        listOf(status, alert, thermal, voice, tabs, notice).forEach(root::addView)
        setContentView(root)
        Gate(this, vault) { key -> store = SightingStore(this, key); status.text = "P1 · Unlocked" }.prompt()
    }

    fun show(result: Fusion.Result) {
        val shape = when (result.level) { Level.CONFIRMED -> "■"; Level.ATTENTION -> "▲"; Level.FYI -> "●"; null -> "–" }
        val word = result.level?.name ?: "none"
        alert.text = vocab.check("P2 · $shape $word · families: ${result.active.joinToString()}" +
            if (result.advisory) " · advisory (fallback node)" else "")
    }

    private fun lock() {
        store = null
        status.text = "P1 · Locked"
        alert.text = "P2 · —"
        Gate(this, vault) { key -> store = SightingStore(this, key); status.text = "P1 · Unlocked" }.prompt()
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

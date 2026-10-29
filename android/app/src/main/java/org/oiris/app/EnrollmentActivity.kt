package org.oiris.app

import android.os.Bundle
import android.text.InputType
import android.view.WindowManager
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import org.oiris.core.Angle
import org.oiris.core.EnrollmentFlow
import java.util.concurrent.Executors

/** M-16 guided enrollment screen (spec 7.3). Off by default: locked unless the pod reports M-16 on;
 *  unlocking shows the full warning and needs the typed phrase. Five-angle checklist, one prompt at a
 *  time, plain rejection reasons from the pod's quality checks, "Template complete for <name>".
 *  No enrollment limit. Frames go only to the paired pod over the encrypted link, then are zeroed. */
class EnrollmentActivity : FragmentActivity() {
    private val io = Executors.newSingleThreadExecutor()
    private val camExec = Executors.newSingleThreadExecutor()
    private var flow: EnrollmentFlow? = null
    @Volatile private var latest: Triple<Int, Int, ByteArray>? = null
    private lateinit var status: TextView
    private lateinit var body: LinearLayout
    private val checks = mutableMapOf<Angle, CheckBox>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 48, 32, 32) }
        status = TextView(this).apply { textSize = 18f }
        body.addView(TextView(this).apply { text = getString(R.string.fm_title); textSize = 22f })
        body.addView(status)
        setContentView(ScrollView(this).apply { addView(body) })
        val link = PodLink.current
        if (link == null) { status.text = getString(R.string.pod_not_connected); return }
        val f = EnrollmentFlow { req -> link.request(req) }.also { flow = it }
        bg({ f.open() }) { stage -> if (stage == EnrollmentFlow.Stage.LOCKED) showLocked() else showReady() }
    }

    private fun <T> bg(work: () -> T, ui: (T) -> Unit) = io.execute {
        val r = runCatching(work)
        runOnUiThread { r.fold(ui) { e -> status.text = e.message ?: "error" } }
    }

    private fun clearBelowStatus() { while (body.childCount > 2) body.removeViewAt(2) }

    private fun showLocked() {
        clearBelowStatus()
        status.text = getString(R.string.fm_locked)
        body.addView(Button(this).apply { text = getString(R.string.fm_read_warning); minHeight = 144
            setOnClickListener { bg({ flow!!.showWarning() }) { showWarning() } } })
    }

    private fun showWarning() {
        clearBelowStatus()
        status.text = getString(R.string.fm_warning_heading)
        body.addView(TextView(this).apply { text = flow!!.warningText; setPadding(0, 16, 0, 16) })
        val typed = EditText(this).apply { hint = getString(R.string.fm_type_phrase); inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS }
        body.addView(typed)
        body.addView(Button(this).apply { text = getString(R.string.fm_turn_on); minHeight = 144
            setOnClickListener { val t = typed.text.toString(); bg({ flow!!.optIn(t) }) { ok -> if (ok) showReady() else status.text = flow!!.lastMessage } } })
    }

    private fun showReady() {
        clearBelowStatus()
        status.text = getString(R.string.fm_ready)
        val name = EditText(this).apply { hint = getString(R.string.fm_name_hint) }
        val consent = EditText(this).apply { hint = getString(R.string.fm_consent_hint) }
        val guardian = CheckBox(this).apply { text = getString(R.string.fm_guardian) }
        listOf(name, consent, guardian).forEach(body::addView)
        body.addView(Button(this).apply { text = getString(R.string.fm_start_person); minHeight = 144
            setOnClickListener {
                val n = name.text.toString().trim(); val c = consent.text.toString().trim().ifEmpty { null }
                if (n.isEmpty()) { status.text = getString(R.string.fm_name_hint); return@setOnClickListener }
                bg({ flow!!.startPerson(n, c, guardian.isChecked) }) { showCapture() }
            } })
    }

    private fun showCapture() {
        clearBelowStatus()
        val f = flow!!
        status.text = f.lastMessage
        val preview = PreviewView(this)
        body.addView(preview, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 720))
        checks.clear()
        Angle.values().forEach { a -> checks[a] = CheckBox(this).apply { text = a.wire; isEnabled = false }.also(body::addView) }
        body.addView(Button(this).apply { text = getString(R.string.fm_capture); minHeight = 144
            setOnClickListener {
                val shot = latest ?: run { status.text = getString(R.string.fm_no_frame); return@setOnClickListener }
                val angle = f.nextAngle() ?: Angle.FRONT
                bg({ f.submit(angle, shot.first, shot.second, shot.third.copyOf()) }) { refresh() }
            } })
        body.addView(Button(this).apply { text = getString(R.string.fm_finish); minHeight = 144
            setOnClickListener { bg({ f.finish() }) { done -> refresh(); if (done) { stopCamera(); showReady(); status.text = f.lastMessage } } } })
        startCamera(preview)
    }

    private fun refresh() {
        val f = flow!!
        status.text = f.lastMessage
        f.checklist().forEach { (a, ok) -> checks[a]?.isChecked = ok }
    }

    private fun startCamera(pv: PreviewView) {
        val fut = ProcessCameraProvider.getInstance(this)
        fut.addListener({
            val p = fut.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(pv.surfaceProvider) }
            val analysis = ImageAnalysis.Builder().setTargetResolution(android.util.Size(480, 360))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(camExec) { img -> latest?.third?.fill(0); latest = toBgr(img); img.close() }
            p.unbindAll()
            p.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, preview, analysis)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun stopCamera() {
        ProcessCameraProvider.getInstance(this).get().unbindAll()
        latest?.third?.fill(0); latest = null
    }

    /** YUV_420_888 -> packed BGR (BT.601), the format the pod's backend expects. */
    private fun toBgr(img: ImageProxy): Triple<Int, Int, ByteArray> {
        val w = img.width; val h = img.height
        val (yp, up, vp) = img.planes.let { Triple(it[0], it[1], it[2]) }
        val out = ByteArray(w * h * 3)
        for (y in 0 until h) for (x in 0 until w) {
            val yy = (yp.buffer.get(y * yp.rowStride + x * yp.pixelStride).toInt() and 0xff) - 16
            val ui = (y / 2) * up.rowStride + (x / 2) * up.pixelStride
            val u = (up.buffer.get(ui).toInt() and 0xff) - 128
            val v = (vp.buffer.get((y / 2) * vp.rowStride + (x / 2) * vp.pixelStride).toInt() and 0xff) - 128
            val c = 1.164f * yy
            val o = (y * w + x) * 3
            out[o] = (c + 2.018f * u).toInt().coerceIn(0, 255).toByte()
            out[o + 1] = (c - 0.391f * u - 0.813f * v).toInt().coerceIn(0, 255).toByte()
            out[o + 2] = (c + 1.596f * v).toInt().coerceIn(0, 255).toByte()
        }
        return Triple(w, h, out)
    }

    override fun onStop() {
        super.onStop()
        runCatching { stopCamera() }
        flow?.let { f -> io.execute { runCatching { f.end() } } }   // clears every capture buffer on the pod
    }

    override fun onDestroy() { io.shutdown(); camExec.shutdown(); super.onDestroy() }
}

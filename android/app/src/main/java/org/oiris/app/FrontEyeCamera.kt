package org.oiris.app

import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import org.oiris.core.EyeFeatures
import java.util.concurrent.Executors

/** M-13 fallback node, front camera: blink and pupil features (ported from oiris/features/eye.py,
 *  JVM-checked against shared vectors). The eye must be framed in the centre guide box. Frames
 *  are analysed in RAM and dropped; only the numbers below leave this class. REPORT-ONLY: these
 *  features are shown to the operator and never fed to fusion, so the node still cannot alert alone. */
class FrontEyeCamera(private val owner: LifecycleOwner, private val onStats: (Stats) -> Unit) {
    data class Stats(val pupilPx: Double, val quality: Double, val blinksPerMin: Double?, val fps: Double)

    private val exec = Executors.newSingleThreadExecutor()
    private var camera: Camera? = null
    private val open = ArrayDeque<Double>(); private val times = ArrayDeque<Long>()
    private var openMedian = 0.0

    fun start(ctx: android.content.Context) {
        val f = ProcessCameraProvider.getInstance(ctx)
        f.addListener({
            val provider = f.get()
            val analysis = ImageAnalysis.Builder().setTargetResolution(android.util.Size(640, 480))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(exec, ::analyse)
            provider.unbindAll()
            camera = provider.bindToLifecycle(owner, CameraSelector.DEFAULT_FRONT_CAMERA, analysis)
        }, ContextCompat.getMainExecutor(ctx))
    }

    /** Centre ROI (guide box: middle 30% x 20% of the frame), Y plane, subsampled to 48x32. */
    private fun roi(img: ImageProxy, gw: Int = 48, gh: Int = 32): DoubleArray {
        val p = img.planes[0]; val buf = p.buffer; val rs = p.rowStride; val ps = p.pixelStride
        val x0 = img.width * 35 / 100; val y0 = img.height * 40 / 100
        val rw = img.width * 30 / 100; val rh = img.height * 20 / 100
        return DoubleArray(gw * gh) { i ->
            val sx = x0 + (i % gw) * rw / gw; val sy = y0 + (i / gw) * rh / gh
            (buf.get(sy * rs + sx * ps).toInt() and 0xff).toDouble()
        }
    }

    private fun analyse(img: ImageProxy) {
        try {
            val r = roi(img)
            val (d, q) = EyeFeatures.pupilDiameter(r, 48, 32)
            val med = r.sorted()[r.size / 2]
            val dark = r.count { it < med * 0.5 }.toDouble() / r.size
            val now = System.currentTimeMillis()
            if (open.size < 30) openMedian = (openMedian * open.size + dark) / (open.size + 1)   // first second = open-eye calibration
            open.addLast(EyeFeatures.openness(dark, openMedian)); times.addLast(now)
            while (times.isNotEmpty() && now - times.first() > 60_000) { times.removeFirst(); open.removeFirst() }
            val spanS = (times.last() - times.first()) / 1000.0
            val fps = if (spanS > 0) (times.size - 1) / spanS else 0.0
            val rate = if (spanS >= 10 && fps > 5) EyeFeatures.blinks(open.toDoubleArray(), fps).size * 60.0 / spanS else null
            onStats(Stats(d, q, rate, fps))
        } finally { img.close() }
    }

    fun stop() { exec.shutdown(); open.clear(); times.clear() }
}

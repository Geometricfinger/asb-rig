package org.oiris.app

import android.annotation.SuppressLint
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.util.concurrent.Executors

/** CameraX glint capture for the fallback node (M-13): the torch is toggled on alternate analysed
 *  frames; each on/off luminance pair goes to FallbackNode.glintScore (same rule as
 *  oiris/features/optical.py). Frames are analysed in RAM and dropped; nothing is stored. */
class GlintCamera(private val owner: LifecycleOwner, private val node: FallbackNode) {
    private val exec = Executors.newSingleThreadExecutor()
    private var camera: Camera? = null
    private var torchOn = false
    private var lastOff: IntArray? = null
    @Volatile var pairs = 0; private set

    fun start(ctx: android.content.Context) {
        val f = ProcessCameraProvider.getInstance(ctx)
        f.addListener({
            val provider = f.get()
            val analysis = ImageAnalysis.Builder()
                .setTargetResolution(android.util.Size(320, 240))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(exec, ::analyse)
            provider.unbindAll()
            camera = provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, analysis)
        }, ContextCompat.getMainExecutor(ctx))
    }

    @SuppressLint("UnsafeOptInUsageError")
    private fun analyse(img: ImageProxy) {
        try {
            val luma = lumaGrid(img)
            if (torchOn) {
                lastOff?.let { off -> node.lastGlint = node.glintScore(luma, off); pairs++ }
            } else lastOff = luma
            torchOn = !torchOn
            camera?.cameraControl?.enableTorch(torchOn)
        } finally { img.close() }
    }

    /** Y plane subsampled to a fixed 80x60 grid so on/off pairs line up regardless of stride. */
    private fun lumaGrid(img: ImageProxy, gw: Int = 80, gh: Int = 60): IntArray {
        val p = img.planes[0]; val buf = p.buffer; val rs = p.rowStride; val ps = p.pixelStride
        val out = IntArray(gw * gh)
        for (y in 0 until gh) for (x in 0 until gw) {
            val sx = x * img.width / gw; val sy = y * img.height / gh
            out[y * gw + x] = buf.get(sy * rs + sx * ps).toInt() and 0xff
        }
        return out
    }

    fun stop() { camera?.cameraControl?.enableTorch(false); exec.shutdown() }
}

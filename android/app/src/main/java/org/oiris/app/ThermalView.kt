package org.oiris.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.view.View
import org.oiris.core.ThermalRender

/** P3 live thermal view: draws the latest thermal frame (degrees C grid from the pod's thermal
 *  camera, via the encrypted link) as a nearest-neighbour scaled bitmap. Grayscale by default,
 *  colour overlay on toggle (same ramp as the glasses G3 window). Not a medical measurement. */
class ThermalView(ctx: Context) : View(ctx) {
    private var bmp: Bitmap? = null
    private val px = Paint().apply { isFilterBitmap = false }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.LTGRAY; textSize = 36f }
    private var last: Triple<DoubleArray, Int, Int>? = null
    var colour = false
        set(v) { field = v; last?.let { (c, w, h) -> render(c, w, h) } }
    var placeholder = "No thermal source: pod not connected"
    var frames = 0L; private set

    /** Thread-safe: may be called from the link thread. */
    fun setFrame(celsius: DoubleArray, w: Int, h: Int) {
        require(celsius.size == w * h && w > 0 && h > 0) { "frame size" }
        post { render(celsius, w, h) }
    }

    private fun render(celsius: DoubleArray, w: Int, h: Int) {
        val b = bmp?.takeIf { it.width == w && it.height == h } ?: Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888).also { bmp = it }
        b.setPixels(ThermalRender.argb(celsius, colour), 0, w, 0, 0, w, h)
        last = Triple(celsius, w, h); frames++
        invalidate()
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        setMeasuredDimension(w, w * 3 / 4)          // 4:3 like the 32x24 MLX90640 grid
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawColor(Color.BLACK)
        val b = bmp
        if (b == null) { canvas.drawText(placeholder, 24f, height / 2f, text); return }
        canvas.drawBitmap(b, null, Rect(0, 0, width, height), px)
        canvas.drawText(if (colour) "Colour overlay" else "Grayscale", 16f, 44f, text)
    }
}

package org.oiris.app

import android.content.Context
import android.os.VibrationEffect
import android.os.Vibrator
import org.oiris.core.AlertVisual
import org.oiris.core.AlertVisuals

/** Alert visuals per C7 tokens (assets/design_tokens.json): shape + "signal" word first, colour
 *  as a redundant cue, distinct haptic per level, never flashing, never "robot". */
class AlertUi(private val ctx: Context) {
    val visuals: Map<String, AlertVisual> =
        AlertVisuals.fromTokens(ctx.assets.open("design_tokens.json").bufferedReader().use { it.readText() })

    fun forEngine(level: String?): AlertVisual? = AlertVisuals.forEngine(level)?.let { visuals[it] }

    fun haptic(v: AlertVisual) {
        val vib = ctx.getSystemService(Vibrator::class.java) ?: return
        if (vib.hasVibrator()) vib.vibrate(VibrationEffect.createWaveform(v.haptic, -1))
    }
}

package org.asbrig.app

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import android.os.SystemClock

/** M-06: tiered voice output with whitelisted phrases; offline voices only (voices that
 *  need the network are rejected). Confirmed tier requires an operator confirmation and barges in. */
class VoiceOut(ctx: Context, private val vocab: Vocabulary, private val haptic: () -> Unit) : TextToSpeech.OnInitListener {
    private val tts = TextToSpeech(ctx, this)
    private var lastAttention = 0L
    var ready = false; private set

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        val offline: Voice? = tts.voices?.firstOrNull { !it.isNetworkConnectionRequired && it.locale.language == "en" }
        if (offline != null) { tts.voice = offline; ready = true }
    }

    fun announce(level: Level, key: String, slots: Map<String, String> = emptyMap(), operatorConfirmed: Boolean = false) {
        when (level) {
            Level.FYI -> haptic()
            Level.ATTENTION -> {
                val now = SystemClock.elapsedRealtime()
                if (now - lastAttention < 10_000 || !ready) return
                lastAttention = now
                tts.speak(vocab.render(key, slots), TextToSpeech.QUEUE_ADD, null, key)
            }
            Level.CONFIRMED -> {
                require(operatorConfirmed) { "confirmed tier needs operator confirmation" }
                if (ready) tts.speak(vocab.render(key, slots), TextToSpeech.QUEUE_FLUSH, null, key)   // barge-in
            }
        }
    }

    fun shutdown() = tts.shutdown()
}

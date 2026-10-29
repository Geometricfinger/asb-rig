package org.oiris.app

import android.os.SystemClock

/** Phone panic: 5x volume-down within 3 s = soft panic only (clear screens, drop keys,
 *  require unlock). Hard erase is only on the pod's double-step gesture or 10 failed unlocks. */
class Panic(private val onSoft: () -> Unit) {
    private val presses = ArrayDeque<Long>()

    fun volumeDown() {
        val now = SystemClock.elapsedRealtime()
        presses.addLast(now)
        while (presses.isNotEmpty() && now - presses.first() > 3000) presses.removeFirst()
        if (presses.size >= 5) { presses.clear(); onSoft() }
    }
}

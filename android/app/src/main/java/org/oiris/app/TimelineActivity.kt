package org.oiris.app

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.fragment.app.FragmentActivity
import org.oiris.core.Timeline
import java.text.DateFormat
import java.util.Date

/** M-14 sweep timeline + review (P5 tab): sweeps newest first, what is new since the last
 *  review highlighted, then sightings with their review state. Reads the encrypted store of the
 *  unlocked session only; nothing is shown while locked. Signatures, never identities. */
class TimelineActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        render()
    }

    private fun fmt(t: Double) = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date((t * 1000).toLong()))

    private fun render() {
        val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(32, 48, 32, 32) }
        fun head(s: String) = list.addView(TextView(this).apply { text = s; textSize = 20f; setTypeface(typeface, Typeface.BOLD); setPadding(0, 24, 0, 8) })
        val store = SessionKeys.store
        if (store == null) {
            list.addView(TextView(this).apply { text = getString(R.string.timeline_locked) })
        } else {
            val last = store.lastReviewed()
            val sweeps = Timeline.ordered(store.sweeps())
            val fresh = Timeline.newSince(sweeps, last).map { it.id }.toSet()
            head(getString(R.string.timeline_sweeps) + if (fresh.isNotEmpty()) " · ${fresh.size} new" else "")
            if (sweeps.isEmpty()) list.addView(TextView(this).apply { text = getString(R.string.timeline_empty) })
            sweeps.forEach { s ->
                list.addView(TextView(this).apply {
                    text = (if (s.id in fresh) "● NEW  " else "○ ") + "${fmt(s.tStart)} · " + Timeline.line(s)
                    setTextColor(if (s.id in fresh) Color.WHITE else Color.LTGRAY); setPadding(0, 8, 0, 8)
                })
            }
            head(getString(R.string.timeline_sightings))
            val rows = store.sightings()
            if (rows.isEmpty()) list.addView(TextView(this).apply { text = getString(R.string.timeline_no_sightings) })
            rows.forEach { r ->
                list.addView(TextView(this).apply {
                    text = (if (r.t > last) "● " else "○ ") + "${fmt(r.t)} · ${r.code} · ${r.verdict}" + if (r.fix == "no_fix") " · no GPS fix" else ""
                    setPadding(0, 8, 0, 8)
                })
            }
            list.addView(Button(this).apply {
                text = getString(R.string.timeline_mark_reviewed); minHeight = 144
                setOnClickListener { store.markReviewed(); render() }
            })
        }
        setContentView(ScrollView(this).apply { addView(list) })
    }
}

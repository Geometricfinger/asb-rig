package org.oiris.app

import android.content.Context
import org.json.JSONObject

/** Mirror of oiris/guard/vocabulary.py, loaded from the shared schema/vocabulary.json asset. */
class Vocabulary(json: String) {
    private val banned: Regex
    private val templates: Map<String, String>
    private val slots: Map<String, Set<String>>

    init {
        val o = JSONObject(json)
        val pats = o.getJSONArray("banned_patterns")
        banned = Regex("\\b(" + (0 until pats.length()).joinToString("|") { pats.getString(it) } + ")\\b", RegexOption.IGNORE_CASE)
        val t = o.getJSONObject("phrase_templates")
        templates = t.keys().asSequence().associateWith { t.getString(it) }
        val s = o.getJSONObject("slot_values")
        slots = s.keys().asSequence().associateWith { k ->
            val a = s.getJSONArray(k); (0 until a.length()).map { a.getString(it) }.toSet()
        }
    }

    fun check(text: String): String {
        require(!banned.containsMatchIn(text)) { "banned wording in output" }
        return text
    }

    /** Only whitelisted templates with whitelisted slot values can be rendered. */
    fun render(key: String, values: Map<String, String> = emptyMap()): String {
        var out = templates[key] ?: error("no template $key")
        for ((k, v) in values) {
            require(slots[k]?.contains(v) == true) { "slot $k not whitelisted" }
            out = out.replace("{$k}", v)
        }
        require(!out.contains('{')) { "missing slot" }
        return check(out)
    }

    companion object {
        fun load(ctx: Context) = Vocabulary(ctx.assets.open("vocabulary.json").bufferedReader().readText())
    }
}

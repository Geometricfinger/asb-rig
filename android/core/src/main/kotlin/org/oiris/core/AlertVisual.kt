package org.oiris.core

/** Alert visuals per C7 tokens (Module Map 6.1): three levels, each a distinct shape + "signal" word,
 *  colour a redundant cue only; never "robot", never an identity. Values mirror oiris/ui/design_tokens.json. */
enum class Shape { CIRCLE, TRIANGLE, DIAMOND }

data class AlertVisual(val level: String, val word: String, val shape: Shape, val argb: Long, val haptic: LongArray) {
    val glyph get() = when (shape) { Shape.CIRCLE -> "●"; Shape.TRIANGLE -> "▲"; Shape.DIAMOND -> "◆" }
    fun line(detail: String) = "$glyph $word · $detail"
    override fun equals(other: Any?) = other is AlertVisual && other.level == level
    override fun hashCode() = level.hashCode()
}

object AlertVisuals {
    /** Built from the C7 tokens JSON text (packaged as an asset). */
    @Suppress("UNCHECKED_CAST")
    fun fromTokens(json: String): Map<String, AlertVisual> {
        val t = Json.decode(json) as Map<String, Any?>
        val levels = t["alert_levels"] as Map<String, Map<String, Any?>>
        val colours = (t["color"] as Map<String, Any?>)["alert"] as Map<String, String>
        require(levels.keys == setOf("low", "medium", "confirmed")) { "exactly three levels" }
        val haptics = mapOf("low" to longArrayOf(0, 40), "medium" to longArrayOf(0, 40, 80, 40), "confirmed" to longArrayOf(0, 300))
        val out = levels.mapValues { (k, v) ->
            val word = v["word"] as String
            require("signal" in word.lowercase() && "robot" !in word.lowercase()) { "level words use 'signal'" }
            AlertVisual(k, word, Shape.valueOf((v["shape"] as String).uppercase()), 0xFF000000 or colours[k]!!.removePrefix("#").toLong(16), haptics[k]!!)
        }
        require(out.values.map { it.shape }.toSet().size == 3) { "distinct shapes" }
        return out
    }

    /** Engine level names (fyi / attention / confirmed) to token levels. */
    fun forEngine(level: String?): String? = when (level) { "fyi" -> "low"; "attention" -> "medium"; "confirmed" -> "confirmed"; else -> null }
}

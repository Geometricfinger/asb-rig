package org.oiris.core

/** Minimal canonical JSON (sorted keys, no spaces) for the enrollment protocol. Pure Kotlin so the
 *  same code runs in the app and in JVM checks; matches Python json.dumps(sort_keys=True, separators=(",", ":")). */
object Json {
    fun encode(v: Any?): String = StringBuilder().also { enc(v, it) }.toString()

    private fun enc(v: Any?, sb: StringBuilder) {
        when (v) {
            null -> sb.append("null")
            is Boolean -> sb.append(v)
            is Int, is Long -> sb.append(v)
            is Double -> sb.append(if (v == Math.floor(v) && !v.isInfinite() && Math.abs(v) < 1e15) "${v.toLong()}.0" else v.toString())
            is String -> str(v, sb)
            is Map<*, *> -> { sb.append('{'); v.entries.sortedBy { it.key as String }.forEachIndexed { i, e ->
                if (i > 0) sb.append(','); str(e.key as String, sb); sb.append(':'); enc(e.value, sb) }; sb.append('}') }
            is List<*> -> { sb.append('['); v.forEachIndexed { i, x -> if (i > 0) sb.append(','); enc(x, sb) }; sb.append(']') }
            else -> throw IllegalArgumentException("unsupported ${v::class}")
        }
    }

    private fun str(s: String, sb: StringBuilder) {
        sb.append('"')
        for (c in s) when {
            c == '"' -> sb.append("\\\""); c == '\\' -> sb.append("\\\\")
            c == '\n' -> sb.append("\\n"); c == '\r' -> sb.append("\\r"); c == '\t' -> sb.append("\\t")
            c.code < 0x20 || c.code > 0x7e -> sb.append("\\u%04x".format(c.code))
            else -> sb.append(c)
        }
        sb.append('"')
    }

    fun decode(s: String): Any? = P(s).run { val v = value(); ws(); if (i != s.length) err(); v }

    private class P(val s: String) {
        var i = 0
        fun err(): Nothing = throw IllegalArgumentException("bad JSON at $i")
        fun ws() { while (i < s.length && s[i] in " \t\r\n") i++ }
        fun value(): Any? {
            ws(); if (i >= s.length) err()
            return when (s[i]) {
                '{' -> { i++; val m = LinkedHashMap<String, Any?>(); ws()
                    if (s[i] == '}') { i++; return m }
                    while (true) { ws(); val k = value() as? String ?: err(); ws(); if (s[i++] != ':') err(); m[k] = value(); ws()
                        when (s[i++]) { ',' -> continue; '}' -> return m; else -> err() } } }
                '[' -> { i++; val l = ArrayList<Any?>(); ws()
                    if (s[i] == ']') { i++; return l }
                    while (true) { l.add(value()); ws(); when (s[i++]) { ',' -> continue; ']' -> return l; else -> err() } } }
                '"' -> { i++; val sb = StringBuilder()
                    while (true) { val c = s[i++]
                        when (c) { '"' -> return sb.toString()
                            '\\' -> when (val e = s[i++]) { 'n' -> sb.append('\n'); 't' -> sb.append('\t'); 'r' -> sb.append('\r')
                                'b' -> sb.append('\b'); 'f' -> sb.append('\u000c')
                                'u' -> { sb.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4 }
                                else -> sb.append(e) }
                            else -> sb.append(c) } } }
                't' -> { i += 4; true }; 'f' -> { i += 5; false }; 'n' -> { i += 4; null }
                else -> { val st = i; while (i < s.length && s[i] in "-+.eE0123456789") i++
                    val t = s.substring(st, i); if (t.isEmpty()) err()
                    if (t.any { it in ".eE" }) t.toDouble() else t.toLong() }
            }
        }
    }
}

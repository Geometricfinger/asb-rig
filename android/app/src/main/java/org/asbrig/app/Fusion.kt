package org.asbrig.app

/** Same evidence rule as asb/fusion/stack.py: >=2 families for ATTENTION, 1 = FYI,
 *  >=2 unhealthy families suppress. A fallback node has only optical + RF and is advisory. */
enum class Health { OK, DEGRADED, FAILED }
enum class Level { FYI, ATTENTION, CONFIRMED }

data class Score(val module: String, val value: Double, val confidence: Double, val health: Health = Health.OK) {
    init { require(value in 0.0..1.0 && confidence in 0.0..1.0) { "C1: scores are in [0,1]" } }
}

object Fusion {
    val family = mapOf(
        "S_glint" to "optical", "S_nir_emit" to "optical", "S_motion" to "optical", "S_newobj" to "optical",
        "S_thermal" to "thermal", "S_rf" to "rf", "S_rf_drift" to "rf", "S_radar" to "vital", "S_live" to "vital",
        "S_eye" to "eye_liveness", "S_voice" to "voice",
    )

    data class Result(val level: Level?, val active: List<String>, val suppressed: Boolean, val advisory: Boolean)

    fun fuse(scores: List<Score>, fallbackNode: Boolean): Result {
        val unhealthy = scores.filter { it.health == Health.FAILED }.mapNotNull { family[it.module] }.toSet() -
            scores.filter { it.health != Health.FAILED }.mapNotNull { family[it.module] }.toSet()
        if (unhealthy.size >= 2) return Result(null, emptyList(), true, fallbackNode)
        val active = scores.filter { it.health != Health.FAILED && it.value >= 0.5 && it.confidence > 0 }
            .mapNotNull { family[it.module] }.distinct()
        val level = when {
            active.size >= 2 -> Level.ATTENTION
            active.size == 1 -> Level.FYI
            else -> null
        }
        return Result(level, active, false, fallbackNode)
    }
}

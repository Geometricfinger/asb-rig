package org.oiris.core

import java.util.Base64

/** M-16 guided enrollment on the phone (spec 7.3). The phone only captures and guides; the pod's
 *  EnrollmentPort (oiris/modules/face_match/remote.py) checks quality, builds and seals templates.
 *  Off by default: locked until the user reads the warning and types "I UNDERSTAND". No count limit. */
enum class Angle(val wire: String, val prompt: String) {
    FRONT("front", "Look straight at the camera"), LEFT("left", "Turn your head to the left"),
    RIGHT("right", "Turn your head to the right"), UP("up", "Tilt your head up"), DOWN("down", "Tilt your head down");
    companion object { fun of(w: String) = values().first { it.wire == w } }
}

const val CONFIRM_PHRASE = "I UNDERSTAND"

/** Request builders: canonical JSON strings carried inside SecureChannel frames. */
object EnrollmentProtocol {
    fun status() = Json.encode(mapOf("op" to "status"))
    fun warning(jurisdiction: String) = Json.encode(mapOf("op" to "warning", "jurisdiction" to jurisdiction))
    fun optIn(typed: String, modes: List<String>, warningShown: String, jurisdiction: String) =
        Json.encode(mapOf("op" to "opt_in", "typed" to typed, "modes" to modes, "warning_shown" to warningShown, "jurisdiction" to jurisdiction))
    fun startSession() = Json.encode(mapOf("op" to "start_session"))
    fun addPerson(session: String, label: String, consentId: String?, guardian: Boolean) =
        Json.encode(mapOf("op" to "add_person", "session" to session, "label" to label, "consent_id" to consentId, "guardian" to guardian))
    fun shot(person: String, angle: Angle, w: Int, h: Int, bgr: ByteArray) =
        Json.encode(mapOf("op" to "shot", "person" to person, "angle" to angle.wire, "w" to w, "h" to h,
            "fmt" to "bgr", "pixels_b64" to Base64.getEncoder().encodeToString(bgr)))
    fun finish(person: String) = Json.encode(mapOf("op" to "finish", "person" to person))
    fun endSession(session: String) = Json.encode(mapOf("op" to "end_session", "session" to session))
}

/** UI state machine for the enrollment screen, independent of Android views (tested on the JVM). */
class EnrollmentFlow(private val send: (String) -> String) {
    enum class Stage { LOCKED, WARNING, READY, CAPTURING, COMPLETE }
    var stage = Stage.LOCKED; private set
    var warningText = ""; private set
    var session: String? = null; private set
    var person: String? = null; private set
    var personLabel = ""; private set
    val accepted = mutableMapOf<Angle, Int>()
    var lastMessage = ""; private set
    var enrolledThisSession = 0; private set

    @Suppress("UNCHECKED_CAST")
    private fun call(req: String): Map<String, Any?> {
        val r = Json.decode(send(req)) as Map<String, Any?>
        if (r["ok"] != true) throw IllegalStateException(r["error"] as? String ?: "pod refused")
        return r
    }

    /** On open: unlocked only if the pod reports M-16 on and opted in. */
    fun open(): Stage {
        val r = call(EnrollmentProtocol.status())
        stage = if (r["opted_in"] == true && (r["modes"] as List<*>).contains("personal")) Stage.READY else Stage.LOCKED
        return stage
    }

    fun showWarning(jurisdiction: String = "strictest") {
        warningText = call(EnrollmentProtocol.warning(jurisdiction))["text"] as String
        stage = Stage.WARNING
    }

    /** Typed opt-in. Anything but the exact phrase keeps the module off. */
    fun optIn(typed: String, jurisdiction: String = "strictest"): Boolean {
        check(stage == Stage.WARNING) { "show the warning first" }
        if (typed.trim() != CONFIRM_PHRASE) { lastMessage = "Type \"$CONFIRM_PHRASE\" to turn face matching on"; return false }
        call(EnrollmentProtocol.optIn(typed, listOf("personal"), warningText, jurisdiction))
        stage = Stage.READY; return true
    }

    fun startPerson(label: String, consentId: String?, guardian: Boolean = false) {
        check(stage == Stage.READY || stage == Stage.COMPLETE) { "enrollment is locked" }
        val s = session ?: (call(EnrollmentProtocol.startSession())["session"] as String).also { session = it }
        person = call(EnrollmentProtocol.addPerson(s, label, consentId, guardian))["person"] as String
        personLabel = label; accepted.clear(); stage = Stage.CAPTURING
        lastMessage = nextAngle()?.prompt ?: ""
    }

    fun nextAngle(): Angle? = Angle.values().firstOrNull { (accepted[it] ?: 0) == 0 }
    fun checklist(): List<Pair<Angle, Boolean>> = Angle.values().map { it to ((accepted[it] ?: 0) > 0) }
    fun shotsAccepted() = accepted.values.sum()

    /** Submit one captured frame for the requested angle; returns whether it was accepted. */
    fun submit(angle: Angle, w: Int, h: Int, bgr: ByteArray): Boolean {
        check(stage == Stage.CAPTURING)
        if (shotsAccepted() >= 10) { lastMessage = "10 shots captured; finish this person"; return false }
        val r = call(EnrollmentProtocol.shot(person!!, angle, w, h, bgr))
        bgr.fill(0)   // the frame leaves RAM as soon as it is sent
        return if (r["accepted"] == true) {
            accepted[angle] = (accepted[angle] ?: 0) + 1
            lastMessage = nextAngle()?.prompt ?: "All angles captured. Add extras or finish."
            true
        } else { lastMessage = r["reason"] as? String ?: "shot rejected"; false }
    }

    fun finish(): Boolean {
        val r = call(EnrollmentProtocol.finish(person!!))
        return if (r["complete"] == true) {
            lastMessage = "Template complete for $personLabel"; stage = Stage.COMPLETE; enrolledThisSession++; person = null; true
        } else { lastMessage = r["message"] as? String ?: "template incomplete"; false }
    }

    fun end() {
        session?.let { call(EnrollmentProtocol.endSession(it)) }
        session = null; person = null; accepted.clear()
        stage = if (stage == Stage.LOCKED || stage == Stage.WARNING) stage else Stage.READY
    }
}

package org.oiris.app

/** In-memory handle to the unlocked store for secondary screens; cleared on lock/panic. */
object SessionKeys {
    @Volatile var store: SightingStore? = null
}

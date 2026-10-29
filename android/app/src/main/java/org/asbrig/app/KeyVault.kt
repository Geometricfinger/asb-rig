package org.asbrig.app

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.content.Context
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** M-04/M-15: a 256-bit SQLCipher key wrapped by an Android Keystore AES-256-GCM key that
 *  requires strong biometric auth per use (bound to BiometricPrompt via CryptoObject).
 *  StrongBox is requested when the device has it. Crypto-erase = delete the Keystore key. */
class KeyVault(private val ctx: Context) {
    private val alias = "asb-db-wrap"
    private val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private val prefs get() = ctx.getSharedPreferences("asb_vault", Context.MODE_PRIVATE)

    fun ensureKey() {
        if (ks.containsAlias(alias)) return
        fun spec(strongBox: Boolean) = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
            .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
            .setInvalidatedByBiometricEnrollment(true)
            .setIsStrongBoxBacked(strongBox)
            .build()
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        try { gen.init(spec(true)); gen.generateKey() } catch (e: Exception) { gen.init(spec(false)); gen.generateKey() }
    }

    private fun key(): SecretKey = ks.getKey(alias, null) as SecretKey

    /** Cipher to hand to BiometricPrompt.CryptoObject; it only works after the user authenticates. */
    fun cipherForUnlock(): Cipher {
        ensureKey()
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        val iv = prefs.getString("iv", null)
        if (iv == null) c.init(Cipher.ENCRYPT_MODE, key())
        else c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv.hexToBytes()))
        return c
    }

    /** Called with the authenticated cipher; returns the database key (creating it on first run). */
    fun dbKey(authenticated: Cipher): ByteArray {
        val wrapped = prefs.getString("wrapped", null)
        return if (wrapped == null) {
            val k = ByteArray(32).also { SecureRandom().nextBytes(it) }
            prefs.edit().putString("wrapped", authenticated.doFinal(k).toHex()).putString("iv", authenticated.iv.toHex()).apply()
            k
        } else authenticated.doFinal(wrapped.hexToBytes())
    }

    fun cryptoErase() {
        if (ks.containsAlias(alias)) ks.deleteEntry(alias)
        prefs.edit().clear().apply()
        ctx.deleteDatabase(SightingStore.NAME)
    }
}

fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }
fun String.hexToBytes() = chunked(2).map { it.toInt(16).toByte() }.toByteArray()

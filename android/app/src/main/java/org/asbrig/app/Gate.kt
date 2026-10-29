package org.asbrig.app

import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import javax.crypto.Cipher

/** M-15 app gate: BiometricPrompt BIOMETRIC_STRONG bound to a Keystore key through a
 *  CryptoObject, so bypassing the UI cannot decrypt the database. 10 failed attempts trigger
 *  crypto-erase (D-23). Note: per AndroidX rules, DEVICE_CREDENTIAL cannot be combined with a
 *  CryptoObject on API < 30, so the credential fallback is offered only on API 30+. */
class Gate(private val activity: FragmentActivity, private val vault: KeyVault, private val onUnlocked: (ByteArray) -> Unit) {
    private var failures = 0
    private val limit = 10

    fun prompt() {
        val cipher: Cipher = vault.cipherForUnlock()
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(activity.getString(R.string.gate_title))
            .setSubtitle(activity.getString(R.string.gate_subtitle))
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .setNegativeButtonText("Cancel")
            .build()
        BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                failures = 0
                val c = result.cryptoObject?.cipher ?: return
                onUnlocked(vault.dbKey(c))
            }
            override fun onAuthenticationFailed() {
                failures += 1
                if (failures >= limit) vault.cryptoErase()
            }
        }).authenticate(info, BiometricPrompt.CryptoObject(cipher))
    }
}

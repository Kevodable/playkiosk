package it.bigbenmatic.gamelauncher

import android.content.Context

/** Persists which games are visible to children and the parental PIN. */
class PrefsManager(context: Context) {
    private val prefs = context.getSharedPreferences("game_launcher_prefs", Context.MODE_PRIVATE)

    fun getSelectedPackages(): Set<String> =
        prefs.getStringSet(KEY_SELECTED, emptySet()) ?: emptySet()

    fun setSelectedPackages(packages: Set<String>) {
        prefs.edit().putStringSet(KEY_SELECTED, packages).apply()
    }

    fun getPin(): String = prefs.getString(KEY_PIN, DEFAULT_PIN) ?: DEFAULT_PIN

    fun setPin(pin: String) {
        prefs.edit().putString(KEY_PIN, pin).apply()
    }

    companion object {
        private const val KEY_SELECTED = "selected_packages"
        private const val KEY_PIN = "parent_pin"
        const val DEFAULT_PIN = "1234"
    }
}

package it.bigbenmatic.gamelauncher

import android.content.Context
import java.util.UUID

/** Generates a stable per-device identifier on first launch, used to identify this
 * monitor in the remote fleet config and in telemetry reports. */
object DeviceIdManager {
    private const val PREFS = "device_identity"
    private const val KEY_DEVICE_ID = "device_id"

    fun getDeviceId(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val existing = prefs.getString(KEY_DEVICE_ID, null)
        if (existing != null) return existing
        val generated = UUID.randomUUID().toString()
        prefs.edit().putString(KEY_DEVICE_ID, generated).apply()
        return generated
    }
}

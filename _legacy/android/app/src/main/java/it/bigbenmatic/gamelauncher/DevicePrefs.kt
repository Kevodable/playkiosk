package it.bigbenmatic.gamelauncher

import android.content.Context

/** Local cache of the last fleet config received, plus diagnostics data shown on the
 * hidden Diagnostics screen (Module 2) so an operator can read the device identity
 * and connection health without ADB. */
class DevicePrefs(context: Context) {
    private val prefs = context.getSharedPreferences("fleet_prefs", Context.MODE_PRIVATE)

    fun getCachedConfigJson(): String? = prefs.getString(KEY_CONFIG_JSON, null)

    fun setCachedConfigJson(json: String) {
        prefs.edit().putString(KEY_CONFIG_JSON, json).apply()
    }

    fun getConfigVersion(): Int = prefs.getInt(KEY_CONFIG_VERSION, -1)

    fun setConfigVersion(version: Int) {
        prefs.edit().putInt(KEY_CONFIG_VERSION, version).apply()
    }

    /** Versione del content-pack (giochi+asset) attualmente scompattato su disco. -1 = nessuno. */
    fun getContentVersion(): Int = prefs.getInt(KEY_CONTENT_VERSION, -1)

    fun setContentVersion(version: Int) {
        prefs.edit().putInt(KEY_CONTENT_VERSION, version).apply()
    }

    /** Last manifest URL the router resolved for this device (multi-tenant). Cached so the
     * device can keep loading its own client's manifest even if the router is briefly
     * unreachable. Null until the first successful router resolution. */
    fun getResolvedManifestUrl(): String? = prefs.getString(KEY_MANIFEST_URL, null)

    fun setResolvedManifestUrl(url: String) {
        prefs.edit().putString(KEY_MANIFEST_URL, url).apply()
    }

    /** Tenant identity resolved by the router (for telemetry + diagnostics). Defaults to the
     * "cliente zero" Big Ben Matic so legacy devices report a sensible value. */
    fun getClientId(): String = prefs.getString(KEY_CLIENT_ID, DEFAULT_CLIENT_ID) ?: DEFAULT_CLIENT_ID

    fun setClientId(clientId: String) {
        prefs.edit().putString(KEY_CLIENT_ID, clientId).apply()
    }

    fun getLocationId(): String? = prefs.getString(KEY_LOCATION_ID, null)

    fun setLocationId(locationId: String?) {
        prefs.edit().putString(KEY_LOCATION_ID, locationId).apply()
    }

    fun getLastTelemetrySuccessMillis(): Long = prefs.getLong(KEY_LAST_TELEMETRY_OK, 0L)

    fun setLastTelemetrySuccessMillis(millis: Long) {
        prefs.edit().putLong(KEY_LAST_TELEMETRY_OK, millis).apply()
    }

    fun getLastConnectionStatus(): String = prefs.getString(KEY_LAST_CONN_STATUS, "mai contattato") ?: "mai contattato"

    fun setLastConnectionStatus(status: String) {
        prefs.edit().putString(KEY_LAST_CONN_STATUS, status).apply()
    }

    /** Local-only lifeline Wi-Fi (never sent anywhere): the safety-net network the device
     * falls back to so it can always reach the remote config, even if the venue Wi-Fi changes. */
    fun getLifelineWifi(): WifiNetwork? {
        val ssid = prefs.getString(KEY_WIFI_SSID, null)?.takeIf { it.isNotBlank() } ?: return null
        return WifiNetwork(
            ssid = ssid,
            password = prefs.getString(KEY_WIFI_PASS, null),
            priority = 0,
            hidden = prefs.getBoolean(KEY_WIFI_HIDDEN, false),
        )
    }

    fun setLifelineWifi(ssid: String, password: String, hidden: Boolean) {
        prefs.edit()
            .putString(KEY_WIFI_SSID, ssid)
            .putString(KEY_WIFI_PASS, password)
            .putBoolean(KEY_WIFI_HIDDEN, hidden)
            .apply()
    }

    companion object {
        const val DEFAULT_CLIENT_ID = "bigbenmatic"
        private const val KEY_CONFIG_JSON = "cached_config_json"
        private const val KEY_CONFIG_VERSION = "cached_config_version"
        private const val KEY_CONTENT_VERSION = "content_pack_version"
        private const val KEY_MANIFEST_URL = "resolved_manifest_url"
        private const val KEY_CLIENT_ID = "resolved_client_id"
        private const val KEY_LOCATION_ID = "resolved_location_id"
        private const val KEY_LAST_TELEMETRY_OK = "last_telemetry_success_millis"
        private const val KEY_LAST_CONN_STATUS = "last_connection_status"
        private const val KEY_WIFI_SSID = "lifeline_wifi_ssid"
        private const val KEY_WIFI_PASS = "lifeline_wifi_pass"
        private const val KEY_WIFI_HIDDEN = "lifeline_wifi_hidden"
    }
}

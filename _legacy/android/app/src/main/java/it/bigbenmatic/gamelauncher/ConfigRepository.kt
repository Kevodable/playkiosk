package it.bigbenmatic.gamelauncher

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.net.HttpURLConnection
import java.net.URL

/**
 * URL of the static `config.json` published on GitHub Pages (Module 1). Hosted under a
 * dedicated `/launcher/` path so it never collides with the repo's existing root site.
 * Replace with the real GitHub Pages URL for this repo/account once Pages is enabled.
 */
const val FLEET_CONFIG_URL = "https://kevodable.github.io/Fun-Planet-touch/launcher/config.json"

enum class ConnectionStatus { ONLINE, OFFLINE }

/** Downloads and caches the remote fleet config (Module 1). Offline-first: the last
 * successfully parsed config survives app/process restarts and is used immediately
 * while a fresh copy is fetched in the background. */
class ConfigRepository(context: Context) {
    private val appContext = context.applicationContext
    private val devicePrefs = DevicePrefs(appContext)
    private val deviceId = DeviceIdManager.getDeviceId(appContext)

    private val _config = MutableStateFlow<ResolvedConfig?>(loadCached())
    val config: StateFlow<ResolvedConfig?> = _config

    private val _connectionStatus = MutableStateFlow(ConnectionStatus.OFFLINE)
    val connectionStatus: StateFlow<ConnectionStatus> = _connectionStatus

    private fun loadCached(): ResolvedConfig? {
        val cached = devicePrefs.getCachedConfigJson() ?: return null
        return runCatching { RemoteConfigParser.parse(cached, deviceId) }.getOrNull()
    }

    /** Fetches the device's manifest, applies it only if `configVersion` changed, and
     * persists it for offline use. Safe to call repeatedly from a polling loop.
     *
     * Multi-tenant: first resolves which manifest to load via the router (see
     * [resolveManifestUrl]); the rest of the pipeline is identical to the single-file flow. */
    fun refresh() {
        val manifestUrl = resolveManifestUrl()

        val raw = runCatching { download(manifestUrl) }.getOrNull()
        if (raw == null) {
            _connectionStatus.value = ConnectionStatus.OFFLINE
            return
        }
        _connectionStatus.value = ConnectionStatus.ONLINE

        val parsed = runCatching { RemoteConfigParser.parse(raw, deviceId) }.getOrNull()
        if (parsed == null) {
            Log.w(TAG, "Config JSON non valido, ignorato")
            return
        }

        val previousVersion = devicePrefs.getConfigVersion()
        if (parsed.configVersion == previousVersion) {
            return // nothing changed, skip re-apply
        }

        devicePrefs.setCachedConfigJson(raw)
        devicePrefs.setConfigVersion(parsed.configVersion)
        _config.value = parsed
        Log.i(TAG, "Config aggiornata: v$previousVersion -> v${parsed.configVersion}")
    }

    /**
     * Resolves which manifest URL to download for this device.
     *  - Tries the router (`fleet.json`); on success persists manifestUrl + tenant identity.
     *  - If the router is unreachable or the device isn't mapped, reuses the last resolved
     *    manifest, and as a final fallback the legacy [FLEET_CONFIG_URL] — so a device with
     *    no router entry (and every currently installed Big Ben monitor) keeps working.
     */
    private fun resolveManifestUrl(): String {
        val routerRaw = runCatching { download(FLEET_ROUTER_URL) }.getOrNull()
        if (routerRaw != null) {
            val route = runCatching { FleetRouterParser.resolve(routerRaw, deviceId) }.getOrNull()
            if (route != null) {
                devicePrefs.setResolvedManifestUrl(route.manifestUrl)
                devicePrefs.setClientId(route.clientId)
                devicePrefs.setLocationId(route.locationId)
                return route.manifestUrl
            }
        }
        return devicePrefs.getResolvedManifestUrl() ?: FLEET_CONFIG_URL
    }

    private fun download(urlString: String): String {
        // Cache-busting + niente cache: evita di ricevere una copia vecchia da CDN/cache.
        val busted = urlString + (if (urlString.contains("?")) "&" else "?") + "t=" + System.currentTimeMillis()
        val connection = URL(busted).openConnection() as HttpURLConnection
        connection.connectTimeout = 10_000
        connection.readTimeout = 10_000
        connection.requestMethod = "GET"
        connection.useCaches = false
        connection.setRequestProperty("Cache-Control", "no-cache")
        connection.setRequestProperty("Pragma", "no-cache")
        return try {
            connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        private const val TAG = "ConfigRepository"
    }
}

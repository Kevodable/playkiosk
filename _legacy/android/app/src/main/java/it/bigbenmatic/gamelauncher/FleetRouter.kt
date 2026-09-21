package it.bigbenmatic.gamelauncher

import org.json.JSONObject

/**
 * URL of the multi-tenant router published on GitHub Pages. The router maps each device
 * UUID (and a `default` fallback) to the URL of the client-specific manifest to load.
 * This is the only "global" file: everything else lives in per-client manifests that
 * reuse the exact same schema as the legacy single config.json.
 */
const val FLEET_ROUTER_URL = "https://kevodable.github.io/Fun-Planet-touch/launcher/fleet.json"

/** The tenant route resolved for this device: which manifest to load and who it belongs to. */
data class RouteResolution(
    val manifestUrl: String,
    val clientId: String,
    val locationId: String?,
)

/**
 * Parses `fleet.json` and resolves the route for [deviceId]. Resolution order:
 *   1. `devices[deviceId]` if present (the device is explicitly assigned to a client)
 *   2. otherwise the `default` entry (Big Ben Matic = "cliente zero", legacy behaviour)
 * Returns null only if neither is usable, so the caller can fall back to the legacy
 * config URL and keep working — no installed device is ever left without a manifest.
 */
object FleetRouterParser {

    fun resolve(json: String, deviceId: String): RouteResolution? {
        val root = JSONObject(json)
        val devices = root.optJSONObject("devices")
        val entry = devices?.optJSONObject(deviceId) ?: root.optJSONObject("default") ?: return null

        val manifestUrl = entry.optStringOrNull("manifestUrl") ?: return null
        val clientId = entry.optStringOrNull("clientId") ?: DevicePrefs.DEFAULT_CLIENT_ID
        val locationId = entry.optStringOrNull("locationId")
        return RouteResolution(manifestUrl, clientId, locationId)
    }

    private fun JSONObject.optStringOrNull(key: String): String? =
        if (has(key) && !isNull(key)) optString(key).takeIf { it.isNotBlank() } else null
}

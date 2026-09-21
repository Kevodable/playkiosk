package it.bigbenmatic.gamelauncher

import android.content.Context
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.net.wifi.WifiNetworkSuggestion
import android.os.Build
import android.util.Log

/**
 * Configures the Wi-Fi networks the monitor may auto-join, providing the failover the
 * operator asked for: a local "lifeline" network (entered once on-device, never public)
 * plus zero or more venue networks pushed from the remote config. Once both are
 * registered, Android connects to whichever is in range — so if the venue changes its
 * credentials the monitor stays online via the lifeline, downloads the new config with
 * the updated venue credentials, and reconnects automatically.
 *
 * NOTE: programmatic Wi-Fi behaviour differs across Android versions and OEMs and could
 * not be tested on a real device here — verify on the target tablet. On Android 10+ the
 * suggestion API does not force an immediate switch; it lets the system auto-join.
 */
object WifiProvisioner {

    fun apply(context: Context, networks: List<WifiNetwork>) {
        val unique = networks.distinctBy { it.ssid }.filter { it.ssid.isNotBlank() }
        if (unique.isEmpty()) return
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return
        val isOwner = KioskManager.isDeviceOwner(context)
        runCatching {
            when {
                // Da Device Owner possiamo usare le API legacy "privilegiate" anche su
                // Android 10+: aggiungono la rete e FORZANO la connessione, senza la
                // notifica di approvazione richiesta dalle "suggestion".
                isOwner -> connectAsDeviceOwner(wifi, unique)
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q -> applySuggestions(wifi, unique)
                else -> applyLegacy(wifi, unique)
            }
        }.onFailure { Log.w(TAG, "Configurazione Wi-Fi fallita: ${it.message}") }
    }

    /**
     * Device Owner: aggiunge le reti e si connette davvero a quella a priorità più alta
     * (di norma la "lifeline"). Idempotente: rimuove prima eventuali nostre configurazioni
     * con lo stesso SSID per non accumularle. Funziona su tutte le versioni perché un app
     * Device Owner è esente dalle restrizioni alle API legacy del Wi-Fi.
     */
    @Suppress("DEPRECATION")
    private fun connectAsDeviceOwner(wifi: WifiManager, networks: List<WifiNetwork>) {
        if (!wifi.isWifiEnabled) runCatching { wifi.isWifiEnabled = true }
        val existing = runCatching { wifi.configuredNetworks }.getOrNull().orEmpty()
        val ordered = networks.sortedByDescending { it.priority }
        var primaryNetId = -1
        for (n in ordered) {
            val quoted = "\"${n.ssid}\""
            // Riusa la rete se già configurata (niente remove+riadd: evitava il "flapping").
            var id = existing.firstOrNull { it.SSID == quoted }?.networkId ?: -1
            if (id == -1) {
                val conf = WifiConfiguration().apply {
                    SSID = quoted
                    hiddenSSID = n.hidden
                    if (n.password.isNullOrEmpty()) {
                        allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
                    } else {
                        preSharedKey = "\"${n.password}\""
                    }
                }
                id = wifi.addNetwork(conf)
            }
            if (id != -1) {
                if (primaryNetId == -1) primaryNetId = id
                runCatching { wifi.enableNetwork(id, false) }
            } else {
                Log.w(TAG, "addNetwork rifiutato SSID=${n.ssid}")
            }
        }
        runCatching { wifi.saveConfiguration() }
        // Forza la connessione alla rete a priorità più alta (disabilita temporaneamente le altre).
        if (primaryNetId != -1) {
            wifi.enableNetwork(primaryNetId, true)
            wifi.reconnect()
        }
    }

    private fun applySuggestions(wifi: WifiManager, networks: List<WifiNetwork>) {
        val suggestions = networks.map { n ->
            WifiNetworkSuggestion.Builder()
                .setSsid(n.ssid)
                .apply {
                    if (!n.password.isNullOrEmpty()) setWpa2Passphrase(n.password)
                    setIsHiddenSsid(n.hidden)
                }
                .build()
        }
        // Idempotent: clear our previous suggestions before re-adding the current set.
        runCatching { wifi.removeNetworkSuggestions(suggestions) }
        val status = wifi.addNetworkSuggestions(suggestions)
        if (status != WifiManager.STATUS_NETWORK_SUGGESTIONS_SUCCESS) {
            Log.w(TAG, "addNetworkSuggestions status=$status")
        }
    }

    @Suppress("DEPRECATION")
    private fun applyLegacy(wifi: WifiManager, networks: List<WifiNetwork>) {
        for (n in networks) {
            val conf = WifiConfiguration().apply {
                SSID = "\"${n.ssid}\""
                hiddenSSID = n.hidden
                priority = n.priority
                if (n.password.isNullOrEmpty()) {
                    allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
                } else {
                    preSharedKey = "\"${n.password}\""
                }
            }
            val netId = wifi.addNetwork(conf)
            if (netId != -1) {
                wifi.enableNetwork(netId, false)
            } else {
                Log.w(TAG, "addNetwork ha rifiutato SSID=${n.ssid}")
            }
        }
        runCatching { wifi.saveConfiguration() }
    }

    private const val TAG = "WifiProvisioner"
}

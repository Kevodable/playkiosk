package it.bigbenmatic.gamelauncher

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Owns the long-running fleet-management loops (Modules 1 & 3) for the whole app
 * lifetime, independent of any single Activity instance. Running them here (rather
 * than tied to MainActivity) keeps polling/telemetry alive across configuration
 * changes and matches how this app already runs as the persistent Home launcher.
 */
class FleetApp : Application() {

    lateinit var configRepository: ConfigRepository
    lateinit var telemetryManager: TelemetryManager
    private lateinit var devicePrefs: DevicePrefs

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        configRepository = ConfigRepository(this)
        telemetryManager = TelemetryManager(this)
        devicePrefs = DevicePrefs(this)
        // Abilita la cache su disco delle immagini (branding/icone/pubblicità) per l'offline.
        RemoteImageLoader.init(this)

        // Apply Wi-Fi straight away (lifeline + whatever the cached config carries) so the
        // device can reach the network before the first poll completes.
        applyWifi()

        startConfigPollingLoop()
        startTelemetryLoop()
    }

    /** Registers the lifeline Wi-Fi plus any venue networks from the active config. */
    fun applyWifi() {
        val lifeline = devicePrefs.getLifelineWifi()
        val remote = configRepository.config.value?.wifiNetworks.orEmpty()
        val all = (listOfNotNull(lifeline) + remote)
        if (all.isNotEmpty()) WifiProvisioner.apply(this, all)
    }

    /**
     * Installs / updates / removes APKs declared in the config (Module: remote app delivery).
     * Silent installs require Device Owner, so this is a no-op otherwise — without it the
     * system would need a user prompt that the kiosk blocks anyway. Idempotent: it only acts
     * when a package is missing or older than requested, so it is safe to run every poll.
     */
    private fun applyManagedApps() {
        if (!KioskManager.isDeviceOwner(this)) return
        val config = configRepository.config.value ?: return

        for (app in config.managedApps) {
            if (app.action == "uninstall") {
                if (isInstalled(app.packageName)) ApkInstaller.uninstall(this, app.packageName)
            } else {
                val url = app.apkUrl ?: continue
                if (needsInstall(app.packageName, app.versionCode)) {
                    ApkInstaller.installFromUrl(this, url, app.sha256)
                }
            }
        }

        // Self-update of the launcher itself, driven by `defaults.update`.
        val update = config.update
        if (update.silentInstall && !update.apkUrl.isNullOrBlank() &&
            update.latestVersionCode > currentVersionCode()
        ) {
            ApkInstaller.installFromUrl(this, update.apkUrl, null)
        }
    }

    private fun installedVersionCode(pkg: String): Int? = runCatching {
        @Suppress("DEPRECATION")
        packageManager.getPackageInfo(pkg, 0).versionCode
    }.getOrNull()

    private fun isInstalled(pkg: String): Boolean = installedVersionCode(pkg) != null

    /** Missing package -> install. Present package -> reinstall only if a newer versionCode is requested. */
    private fun needsInstall(pkg: String, targetVersion: Int): Boolean {
        val installed = installedVersionCode(pkg) ?: return true
        return targetVersion > 0 && installed < targetVersion
    }

    private fun currentVersionCode(): Int = installedVersionCode(packageName) ?: 0

    private fun startConfigPollingLoop() {
        scope.launch {
            while (true) {
                runCatching { configRepository.refresh() }
                val online = configRepository.connectionStatus.value == ConnectionStatus.ONLINE
                // Riapplica il Wi-Fi SOLO se offline (es. al boot o dopo una caduta): evita di
                // forzare riconnessioni quando è già connesso, che causavano i distacchi.
                if (!online) runCatching { applyWifi() }
                runCatching { applyManagedApps() }
                // Blindatura offline: quando c'è rete, scarica una volta il content-pack dei
                // giochi e i media della pubblicità, così restano disponibili anche senza rete.
                if (online) configRepository.config.value?.let { cfg ->
                    runCatching { ContentPackManager.sync(this@FleetApp, cfg.content) }
                    runCatching { prefetchAttract(cfg.attract) }
                }
                val minutes = configRepository.config.value?.pollIntervalMinutes?.takeIf { it > 0 } ?: 15
                delay(if (online) minutes * 60_000L else 20_000L)
            }
        }
    }

    /** Pre-scarica i media della pubblicità così l'attract funziona anche offline. */
    private suspend fun prefetchAttract(attract: AttractConfig) {
        if (!attract.enabled) return
        for (item in attract.items) {
            if (item.type.equals("video", ignoreCase = true)) {
                MediaCache.ensure(this, item.url)
            } else {
                RemoteImageLoader.load(item.url) // popola la cache immagini su disco
            }
        }
    }

    private fun startTelemetryLoop() {
        scope.launch {
            var secondsElapsed = 0L
            while (true) {
                delay(HEARTBEAT_TICK_MS)
                secondsElapsed += HEARTBEAT_TICK_MS / 1000

                val config = configRepository.config.value
                val telemetry = config?.telemetry
                if (telemetry?.enabled != true || telemetry.reportUrl.isNullOrBlank()) continue

                val heartbeatEverySeconds = (telemetry.heartbeatIntervalMinutes.takeIf { it > 0 } ?: 5) * 60L
                val reportEverySeconds = (telemetry.reportIntervalMinutes.takeIf { it > 0 } ?: 30) * 60L

                if (secondsElapsed % reportEverySeconds < HEARTBEAT_TICK_MS / 1000) {
                    telemetryManager.enqueueFullReport(this@FleetApp, config)
                } else if (secondsElapsed % heartbeatEverySeconds < HEARTBEAT_TICK_MS / 1000) {
                    telemetryManager.enqueueHeartbeat(config)
                }

                runCatching { telemetryManager.flushQueue(telemetry.reportUrl) }
            }
        }
    }

    companion object {
        private const val HEARTBEAT_TICK_MS = 30_000L
    }
}

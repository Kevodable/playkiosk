package it.bigbenmatic.gamelauncher

import android.content.Context
import android.os.BatteryManager
import android.os.SystemClock
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/** Sends heartbeat/usage telemetry to the Google Apps Script receiver configured via
 * `telemetry.reportUrl` in the fleet config (Module 3). Sends never block the caller:
 * payloads are queued locally first and flushed on a background thread, so a flaky
 * connection just delays delivery instead of breaking the UI. */
class TelemetryManager(context: Context) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("telemetry_queue", Context.MODE_PRIVATE)
    private val devicePrefs = DevicePrefs(appContext)
    private val deviceId = DeviceIdManager.getDeviceId(appContext)

    /** Per-package launch counters since the last full report was sent successfully. */
    fun recordGameLaunch(packageName: String) {
        val counters = prefs.getString(KEY_COUNTERS, null)?.let { JSONObject(it) } ?: JSONObject()
        counters.put(packageName, counters.optInt(packageName, 0) + 1)
        prefs.edit().putString(KEY_COUNTERS, counters.toString()).apply()
    }

    fun enqueueHeartbeat(config: ResolvedConfig?) {
        val payload = JSONObject().apply {
            put("type", "heartbeat")
            put("deviceId", deviceId)
            put("clientId", devicePrefs.getClientId())
            put("locationId", devicePrefs.getLocationId() ?: "")
            put("label", config?.deviceLabel ?: "")
            put("timestamp", isoNow())
            put("configVersion", config?.configVersion ?: -1)
            put("appVersion", appVersionCode())
        }
        enqueue(payload)
    }

    fun enqueueFullReport(context: Context, config: ResolvedConfig?) {
        val counters = prefs.getString(KEY_COUNTERS, null)?.let { JSONObject(it) } ?: JSONObject()
        val topGames = JSONArray()
        val packageToId = config?.games?.associate { it.packageName to it.id } ?: emptyMap()
        for (pkg in counters.keys()) {
            topGames.put(JSONObject().apply {
                put("id", packageToId[pkg] ?: pkg)
                put("launches", counters.optInt(pkg, 0))
            })
        }

        val payload = JSONObject().apply {
            put("type", "report")
            put("deviceId", deviceId)
            put("clientId", devicePrefs.getClientId())
            put("locationId", devicePrefs.getLocationId() ?: "")
            put("label", config?.deviceLabel ?: "")
            put("appVersion", appVersionCode())
            put("configVersion", config?.configVersion ?: -1)
            put("timestamp", isoNow())
            put("batteryPercent", batteryPercent(context))
            put("uptimeSeconds", SystemClock.elapsedRealtime() / 1000)
            put("topGames", topGames)
        }
        enqueue(payload)
        prefs.edit().remove(KEY_COUNTERS).apply()
    }

    /** Tries to send every queued payload, in order, stopping at the first failure so
     * nothing is lost or reordered; whatever remains stays queued for the next call. */
    fun flushQueue(reportUrl: String?) {
        if (reportUrl.isNullOrBlank()) return
        val queue = loadQueue()
        if (queue.length() == 0) return

        var sentCount = 0
        for (i in 0 until queue.length()) {
            val payload = queue.getJSONObject(i)
            val ok = runCatching { post(reportUrl, payload) }.getOrDefault(false)
            if (ok) {
                sentCount++
            } else {
                break
            }
        }

        if (sentCount > 0) {
            devicePrefs.setLastTelemetrySuccessMillis(System.currentTimeMillis())
            devicePrefs.setLastConnectionStatus("online")
            val remaining = JSONArray()
            for (i in sentCount until queue.length()) remaining.put(queue.getJSONObject(i))
            saveQueue(remaining)
        } else {
            devicePrefs.setLastConnectionStatus("offline")
        }
    }

    private fun enqueue(payload: JSONObject) {
        val queue = loadQueue()
        queue.put(payload)
        // Cap the queue so a long offline stretch can't grow it unbounded.
        val trimmed = if (queue.length() > MAX_QUEUE_SIZE) {
            JSONArray((queue.length() - MAX_QUEUE_SIZE until queue.length()).map { queue.getJSONObject(it) })
        } else queue
        saveQueue(trimmed)
    }

    private fun loadQueue(): JSONArray =
        prefs.getString(KEY_QUEUE, null)?.let { JSONArray(it) } ?: JSONArray()

    private fun saveQueue(queue: JSONArray) {
        prefs.edit().putString(KEY_QUEUE, queue.toString()).apply()
    }

    private fun post(urlString: String, payload: JSONObject): Boolean {
        val connection = URL(urlString).openConnection() as HttpURLConnection
        connection.connectTimeout = 10_000
        connection.readTimeout = 10_000
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        return try {
            connection.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            code in 200..299
        } catch (e: Exception) {
            Log.w(TAG, "Invio telemetria fallito: ${e.message}")
            false
        } finally {
            connection.disconnect()
        }
    }

    private fun appVersionCode(): Int = runCatching {
        appContext.packageManager.getPackageInfo(appContext.packageName, 0).let {
            @Suppress("DEPRECATION")
            it.versionCode
        }
    }.getOrDefault(0)

    private fun batteryPercent(context: Context): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager ?: return -1
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun isoNow(): String {
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        format.timeZone = TimeZone.getTimeZone("UTC")
        return format.format(Date())
    }

    companion object {
        private const val TAG = "TelemetryManager"
        private const val KEY_QUEUE = "pending_queue"
        private const val KEY_COUNTERS = "game_counters"
        private const val MAX_QUEUE_SIZE = 200
    }
}

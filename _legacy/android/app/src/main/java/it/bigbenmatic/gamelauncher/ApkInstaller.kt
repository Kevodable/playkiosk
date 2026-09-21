package it.bigbenmatic.gamelauncher

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.util.Log
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Silent APK install/uninstall via [PackageInstaller]. When this app is provisioned as
 * Device Owner the system performs the install without any user prompt, so it works while
 * the kiosk lock task is engaged. On a non-provisioned device the install falls back to
 * the standard Android confirmation dialog (handled by [InstallResultReceiver]), which is
 * only useful for manual testing before the device-owner setup.
 *
 * All calls block on network/IO: invoke them from a background coroutine (see FleetApp).
 */
object ApkInstaller {
    private const val TAG = "ApkInstaller"
    const val ACTION_INSTALL_RESULT = "it.bigbenmatic.gamelauncher.INSTALL_RESULT"

    /** Downloads [apkUrl], optionally verifies its SHA-256 against [expectedSha256], and
     *  installs/updates it silently. Returns failure (logged) on any download/checksum/IO error
     *  so the caller can simply skip and retry on the next poll. */
    fun installFromUrl(context: Context, apkUrl: String, expectedSha256: String? = null): Result<Unit> =
        runCatching {
            val apk = downloadToCache(context, apkUrl)
            try {
                if (expectedSha256 != null) {
                    val actual = sha256(apk)
                    require(actual.equals(expectedSha256, ignoreCase = true)) {
                        "Checksum SHA-256 non valido (atteso $expectedSha256, ottenuto $actual)"
                    }
                }
                installFile(context, apk)
            } finally {
                apk.delete()
            }
        }.onFailure { Log.w(TAG, "Installazione fallita da $apkUrl: ${it.message}") }

    /** Silently removes [packageName] (Device Owner only). */
    fun uninstall(context: Context, packageName: String) {
        runCatching {
            context.packageManager.packageInstaller
                .uninstall(packageName, resultSender(context, "uninstall-$packageName").intentSender)
        }.onFailure { Log.w(TAG, "Disinstallazione fallita di $packageName: ${it.message}") }
    }

    private fun installFile(context: Context, apk: File) {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        // Android 12+ richiede di dichiarare esplicitamente che non serve conferma utente:
        // da Device Owner così l'installazione/aggiornamento è davvero SILENZIOSA (OTA automatico).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            runCatching {
                params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
            }
        }
        val sessionId = installer.createSession(params)
        installer.openSession(sessionId).use { session ->
            session.openWrite("apk", 0, apk.length()).use { out ->
                apk.inputStream().use { it.copyTo(out) }
                session.fsync(out)
            }
            session.commit(resultSender(context, "install-$sessionId").intentSender)
        }
    }

    private fun resultSender(context: Context, tag: String): PendingIntent {
        val intent = Intent(ACTION_INSTALL_RESULT).setPackage(context.packageName)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0
        return PendingIntent.getBroadcast(context, tag.hashCode(), intent, flags)
    }

    private fun downloadToCache(context: Context, urlString: String): File {
        val out = File.createTempFile("fleet-", ".apk", context.cacheDir)
        val conn = URL(urlString).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 30_000
        conn.instanceFollowRedirects = true
        try {
            conn.inputStream.use { input -> out.outputStream().use { input.copyTo(it) } }
        } catch (t: Throwable) {
            out.delete()
            throw t
        } finally {
            conn.disconnect()
        }
        return out
    }

    private fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(8192)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}

package it.bigbenmatic.gamelauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.util.Log

/**
 * Receives the result of [PackageInstaller] sessions started by [ApkInstaller].
 *
 * Under Device Owner the install completes silently (STATUS_SUCCESS). On a device that is
 * not yet provisioned the system returns STATUS_PENDING_USER_ACTION with a confirmation
 * intent, which we launch so that manual installs work for testing before the kiosk is set up.
 */
class InstallResultReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        val pkg = intent.getStringExtra(PackageInstaller.EXTRA_PACKAGE_NAME)
        when (status) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                }
                confirm?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                runCatching { confirm?.let { context.startActivity(it) } }
            }
            PackageInstaller.STATUS_SUCCESS ->
                Log.i(TAG, "Installazione/aggiornamento completato: $pkg")
            else ->
                Log.w(
                    TAG,
                    "Esito installazione $pkg: status=$status, " +
                        "msg=${intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)}",
                )
        }
    }

    companion object {
        private const val TAG = "InstallResultReceiver"
    }
}

package it.bigbenmatic.gamelauncher

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.graphics.drawable.Drawable

data class GameApp(
    val packageName: String,        // app native: package reale; giochi web: "web:<id>"
    val label: String,
    val icon: Drawable?,            // null per i giochi web (icona via iconUrl)
    val url: String? = null,        // se valorizzato: gioco web aperto nella WebView interna
    val iconUrl: String? = null,    // icona remota per i giochi web
)

/** Lists launchable apps on the device, excluding this launcher itself. */
object InstalledAppsRepository {

    fun getAllLaunchableApps(context: Context): List<GameApp> {
        val pm = context.packageManager
        val intent = Intent(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) }
        val resolved = pm.queryIntentActivities(intent, PackageManager.MATCH_ALL)

        return resolved
            .asSequence()
            .map { it.activityInfo.applicationInfo }
            .distinctBy { it.packageName }
            .filter { it.packageName != context.packageName }
            .map { appInfo: ApplicationInfo ->
                GameApp(
                    packageName = appInfo.packageName,
                    label = pm.getApplicationLabel(appInfo).toString(),
                    icon = pm.getApplicationIcon(appInfo),
                )
            }
            .sortedBy { it.label.lowercase() }
            .toList()
    }

    fun launch(context: Context, packageName: String): Boolean {
        val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
            ?: return false
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(launchIntent)
        return true
    }
}

package it.bigbenmatic.gamelauncher

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.Build

/**
 * Wraps Android's Lock Task ("kiosk") APIs. Full protection (blocking Home, Recents,
 * status bar and any app outside the allow-list) only works once this app has been
 * provisioned as Device Owner on the tablet — see README.md for the one-time adb command.
 * Without Device Owner, lock task is not engaged automatically so that launching the
 * actual games (which run as separate apps/tasks) keeps working.
 */
object KioskManager {

    /** Finestra di "manutenzione": mentre è attiva, il kiosk NON si ri-aggancia da solo
     *  (così l'operatore può uscire davvero e usare il sistema). Vedi release()/engage(). */
    @Volatile private var maintenanceUntilMs = 0L
    private const val MAINTENANCE_MS = 5 * 60 * 1000L   // 5 minuti

    fun inMaintenance(): Boolean = android.os.SystemClock.elapsedRealtime() < maintenanceUntilMs

    fun adminComponent(context: Context) = ComponentName(context, DeviceOwnerReceiver::class.java)

    fun isDeviceOwner(context: Context): Boolean {
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        return dpm.isDeviceOwnerApp(context.packageName)
    }

    /** Keeps the lock-task allow-list in sync with the games chosen in Settings. */
    fun syncAllowedPackages(context: Context, selectedGamePackages: Set<String>) {
        if (!isDeviceOwner(context)) return
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val allowed = (selectedGamePackages + context.packageName).toTypedArray()
        dpm.setLockTaskPackages(adminComponent(context), allowed)

        // setLockTaskFeatures() e le costanti LOCK_TASK_FEATURE_* esistono solo da Android 9
        // (API 28). Su Android 8.x (es. alcuni monitor signage iiyama) il metodo non esiste e
        // chiamarlo manda in crash l'app all'avvio: lo saltiamo. Il lock task funziona lo stesso,
        // solo più restrittivo di default (che per un kiosk va benissimo).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            // Block Home/Recents/notifications; allow the power-button global actions menu.
            runCatching {
                dpm.setLockTaskFeatures(
                    adminComponent(context),
                    DevicePolicyManager.LOCK_TASK_FEATURE_GLOBAL_ACTIONS,
                )
            }
        }
    }

    /**
     * Tiene lo schermo SEMPRE acceso quando il tablet è alimentato (carica AC/USB/wireless).
     * Imposta la global setting STAY_ON_WHILE_PLUGGED_IN: persiste a livello di sistema e
     * vale anche fuori dall'app. Richiede Device Owner. Idempotente.
     */
    fun keepScreenOnWhilePlugged(context: Context) {
        if (!isDeviceOwner(context)) return
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val plugged = android.os.BatteryManager.BATTERY_PLUGGED_AC or
            android.os.BatteryManager.BATTERY_PLUGGED_USB or
            android.os.BatteryManager.BATTERY_PLUGGED_WIRELESS
        runCatching {
            dpm.setGlobalSetting(
                adminComponent(context),
                android.provider.Settings.Global.STAY_ON_WHILE_PLUGGED_IN,
                plugged.toString(),
            )
        }
    }

    /** Engages kiosk pinning if this app is Device Owner. Safe to call repeatedly.
     *  Durante la finestra di manutenzione non fa nulla, così l'uscita temporanea regge. */
    fun engage(activity: Activity) {
        if (!isDeviceOwner(activity)) return
        if (inMaintenance()) return
        val am = activity.getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
        if (am.lockTaskModeState == android.app.ActivityManager.LOCK_TASK_MODE_NONE) {
            runCatching { activity.startLockTask() }
        }
    }

    /**
     * Uscita temporanea dal kiosk per manutenzione. Apre una finestra di 5 minuti in cui il
     * kiosk non si ri-aggancia, sblocca il pinning e porta l'operatore nelle Impostazioni
     * Android (uscita reale dall'app). Rientrando nel launcher entro la finestra NON si
     * ri-blocca; dopo 5 minuti (o al riavvio) il kiosk si riattiva da solo.
     */
    fun release(activity: Activity) {
        maintenanceUntilMs = android.os.SystemClock.elapsedRealtime() + MAINTENANCE_MS
        runCatching { activity.stopLockTask() }
        // Prima esci dal lock task, poi apri le Impostazioni (fuori dalla allow-list).
        runCatching {
            activity.startActivity(
                android.content.Intent(android.provider.Settings.ACTION_SETTINGS)
                    .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }

    /** Rientra subito in kiosk (annulla la finestra di manutenzione) e riaggancia il pinning. */
    fun resume(activity: Activity) {
        maintenanceUntilMs = 0L
        engage(activity)
    }
}

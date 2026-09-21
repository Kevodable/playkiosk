package it.bigbenmatic.gamelauncher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Avvia il launcher all'accensione del dispositivo.
 *
 * Serve sui monitor "signage" (es. alcuni iiyama Android 8.x) il cui firmware NON rispetta
 * l'app Home di Android al boot: senza questo, all'avvio resta l'interfaccia del produttore
 * invece del launcher. Su un Android "normale" è ridondante (l'Home parte già da sola) e non
 * fa danni, perché MainActivity è `singleTask`: se è già in primo piano, non viene duplicata.
 *
 * Includiamo anche le action di "quick boot" usate da diversi produttori.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        when (intent?.action) {
            Intent.ACTION_BOOT_COMPLETED,
            "android.intent.action.QUICKBOOT_POWERON",
            "com.htc.intent.action.QUICKBOOT_POWERON" -> {
                val launch = Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                runCatching { context.startActivity(launch) }
            }
        }
    }
}

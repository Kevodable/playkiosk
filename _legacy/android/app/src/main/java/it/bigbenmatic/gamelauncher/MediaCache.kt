package it.bigbenmatic.gamelauncher

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** Cache su disco per file "pesanti" (i video della pubblicità) indicati per URL. **Offline-first**:
 * `ensure()` scarica una volta sola (quando c'è rete) in `filesDir/mediacache`; poi `cachedFile()`
 * restituisce il file locale così il video parte anche senza rete. Chiave = SHA-1 dell'URL. */
object MediaCache {

    private fun dir(context: Context): File =
        File(context.applicationContext.filesDir, "mediacache").apply { mkdirs() }

    /** Il file locale se già scaricato, altrimenti null. */
    fun cachedFile(context: Context, url: String): File? {
        val f = File(dir(context), keyFor(url))
        return if (f.exists() && f.length() > 0) f else null
    }

    /** Scarica il media se manca. Idempotente e sicuro da chiamare ad ogni sync. */
    suspend fun ensure(context: Context, url: String) = withContext(Dispatchers.IO) {
        val target = File(dir(context), keyFor(url))
        if (target.exists() && target.length() > 0) return@withContext
        runCatching {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout = 30_000
            }
            val tmp = File(target.parentFile, target.name + ".tmp")
            connection.inputStream.use { input -> tmp.outputStream().use { input.copyTo(it) } }
            tmp.renameTo(target)
        }
    }

    private fun keyFor(url: String): String =
        MessageDigest.getInstance("SHA-1").digest(url.toByteArray())
            .joinToString("") { "%02x".format(it) }
}

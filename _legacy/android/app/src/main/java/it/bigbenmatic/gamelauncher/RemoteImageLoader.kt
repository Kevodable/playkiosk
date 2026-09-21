package it.bigbenmatic.gamelauncher

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** Tiny dependency-free image fetcher usato per branding (logo/sfondo), icone e i media della
 * pubblicità che il config remoto indica per URL. **Offline-first**: ogni immagine scaricata
 * viene salvata su disco (`filesDir/imgcache`), così dopo la prima volta è disponibile anche
 * senza rete — per anni. Chiave = SHA-1 dell'URL (gli upload usano nomi con timestamp, quindi
 * una nuova immagine ha URL diverso e non collide con la cache vecchia). */
object RemoteImageLoader {

    @Volatile private var cacheDir: File? = null

    /** Da chiamare una volta (FleetApp) per abilitare la cache su disco. */
    fun init(context: Context) {
        cacheDir = File(context.applicationContext.filesDir, "imgcache").apply { mkdirs() }
    }

    suspend fun load(url: String): Bitmap? = withContext(Dispatchers.IO) {
        val file = cacheDir?.let { File(it, keyFor(url)) }
        if (file != null && file.exists()) {
            BitmapFactory.decodeFile(file.absolutePath)?.let { return@withContext it }
        }
        runCatching {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 10_000
                readTimeout = 10_000
            }
            val bytes = connection.inputStream.use { it.readBytes() }
            if (file != null) runCatching {
                val tmp = File(file.parentFile, file.name + ".tmp")
                tmp.writeBytes(bytes)
                tmp.renameTo(file)
            }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        }.getOrNull()
    }

    private fun keyFor(url: String): String =
        MessageDigest.getInstance("SHA-1").digest(url.toByteArray())
            .joinToString("") { "%02x".format(it) }
}

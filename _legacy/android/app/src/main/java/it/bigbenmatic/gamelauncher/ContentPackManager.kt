package it.bigbenmatic.gamelauncher

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * Gestisce il **content-pack** dei giochi (offline-first). Quando c'è rete, scarica una volta
 * uno zip versionato (tutti i giochi web + asset), lo scompatta in `filesDir/content/<versione>/`
 * e ci punta. Da lì in poi i giochi si caricano da `file://` **senza rete, per anni**; il pack si
 * aggiorna solo quando il config indica una `version` più alta (stessa logica dell'OTA APK).
 *
 * Mapping: se un gioco ha `url` che inizia con `content.baseUrl` (la cartella remota che
 * corrisponde alla radice del pack) e il file locale esiste, si carica quello; altrimenti si
 * ripiega sull'URL remoto (online). Nessuna modifica per-gioco al config.
 */
object ContentPackManager {

    /** Scarica e scompatta il pack se il config ne indica uno più nuovo di quello installato. */
    suspend fun sync(context: Context, content: ContentConfig?): Unit = withContext(Dispatchers.IO) {
        val url = content?.url?.takeIf { it.isNotBlank() } ?: return@withContext
        val version = content.version
        if (version <= 0) return@withContext
        val prefs = DevicePrefs(context)
        val installed = prefs.getContentVersion()
        val versionDir = File(contentRoot(context), version.toString())
        if (installed == version && versionDir.isDirectory) return@withContext

        val tmpDir = File(contentRoot(context), "$version.tmp")
        runCatching {
            if (tmpDir.exists()) tmpDir.deleteRecursively()
            tmpDir.mkdirs()
            downloadAndUnzip(url, tmpDir)
            if (versionDir.exists()) versionDir.deleteRecursively()
            if (!tmpDir.renameTo(versionDir)) error("rename fallito")
            prefs.setContentVersion(version)
            // Pulizia delle versioni vecchie: teniamo solo quella corrente.
            contentRoot(context).listFiles()?.forEach { f ->
                if (f.name != version.toString()) f.deleteRecursively()
            }
        }.onFailure {
            runCatching { tmpDir.deleteRecursively() }
        }
        Unit
    }

    /**
     * Se il pack installato contiene il file puntato da [remoteUrl] (rispetto a [content]?.baseUrl),
     * ritorna l'URL `file://` locale; altrimenti null (→ il chiamante usa l'URL remoto).
     */
    fun localUrlFor(context: Context, remoteUrl: String, content: ContentConfig?): String? {
        val base = content?.baseUrl?.takeIf { it.isNotBlank() } ?: return null
        if (!remoteUrl.startsWith(base)) return null
        val version = DevicePrefs(context).getContentVersion()
        if (version <= 0) return null
        val versionDir = File(contentRoot(context), version.toString())
        if (!versionDir.isDirectory) return null
        // Path relativo dentro il pack, senza query/hash.
        val rel = remoteUrl.substring(base.length).substringBefore('?').substringBefore('#')
        val local = File(versionDir, rel)
        if (!local.exists()) return null
        // Sicurezza: il file deve restare dentro la cartella del pack.
        val root = versionDir.canonicalPath
        if (!local.canonicalPath.startsWith(root)) return null
        return "file://" + local.absolutePath
    }

    private fun contentRoot(context: Context): File =
        File(context.applicationContext.filesDir, "content").apply { mkdirs() }

    private fun downloadAndUnzip(url: String, targetDir: File) {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 60_000
        }
        connection.inputStream.use { raw ->
            ZipInputStream(raw.buffered()).use { zip ->
                val rootPath = targetDir.canonicalPath
                var entry = zip.nextEntry
                while (entry != null) {
                    val outFile = File(targetDir, entry.name)
                    // Protezione zip-slip: nessuna entry può uscire dalla cartella target.
                    if (!outFile.canonicalPath.startsWith(rootPath)) {
                        error("entry non valida nello zip: ${entry.name}")
                    }
                    if (entry.isDirectory) {
                        outFile.mkdirs()
                    } else {
                        outFile.parentFile?.mkdirs()
                        outFile.outputStream().use { zip.copyTo(it) }
                    }
                    zip.closeEntry()
                    entry = zip.nextEntry
                }
            }
        }
    }
}

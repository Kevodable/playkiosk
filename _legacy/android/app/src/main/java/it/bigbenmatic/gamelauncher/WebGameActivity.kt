package it.bigbenmatic.gamelauncher

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * Mostra un **gioco web** (HTML/CSS/JS ospitato su GitHub Pages, es. la cartella
 * `big-ben-giochi/`) dentro una WebView a tutto schermo, restando nella STESSA
 * app del launcher.
 *
 * Perché così:
 *  - i giochi web girano dentro il lock task del kiosk senza installare APK
 *    aggiuntive (è un'Activity del nostro stesso package, sempre permessa);
 *  - si aggiungono/aggiornano interamente da remoto via `config.json` (un gioco
 *    con il campo `url` viene aperto qui), senza ridistribuire il launcher;
 *  - il Device Owner / kiosk resta intatto.
 *
 * Contratto con i giochi (vedi `assets/shared.js` → `BB.home()`):
 *   window.AndroidLauncher.goHome()  → chiude la WebView e torna alla griglia.
 * Restano validi anche il pulsante flottante "Torna ai giochi" e il timer di
 * sessione del launcher, che riportano comunque alla griglia.
 */
class WebGameActivity : ComponentActivity() {

    private var webView: WebView? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        hideSystemBars()
        // Schermo sempre acceso durante il gioco.
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val wv = WebView(this).apply {
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true                 // localStorage: record/preferenze dei giochi
                mediaPlaybackRequiresUserGesture = false // i suoni partono al primo tap
                loadWithOverviewMode = true
                useWideViewPort = true
                cacheMode = WebSettings.LOAD_DEFAULT
                // Content-pack offline: i giochi possono essere caricati da file:// e devono poter
                // leggere i propri asset relativi (script/immagini/json) dalla stessa cartella.
                allowFileAccess = true
                allowContentAccess = true
                @Suppress("DEPRECATION")
                allowFileAccessFromFileURLs = true
                builtInZoomControls = false
                displayZoomControls = false
                setSupportZoom(false)
            }
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            // Resta dentro la WebView: nessuna apertura di browser esterni.
            webViewClient = WebViewClient()
            // Bridge nativo esposto come window.AndroidLauncher
            addJavascriptInterface(GoHomeBridge(), "AndroidLauncher")
        }
        webView = wv
        setContentView(wv)
        loadFromIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        loadFromIntent(intent)   // singleTask: riusa l'istanza per aprire un altro gioco
    }

    private fun loadFromIntent(intent: Intent?) {
        val url = intent?.getStringExtra(EXTRA_URL)
        if (url.isNullOrBlank()) { finish(); return }
        webView?.loadUrl(url)
    }

    /** Oggetto JavaScript esposto al gioco come `window.AndroidLauncher`. */
    private inner class GoHomeBridge {
        @JavascriptInterface
        fun goHome() {
            // Torna alla griglia del launcher chiudendo la WebView.
            runOnUiThread { finish() }
        }
    }

    override fun onResume() {
        super.onResume()
        hideSystemBars()
        webView?.onResume()
    }

    override fun onPause() {
        super.onPause()
        webView?.onPause()
    }

    /**
     * Una sola WebView viva alla volta: quando il launcher torna in primo piano
     * (pulsante flottante "Torna ai giochi" o timer di sessione), chiudiamo la
     * WebView così fermiamo audio/loop e al prossimo gioco ripartiamo puliti.
     * La rotazione non passa di qui grazie a `configChanges` nel manifest.
     */
    override fun onStop() {
        super.onStop()
        if (!isFinishing && !isChangingConfigurations) finish()
    }

    @Suppress("OVERRIDE_DEPRECATION")
    override fun onBackPressed() {
        // "Indietro" = esci dal gioco e torna alla griglia.
        finish()
    }

    override fun onDestroy() {
        webView?.destroy()
        webView = null
        super.onDestroy()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    private fun hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.hide(WindowInsetsCompat.Type.systemBars())
        controller.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    }

    companion object {
        private const val EXTRA_URL = "url"

        /** Avvia un gioco web all'[url] indicato. */
        fun launch(context: Context, url: String) {
            val intent = Intent(context, WebGameActivity::class.java)
                .putExtra(EXTRA_URL, url)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
        }
    }
}

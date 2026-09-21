package it.bigbenmatic.gamelauncher

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.VideoView
import androidx.activity.ComponentActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/**
 * Schermo pubblicitario / "attract": parte dalla home dopo l'inattività e fa scorrere a
 * tutto schermo le immagini/video definiti in `defaults.attract`, finché qualcuno tocca
 * lo schermo (poi si chiude e torna ai giochi). Nessuna dipendenza esterna: ImageView per
 * le immagini (via RemoteImageLoader) e VideoView per i video (per URL, anche esterni).
 */
class AttractActivity : ComponentActivity() {

    private lateinit var image: ImageView
    private lateinit var video: VideoView
    private val handler = Handler(Looper.getMainLooper())
    private var items: List<AttractItem> = emptyList()
    private var idx = 0
    private var failures = 0
    private var muteVideo = true
    private var defaultSeconds = 8
    private var stopped = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        hideSystemBars()

        val root = FrameLayout(this).apply { setBackgroundColor(0xFF000000.toInt()) }
        image = ImageView(this).apply {
            layoutParams = FrameLayout.LayoutParams(MATCH, MATCH)
            scaleType = ImageView.ScaleType.FIT_CENTER
            visibility = View.GONE
        }
        video = VideoView(this).apply {
            layoutParams = FrameLayout.LayoutParams(MATCH, MATCH, Gravity.CENTER)
            visibility = View.GONE
        }
        root.addView(image)
        root.addView(video)
        setContentView(root)

        val cfg = (application as FleetApp).configRepository.config.value?.attract
        if (cfg == null || !cfg.enabled || cfg.items.isEmpty()) { finish(); return }
        items = cfg.items
        muteVideo = cfg.muteVideo
        defaultSeconds = if (cfg.itemSeconds > 0) cfg.itemSeconds else 8
        addCallToAction(root, cfg.callToAction)
        showCurrent()
    }

    /** Messaggio in sovraimpressione (es. "Tocca lo schermo per giocare"): visibile ma discreto,
     *  pillola semitrasparente in basso con una pulsazione morbida. Vuoto = niente messaggio. */
    private fun addCallToAction(root: FrameLayout, message: String) {
        val text = message.trim()
        if (text.isEmpty()) return
        val dp = { v: Float -> android.util.TypedValue.applyDimension(
            android.util.TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt() }
        val label = android.widget.TextView(this).apply {
            this.text = text
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 22f
            typeface = android.graphics.Typeface.DEFAULT_BOLD
            setPadding(dp(30f), dp(14f), dp(30f), dp(14f))
            background = android.graphics.drawable.GradientDrawable().apply {
                cornerRadius = dp(40f).toFloat()
                setColor(0x8C000000.toInt())   // nero ~55% opaco: leggibile ma non invadente
            }
        }
        val lp = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL,
        ).apply { bottomMargin = dp(52f) }
        root.addView(label, lp)   // aggiunto per ultimo → sopra immagine/video
        val pulse = android.view.animation.AlphaAnimation(0.55f, 1f).apply {
            duration = 1100
            repeatMode = android.view.animation.Animation.REVERSE
            repeatCount = android.view.animation.Animation.INFINITE
        }
        label.startAnimation(pulse)
    }

    private fun showCurrent() {
        if (stopped || items.isEmpty()) { if (!stopped) finish(); return }
        val item = items[idx % items.size]
        if (item.type.equals("video", ignoreCase = true)) showVideo(item) else showImage(item)
    }

    private fun advance() {
        if (stopped) return
        idx = (idx + 1) % items.size
        showCurrent()
    }

    /** Un media non mostrabile (offline/URL rotto): salta. Se tutti falliscono, esce. */
    private fun onItemFail() {
        failures++
        if (failures >= items.size) { finish(); return }
        advance()
    }

    private fun showImage(item: AttractItem) {
        video.visibility = View.GONE
        runCatching { video.stopPlayback() }
        lifecycleScope.launch {
            val bmp = RemoteImageLoader.load(item.url)
            if (stopped) return@launch
            if (bmp == null) { onItemFail(); return@launch }
            failures = 0
            image.setImageBitmap(bmp)
            image.visibility = View.VISIBLE
            val secs = if (item.seconds > 0) item.seconds else defaultSeconds
            handler.postDelayed({ advance() }, secs * 1000L)
        }
    }

    private fun showVideo(item: AttractItem) {
        image.visibility = View.GONE
        video.visibility = View.VISIBLE
        // Offline-first: se il video è già in cache su disco lo riproduciamo da lì; altrimenti lo
        // streammiamo dall'URL e lo scarichiamo in background per la prossima volta.
        val cached = MediaCache.cachedFile(this, item.url)
        val uri = if (cached != null) Uri.fromFile(cached) else Uri.parse(item.url)
        if (cached == null) lifecycleScope.launch(kotlinx.coroutines.Dispatchers.IO) {
            runCatching { MediaCache.ensure(this@AttractActivity, item.url) }
        }
        runCatching {
            video.setVideoURI(uri)
            video.setOnPreparedListener { mp ->
                failures = 0
                if (muteVideo) mp.setVolume(0f, 0f)
                mp.isLooping = false
                video.start()
            }
            video.setOnCompletionListener { advance() }
            video.setOnErrorListener { _, _, _ -> onItemFail(); true }
        }.onFailure { onItemFail() }
    }

    // Qualunque tocco chiude lo schermo pubblicitario e torna ai giochi.
    override fun dispatchTouchEvent(ev: MotionEvent?): Boolean {
        finish()
        return true
    }

    override fun onPause() {
        super.onPause()
        if (!isFinishing) finish()
    }

    override fun finish() {
        stopped = true
        handler.removeCallbacksAndMessages(null)
        runCatching { video.stopPlayback() }
        super.finish()
    }

    private fun hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val c = WindowInsetsControllerCompat(window, window.decorView)
        c.hide(WindowInsetsCompat.Type.systemBars())
        c.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
    }

    companion object {
        private const val MATCH = FrameLayout.LayoutParams.MATCH_PARENT

        fun launch(context: Context) {
            runCatching {
                context.startActivity(
                    Intent(context, AttractActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }
        }
    }
}

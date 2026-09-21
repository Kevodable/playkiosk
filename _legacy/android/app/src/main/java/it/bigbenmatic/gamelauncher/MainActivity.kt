package it.bigbenmatic.gamelauncher

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.ImageView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class Screen { HOME, PIN_ENTRY, SETTINGS, DIAGNOSTICS }

class MainActivity : ComponentActivity() {

    private lateinit var prefs: PrefsManager
    private val resumeTick = mutableStateOf(0)
    // Bumped on every touch/key the launcher receives; drives the idle-timeout reset.
    private val interactionTick = mutableStateOf(0L)
    // True solo quando il launcher è in primo piano: evita di lanciare l'attract
    // mentre un gioco è davanti (il launcher è in pausa dietro di esso).
    private val isForeground = mutableStateOf(true)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = PrefsManager(this)
        hideSystemBars()
        // Schermo sempre acceso: mentre l'app è in primo piano (qualsiasi alimentazione)
        // e, da Device Owner, anche a livello di sistema quando il tablet è alimentato.
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        KioskManager.keepScreenOnWhilePlugged(this)
        KioskManager.syncAllowedPackages(this, prefs.getSelectedPackages())

        setContent {
            LauncherApp(
                prefs = prefs,
                resumeTick = resumeTick.value,
                interactionTick = interactionTick.value,
                isForeground = isForeground.value,
            )
        }
    }

    override fun onUserInteraction() {
        super.onUserInteraction()
        interactionTick.value = android.os.SystemClock.elapsedRealtime()
    }

    override fun onResume() {
        super.onResume()
        hideSystemBars()
        KioskManager.engage(this)
        // Back on the grid: the floating "back to games" button and the session timer are done.
        FloatingHomeButton.hide(this)
        SessionTimer.cancel()
        isForeground.value = true
        resumeTick.value++
        interactionTick.value = android.os.SystemClock.elapsedRealtime()
    }

    override fun onPause() {
        super.onPause()
        isForeground.value = false
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
}

@OptIn(ExperimentalComposeUiApi::class, androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun LauncherApp(prefs: PrefsManager, resumeTick: Int, interactionTick: Long, isForeground: Boolean) {
    val context = LocalContext.current
    val fleetApp = context.applicationContext as FleetApp
    val config by fleetApp.configRepository.config.collectAsState()
    val connectionStatus by fleetApp.configRepository.connectionStatus.collectAsState()

    var screen by remember { mutableStateOf(Screen.HOME) }
    var selectedPackages by remember { mutableStateOf(prefs.getSelectedPackages()) }
    var allApps by remember { mutableStateOf(InstalledAppsRepository.getAllLaunchableApps(context)) }

    fun refreshApps() {
        allApps = InstalledAppsRepository.getAllLaunchableApps(context)
        // Drop selections for apps that were uninstalled in the meantime.
        val stillInstalled = allApps.map { it.packageName }.toSet()
        if (!selectedPackages.all { it in stillInstalled }) {
            selectedPackages = selectedPackages.intersect(stillInstalled)
            prefs.setSelectedPackages(selectedPackages)
        }
    }

    LaunchedEffect(Unit) { refreshApps() }

    // Effective PIN: the remotely configured exit PIN wins over the local one when present.
    val effectivePin = config?.kiosk?.exitPin?.takeIf { it.isNotBlank() } ?: prefs.getPin()

    // Effective game list: when the fleet config defines visible games that are actually
    // installed, those drive the grid (remote control); otherwise we fall back to the
    // locally chosen games so the app keeps working with no or stale config.
    val installedByPkg = remember(allApps) { allApps.associateBy { it.packageName } }
    // Giochi nativi gestiti da remoto: pacchetti effettivamente installati sul device.
    val remoteNativeGames = config?.games.orEmpty()
        .filter { it.visible && it.packageName != null && installedByPkg.containsKey(it.packageName) }
    // Giochi web gestiti da remoto: hanno un `url` e vengono aperti nella WebView interna
    // (WebGameActivity), quindi non richiedono installazione né package locale.
    val remoteWebGames = config?.games.orEmpty()
        .filter { it.visible && it.url != null }
    val usingRemoteGames = remoteNativeGames.isNotEmpty() || remoteWebGames.isNotEmpty()
    val effectiveGames: List<GameApp> = if (usingRemoteGames) {
        // Rispetta l'ordine definito nel config; per ogni voce crea la tile giusta
        // (nativa se il package è installato, web se è presente l'url).
        config?.games.orEmpty().filter { it.visible }.mapNotNull { rg ->
            when {
                rg.url != null -> GameApp(
                    packageName = "web:" + rg.id,   // chiave sintetica univoca per la griglia
                    label = rg.displayName ?: rg.id,
                    icon = null,
                    url = rg.url,
                    iconUrl = rg.iconUrl,
                )
                rg.packageName != null && installedByPkg.containsKey(rg.packageName) -> {
                    val base = installedByPkg[rg.packageName]!!
                    base.copy(label = rg.displayName ?: base.label, iconUrl = rg.iconUrl)
                }
                else -> null
            }
        }
    } else {
        allApps.filter { it.packageName in selectedPackages }
    }

    // Keep the kiosk allow-list in sync with whatever is actually playable right now. Remotely
    // managed apps that are installed are added too, so games pushed via PackageInstaller are
    // launchable inside the lock task even before they are listed under `games`.
    val managedPackages = config?.managedApps.orEmpty()
        .filter { it.action != "uninstall" && installedByPkg.containsKey(it.packageName) }
        .map { it.packageName }.toSet()
    // I giochi web girano dentro il nostro stesso package (sempre permesso nel lock task),
    // quindi alla whitelist servono solo i package dei giochi nativi.
    val baseAllowed = if (usingRemoteGames) remoteNativeGames.mapNotNull { it.packageName }.toSet() else selectedPackages
    val allowedPackages = baseAllowed + managedPackages
    LaunchedEffect(allowedPackages) { KioskManager.syncAllowedPackages(context, allowedPackages) }

    // Single-game stations: boot straight into the configured package each time we land on Home.
    val autoLaunch = config?.kiosk?.autoLaunchPackage
    LaunchedEffect(autoLaunch, resumeTick, screen) {
        if (screen == Screen.HOME && autoLaunch != null && installedByPkg.containsKey(autoLaunch)) {
            fleetApp.telemetryManager.recordGameLaunch(autoLaunch)
            InstalledAppsRepository.launch(context, autoLaunch)
        }
    }

    // Idle timeout: if the operator leaves a sub-screen open (Settings/PIN/Diagnostics)
    // and nobody touches the screen for idleTimeoutSeconds, return to the clean grid.
    // Runs only off the HOME screen, so it never disturbs the grid itself nor a running
    // game (while a game is foreground the launcher is on HOME behind it).
    val idleTimeoutSeconds = config?.kiosk?.idleTimeoutSeconds ?: 0
    LaunchedEffect(idleTimeoutSeconds, screen, interactionTick) {
        if (idleTimeoutSeconds > 0 && screen != Screen.HOME) {
            kotlinx.coroutines.delay(idleTimeoutSeconds * 1000L)
            screen = Screen.HOME
        }
    }

    // Schermo pubblicitario / attract: dalla home, dopo `idleSeconds` di inattività e solo
    // se il launcher è in primo piano (nessun gioco davanti), parte il loop dei media.
    val attract = config?.attract
    val attractIdle = attract?.idleSeconds ?: 0
    LaunchedEffect(attract?.enabled, attractIdle, attract?.items?.size, screen, interactionTick, isForeground) {
        if (attract?.enabled == true && attract.items.isNotEmpty() && attractIdle > 0 &&
            screen == Screen.HOME && isForeground
        ) {
            kotlinx.coroutines.delay(attractIdle * 1000L)
            AttractActivity.launch(context)
        }
    }

    val colorScheme = rememberColorScheme(config?.branding)

    MaterialTheme(colorScheme = colorScheme) {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            val operational = config?.operational
            when {
                operational?.status == "maintenance" && screen == Screen.HOME -> MaintenanceScreen(
                    message = operational.maintenanceMessage,
                    branding = config?.branding,
                    onRequestSettings = { screen = Screen.PIN_ENTRY },
                )
                screen == Screen.HOME -> HomeScreen(
                    games = effectiveGames,
                    columns = config?.layout?.columns ?: 0,
                    showLabels = config?.layout?.showLabels ?: true,
                    banner = operational?.banner,
                    branding = config?.branding,
                    onPlay = { game ->
                        fleetApp.telemetryManager.recordGameLaunch(game.packageName)
                        // Giochi web → WebView interna; giochi nativi → lancio del package.
                        val launched = if (game.url != null) {
                            // Offline-first: se il content-pack locale contiene il gioco, lo carica
                            // da file:// (funziona senza rete); altrimenti ripiega sull'URL remoto.
                            val gameUrl = ContentPackManager.localUrlFor(context, game.url, config?.content)
                                ?: game.url
                            WebGameActivity.launch(context, gameUrl); true
                        } else {
                            InstalledAppsRepository.launch(context, game.packageName)
                        }
                        if (launched) {
                            // Show the floating "back to games" button on top of the game so the
                            // child can always return to the grid (even in kiosk, where Home is blocked).
                            FloatingHomeButton.show(context)
                            // Start the session limit: a per-game limit (if set) wins over the global one.
                            // Per i giochi web la chiave è "web:<id>", quindi confrontiamo entrambe le forme.
                            val perGame = config?.games?.firstOrNull {
                                it.packageName == game.packageName || ("web:" + it.id) == game.packageName
                            }?.sessionLimitSeconds ?: 0
                            val limit = if (perGame > 0) perGame else (config?.kiosk?.sessionLimitSeconds ?: 0)
                            SessionTimer.start(context, limit)
                        } else {
                            Toast.makeText(context, "Gioco non disponibile", Toast.LENGTH_SHORT).show()
                            refreshApps()
                        }
                    },
                    onRequestSettings = { screen = Screen.PIN_ENTRY },
                )
                screen == Screen.PIN_ENTRY -> PinEntryScreen(
                    expectedPin = effectivePin,
                    onSuccess = { screen = Screen.SETTINGS },
                    onCancel = { screen = Screen.HOME },
                )
                screen == Screen.SETTINGS -> SettingsScreen(
                    allApps = allApps,
                    selectedPackages = selectedPackages,
                    currentPin = prefs.getPin(),
                    remoteControlled = usingRemoteGames,
                    onToggle = { pkg, checked ->
                        selectedPackages = if (checked) selectedPackages + pkg else selectedPackages - pkg
                        prefs.setSelectedPackages(selectedPackages)
                    },
                    onChangePin = { newPin -> prefs.setPin(newPin) },
                    onOpenDiagnostics = { screen = Screen.DIAGNOSTICS },
                    onDone = { screen = Screen.HOME },
                )
                screen == Screen.DIAGNOSTICS -> DiagnosticsScreen(
                    config = config,
                    connectionStatus = connectionStatus,
                    onBack = { screen = Screen.SETTINGS },
                )
            }
        }
    }
}

// Palette sampled from the Kids Fun Planet logo.
private val LogoCoral = Color(0xFFCC7375)
private val LogoPink = Color(0xFFD89FA6)
private val LogoTan = Color(0xFFD1B085)
private val LogoSage = Color(0xFF8A9978)
private val LogoTeal = Color(0xFF7AACAD)
private val LogoSky = Color(0xFFB5DCEB)
private val LogoYellow = Color(0xFFFDCE72)

private fun parseColorOrNull(hex: String?): Color? =
    hex?.let { runCatching { Color(android.graphics.Color.parseColor(it)) }.getOrNull() }

@Composable
private fun rememberColorScheme(branding: Branding?) = lightColorScheme(
    primary = parseColorOrNull(branding?.primaryColor) ?: Color(0xFF3346D6),
    secondary = parseColorOrNull(branding?.accentColor) ?: LogoYellow,
    background = Color(0xFFF0F4FF),
    surface = Color.White,
)

/** Background: a remote branding image if the config supplies one (downloaded once),
 * otherwise the built-in logo gradient. */
@Composable
private fun LauncherBackground(branding: Branding?, modifier: Modifier = Modifier) {
    val backgroundUrl = branding?.backgroundUrl
    var remoteBg by remember(backgroundUrl) { mutableStateOf<android.graphics.Bitmap?>(null) }
    LaunchedEffect(backgroundUrl) {
        if (backgroundUrl != null) remoteBg = RemoteImageLoader.load(backgroundUrl)
    }
    val bmp = remoteBg
    if (bmp != null) {
        Image(
            bitmap = bmp.asImageBitmap(),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = modifier.fillMaxSize(),
        )
    } else {
        LogoBackground(modifier)
    }
}

@Composable
private fun LogoBackground(modifier: Modifier = Modifier) {
    val gradient = Brush.linearGradient(
        colors = listOf(LogoCoral, LogoPink, LogoTan, LogoSage, LogoTeal, LogoSky),
    )
    Box(modifier = modifier.fillMaxSize().background(gradient)) {
        Image(
            painter = painterResource(id = R.drawable.logo_fun_planet),
            contentDescription = null,
            contentScale = ContentScale.Fit,
            alpha = 0.22f,
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth(0.92f),
        )
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun HomeScreen(
    games: List<GameApp>,
    columns: Int,
    showLabels: Boolean,
    banner: Banner?,
    branding: Branding?,
    onPlay: (GameApp) -> Unit,
    onRequestSettings: () -> Unit,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        LauncherBackground(branding)

        Column(modifier = Modifier.fillMaxSize().padding(20.dp)) {
            Box(
                modifier = Modifier
                    .align(Alignment.End)
                    .size(40.dp)
                    .clip(RoundedCornerShape(50))
                    .background(Color.White.copy(alpha = 0.55f))
                    .combinedClickable(onClick = {}, onLongClick = onRequestSettings),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.Settings, contentDescription = "Impostazioni", tint = Color.White)
            }
            Spacer(Modifier.height(12.dp))

            // Logo (branding.logoUrl): mostrato come elemento sopra lo sfondo, se presente.
            // Per-dispositivo si può impostare il logo del locale; vuoto = nessun logo qui.
            val logoUrl = branding?.logoUrl
            if (logoUrl != null) {
                var logoBmp by remember(logoUrl) { mutableStateOf<android.graphics.Bitmap?>(null) }
                LaunchedEffect(logoUrl) { logoBmp = RemoteImageLoader.load(logoUrl) }
                logoBmp?.let {
                    Image(
                        bitmap = it.asImageBitmap(),
                        contentDescription = null,
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .align(Alignment.CenterHorizontally)
                            .heightIn(max = 100.dp)
                            .padding(bottom = 6.dp),
                    )
                }
            }

            if (banner?.enabled == true && banner.text.isNotBlank()) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.85f)),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = banner.text,
                        modifier = Modifier.padding(12.dp).fillMaxWidth(),
                        fontWeight = FontWeight.SemiBold,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                }
                Spacer(Modifier.height(12.dp))
            }

            if (games.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        text = "Nessun gioco configurato.\nTieni premuto l'icona in alto per aprire le impostazioni.",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            } else {
                // Griglia auto-adattiva: misura lo spazio reale disponibile e dimensiona le
                // tessere per RIEMPIRE tutto lo schermo, su qualsiasi monitor (proporzioni/
                // risoluzione diverse). Le colonne restano quelle configurate; con columns<=0
                // vengono scelte in automatico per tessere il più possibile quadrate.
                val spacing = 16.dp
                BoxWithConstraints(modifier = Modifier.weight(1f).fillMaxWidth()) {
                    val cols = (if (columns > 0) columns
                                else autoColumns(games.size, maxWidth / maxHeight))
                        .coerceIn(1, games.size)
                    val rows = (games.size + cols - 1) / cols
                    val cellW = (maxWidth - spacing * (cols - 1)) / cols
                    val cellH = (maxHeight - spacing * (rows - 1)) / rows
                    if (cellH >= 96.dp) {
                        // Riempie l'intera area senza scroll: tessere grandi quanto lo spazio.
                        Column(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(spacing, Alignment.CenterVertically),
                        ) {
                            for (r in 0 until rows) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.spacedBy(spacing, Alignment.CenterHorizontally),
                                ) {
                                    for (c in 0 until cols) {
                                        val idx = r * cols + c
                                        if (idx < games.size) {
                                            Box(modifier = Modifier.size(cellW, cellH)) {
                                                GameTile(games[idx], showLabels) { onPlay(games[idx]) }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } else {
                        // Troppi giochi per riempire senza rimpicciolire troppo → griglia scrollabile.
                        LazyVerticalGrid(
                            columns = GridCells.Fixed(cols),
                            horizontalArrangement = Arrangement.spacedBy(spacing),
                            verticalArrangement = Arrangement.spacedBy(spacing),
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            items(games, key = { it.packageName }) { game ->
                                Box(modifier = Modifier.fillMaxWidth().aspectRatio(1f)) {
                                    GameTile(game, showLabels) { onPlay(game) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun GameTile(game: GameApp, showLabel: Boolean, onClick: () -> Unit) {
    // La tessera riempie lo spazio che le dà il chiamante e si auto-misura: icona ed
    // etichetta scalano in proporzione, così resta bella su schermi di ogni dimensione.
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.White)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        val minSide = if (maxWidth < maxHeight) maxWidth else maxHeight
        val iconSize = minSide * (if (showLabel) 0.52f else 0.66f)
        val labelSp = (minSide.value * 0.13f).coerceIn(13f, 26f)

        // Icona: drawable dell'app nativa; per i giochi web carica l'immagine
        // remota (iconUrl) e, se assente, mostra il logo come ripiego.
        var remoteIcon by remember(game.iconUrl) { mutableStateOf<android.graphics.Bitmap?>(null) }
        LaunchedEffect(game.iconUrl) {
            if (game.icon == null && game.iconUrl != null) remoteIcon = RemoteImageLoader.load(game.iconUrl)
        }
        Column(
            modifier = Modifier.padding(minSide * 0.08f),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            when {
                game.icon != null -> AndroidView(
                    factory = { ctx -> ImageView(ctx) },
                    update = { it.setImageDrawable(game.icon) },
                    modifier = Modifier.size(iconSize),
                )
                remoteIcon != null -> Image(
                    bitmap = remoteIcon!!.asImageBitmap(),
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.size(iconSize),
                )
                else -> Image(
                    painter = painterResource(id = R.drawable.logo_fun_planet),
                    contentDescription = null,
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.size(iconSize),
                )
            }
            if (showLabel) {
                Spacer(Modifier.height(minSide * 0.05f))
                Text(
                    text = game.label,
                    fontSize = labelSp.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
            }
        }
    }
}

/** Sceglie il numero di colonne per tessere il più possibile quadrate, dato il numero di
 *  giochi e il rapporto larghezza/altezza dell'area. Usata solo quando columns<=0 (auto). */
private fun autoColumns(count: Int, aspect: Float): Int {
    if (count <= 1) return 1
    var best = 1
    var bestScore = Float.MAX_VALUE
    for (c in 1..count) {
        val r = (count + c - 1) / c
        val tileAspect = (aspect / c) * r          // ~1 = quadrata
        val score = kotlin.math.abs(kotlin.math.ln(tileAspect.toDouble())).toFloat()
        if (score < bestScore) { bestScore = score; best = c }
    }
    return best
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun MaintenanceScreen(
    message: String,
    branding: Branding?,
    onRequestSettings: () -> Unit,
) {
    Box(modifier = Modifier.fillMaxSize()) {
        LauncherBackground(branding)
        // Hidden long-press affordance so an operator can still reach settings.
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .size(64.dp)
                .combinedClickable(onClick = {}, onLongClick = onRequestSettings),
        )
        Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
            Card(colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.9f))) {
                Text(
                    text = message.ifBlank { "Postazione temporaneamente fuori servizio. Torna presto!" },
                    modifier = Modifier.padding(28.dp),
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
            }
        }
    }
}

@Composable
private fun PinEntryScreen(expectedPin: String, onSuccess: () -> Unit, onCancel: () -> Unit) {
    var input by remember { mutableStateOf("") }
    var error by remember { mutableStateOf(false) }

    Dialog(onDismissRequest = onCancel) {
        Card(shape = RoundedCornerShape(20.dp)) {
            Column(modifier = Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Filled.Lock, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(8.dp))
                Text("Area riservata ai genitori", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                Spacer(Modifier.height(16.dp))
                OutlinedTextField(
                    value = input,
                    onValueChange = { if (it.length <= 8) { input = it; error = false } },
                    label = { Text("PIN") },
                    visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                        keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword
                    ),
                    isError = error,
                )
                if (error) {
                    Text("PIN errato", color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                }
                Spacer(Modifier.height(16.dp))
                Row {
                    TextButton(onClick = onCancel) { Text("Annulla") }
                    Spacer(Modifier.width(8.dp))
                    Button(onClick = {
                        if (input == expectedPin) onSuccess() else error = true
                    }) { Text("Entra") }
                }
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    allApps: List<GameApp>,
    selectedPackages: Set<String>,
    currentPin: String,
    remoteControlled: Boolean,
    onToggle: (String, Boolean) -> Unit,
    onChangePin: (String) -> Unit,
    onOpenDiagnostics: () -> Unit,
    onDone: () -> Unit,
) {
    val context = LocalContext.current
    var newPin by remember { mutableStateOf("") }
    val kioskActive = remember { KioskManager.isDeviceOwner(context) }

    Column(modifier = Modifier.fillMaxSize().padding(20.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Impostazioni", fontSize = 28.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = onOpenDiagnostics) { Text("Diagnostica") }
            Spacer(Modifier.width(8.dp))
            Button(onClick = onDone) { Text("Fatto") }
        }
        Spacer(Modifier.height(8.dp))

        Card(
            colors = CardDefaults.cardColors(
                containerColor = if (kioskActive) Color(0xFFE3F5E9) else Color(0xFFFDF0D9),
            ),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(Modifier.padding(12.dp)) {
                Text(
                    text = if (kioskActive) "Modalità Kiosk: ATTIVA" else "Modalità Kiosk: NON ATTIVA",
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = if (kioskActive)
                        "L'app è bloccata a schermo intero: i bambini non possono uscire né aprire altre app."
                    else
                        "Per bloccare davvero l'uscita dall'app, configura questo tablet come dispositivo dedicato (vedi README.md, sezione Modalità Kiosk).",
                    fontSize = 12.sp,
                )
                if (kioskActive) {
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(onClick = {
                        (context as? android.app.Activity)?.let { KioskManager.release(it) }
                    }) { Text("Esci temporaneamente (Impostazioni)") }
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = "Apre le Impostazioni Android per la manutenzione. Per ~5 minuti " +
                            "il kiosk non si riattiva (poi torna da solo). Rientra subito col pulsante qui sotto.",
                        fontSize = 11.sp,
                    )
                    Spacer(Modifier.height(6.dp))
                    OutlinedButton(onClick = {
                        (context as? android.app.Activity)?.let { KioskManager.resume(it) }
                    }) { Text("Rientra in kiosk ora") }
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        if (remoteControlled) {
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFFE7EEFF)),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = "I giochi mostrati sono gestiti da remoto (config.json della flotta). " +
                        "Le selezioni qui sotto restano valide solo come riserva se la configurazione remota non è disponibile.",
                    modifier = Modifier.padding(12.dp),
                    fontSize = 12.sp,
                )
            }
            Spacer(Modifier.height(12.dp))
        }
        Text("Scegli quali giochi mostrare ai bambini:", color = Color.Gray)
        Spacer(Modifier.height(8.dp))

        LazyVerticalGrid(
            columns = GridCells.Fixed(1),
            modifier = Modifier.weight(1f),
        ) {
            items(allApps, key = { it.packageName }) { app ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AndroidView(
                        factory = { ctx -> ImageView(ctx) },
                        update = { it.setImageDrawable(app.icon) },
                        modifier = Modifier.size(40.dp),
                    )
                    Spacer(Modifier.width(12.dp))
                    Text(app.label, modifier = Modifier.weight(1f))
                    Checkbox(
                        checked = app.packageName in selectedPackages,
                        onCheckedChange = { checked -> onToggle(app.packageName, checked) },
                    )
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Text("Cambia PIN genitori (attuale: $currentPin):", color = Color.Gray)
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = newPin,
                onValueChange = { if (it.length <= 8) newPin = it },
                label = { Text("Nuovo PIN") },
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            Button(onClick = {
                if (newPin.isNotBlank()) {
                    onChangePin(newPin)
                    newPin = ""
                }
            }) { Text("Salva") }
        }
    }
}

@Composable
private fun DiagnosticsScreen(
    config: ResolvedConfig?,
    connectionStatus: ConnectionStatus,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val fleetApp = context.applicationContext as FleetApp
    val deviceId = remember { DeviceIdManager.getDeviceId(context) }
    val devicePrefs = remember { DevicePrefs(context) }
    val existingLifeline = remember { devicePrefs.getLifelineWifi() }
    var wifiSsid by remember { mutableStateOf(existingLifeline?.ssid ?: "") }
    var wifiPass by remember { mutableStateOf(existingLifeline?.password ?: "") }
    var wifiSaved by remember { mutableStateOf(false) }
    val appVersion = remember {
        runCatching {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, 0).versionCode
        }.getOrDefault(0)
    }
    val lastTelemetry = remember {
        val millis = devicePrefs.getLastTelemetrySuccessMillis()
        if (millis == 0L) "mai" else SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.ITALY).format(Date(millis))
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp).verticalScroll(rememberScrollState()),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Diagnostica", fontSize = 28.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Button(onClick = onBack) { Text("Indietro") }
        }
        Spacer(Modifier.height(16.dp))

        DiagnosticRow("ID dispositivo", deviceId)
        DiagnosticRow(
            "Cliente / location",
            devicePrefs.getClientId() + (devicePrefs.getLocationId()?.let { " / $it" } ?: ""),
        )
        DiagnosticRow("Etichetta (label)", config?.deviceLabel ?: "— (non assegnata nel config remoto)")
        DiagnosticRow("Versione app", appVersion.toString())
        DiagnosticRow("Versione config attiva", config?.configVersion?.toString() ?: "nessuna")
        DiagnosticRow("Ultimo contatto telemetria", lastTelemetry)
        DiagnosticRow(
            "Stato connessione config",
            if (connectionStatus == ConnectionStatus.ONLINE) "online" else "offline",
        )
        DiagnosticRow("Stato operativo", config?.operational?.status ?: "—")

        // Forza subito un nuovo scaricamento della configurazione (senza aspettare il poll).
        Spacer(Modifier.height(12.dp))
        val cfgScope = rememberCoroutineScope()
        var cfgRefreshMsg by remember { mutableStateOf<String?>(null) }
        var cfgRefreshing by remember { mutableStateOf(false) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(
                enabled = !cfgRefreshing,
                onClick = {
                    cfgRefreshing = true
                    cfgRefreshMsg = "Aggiorno…"
                    cfgScope.launch {
                        withContext(Dispatchers.IO) { runCatching { fleetApp.configRepository.refresh() } }
                        val online = fleetApp.configRepository.connectionStatus.value == ConnectionStatus.ONLINE
                        val v = fleetApp.configRepository.config.value?.configVersion ?: 0
                        cfgRefreshMsg = if (online) "✓ Config v$v (online)" else "Offline: nessuna risposta"
                        cfgRefreshing = false
                    }
                },
            ) { Text(if (cfgRefreshing) "Attendere…" else "Aggiorna config ora") }
            cfgRefreshMsg?.let {
                Spacer(Modifier.width(12.dp))
                Text(it, fontSize = 12.sp)
            }
        }

        Spacer(Modifier.height(20.dp))
        Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFF0F4FF))) {
            Text(
                text = "Comunica al gestore l'ID dispositivo qui sopra per aggiungere o configurare " +
                    "questo monitor nel file config.json della flotta.",
                modifier = Modifier.padding(12.dp),
                fontSize = 12.sp,
            )
        }

        Spacer(Modifier.height(24.dp))
        Text("Wi-Fi di salvataggio (lifeline)", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(
            text = "Rete di riserva memorizzata solo su questo dispositivo (non viene mai inviata online). " +
                "Serve come ancora di salvezza: se il Wi-Fi del locale cambia password, il monitor resta " +
                "raggiungibile su questa rete, scarica la nuova configurazione e si riconnette da solo.",
            fontSize = 12.sp,
            color = Color.Gray,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = wifiSsid,
            onValueChange = { wifiSsid = it; wifiSaved = false },
            label = { Text("Nome rete (SSID)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = wifiPass,
            onValueChange = { wifiPass = it; wifiSaved = false },
            label = { Text("Password (vuota = rete aperta)") },
            visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(
                onClick = {
                    devicePrefs.setLifelineWifi(wifiSsid.trim(), wifiPass, hidden = false)
                    fleetApp.applyWifi()
                    wifiSaved = true
                },
                enabled = wifiSsid.isNotBlank(),
            ) { Text("Salva e applica") }
            if (wifiSaved) {
                Spacer(Modifier.width(12.dp))
                Text("Salvata ✓", color = Color(0xFF2E7D32), fontWeight = FontWeight.SemiBold)
            }
        }

        Spacer(Modifier.height(24.dp))
        Text("Pulsante \"Torna ai giochi\" flottante", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(
            text = "Mostra un pulsante sopra i giochi per tornare alla griglia in qualsiasi momento " +
                "(indispensabile in modalità kiosk, dove il tasto Home è bloccato). Richiede il " +
                "permesso \"Mostra sopra le altre app\".",
            fontSize = 12.sp,
            color = Color.Gray,
        )
        Spacer(Modifier.height(8.dp))
        val overlayOk = FloatingHomeButton.canDraw(context)
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (overlayOk) {
                Text("Permesso attivo ✓", color = Color(0xFF2E7D32), fontWeight = FontWeight.SemiBold)
            } else {
                Button(onClick = {
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + context.packageName),
                    ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    runCatching { context.startActivity(intent) }
                }) { Text("Attiva permesso") }
            }
        }

        Spacer(Modifier.height(24.dp))
        val scope = rememberCoroutineScope()
        val isDeviceOwner = remember { KioskManager.isDeviceOwner(context) }
        var apkUrl by remember { mutableStateOf("") }
        var installing by remember { mutableStateOf(false) }
        var installStatus by remember { mutableStateOf<String?>(null) }

        Text("Installa app (APK da URL)", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Text(
            text = if (isDeviceOwner) {
                "Scarica e installa un APK in modo silenzioso (questo dispositivo è Device Owner). " +
                    "Utile per provare al volo un gioco o un aggiornamento senza PC. Per installare " +
                    "a tutta la flotta, usa invece \"managedApps\" nel config.json."
            } else {
                "⚠ Questo dispositivo NON è Device Owner: l'installazione mostrerà la richiesta di " +
                    "conferma di Android e funziona solo fuori dal kiosk."
            },
            fontSize = 12.sp,
            color = Color.Gray,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = apkUrl,
            onValueChange = { apkUrl = it; installStatus = null },
            label = { Text("URL del file .apk") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Button(
                enabled = apkUrl.isNotBlank() && !installing,
                onClick = {
                    installing = true
                    installStatus = "Download in corso…"
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            ApkInstaller.installFromUrl(context, apkUrl.trim())
                        }
                        installing = false
                        installStatus = if (result.isSuccess) {
                            "Installazione avviata ✓"
                        } else {
                            "Errore: ${result.exceptionOrNull()?.message ?: "sconosciuto"}"
                        }
                    }
                },
            ) { Text(if (installing) "Attendere…" else "Installa") }
            installStatus?.let {
                Spacer(Modifier.width(12.dp))
                Text(it, fontSize = 12.sp)
            }
        }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun DiagnosticRow(label: String, value: String) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Text(label, fontSize = 12.sp, color = Color.Gray)
        Text(value, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        Divider(Modifier.padding(top = 6.dp))
    }
}

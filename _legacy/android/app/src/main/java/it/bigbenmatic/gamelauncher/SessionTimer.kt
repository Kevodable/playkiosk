package it.bigbenmatic.gamelauncher

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Enforces a per-game time limit. When a game is launched [start] is called with the effective
 * limit (seconds); once it elapses the launcher grid is brought back to the front, ending the
 * session. The countdown runs on an application-scoped coroutine so it survives the launcher
 * Activity being in the background while the game is on top. Configured entirely from the remote
 * config (`kiosk.sessionLimitSeconds` globally, or per-game `games[].sessionLimitSeconds`).
 */
object SessionTimer {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var job: Job? = null

    /** Starts (or restarts) the countdown. [seconds] <= 0 disables the limit. */
    fun start(context: Context, seconds: Int) {
        cancel()
        if (seconds <= 0) return
        val app = context.applicationContext
        job = scope.launch {
            delay(seconds * 1000L)
            FloatingHomeButton.returnToGrid(app)
        }
    }

    /** Stops the countdown (e.g. when we are already back on the grid). */
    fun cancel() {
        job?.cancel()
        job = null
    }
}

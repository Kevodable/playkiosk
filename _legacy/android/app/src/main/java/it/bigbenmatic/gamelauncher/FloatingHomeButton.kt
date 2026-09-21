package it.bigbenmatic.gamelauncher

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import kotlin.math.abs

/**
 * A small "back to games" button drawn on top of any running game via the draw-over-other-apps
 * overlay. Tapping it brings the launcher grid back to the front — essential in kiosk mode where
 * Home/Back are blocked, and handy everywhere else. Draggable so it can be moved off a game's
 * own controls. Completely no-op if the overlay permission has not been granted.
 */
object FloatingHomeButton {

    private var view: View? = null

    /** Whether the draw-over-other-apps permission is available (always true before Android 6). */
    fun canDraw(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(context)

    /** Shows the floating button (idempotent). Safe to call when already visible or unpermitted. */
    fun show(context: Context) {
        val ctx = context.applicationContext
        if (view != null || !canDraw(ctx)) return
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dp = { v: Float -> TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, ctx.resources.displayMetrics) }

        val button = TextView(ctx).apply {
            text = "🏠 Giochi"
            setTextColor(Color.WHITE)
            textSize = 16f
            setPadding(dp(16f).toInt(), dp(10f).toInt(), dp(16f).toInt(), dp(10f).toInt())
            background = GradientDrawable().apply {
                cornerRadius = dp(28f)
                setColor(Color.parseColor("#E63346D6"))
            }
        }

        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = dp(16f).toInt()
            y = dp(16f).toInt()
        }

        // Distinguish a tap (return to grid) from a drag (reposition the button).
        button.setOnTouchListener(object : View.OnTouchListener {
            private var downX = 0f
            private var downY = 0f
            private var startX = 0
            private var startY = 0
            private var dragged = false

            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.action) {
                    MotionEvent.ACTION_DOWN -> {
                        downX = e.rawX; downY = e.rawY
                        startX = params.x; startY = params.y
                        dragged = false
                    }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = (e.rawX - downX).toInt()
                        val dy = (e.rawY - downY).toInt()
                        if (abs(dx) > 12 || abs(dy) > 12) dragged = true
                        params.x = startX + dx
                        params.y = startY + dy
                        runCatching { wm.updateViewLayout(v, params) }
                    }
                    MotionEvent.ACTION_UP -> {
                        if (!dragged) {
                            v.performClick()
                            returnToGrid(ctx)
                        }
                    }
                }
                return true
            }
        })

        runCatching {
            wm.addView(button, params)
            view = button
        }
    }

    /** Removes the floating button if present. */
    fun hide(context: Context) {
        val v = view ?: return
        val wm = context.applicationContext.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        runCatching { wm.removeView(v) }
        view = null
    }

    /** Brings the launcher grid back to the foreground. Shared by the floating button and the
     *  session-limit timer. */
    fun returnToGrid(context: Context) {
        val intent = Intent(context.applicationContext, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        runCatching { context.applicationContext.startActivity(intent) }
    }
}

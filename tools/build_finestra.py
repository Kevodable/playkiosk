"""Cornice-finestra del menu: tools/art/finestra_menu.png (Scenario) ->
kiosk/tenants/default/assets/window.webp (1920x1080, centro trasparente).

L'arte arriva con alpha quasi binaria (telaio >=230, apertura <50) e residui
magenta nell'apertura: soglia, pulizia dei puntini (apri/chiudi), bordo
ammorbidito di 1px. Stampa l'apertura misurata (contentBox in %) da copiare
nel config del tenant.
"""
from PIL import Image, ImageFilter
import numpy as np

SRC = "tools/art/finestra_menu.png"
OUT = "kiosk/tenants/default/assets/window.webp"
W, H = 1920, 1080

im = Image.open(SRC).convert("RGBA").resize((W, H), Image.LANCZOS)
rgb = im.convert("RGB")
a = np.array(im)[..., 3]
mask = Image.fromarray(((a > 128) * 255).astype("uint8"))
# chiudi i buchini nel telaio, poi togli i puntini nell'apertura
mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
mask = mask.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))
mask = mask.filter(ImageFilter.GaussianBlur(0.8))
out = rgb.copy()
out.putalpha(mask)
out.save(OUT, quality=90, method=6)

m = np.array(mask) > 128
cy, cx = H // 2, W // 2
row, col = m[cy], m[:, cx]
left = cx - np.argmax(row[cx::-1])      # primo pixel di telaio a sinistra
right = cx + np.argmax(row[cx:])
top = cy - np.argmax(col[cy::-1])
bottom = cy + np.argmax(col[cy:])
print("apertura px: x %d..%d  y %d..%d" % (left, right, top, bottom))
print("contentBox %%: top %.1f bottom %.1f left %.1f right %.1f" % (
    100 * (top + 1) / H, 100 * (H - bottom) / H,
    100 * (left + 1) / W, 100 * (W - right) / W))

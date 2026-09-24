"""Cornice-finestra del menu, v2 (persiane di legno aperte, davanzale coi vasi):
tools/art/finestra_menu_v2.png (Scenario, 1672x941 RGB, apertura magenta
piena) -> kiosk/tenants/default/assets/window-v2.webp (1920x1080).

1. scontorno del magenta (distanza dal colore campionato, bordo morbido);
2. la banda centrale del telaio (solo assi lisce: architrave e davanzale,
   lontano da vasi e cerniere) viene allargata di STRETCH, cosi' l'apertura
   diventa piu' "16:9";
3. ritaglio centrato 16:9 dall'alto CROP_TOP al basso CROP_BOTTOM: persiane
   e davanzale escono in parte dallo schermo ("zoom"), ma restano cornice.
Stampa l'apertura misurata (contentBox in %) da mettere nel config.
"""
from PIL import Image
import numpy as np

SRC = "tools/art/finestra_menu_v2.png"
OUT = "kiosk/tenants/default/assets/window-v2.webp"
W, H = 1920, 1080
KEY = np.array([231, 79, 251])     # magenta campionato nell'apertura
D0, D1 = 40, 90                    # distanza: <D0 trasparente, >D1 pieno
BAND = (440, 1230)                 # banda allargabile (x sorgente)
STRETCH = 1.31
CROP_TOP, CROP_BOTTOM = 100, 875   # y sorgente visibili

src = Image.open(SRC).convert("RGB")
rgb = np.array(src).astype(float)
d = np.linalg.norm(rgb - KEY, axis=2)
alpha = np.clip((d - D0) / (D1 - D0), 0, 1)
# de-spill: sul bordo morbido togli la tinta magenta verso il colore pieno
rgb = np.where(alpha[..., None] < 1, rgb * alpha[..., None] + (1 - alpha[..., None]) * rgb.min(axis=2, keepdims=True), rgb)
img = Image.fromarray(np.dstack([rgb, alpha * 255]).astype("uint8"))

sw, sh = img.size
left = img.crop((0, 0, BAND[0], sh))
mid = img.crop((BAND[0], 0, BAND[1], sh))
right = img.crop((BAND[1], 0, sw, sh))
mw = round(mid.width * STRETCH)
wide = Image.new("RGBA", (left.width + mw + right.width, sh))
wide.paste(left, (0, 0))
wide.paste(mid.resize((mw, sh), Image.LANCZOS), (left.width, 0))
wide.paste(right, (left.width + mw, 0))

ch = CROP_BOTTOM - CROP_TOP
cw = round(ch * W / H)
x0 = (wide.width - cw) // 2
out = wide.crop((x0, CROP_TOP, x0 + cw, CROP_BOTTOM)).resize((W, H), Image.LANCZOS)
out.save(OUT, quality=90, method=6)

m = np.array(out)[..., 3] > 128
cy, cx = H // 2, W // 2
row, col = m[cy], m[:, cx]
l = cx - np.argmax(row[cx::-1]); r = cx + np.argmax(row[cx:])
t = cy - np.argmax(col[cy::-1]); b = cy + np.argmax(col[cy:])
print("crop x0 %d larghezza %d (immagine allargata %d)" % (x0, cw, wide.width))
print("apertura px: x %d..%d  y %d..%d  (%dx%d)" % (l, r, t, b, r - l - 1, b - t - 1))
print("contentBox %%: top %.1f bottom %.1f left %.1f right %.1f" % (
    100 * (t + 1) / H, 100 * (H - b) / H, 100 * (l + 1) / W, 100 * (W - r) / W))

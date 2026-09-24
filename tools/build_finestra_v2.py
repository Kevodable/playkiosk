"""Cornice-finestra del menu, v2 (dall'arte con persiane aperte e vasi, che
qui vengono tolti: resta architrave, stipiti, davanzale):
tools/art/finestra_menu_v2.png (Scenario, 1672x941 RGB, apertura magenta
piena) -> kiosk/tenants/default/assets/window-v2.webp (1920x1080).

1. scontorno del magenta (distanza dal colore campionato, bordo morbido);
2. via le cerniere (ricoperte con lo stipite);
3. la banda centrale del telaio (solo assi lisce: architrave e davanzale,
   lontano dai vasi) viene allargata quanto serve perche' il bordo schermo
   cada a SIDE_L/SIDE_R, subito dentro le persiane (fuori del tutto);
4. via i vasi coi fiori (zona ricostruita da stipite e fasce orizzontali);
5. ritaglio 16:9 da CROP_TOP a CROP_BOTTOM: cornice = architrave, stipiti,
   davanzale.
Stampa l'apertura misurata (contentBox in %) da mettere nel config.
"""
from PIL import Image, ImageFilter
import numpy as np

SRC = "tools/art/finestra_menu_v2.png"
OUT = "kiosk/tenants/default/assets/window-v2.webp"
W, H = 1920, 1080
KEY = np.array([231, 79, 251])     # magenta campionato nell'apertura
D0, D1 = 40, 90                    # distanza: <D0 trasparente, >D1 pieno
BAND = (440, 1230)                 # banda allargabile (x sorgente)
SIDE_L, SIDE_R = 310, 1359         # x sorgente dei bordi schermo: subito dentro
                                   # il profilo delle persiane (via del tutto);
                                   # l'allargamento della banda si ricava da qui
# cerniere sullo stipite: (x0, x1, y0, y1, y_vaso) misurate sull'originale;
# sopra y_vaso si ricopre tutto, dal vaso in giu' solo ferro e contorni
HINGES = [(309, 337, 200, 302, 999), (309, 337, 625, 732, 690),
          (1333, 1359, 200, 302, 999), (1333, 1359, 625, 732, 683)]
JAMB_Y = 450                       # riga di stipite pulito da cui ricopiare
CROP_TOP, CROP_BOTTOM = 100, 875   # y sorgente visibili

src = Image.open(SRC).convert("RGB")
rgb = np.array(src).astype(float)
d = np.linalg.norm(rgb - KEY, axis=2)
alpha = np.clip((d - D0) / (D1 - D0), 0, 1)
# de-spill: sul bordo morbido togli la tinta magenta verso il colore pieno
rgb = np.where(alpha[..., None] < 1, rgb * alpha[..., None] + (1 - alpha[..., None]) * rgb.min(axis=2, keepdims=True), rgb)
# via le cerniere: ricoperte con lo stipite della stessa colonna (riga
# JAMB_Y); dove c'e' il vaso solo ferro e contorni, foglie e fiori restano.
for x0, x1, y0, y1, ypot in HINGES:
    blk = rgb[y0:y1, x0:x1]
    jamb = np.broadcast_to(rgb[JAMB_Y, x0:x1], blk.shape)
    ys = np.arange(y0, y1)[:, None]
    green = blk[..., 1] > blk[..., 0] + 10
    light = blk.max(axis=2) > 190
    iron = ~(green | light)
    hm = Image.fromarray((iron * 255).astype("uint8")).filter(ImageFilter.MaxFilter(3))
    iron = (np.array(hm) > 0) & ~green
    repl = (ys < ypot) | iron
    blk[repl] = jamb[repl]
# via i vasi coi fiori: la zona si ricostruisce con cio' che c'e' dietro.
# Stipite (e suo profilo teal) = riga JAMB_Y della stessa colonna; apertura,
# profilo inferiore, battuta e davanzale = stessa riga, 150 px verso il
# centro (sono fasce orizzontali uniformi). Misure sull'originale.
POT_Y0, RAIL_Y, SILL_Y, POT_Y1 = 640, 764, 785, 812
def fill_jamb(xa, xb, ya, yb):
    rgb[ya:yb, xa:xb] = rgb[JAMB_Y, xa:xb]
    alpha[ya:yb, xa:xb] = alpha[JAMB_Y, xa:xb]
def fill_shift(xa, xb, ya, yb, dx):
    rgb[ya:yb, xa:xb] = rgb[ya:yb, xa + dx:xb + dx]
    alpha[ya:yb, xa:xb] = alpha[ya:yb, xa + dx:xb + dx]
# sinistra: stipite 309-358, profilo 358-367, apertura da 367
fill_jamb(309, 358, POT_Y0, SILL_Y)
fill_jamb(358, 367, POT_Y0, RAIL_Y)
fill_shift(358, 367, RAIL_Y, SILL_Y, 150)
fill_shift(367, 440, POT_Y0, POT_Y1, 150)
fill_shift(309, 367, SILL_Y, POT_Y1, 150)
# destra: apertura fino a 1302, profilo 1303-1312, stipite 1312-1363
fill_jamb(1312, 1363, POT_Y0, SILL_Y)
fill_jamb(1303, 1312, POT_Y0, RAIL_Y)
fill_shift(1303, 1312, RAIL_Y, SILL_Y, -150)
fill_shift(1232, 1303, POT_Y0, POT_Y1, -150)
fill_shift(1303, 1363, SILL_Y, POT_Y1, -150)

img = Image.fromarray(np.dstack([rgb, alpha * 255]).astype("uint8"))

sw, sh = img.size
left = img.crop((0, 0, BAND[0], sh))
mid = img.crop((BAND[0], 0, BAND[1], sh))
right = img.crop((BAND[1], 0, sw, sh))
ch = CROP_BOTTOM - CROP_TOP
cw = round(ch * W / H)
mw = cw - (SIDE_R - SIDE_L) + mid.width
wide = Image.new("RGBA", (left.width + mw + right.width, sh))
wide.paste(left, (0, 0))
wide.paste(mid.resize((mw, sh), Image.LANCZOS), (left.width, 0))
wide.paste(right, (left.width + mw, 0))

x0 = SIDE_L
out = wide.crop((x0, CROP_TOP, x0 + cw, CROP_BOTTOM)).resize((W, H), Image.LANCZOS)
out.save(OUT, quality=90, method=6)

m = np.array(out)[..., 3] > 128
cy, cx = H // 2, W // 2
row, col = m[cy], m[:, cx]
l = cx - np.argmax(row[cx::-1]); r = cx + np.argmax(row[cx:])
t = cy - np.argmax(col[cy::-1]); b = cy + np.argmax(col[cy:])
print("crop x0 %d larghezza %d, banda allargata x%.3f" % (x0, cw, mw / mid.width))
print("apertura px: x %d..%d  y %d..%d  (%dx%d)" % (l, r, t, b, r - l - 1, b - t - 1))
print("contentBox %%: top %.1f bottom %.1f left %.1f right %.1f" % (
    100 * (t + 1) / H, 100 * (H - b) / H, 100 * (l + 1) / W, 100 * (W - r) / W))

"""Cut the in-game sprites for kiosk/games/sequenza from the sequenza icon art.

  pinguino.webp        the penguin, whole (raised flipper pointing at the panel)
  pannello.webp        the cream panel with four empty sockets
  tasto_<colore>.webp  the four glossy buttons, squared up
Prints JSON: flipper tip (fraction of pinguino.webp), used as the pointer origin.
Usage: python3 build_sequenza_sprites.py <out dir>   (art from tools/art/sequenza.png)
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from iconkit import load_cutout, layer, mask_box, mask_ellipse, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "sequenza.png"))
H, W = px.shape[:2]
xx = np.arange(W)[None, :]

# --- geometry measured on the 1104x832 source (see build_sequenza.py)
BUTTONS = {"blu": (699, 369), "rosso": (915, 370), "verde": (700, 580), "giallo": (914, 580)}
R = 74
PANEL = (589, 262, 1014, 681)
SOCKET = (226, 216, 200)
TIP = (574, 336)                 # tip of the raised flipper
PENGUIN_SEED = (300, 560)

# the panel's faint top edge breaks the flood fill: force it opaque
x0, y0, x1, y1 = PANEL
rgba[y0:y1, x0:x1, :3] = px[y0:y1, x0:x1]
rgba[y0:y1, x0:x1, 3] = 255

def crop(mask, pad):
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1

def save(arr, mask, name, box=None, square=None):
    box = box or crop(mask, 3)
    im = to_img(layer(arr, mask)).crop(box)
    if square:
        side = max(im.size)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
        im = sq.resize((square, square), Image.LANCZOS)
    im.save(os.path.join(OUT, name), "WEBP", quality=92, method=6)
    return box

alpha = rgba[..., 3] > 0
# buttons
btn_m = {}
for name, (bx, by) in BUTTONS.items():
    m = mask_ellipse(px.shape, (bx - R - 6, by - R - 6, bx + R + 6, by + R + 8)) & alpha
    btn_m[name] = m
    save(rgba, m, f"tasto_{name}.webp", square=192)
# panel with empty sockets
panel = rgba.copy()
img = to_img(panel)
d = ImageDraw.Draw(img)
for bx, by in BUTTONS.values():
    d.ellipse((bx - R - 6, by - R - 6, bx + R + 6, by + R + 8), fill=SOCKET + (255,))
panel = np.array(img).astype(float)
panel_m = mask_box(px.shape, (x0 - 6, y0 - 6, x1 + 6, y1 + 8)) & (panel[..., 3] > 0)
save(panel, panel_m, "pannello.webp")

# penguin, whole (its raised flipper already points at the panel)
peng_m = connected(alpha & (xx < x0 - 10), PENGUIN_SEED)
box = save(rgba, peng_m, "pinguino.webp")

bx0, by0, bx1, by1 = box
f = lambda p: [round((p[0] - bx0) / (bx1 - bx0), 4), round((p[1] - by0) / (by1 - by0), 4)]
print(json.dumps({"pinguino": box, "punta": f(TIP),
                  "pannello": crop(panel_m, 3)}))

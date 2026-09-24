"""Cut the in-game sprites for kiosk/games/tris from the tris icon art.

  rana.webp        the frog, whole (grid bars and ground shadow excluded)
  gettone_x.webp   the red X token, squared up
  gettone_o.webp   the blue O token, squared up
The grid is drawn in the game (purple rounded bars, like the icon).
Usage: python3 build_tris_sprites.py <out dir>   (art from tools/art/tris.png)
"""
import os, sys
import numpy as np
from PIL import Image
from iconkit import load_cutout, layer, mask_box, connected, dilate, erode, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
POCKETS = [(648, 442), (818, 442), (648, 627), (818, 627), (648, 690), (818, 690),
           (965, 442), (965, 627), (522, 442), (522, 620), (522, 690), (648, 300), (818, 300)]
px, rgba = load_cutout(os.path.join(HERE, "art", "tris.png"), seeds=POCKETS)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
alpha = rgba[..., 3] > 0

# --- geometry measured on the 1104x832 source (see build_tris.py)
X_BOX, O_BOX = (500, 98, 648, 252), (736, 82, 922, 264)
FROG_SEED = (330, 560)
O_HOLE = (829, 173)                # centre of the O's hole

def crop(mask, pad):
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1

def square(mask, name, size=240):
    im = to_img(layer(rgba, mask)).crop(crop(mask, 3))
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
    sq.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, name), "WEBP", quality=92, method=6)

green = (g > r + 15) & (g > b + 15)
purple = (b > g + 30) & (r > g + 15) & (px.max(axis=2) < 235)       # grid bars
shadow = (yy > 690) & ~green & (np.abs(g - b) < 22) & (b > r)
x_m = mask_box(px.shape, X_BOX) & alpha
bar_edge = mask_box(px.shape, (540, 240, 612, 340)) & ~green      # outline of the grid bar near the hand
cand = alpha & ~purple & ~shadow & ~x_m & ~bar_edge & (xx < 640)
frog_m = connected(cand, FROG_SEED)
# drop thin slivers (a 2 px bit of outline stuck to the hand): open with a 3 px radius
frog_m = dilate(connected(erode(frog_m, 3), FROG_SEED), 3) & frog_m
frog_m = alpha & ~connected(~frog_m, (0, 0))          # take back enclosed holes
to_img(layer(rgba, frog_m)).crop(crop(frog_m, 3)).save(os.path.join(OUT, "rana.webp"), "WEBP", quality=92, method=6)

square(connected(x_m, (574, 175)) | (x_m & ~frog_m), "gettone_x.webp")
o_m = mask_box(px.shape, O_BOX) & alpha
white = px.min(axis=2) > 225
o_m &= ~connected(white & mask_box(px.shape, O_BOX), O_HOLE)   # the hole of the O is see-through
square(o_m, "gettone_o.webp")
print("ok")

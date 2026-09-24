"""Cut the in-game sprite for kiosk/games/lavagna from the lavagna icon art.

  gattino.webp   the kitten holding its chalk (board, tray and sticks excluded)
The board, the chalk sticks, the outlines to trace and the stamps are drawn
in the game. Mask logic shared with build_lavagna.py (the animated icon).
Usage: python3 build_lavagna_sprites.py <out dir>   (art from tools/art/lavagna.png)
"""
import os, sys
import numpy as np
from iconkit import load_cutout, layer, mask_box, dilate, erode, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "lavagna.png"),
                       seeds=[(650, 620), (480, 610), (600, 600), (700, 600), (760, 630)])
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)

green = (g > r + 15) & (g > b) & (px.max(axis=2) < 170)
wood = (r > 120) & (g < 170) & (b >= 55) & (b < 120) & ((r - g) > 30) & ((r - g) < 85)
shadow = (yy > 630) & (sat < 45) & (r > 170)
fur = (r > 195) & (b < 110) & (g > 70) & (g < 215)
cream = (r > 235) & (g > 205) & (b > 120) & (b < 215)
pinkish = (r > 200) & (g < 190) & (b > 110) & (r - g > 40)
chalk_white = (px.min(axis=2) > 205)
alpha = rgba[..., 3] > 0
core = (fur | cream | pinkish | chalk_white) & ~wood & ~green & alpha & (xx < 600) & ~mask_box(px.shape, (740, 440, 880, 570))
m = connected(dilate(core, 4) & ~green & ~wood & alpha & ~shadow, (300, 500))
m = alpha & ~connected(~m, (0, 0)) & ~shadow
m |= (xx < 388) & alpha & ~shadow
m = connected(m, (300, 500))
# drop thin slivers of the board frame stuck to the ear/body: open with a 3 px radius
m = dilate(connected(erode(m, 3), (300, 500)), 3) & m
m = alpha & ~connected(~m, (0, 0))
ys, xs = np.nonzero(m)
to_img(layer(rgba, m)).crop((int(xs.min()) - 3, int(ys.min()) - 3, int(xs.max()) + 4, int(ys.max()) + 4)) \
    .save(os.path.join(OUT, "gattino.webp"), "WEBP", quality=92, method=6)
print("ok")

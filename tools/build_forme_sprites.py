"""Cut the in-game sprite for kiosk/games/forme from the forme icon art.

  coniglio.webp   the bunny, whole (ground shadow excluded)
The board and the shape blocks are drawn as vectors in the game (7 shapes,
the icon only has 3). Usage:
  python3 build_forme_sprites.py <out dir>   (art from tools/art/forme.png)
"""
import os, sys
import numpy as np
from iconkit import load_cutout, layer, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "forme.png"))
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)

BOARD_X = 505                                  # the bunny is left of the board
shadow = (yy > 725) & (b > g) & (r > g) & (sat < 45)
m = connected((rgba[..., 3] > 0) & ~shadow & (xx < BOARD_X), (300, 500))
m = (rgba[..., 3] > 0) & ~connected(~m, (0, 0))   # take back enclosed holes (eyes)
ys, xs = np.nonzero(m)
to_img(layer(rgba, m)).crop((int(xs.min()) - 3, int(ys.min()) - 3, int(xs.max()) + 4, int(ys.max()) + 4)) \
    .save(os.path.join(OUT, "coniglio.webp"), "WEBP", quality=92, method=6)
print("ok")

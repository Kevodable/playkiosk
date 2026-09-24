"""Cut the in-game sprite for kiosk/games/hanoi from the hanoi icon art.

  elefante.webp   the baby elephant, whole (ground shadow excluded)
Pegs and rings are drawn as vectors in the game (3 to 5 rings of any size).
Usage: python3 build_hanoi_sprites.py <out dir>   (art from tools/art/hanoi.png)
"""
import os, sys
import numpy as np
from iconkit import load_cutout, layer, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "hanoi.png"))
H, W = px.shape[:2]
r = px[..., 0]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)

ELEPHANT_X = 470                             # the elephant is left of the board
SEED = (300, 560)
shadow = (yy > 700) & (sat < 40) & (r < 225) & (r > 150)
m = connected((rgba[..., 3] > 0) & ~shadow & (xx < ELEPHANT_X), SEED)
m = (rgba[..., 3] > 0) & ~connected(~m, (0, 0))       # take back enclosed holes
ys, xs = np.nonzero(m)
to_img(layer(rgba, m)).crop((int(xs.min()) - 3, int(ys.min()) - 3, int(xs.max()) + 4, int(ys.max()) + 4)) \
    .save(os.path.join(OUT, "elefante.webp"), "WEBP", quality=92, method=6)
print("ok")

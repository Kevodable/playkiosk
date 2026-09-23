"""Cut the in-game sprites for kiosk/games/labirinto from the labirinto icon art.

  topo.webp       the mouse, whole (pointing hand included)
  formaggio.webp  the cheese wedge, squared up
Usage: python3 build_labirinto_sprites.py <out dir>   (art from tools/art/labirinto.png)
"""
import os, sys
import numpy as np
from PIL import Image
from iconkit import load_cutout, layer, mask_box, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "labirinto.png"))
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)
alpha = rgba[..., 3] > 0

# --- geometry measured on the 1104x832 source (see build_labirinto.py)
CHEESE = (738, 158, 902, 298)
MAZE_X = 356                       # the maze starts here; the mouse is left of it

def crop(mask, pad):
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1

# mouse: everything left of the maze + its hand over the wall (greys, whites,
# pinks - not the teal wall); ground shadow excluded
shadow = (yy > 700) & (sat < 40) & (r > 150) & (r < 225)
teal = (g > r + 12) & (b > r + 5)                       # maze walls
wall_light = (b >= r) & (px.min(axis=2) > 200)          # the maze's pale bluish rim
cream = ((r - b) > 22) & (px.min(axis=2) > 140) & (sat < 90) & ~((r > g + 40) & (r > b))   # corridor
cand = alpha & ~shadow & ~teal & ~wall_light & ~cream & (xx < 440)
mouse_m = connected(cand, (270, 560))
# eye whites and teeth look like the pale rim: take back every hole enclosed by the mouse
mouse_m = alpha & ~connected(~mouse_m, (0, 0))
to_img(layer(rgba, mouse_m)).crop(crop(mouse_m, 3)).save(os.path.join(OUT, "topo.webp"), "WEBP", quality=92, method=6)

cheese_m = mask_box(px.shape, CHEESE) & (((r > 200) & (g > 110) & (b < 140) & (r > b + 80)) | ((r > 150) & (g < 120) & (b < 80)))
im = to_img(layer(rgba, cheese_m)).crop(crop(cheese_m, 3))
side = max(im.size)
sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
sq.resize((192, 192), Image.LANCZOS).save(os.path.join(OUT, "formaggio.webp"), "WEBP", quality=92, method=6)
print("ok")

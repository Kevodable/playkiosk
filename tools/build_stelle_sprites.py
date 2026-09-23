"""Cut the in-game sprites for kiosk/games/stelle from the stelle icon art.

  volpe.webp        the fox holding its basket (stars and sparkles removed)
  stella_<n>.webp   the icon's smiling stars, each squared up
Prints JSON with the basket mouth and the catch zone as fractions of
volpe.webp.
Usage: python3 build_stelle_sprites.py <out dir>   (art from tools/art/stelle.png)
"""
import json, os, sys
import numpy as np
from PIL import Image
from iconkit import load_cutout, layer, mask_box, dilate, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(os.path.join(HERE, "art", "stelle.png"))
H, W = px.shape[:2]
alpha = rgba[..., 3] > 0

# --- geometry measured on the 1104x832 source (see build_stelle.py)
STARS = [(354, 112, 472, 226), (523, 34, 605, 114), (582, 178, 700, 291), (317, 306, 401, 390)]
FOX_SEED = (545, 700)
BASKET_MOUTH = (542, 624)          # centre of the basket rim
CATCH_X = (455, 640)               # fox body width: generous catch zone for kids

def crop(mask, pad):
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1

stars_m = np.zeros((H, W), bool)
for i, box in enumerate(STARS):
    m = dilate(mask_box(px.shape, box), 4) & alpha
    stars_m |= m
    im = to_img(layer(rgba, m)).crop(crop(m, 3))
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
    sq.resize((192, 192), Image.LANCZOS).save(os.path.join(OUT, f"stella_{i}.webp"), "WEBP", quality=92, method=6)

fox_m = connected(alpha & ~stars_m, FOX_SEED)
box = crop(fox_m, 3)
to_img(layer(rgba, fox_m)).crop(box).save(os.path.join(OUT, "volpe.webp"), "WEBP", quality=92, method=6)
x0, y0, x1, y1 = box
fx = lambda x: round((x - x0) / (x1 - x0), 4)
fy = lambda y: round((y - y0) / (y1 - y0), 4)
print(json.dumps({"volpe": box, "bocca_cesto": [fx(BASKET_MOUTH[0]), fy(BASKET_MOUTH[1])],
                  "presa_x": [fx(CATCH_X[0]), fx(CATCH_X[1])]}))

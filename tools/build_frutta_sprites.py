"""Cut the in-game sprites for kiosk/games/frutta from the frutta icon art.

Outputs (webp, transparent) into the given folder:
  panda.webp    the ninja panda, holding its sword as in the icon
  spada.webp    the same sword alone (it appears under the child's finger)
  mela.webp, arancia.webp, kiwi.webp   the three fruits (sticker look)
Prints JSON with the sword anchor points (fractions of spada.webp): blade
centre, blade tip and hilt.
Usage: python3 build_frutta_sprites.py <icon source image> <out dir>
"""
import json, os, sys
import numpy as np
from iconkit import load_cutout, layer, mask_poly, mask_ellipse, connected, to_img

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
opaque = rgba[..., 3] > 0

# --- geometry measured on the 1104x832 source (see build_frutta.py)
BLADE = [(100, 150), (140, 152), (246, 366), (236, 382), (200, 411), (186, 417),
         (177, 421), (70, 300), (66, 262)]
HANDLE = [(252, 362), (283, 385), (229, 491), (185, 468)]
FRUITS = {"mela": (688, 78, 887, 297), "arancia": (663, 458, 837, 642), "kiwi": (810, 316, 982, 480)}
TIP, HILT, BLADE_MID = (110, 165), (207, 478), (165, 300)
PANDA_SEED = (300, 560)

def save(arr, name, pad=3):
    a = arr[..., 3] > 0
    ys, xs = np.nonzero(a)
    box = tuple(int(v) for v in (xs.min() - pad, ys.min() - pad, xs.max() + pad + 1, ys.max() + pad + 1))
    to_img(arr).crop(box).save(os.path.join(OUT, name), "WEBP", quality=92, method=6)
    return box

sword_m = mask_poly(px.shape, BLADE) | mask_poly(px.shape, HANDLE)
fruit_m = np.zeros((H, W), bool)
boxes = {}
for name, box in FRUITS.items():
    m = mask_ellipse(px.shape, box) & opaque
    fruit_m |= m
    boxes[name] = save(layer(rgba, m), f"{name}.webp")

boxes["spada"] = save(layer(rgba, sword_m & opaque), "spada.webp")

# the panda keeps its own sword (as in the icon); only the fruits go
panda = layer(rgba, opaque & ~fruit_m)
keep = connected(panda[..., 3] > 0, PANDA_SEED) & (np.arange(W)[None, :] < 650)
panda[~keep, 3] = 0
boxes["panda"] = save(panda, "panda.webp")

def frac(pt, box):
    x0, y0, x1, y1 = box
    return [round((pt[0] - x0) / (x1 - x0), 4), round((pt[1] - y0) / (y1 - y0), 4)]

sb = boxes["spada"]
print(json.dumps({"boxes": boxes,
                  "spada": {"punta": frac(TIP, sb), "elsa": frac(HILT, sb), "centro": frac(BLADE_MID, sb)}}))

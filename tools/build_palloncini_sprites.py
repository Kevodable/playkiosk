"""Cut the in-game sprites for kiosk/games/palloncini from the palloncini icon art.

Outputs (webp, transparent) into the given folder:
  palloncino_<colore>.webp  the icon's red balloon (the biggest and sharpest)
                            and hue-shifted copies of it; the dark outline
                            and white highlights are low-saturation, so they
                            are left untouched
  orsetto.webp              the bear without balloons and strings
Prints JSON with the knot position (fraction of the balloon sprite), where
the game hangs the string.
Usage: python3 build_palloncini_sprites.py <icon source image> <out dir>
"""
import colorsys, json, os, sys
import numpy as np
from iconkit import load_cutout, layer, mask_box, mask_ellipse, connected, to_img

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
opaque = rgba[..., 3] > 0

# --- geometry measured on the 1104x832 source (see build_palloncini.py)
BALLOONS = {"red": ((270, 20, 494, 282), (362, 262, 404, 296)),
            "yellow": ((520, 40, 628, 160), (556, 148, 590, 171)),
            "purple": ((650, 94, 810, 280), (714, 266, 748, 293))}
STRINGS = [(372, 296, 394, 594), (374, 662, 392, 694), (719, 293, 743, 490), (561, 171, 583, 318)]
KNOT = (383, 296)                      # bottom of the red balloon's knot
# target hue (degrees) and brightness boost for each colour
COLOURS = {"rosso": None, "giallo": (48, 1.25), "blu": (212, 1.0), "verde": (122, .88),
           "viola": (278, 1.0), "arancio": (26, 1.15), "rosa": (330, 1.1)}

def crop_save(arr, name, pad=3):
    a = arr[..., 3] > 0
    ys, xs = np.nonzero(a)
    box = tuple(int(v) for v in (xs.min() - pad, ys.min() - pad, xs.max() + pad + 1, ys.max() + pad + 1))
    to_img(arr).crop(box).save(os.path.join(OUT, name), "WEBP", quality=92, method=6)
    return box

body, knot = BALLOONS["red"]
red = layer(rgba, (mask_ellipse(px.shape, body) | mask_box(px.shape, knot)) & opaque)

def recolour(arr, hue, boost):
    out = arr.copy()
    a = arr[..., 3] > 0
    rgb = arr[..., :3] / 255
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    target = a & (sat > .12) & (mx > .3)          # the rubber (also its pale edges), not outline/highlights
    ys, xs = np.nonzero(target)
    for y, x in zip(ys, xs):
        h, s, v = colorsys.rgb_to_hsv(*rgb[y, x])
        r, g, b = colorsys.hsv_to_rgb(hue / 360, s, min(1, v * boost))
        out[y, x, :3] = (r * 255, g * 255, b * 255)
    return out

boxes = {}
for name, spec in COLOURS.items():
    arr = red if spec is None else recolour(red, *spec)
    boxes[name] = crop_save(arr, f"palloncino_{name}.webp")

taken = np.zeros((H, W), bool)
for body_box, knot_box in BALLOONS.values():
    taken |= mask_ellipse(px.shape, body_box) | mask_box(px.shape, knot_box)
for s in STRINGS:
    taken |= mask_box(px.shape, s)
bear = layer(rgba, connected(opaque & ~taken, (560, 650)))   # drops the loose sparkles
boxes["orsetto"] = crop_save(bear, "orsetto.webp")

bx0, by0, bx1, by1 = boxes["rosso"]
print(json.dumps({"boxes": boxes,
                  "nodo": [round((KNOT[0] - bx0) / (bx1 - bx0), 4), round((KNOT[1] - by0) / (by1 - by0), 4)]}))

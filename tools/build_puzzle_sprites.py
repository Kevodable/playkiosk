"""Build the images for kiosk/games/puzzle.

  tartaruga.webp        the turtle of the puzzle icon (tray excluded)
  quadro_<animale>.webp the scene of each animal of the family (from the
                        icon art in tools/art/), cut out of its white
                        background and centred on a square pastel card:
                        these are the pictures the child puts back together
Usage: python3 build_puzzle_sprites.py <out dir>
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from iconkit import load_cutout, layer, connected, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
SIZE = 900

# --- turtle: left of the tray, connected to its body
px, rgba = load_cutout(os.path.join(ART, "puzzle.png"), seeds=[(425, 520), (425, 600), (425, 660)])
H, W = px.shape[:2]
xx = np.arange(W)[None, :]
m = connected((rgba[..., 3] > 0) & (xx < 432), (240, 560))
m = (rgba[..., 3] > 0) & ~connected(~m, (0, 0))
ys, xs = np.nonzero(m)
to_img(layer(rgba, m)).crop((int(xs.min()) - 3, int(ys.min()) - 3, int(xs.max()) + 4, int(ys.max()) + 4)) \
    .save(os.path.join(OUT, "tartaruga.webp"), "WEBP", quality=92, method=6)

# --- one picture per animal: (file, name, card colours top/bottom)
SCENE = [
    ("talpe.png", "talpa", "#CDEFB0", "#86CC62"),
    ("memory.png", "gufo", "#D9E4FF", "#B9A8F0"),
    ("palloncini.webp", "orsetto", "#BFE6FF", "#8FCFF5"),
    ("frutta.webp", "panda", "#FFF1CC", "#F7C98A"),
    ("stelle.png", "volpe", "#8F9BE6", "#F2B7C6"),
    ("sequenza.png", "pinguino", "#D6EEFF", "#A8D4F5"),
    ("labirinto.png", "topo", "#FFF3D6", "#F5D48E"),
    ("forme.png", "coniglio", "#FFE3EC", "#F6B8CB"),
    ("tris.png", "rana", "#DDF7D0", "#9FDB86"),
    ("hanoi.png", "elefante", "#FFEBD1", "#F3C590"),
    ("lavagna.png", "gattino", "#FFE8D2", "#F7B98A"),
]

def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

def card(top, bottom):
    t, b = np.array(hexrgb(top), float), np.array(hexrgb(bottom), float)
    k = np.linspace(0, 1, SIZE)[:, None, None]
    grad = (t * (1 - k) + b * k) * np.ones((1, SIZE, 1))
    img = Image.fromarray(grad.astype("uint8")).convert("RGBA")
    d = ImageDraw.Draw(img)
    for y in range(40, SIZE, 90):                      # soft polka dots
        for x in range(40 + (y // 90 % 2) * 45, SIZE, 90):
            d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(255, 255, 255, 70))
    return img

for fname, name, top, bottom in SCENE:
    px, rgba = load_cutout(os.path.join(ART, fname))
    a = rgba[..., 3] > 0
    ys, xs = np.nonzero(a)
    im = to_img(rgba).crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    s = SIZE * .88 / max(im.size)
    im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    c = card(top, bottom)
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0))            # soft ground shadow under the scene
    sa = im.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * .25)
    ox, oy = (SIZE - im.size[0]) // 2, (SIZE - im.size[1]) // 2
    sh.paste((60, 40, 30, 255), (ox + 8, oy + 14), sa)
    c.alpha_composite(sh)
    c.alpha_composite(im, (ox, oy))
    c.convert("RGB").save(os.path.join(OUT, f"quadro_{name}.webp"), "WEBP", quality=90, method=6)
    print(name)

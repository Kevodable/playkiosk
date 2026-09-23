"""Cut the in-game sprites for kiosk/games/memory.

  gufo.webp            the owl of the icon, whole (with its two cards)
  fig_<nome>.webp      card figures, cut automatically from Scenario
                       "sticker sheets" (3x3 grids of separate icons on
                       white): each sheet is split into its 9 cells and the
                       biggest object in each cell is kept, squared up
Usage:
  python3 build_memory_sprites.py <out dir> [sheet.png name1,name2,...,name9] ...
  (the owl comes from tools/art/memory.png)
"""
import os, sys
import numpy as np
from PIL import Image
from iconkit import load_cutout, connected, dilate, to_img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

def crop_box(mask, pad):
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad + 1, int(ys.max()) + pad + 1

# --- owl
px, rgba = load_cutout(os.path.join(HERE, "art", "memory.png"))
to_img(rgba).crop(crop_box(rgba[..., 3] > 0, 3)).save(os.path.join(OUT, "gufo.webp"), "WEBP", quality=92, method=6)
print("gufo.webp")

# --- figure sheets
SIZE = 320                                       # output figure size (square)
args = sys.argv[2:]
for sheet, names in zip(args[0::2], args[1::2]):
    names = names.split(",")
    px, rgba = load_cutout(sheet)
    H, W = px.shape[:2]
    alpha = rgba[..., 3] > 0
    for i, name in enumerate(names):
        r, c = divmod(i, 3)
        x0, x1, y0, y1 = W * c // 3, W * (c + 1) // 3, H * r // 3, H * (r + 1) // 3
        cell = alpha[y0:y1, x0:x1]                 # work on this cell only (fast)
        # the biggest object in the cell: start from its most central opaque pixel
        ys, xs = np.nonzero(cell)
        if not len(xs):
            print("VUOTA", name); continue
        k = np.argmin((xs - (x1 - x0) / 2) ** 2 + (ys - (y1 - y0) / 2) ** 2)
        part = connected(cell, (int(xs[k]), int(ys[k])))
        # keep small detached bits close to it (eyes, a whale's spout...)
        part = part | (dilate(part, 30) & cell)
        obj = np.zeros_like(alpha)
        obj[y0:y1, x0:x1] = part
        out = rgba.copy()
        out[..., 3] = np.where(obj, rgba[..., 3], 0)
        bx0, by0, bx1, by1 = crop_box(obj, 4)
        im = to_img(out).crop((bx0, by0, bx1, by1))
        side = max(im.size)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
        sq.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, f"fig_{name}.webp"), "WEBP", quality=92, method=6)
        print(f"fig_{name}.webp", im.size)

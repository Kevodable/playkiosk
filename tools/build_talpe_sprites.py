"""Cut the in-game sprites for kiosk/games/talpe from the talpe icon art.

Outputs (webp, transparent) into the given folder:
  talpa.webp   the mole WITHOUT the hammer arm (left flank rebuilt by
               mirroring the right one), everything above the dirt line
  zampa.webp   the mole's paw resting on the dirt (drawn in front of it)
  terra.webp   the dirt mound in front of the hole (paw removed)
  martello.webp the mallet alone: the hand is removed and the handle it
               covered is rebuilt by repeating a clean cross-section
All four share one coordinate frame per sprite; sprite boxes and the
anchor points the game needs are printed as JSON.
Usage: python3 build_talpe_sprites.py <talpe.png> <out dir> [preview dir]
"""
import json, math, os, sys
import numpy as np
from PIL import Image
from iconkit import load_cutout, layer, mask_poly, connected, to_img

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW = sys.argv[3] if len(sys.argv) > 3 else None
os.makedirs(OUT, exist_ok=True)
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
opaque = rgba[..., 3] > 0

# --- geometry measured on the 1024x1024 source
DIRT_TOP = [(215, 815), (230, 800), (250, 780), (280, 750), (315, 732), (338, 731), (356, 780),
            (370, 807), (410, 807), (440, 817), (480, 815), (520, 820), (570, 815), (605, 815),
            (720, 820), (740, 745), (765, 735), (810, 785), (840, 815), (870, 830)]
PAW = [(600, 780), (640, 758), (700, 760), (724, 784), (726, 842), (598, 846)]
ARM = [(60, 20), (330, 20), (330, 380), (305, 455), (372, 595), (395, 700), (400, 800), (60, 800)]
MIRROR_X = 563                              # face/body symmetry axis
MIRROR_Y = (480, 812)                       # rows where the left flank is rebuilt
MIRROR_UPTO = 414                           # ...for every x left of this (the arm never reached further)
BLEND = 10                                  # soft seam width
HEAD = [(187, 100), (287, 87), (473, 200), (460, 353), (387, 360), (147, 287), (147, 200)]
AXIS_TOP, AXIS_END = (300, 330), (205, 552)  # handle axis (top under the head, bottom tip)
HANDLE_HALF = 27
REF_Y = 356                                 # clean handle cross-section (between head and hand)
HAND_Y = (378, 505)                         # handle rows hidden by the hand

poly = DIRT_TOP + [(870, 1024), (215, 1024)]
below_dirt = mask_poly(px.shape, poly)
paw_m = mask_poly(px.shape, PAW) & opaque
arm_m = mask_poly(px.shape, ARM)

# --- mole: above the dirt, no arm; left flank mirrored from the right one
mole = rgba.copy()
head_band = mask_poly(px.shape, HEAD)
mole[..., 3] = np.where(opaque & ~below_dirt & ~arm_m & ~paw_m & ~head_band & (yy > 280), rgba[..., 3], 0)
y0, y1 = MIRROR_Y
for y in range(y0, y1):
    for x in range(250, MIRROR_UPTO + BLEND):
        xm = 2 * MIRROR_X - x
        mirrored = np.zeros(4) if (below_dirt[y, xm] or paw_m[y, xm]) else rgba[y, xm]
        w = min(1.0, max(0.0, (MIRROR_UPTO + BLEND - x) / BLEND))
        mole[y, x] = mirrored * w + mole[y, x] * (1 - w)
# drop leftovers of the arm/hand that are no longer attached to the mole
mole[~connected(mole[..., 3] > 0, (560, 600)), 3] = 0
mole[below_dirt, 3] = 0

# --- dirt and paw
dirt = layer(rgba, below_dirt & ~paw_m & opaque)
paw = layer(rgba, paw_m)

# --- hammer: head + handle band, hand removed, handle rebuilt under the hand
ax, ay = AXIS_TOP
bx, by = AXIS_END
L = math.hypot(bx - ax, by - ay)
d = ((bx - ax) / L, (by - ay) / L)
n = (-d[1], d[0])
band = mask_poly(px.shape, [(ax + n[0] * HANDLE_HALF, ay + n[1] * HANDLE_HALF),
                            (bx + n[0] * HANDLE_HALF, by + n[1] * HANDLE_HALF),
                            (bx - n[0] * HANDLE_HALF, by - n[1] * HANDLE_HALF),
                            (ax - n[0] * HANDLE_HALF, ay - n[1] * HANDLE_HALF)])
hammer = layer(rgba, (mask_poly(px.shape, HEAD) | band) & opaque)
# cross-section of the clean handle at REF_Y, stamped along the axis over the hand
t_ref = (REF_Y - ay) / d[1]
cx0, cy0 = ax + d[0] * t_ref, ay + d[1] * t_ref
section = []
for s in np.arange(-HANDLE_HALF, HANDLE_HALF + .5, .5):
    sx, sy = cx0 + n[0] * s, cy0 + n[1] * s
    section.append((s, rgba[int(round(sy)), int(round(sx))].copy()))
t0, t1 = (HAND_Y[0] - ay) / d[1], (HAND_Y[1] - ay) / d[1]
for t in np.arange(t0, t1, .5):
    px0, py0 = ax + d[0] * t, ay + d[1] * t
    for s, colour in section:
        X, Y = int(round(px0 + n[0] * s)), int(round(py0 + n[1] * s))
        hammer[Y, X] = colour

def save(arr, name, pad=4):
    a = arr[..., 3] > 0
    ys, xs = np.nonzero(a)
    box = tuple(int(v) for v in (max(0, xs.min() - pad), max(0, ys.min() - pad), min(W, xs.max() + pad + 1), min(H, ys.max() + pad + 1)))
    to_img(arr).crop(box).save(os.path.join(OUT, name), "WEBP", quality=90, method=6)
    return box

boxes = {"talpa": save(mole, "talpa.webp"), "zampa": save(paw, "zampa.webp"),
         "terra": save(dirt, "terra.webp"), "martello": save(hammer, "martello.webp")}
head_c = (318, 225)                                        # mallet head centre
info = {"boxes": boxes, "martello_perno": AXIS_END, "martello_testa": head_c}
print(json.dumps(info))

if PREVIEW:
    prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
    for arr in (mole, dirt, paw):
        prev.alpha_composite(to_img(arr))
    prev.convert("RGB").save(os.path.join(PREVIEW, "sp_mole.png"))
    prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
    prev.alpha_composite(to_img(hammer))
    prev.convert("RGB").save(os.path.join(PREVIEW, "sp_hammer.png"))

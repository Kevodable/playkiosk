"""Split the Scenario ninja-panda image into layers and build frutta.svg.

The sword swings around the fist; at each swing a white slash crosses a
fruit (apple, then orange), which splits into two halves - cut faces
painted in flesh colour - that fly apart with juice drops, then the fruit
pops back whole. The kiwi (already a slice) wobbles. Usage:
    python3 build_frutta.py <source image> <out.svg> [preview dir]
"""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW_DIR = sys.argv[3] if len(sys.argv) > 3 else None

im = Image.open(SRC).convert("RGB")
W, H = im.size

# --- 1. background -> alpha. The grey outline of each sticker stops the
# flood fill, so the white sticker borders stay (on purpose: sticker look).
flood = im.copy()
MAGENTA = (255, 0, 255)
for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
    if flood.getpixel(seed) != MAGENTA:
        ImageDraw.floodfill(flood, seed, MAGENTA, thresh=40)
fg = Image.eval(ImageChops.difference(flood, Image.new("RGB", (W, H), MAGENTA)).convert("L"),
                lambda v: 0 if v < 8 else 255)
ring = ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(5)))
darkest = Image.fromarray(np.array(im).min(axis=2).astype("uint8"))
soft = Image.eval(darkest, lambda v: max(0, min(255, int((255 - v) * 255 / 55))))
alpha = Image.composite(soft, fg, ring)
rgba = im.copy()
rgba.putalpha(alpha)
a = rgba.getchannel("A")

# --- 2. geometry measured on the 1104x832 source
BLADE = [(100, 150), (140, 152), (246, 366), (236, 382), (200, 411), (186, 417),
         (177, 421), (70, 300), (66, 262)]
HANDLE = [(252, 362), (283, 385), (229, 491), (185, 468)]
FIST = (214, 420)              # sword pivot
FRUITS = {  # sticker ellipse box, centre of the fruit body, flesh colour, juice colour
    "apple":  ((688, 78, 887, 297), (785, 212), "#FFF3C9", "#F4A6A0"),
    "orange": ((663, 458, 837, 642), (750, 556), "#FFC766", "#FF9F1C"),
}
KIWI = (810, 316, 982, 480)
CUT_ANGLE = 30                 # slash direction, degrees below horizontal
FEET_Y = 745

def poly_mask(pts):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m

def ellipse_mask(box):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return m

def with_alpha(mask):
    layer = rgba.copy()
    layer.putalpha(ImageChops.multiply(a, mask))
    return layer

sword_m = ImageChops.lighter(poly_mask(BLADE), poly_mask(HANDLE))
sword = with_alpha(sword_m)

fruit_m = {n: ellipse_mask(f[0]) for n, f in FRUITS.items()}
kiwi_m = ellipse_mask(KIWI)
taken = sword_m
for m in list(fruit_m.values()) + [kiwi_m]:
    taken = ImageChops.lighter(taken, m)
panda = with_alpha(ImageChops.invert(taken))

# rebuild the fist/arm hidden under the wooden handle (seen mid-swing)
arr = np.array(panda).astype(float)
hole = np.array(poly_mask(HANDLE).filter(ImageFilter.MaxFilter(5))) > 0
known = (arr[..., 3] > 200) & ~hole
for _ in range(80):
    todo = hole & ~known
    if not todo.any():
        break
    acc = np.zeros(arr.shape[:2] + (4,)); cnt = np.zeros(arr.shape[:2])
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        sk = np.roll(np.roll(known, dy, 0), dx, 1)
        sc = np.roll(np.roll(arr, dy, 0), dx, 1)
        acc += sc * sk[..., None]; cnt += sk
    grow = todo & (cnt > 0)
    arr[grow] = acc[grow] / cnt[grow][:, None]
    known |= grow
panda = Image.fromarray(arr.clip(0, 255).astype("uint8"))

# fruit halves with a painted cut face
d = (math.cos(math.radians(CUT_ANGLE)), math.sin(math.radians(CUT_ANGLE)))
n = (d[1], -d[0])              # normal pointing up-right
yy, xx = np.mgrid[0:H, 0:W]
hsv = np.array(im.convert("HSV")).astype(int)
colored = (hsv[..., 1] > 90) & (hsv[..., 2] > 80)

def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

halves = {}
wholes = {}
for name, (box, (cx, cy), flesh, _) in FRUITS.items():
    whole = with_alpha(fruit_m[name])
    wholes[name] = whole
    side = (xx - cx) * n[0] + (yy - cy) * n[1]
    near_centre = (xx - cx) ** 2 + (yy - cy) ** 2 < 95 ** 2
    for half, sign in (("a", 1), ("b", -1)):
        h = np.array(whole).copy()
        h[..., 3] = np.where(sign * side > 0, h[..., 3], 0)
        band = (np.abs(side) < 11) & (sign * side > 0) & colored & near_centre
        edge = (np.abs(side) < 3) & (sign * side > 0) & colored & near_centre
        h[band, :3] = hexrgb(flesh)
        h[edge, :3] = (np.array(hexrgb(flesh)) * 0.8).astype(int)
        halves[name + half] = Image.fromarray(h)
kiwi = with_alpha(kiwi_m)

# --- 3. square canvas
VB = (0, -83, 1000)
S = 640
k = S / VB[2]
def to_s(x, y):
    return ((x - VB[0]) * k, (y - VB[1]) * k)

def place(layer):
    canvas = Image.new("RGBA", (VB[2], VB[2]), (0, 0, 0, 0))
    canvas.paste(layer, (-VB[0], -VB[1]), layer)
    return canvas.resize((S, S), Image.LANCZOS)

def b64(img):
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=88, method=6)
    return base64.b64encode(buf.getvalue()).decode()

def img_tag(layer, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<image{c} width="{S}" height="{S}" href="data:image/webp;base64,{b64(place(layer))}"/>'

def origin(x, y):
    sx, sy = to_s(x, y)
    return f"transform-box: view-box; transform-origin: {sx:.1f}px {sy:.1f}px;"

def pct(f):
    return f"{max(0, min(1, f)) * 100:.2f}%"

# --- 4. timeline
T = 6
CUTS = {"apple": 0.30, "orange": 0.72}

sword_kf = ["0% { transform: rotate(0deg); }"]
panda_kf = ["0% { transform: none; }"]
for t in sorted(CUTS.values()):
    sword_kf += [f"{pct(t - .12)} {{ transform: rotate(0deg); animation-timing-function: ease-in-out; }}",
                 f"{pct(t - .04)} {{ transform: rotate(-14deg); animation-timing-function: cubic-bezier(.7,0,1,.5); }}",
                 f"{pct(t)} {{ transform: rotate(30deg); animation-timing-function: ease-out; }}",
                 f"{pct(t + .04)} {{ transform: rotate(22deg); animation-timing-function: ease-in-out; }}",
                 f"{pct(t + .16)} {{ transform: rotate(0deg); }}"]
    panda_kf += [f"{pct(t - .005)} {{ transform: none; }}",
                 f"{pct(t + .03)} {{ transform: scale(1.03, .96); }}",
                 f"{pct(t + .07)} {{ transform: scale(.99, 1.02); }}",
                 f"{pct(t + .1)} {{ transform: none; }}"]
sword_kf.append("100% { transform: rotate(0deg); }")
panda_kf.append("100% { transform: none; }")

css = [
    f".sword {{ {origin(*FIST)} animation: sword {T}s infinite; }}",
    f"@keyframes sword {{ {' '.join(sword_kf)} }}",
    f".panda {{ {origin(W / 2 - 150, FEET_Y)} animation: panda {T}s infinite; }}",
    f"@keyframes panda {{ {' '.join(panda_kf)} }}",
    f".kiwi {{ {origin((KIWI[0] + KIWI[2]) / 2, (KIWI[1] + KIWI[3]) / 2)} animation: kiwi 3.2s ease-in-out infinite alternate; }}",
    "@keyframes kiwi { from { transform: translateY(-1%) rotate(-14deg); } to { transform: translateY(1%) rotate(14deg); } }",
]

fruit_svg = ""
for i, (name, (box, (cx, cy), flesh, juice)) in enumerate(FRUITS.items()):
    t = CUTS[name]
    sx, sy = to_s(cx, cy)
    off = 46 * k                                   # how far the halves fly apart
    css += [
        f".float-{name} {{ {origin(cx, cy)} animation: float-{name} {2.6 + i * .5}s ease-in-out {-i * .9}s infinite alternate; }}",
        f"@keyframes float-{name} {{ from {{ transform: translateY(-1.2%); }} to {{ transform: translateY(1.2%); }} }}",
        f".whole-{name} {{ {origin(cx, cy)} animation: whole-{name} {T}s infinite; }}",
        f"@keyframes whole-{name} {{ 0%, {pct(t - .001)} {{ opacity: 1; transform: scale(1); }} "
        f"{pct(t)} {{ opacity: 0; transform: scale(1); }} "
        f"{pct(t + .21)} {{ opacity: 0; transform: scale(.4); }} "
        f"{pct(t + .215)} {{ opacity: 1; transform: scale(.4); animation-timing-function: cubic-bezier(.3,1.6,.6,1); }} "
        f"{pct(t + .29)}, 100% {{ opacity: 1; transform: scale(1); }} }}",
    ]
    for half, sign in (("a", 1), ("b", -1)):
        dx, dy = sign * n[0] * off, sign * n[1] * off
        css += [
            f".half-{name}{half} {{ {origin(cx, cy)} opacity: 0; animation: half-{name}{half} {T}s infinite; }}",
            f"@keyframes half-{name}{half} {{ 0%, {pct(t - .001)} {{ opacity: 0; transform: none; }} "
            f"{pct(t)} {{ opacity: 1; transform: none; animation-timing-function: ease-out; }} "
            f"{pct(t + .1)} {{ opacity: 1; transform: translate({dx:.1f}px, {dy:.1f}px) rotate({sign * 14}deg); animation-timing-function: ease-in; }} "
            f"{pct(t + .18)} {{ opacity: 0; transform: translate({dx * 1.3:.1f}px, {dy * 1.3 + 40 * k:.1f}px) rotate({sign * 22}deg); }} "
            f"100% {{ opacity: 0; }} }}",
        ]
    # slash: white stroke drawn across the fruit along the cut line
    L = 150
    x0, y0 = to_s(cx - d[0] * L, cy - d[1] * L)
    x1, y1 = to_s(cx + d[0] * L, cy + d[1] * L)
    qx, qy = to_s(cx + n[0] * 22, cy + n[1] * 22)
    path = f"M{x0:.1f} {y0:.1f} Q{qx:.1f} {qy:.1f} {x1:.1f} {y1:.1f}"
    css += [
        f".slash-{name} {{ stroke-dasharray: 100; stroke-dashoffset: 100; opacity: 0; animation: slash-{name} {T}s infinite; }}",
        f"@keyframes slash-{name} {{ 0%, {pct(t - .03)} {{ stroke-dashoffset: 100; opacity: 0; }} "
        f"{pct(t - .029)} {{ stroke-dashoffset: 100; opacity: 1; }} "
        f"{pct(t + .01)} {{ stroke-dashoffset: 0; opacity: 1; }} "
        f"{pct(t + .07)}, 100% {{ stroke-dashoffset: 0; opacity: 0; }} }}",
        f".drops-{name} {{ {origin(cx, cy)} opacity: 0; animation: drops-{name} {T}s infinite; }}",
        f"@keyframes drops-{name} {{ 0%, {pct(t - .001)} {{ opacity: 0; transform: scale(.2); }} "
        f"{pct(t + .005)} {{ opacity: 1; transform: scale(.5); animation-timing-function: ease-out; }} "
        f"{pct(t + .12)} {{ opacity: 0; transform: scale(1.4) translateY(4%); }} 100% {{ opacity: 0; }} }}",
    ]
    drops = "".join(
        f'<circle cx="{sx + 70 * k * math.cos(math.radians(ang)):.1f}" cy="{sy + 70 * k * math.sin(math.radians(ang)):.1f}" '
        f'r="{rr * k:.1f}" fill="{juice}" stroke="#FFFFFF" stroke-width="2"/>'
        for ang, rr in [(-120, 9), (-60, 7), (-10, 10), (60, 8), (130, 9), (175, 7)])
    fruit_svg += (f'<g class="float-{name}">'
                  f'{img_tag(wholes[name], "whole-" + name)}'
                  f'{img_tag(halves[name + "b"], "half-" + name + "b")}'
                  f'{img_tag(halves[name + "a"], "half-" + name + "a")}'
                  f'<g class="drops-{name}">{drops}</g>'
                  f'<path class="slash-{name}" pathLength="100" d="{path}" fill="none" stroke="#BFE6FF" stroke-width="{16 * k * 1.5:.1f}" stroke-linecap="round"/>'
                  f'<path class="slash-{name}" pathLength="100" d="{path}" fill="none" stroke="#FFFFFF" stroke-width="{8 * k * 1.5:.1f}" stroke-linecap="round"/>'
                  f'</g>')

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Taglia la frutta" animata: il panda ninja fa un fendente e la
     frutta si divide in due. Livelli ricavati dall'immagine Scenario con
     tools/build_frutta.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Frutta">
<style>
  {(chr(10) + "  ").join(css)}
</style>
{img_tag(kiwi, "kiwi")}
{fruit_svg}
<g class="panda">
  {img_tag(panda)}
  {img_tag(sword, "sword")}
</g>
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    for name, layer in [("panda", panda), ("sword", sword), ("kiwi", kiwi)] + list(halves.items()):
        prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
        prev.alpha_composite(layer)
        prev.save(os.path.join(PREVIEW_DIR, f"fru_layer_{name}.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

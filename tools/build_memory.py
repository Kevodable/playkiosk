"""Build the animated memory.svg from the Scenario owl image.

The owl holds two cards (heart, star) in front of its head, wing tips in
front of the cards. The cards are REDRAWN as vectors (so they can flip
with no holes) and only the heart/star symbols are cut from the image.
The owl strips hidden behind the cards are rebuilt by diffusion, since they
show for a moment while a card flips. A memory round plays: both cards
turn face down, the heart comes up, the right card shows a star (no pair)
and turns back, then shows a heart - pair! - sparkles and the owl hops.
The owl also blinks. Usage:
    python3 build_memory.py <source image> <out.svg> [preview dir]
"""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW_DIR = sys.argv[3] if len(sys.argv) > 3 else None

im = Image.open(SRC).convert("RGB")
W, H = im.size

# --- 1. background -> alpha (flood fill from the border, narrow soft rim)
flood = im.copy()
MAGENTA = (255, 0, 255)
for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
    if flood.getpixel(seed) != MAGENTA:
        ImageDraw.floodfill(flood, seed, MAGENTA, thresh=40)
fg = Image.eval(ImageChops.difference(flood, Image.new("RGB", (W, H), MAGENTA)).convert("L"),
                lambda v: 0 if v < 8 else 255)
ring = np.array(ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(5)))) > 0
px = np.array(im).astype(float)
edge_a = np.clip((255 - px.min(axis=2)) / 110, 0, 1)
alpha = np.where(np.array(fg) > 0, 1.0, 0.0)
alpha[ring] = edge_a[ring]
safe = np.maximum(alpha, 1e-3)[..., None]
rgb = np.where(ring[..., None], (px - 255 * (1 - alpha[..., None])) / safe, px)

# --- 2. geometry measured on the 1104x832 source
CARDS = {  # corners TL, TR, BL of the outer border (BR follows)
    "L": [(157, 142), (376, 178), (110, 440)],
    "R": [(812, 82), (1015, 152), (717, 355)],
}
SYMBOLS = {"heart": (164, 236, 334, 396), "star": (796, 181, 939, 331)}   # boxes
WING_TIPS = [  # owl wing tips drawn over the cards
    [(236, 424), (300, 416), (340, 486), (226, 490)],
    [(795, 352), (862, 352), (866, 458), (788, 458)],
    [(938, 298), (998, 298), (998, 446), (926, 446)],
]
HIDDEN_OWL = [  # owl head strips hidden behind each card (rebuilt)
    [(352, 205), (382, 200), (372, 300), (348, 480), (320, 480), (340, 300)],
    [(722, 250), (752, 250), (770, 420), (735, 420), (715, 330)],
]
EYES = [((457, 389), 45, 52), ((655, 364), 45, 52)]
FACE = "#F6F1F9"
FEET_Y = 745

def poly_mask(pts, grow=0):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    return m

def card_corners(c):
    (tlx, tly), (trx, try_), (blx, bly) = c
    return [(tlx, tly), (trx, try_), (trx + blx - tlx, try_ + bly - tly), (blx, bly)]

rgba = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype("uint8"))
a = rgba.getchannel("A")

wings = Image.new("L", (W, H), 0)
for w in WING_TIPS:
    wings = ImageChops.lighter(wings, poly_mask(w))
cards_m = Image.new("L", (W, H), 0)
for c in CARDS.values():
    cards_m = ImageChops.lighter(cards_m, poly_mask(card_corners(c), grow=12))

# owl body: everything but the cards; the wing tips go to their own layer
owl = rgba.copy()
owl.putalpha(ImageChops.multiply(a, ImageChops.invert(cards_m)))
# inside the wing-tip zones keep only the feathers (saturated blue), not the
# cream card face showing between them
feathers = Image.fromarray((((px.max(axis=2) - px.min(axis=2)) > 35) & (px.min(axis=2) < 225)).astype("uint8") * 255)
feathers = feathers.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
tips = rgba.copy()
tips.putalpha(ImageChops.multiply(a, ImageChops.multiply(ImageChops.multiply(cards_m, wings), feathers)))

# rebuild the owl strips hidden behind the cards (diffusion from the owl)
arr = np.array(owl).astype(float)
hole = np.zeros((H, W), bool)
for hpoly in HIDDEN_OWL:
    hole |= np.array(poly_mask(hpoly)) > 0
known = (arr[..., 3] > 200) & ~hole
for _ in range(120):
    todo = hole & ~known
    if not todo.any():
        break
    acc = np.zeros((H, W, 4)); cnt = np.zeros((H, W))
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        sk = np.roll(np.roll(known, dy, 0), dx, 1)
        acc += np.roll(np.roll(arr, dy, 0), dx, 1) * sk[..., None]; cnt += sk
    grow = todo & (cnt > 0)
    arr[grow] = acc[grow] / cnt[grow][:, None]
    arr[grow, 3] = 255
    known |= grow
owl = Image.fromarray(arr.clip(0, 255).astype("uint8"))

# symbols: alpha from colourfulness, so the card face around them drops out
sat = px.max(axis=2) - px.min(axis=2)
sym_layers = {}
for name, (x0, y0, x1, y1) in SYMBOLS.items():
    m = np.zeros((H, W)); m[y0:y1, x0:x1] = 1
    sa = np.clip((sat - 14) / 45, 0, 1) * m
    sym_layers[name] = Image.fromarray(np.dstack([px, sa * 255]).clip(0, 255).astype("uint8"))

# --- 3. square canvas
VB = (60, -40, 1000)
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
    img.save(buf, "WEBP", quality=90, method=6)
    return base64.b64encode(buf.getvalue()).decode()

def img_tag(layer, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<image{c} width="{S}" height="{S}" href="data:image/webp;base64,{b64(place(layer))}"/>'

def pct(f):
    return f"{max(0, min(1, f)) * 100:.2f}%"

def geom(c):
    tl, tr, br, bl = [to_s(*p) for p in card_corners(c)]
    cx, cy = (tl[0] + br[0]) / 2, (tl[1] + br[1]) / 2
    ang = math.degrees(math.atan2(tr[1] - tl[1], tr[0] - tl[0]))
    return cx, cy, ang, math.dist(tl, tr), math.dist(tl, bl)

# --- 4. timeline (fractions of the loop); faces: H heart, S star, B back
T = 7
FLIP = 0.05
EVENTS = {
    "L": [(0.12, "B"), (0.30, "H"), (0.86, "B"), (0.93, "H")],
    "R": [(0.17, "B"), (0.40, "S"), (0.52, "B"), (0.64, "H"), (0.88, "B"), (0.95, "S")],
}
START = {"L": "H", "R": "S"}
MATCH = 0.67
BLINKS = [0.06, 0.78]

img_sym = {n: b64(place(l)) for n, l in sym_layers.items()}
css, cards_svg = [], []
heart_c = geom(CARDS["L"])
for name, c in CARDS.items():
    cx, cy, ang, w, h = geom(c)
    faces = ["H", "S", "B"] if name == "R" else ["H", "B"]
    flip_kf = ["0% { transform: scaleX(1); }"]
    face_kf = {f: [f"0% {{ opacity: {1 if f == START[name] else 0}; }}"] for f in faces}
    for t0, face in EVENTS[name]:
        mid = t0 + FLIP / 2
        flip_kf += [f"{pct(t0)} {{ transform: scaleX(1); animation-timing-function: ease-in; }}",
                    f"{pct(mid)} {{ transform: scaleX(0); animation-timing-function: ease-out; }}",
                    f"{pct(t0 + FLIP)} {{ transform: scaleX(1); }}"]
        for f in faces:
            face_kf[f].append(f"{pct(mid)} {{ opacity: {1 if f == face else 0}; }}")
    flip_kf.append("100% { transform: scaleX(1); }")
    css += [f".flip-{name} {{ transform-box: view-box; transform-origin: 0 0; animation: flip-{name} {T}s infinite; }}",
            f"@keyframes flip-{name} {{ {' '.join(flip_kf)} }}"]
    for f in faces:
        css += [f".{name}-{f} {{ animation: {name}-{f} {T}s step-end infinite; }}",
                f"@keyframes {name}-{f} {{ {' '.join(face_kf[f])} }}"]
    r = w * 0.09
    bw = w * 0.055
    rect = (f'x="{-w/2 + bw/2:.1f}" y="{-h/2 + bw/2:.1f}" width="{w - bw:.1f}" height="{h - bw:.1f}" rx="{r:.1f}"')
    card_front = f'<rect {rect} fill="url(#face)" stroke="url(#rim)" stroke-width="{bw:.1f}"/>'
    parts = []
    for f in faces:
        if f == "B":
            parts.append(
                f'<g class="{name}-B"><rect {rect} fill="#5B86DB" stroke="#3E5FAE" stroke-width="{bw:.1f}"/>'
                f'<rect x="{-w/2 + bw * 1.9:.1f}" y="{-h/2 + bw * 1.9:.1f}" width="{w - bw * 3.8:.1f}" height="{h - bw * 3.8:.1f}" rx="{r * .6:.1f}" '
                f'fill="none" stroke="#FFFFFF" stroke-width="{bw * .5:.1f}" opacity=".85"/>'
                f'<circle r="{w * .2:.1f}" fill="#FFD23F" stroke="#3E5FAE" stroke-width="{bw * .5:.1f}"/>'
                f'<circle r="{w * .07:.1f}" fill="#FFFFFF"/></g>')
        else:
            sym = "heart" if f == "H" else "star"
            # each symbol keeps the placement it had on its own card
            sc = heart_c if sym == "heart" else (cx, cy, ang)
            t = f'transform="rotate({-sc[2]:.2f}) translate({-sc[0]:.1f} {-sc[1]:.1f})"'
            parts.append(f'<g class="{name}-{f}">{card_front}'
                         f'<image {t} width="{S}" height="{S}" href="data:image/webp;base64,{img_sym[sym]}"/></g>')
    cards_svg.append(f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({ang:.2f})"><g class="flip-{name}">{"".join(parts)}</g></g>')

def star_pts(cx, cy, r, rot=0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = math.radians(rot - 90 + i * 36)
        pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t):.1f}")
    return " ".join(pts)

sparkles = ""
for name in CARDS:
    cx, cy, _, w, h = geom(CARDS[name])
    for ox, oy, rr, rot in [(-w * .6, -h * .45, 18, 10), (w * .6, -h * .35, 14, -15), (w * .1, -h * .62, 12, 20)]:
        sparkles += (f'<polygon class="spark" points="{star_pts(cx + ox, cy + oy, rr, rot)}" fill="#FFD23F" '
                     f'stroke="#3E5FAE" stroke-width="3" stroke-linejoin="round"/>')

lids = ""
for (ex, ey), rx, ry in EYES:
    x, y = to_s(ex, ey)
    lids += (f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rx * k * 1.2:.1f}" ry="{ry * k * 1.2:.1f}" fill="url(#lid)"/>'
             f'<path d="M{x - rx * k * .75:.1f} {y:.1f} Q{x:.1f} {y + ry * k * .5:.1f} {x + rx * k * .75:.1f} {y:.1f}" '
             f'fill="none" stroke="#2A1F4A" stroke-width="{rx * k * .16:.1f}" stroke-linecap="round"/>')

blink_kf = " ".join(f"{pct(b)} {{ opacity: 1; }} {pct(b + 0.02)} {{ opacity: 0; }}" for b in BLINKS)
fx, fy = to_s(550, FEET_Y)
css += [
    f".owl {{ transform-box: view-box; transform-origin: {fx:.1f}px {fy:.1f}px; animation: joy {T}s infinite; }}",
    f"@keyframes joy {{ 0%, {pct(MATCH)} {{ transform: none; }} "
    f"{pct(MATCH + .03)} {{ transform: scale(1.04, .94); }} {pct(MATCH + .06)} {{ transform: scale(.97, 1.04) translateY(-3%); }} "
    f"{pct(MATCH + .09)} {{ transform: scale(1.02, .98); }} {pct(MATCH + .12)}, 100% {{ transform: none; }} }}",
    f".lids {{ opacity: 0; animation: blink {T}s step-end infinite; }}",
    f"@keyframes blink {{ 0% {{ opacity: 0; }} {blink_kf} }}",
    f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
    f"@keyframes spark {{ 0%, {pct(MATCH)} {{ opacity: 0; transform: scale(.3); }} "
    f"{pct(MATCH + .02)} {{ opacity: 1; transform: scale(1.15); }} {pct(MATCH + .1)} {{ opacity: 1; transform: scale(1); }} "
    f"{pct(MATCH + .15)}, 100% {{ opacity: 0; transform: scale(.8); }} }}",
]

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Memory" animata: il gufo gioca a memory con due carte (ridisegnate
     in vettoriale per poterle girare) e trova la coppia di cuori. Generata
     dall'immagine Scenario con tools/build_memory.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Memory">
<defs>
  <linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FDF7F3"/><stop offset="1" stop-color="#F6ECEF"/></linearGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B3C8EE"/><stop offset="1" stop-color="#7183C6"/></linearGradient>
  <radialGradient id="lid"><stop offset="0.84" stop-color="{FACE}"/><stop offset="1" stop-color="{FACE}" stop-opacity="0"/></radialGradient>
</defs>
<style>
  {(chr(10) + "  ").join(css)}
</style>
<g class="owl">
  {img_tag(owl)}
  <g class="lids">{lids}</g>
  {"".join(cards_svg)}
  {img_tag(tips)}
</g>
<g>{sparkles}</g>
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    for name, layer in [("owl", owl), ("tips", tips)] + list(sym_layers.items()):
        prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
        prev.alpha_composite(layer)
        prev.save(os.path.join(PREVIEW_DIR, f"mem2_{name}.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

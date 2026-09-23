"""Split the Scenario fox+stars image into layers and build stelle.svg.

The three big smiling stars fall one at a time into the fox's basket
(spinning and shrinking as they drop in), a burst of sparkles pops on the
basket and the fox hops; the caught star then pops back in place. The
small background sparkles twinkle. Usage:
    python3 build_stelle.py <source image> <out.svg> [preview dir]
"""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW_DIR = sys.argv[3] if len(sys.argv) > 3 else None

im = Image.open(SRC).convert("RGB")
W, H = im.size

# --- 1. background -> alpha (flood fill from the border)
flood = im.copy()
MAGENTA = (255, 0, 255)
for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
    if flood.getpixel(seed) != MAGENTA:
        ImageDraw.floodfill(flood, seed, MAGENTA, thresh=40)
fg = Image.eval(ImageChops.difference(flood, Image.new("RGB", (W, H), MAGENTA)).convert("L"),
                lambda v: 0 if v < 8 else 255)
# this source is soft-edged: take a wider rim, give it alpha from how far it
# is from white, and remove the white mixed into those pixels (un-premultiply)
# so no pale halo shows on the mint menu background
ring = np.array(ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(5)))) > 0
px = np.array(im).astype(float)
edge_a = np.clip((255 - px.min(axis=2)) / 110, 0, 1)
alpha = np.where(np.array(fg) > 0, 1.0, 0.0)
alpha[ring] = edge_a[ring]
safe = np.maximum(alpha, 1e-3)[..., None]
rgb = np.where(ring[..., None], (px - 255 * (1 - alpha[..., None])) / safe, px)
rgba = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype("uint8"))
a = rgba.getchannel("A")

# --- 2. geometry measured on the 1104x832 source (yellow components)
STARS = [(354, 112, 472, 226), (523, 34, 605, 114), (582, 178, 700, 291), (317, 306, 401, 390)]
SPARKLES = [(733, 262, 764, 293), (503, 258, 524, 279), (311, 407, 328, 425),
            (670, 158, 684, 173), (761, 354, 769, 362)]
BASKET = (542, 612)            # where a caught star disappears (basket mouth)
FEET_Y = 790

def grow(box, px):
    return (box[0] - px, box[1] - px, box[2] + px, box[3] + px)

def region(box, px):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle(grow(box, px), fill=255)
    return m

def with_alpha(mask):
    layer = rgba.copy()
    layer.putalpha(ImageChops.multiply(a, mask))
    return layer

taken = Image.new("L", (W, H), 0)
stars, sparkles = [], []
for box in STARS:
    m = region(box, 6)
    taken = ImageChops.lighter(taken, m)
    stars.append(with_alpha(m))
for box in SPARKLES:
    m = region(box, 4)
    taken = ImageChops.lighter(taken, m)
    sparkles.append(with_alpha(m))
fox = with_alpha(ImageChops.invert(taken))

# --- 3. square canvas
VB = (140, 14, 800)
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

def centre(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

def pct(f):
    return f"{max(0, min(1, f)) * 100:.2f}%"

def star_pts(cx, cy, r, rot=0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = math.radians(rot - 90 + i * 36)
        pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t):.1f}")
    return " ".join(pts)

# --- 4. timeline
T = 6
CATCH = [0.2, 0.42, 0.64, 0.86]     # when each star lands in the basket
FALL = 0.12                    # fall duration
BACK = 0.12                    # time until the caught star pops back

css, body = [], []
bx, by = to_s(*BASKET)
for i, (box, t) in enumerate(zip(STARS, CATCH)):
    cx, cy = centre(box)
    sx, sy = to_s(cx, cy)
    dx, dy = bx - sx, by - sy
    spin = -360 if cx > BASKET[0] else 360
    t0 = t - FALL
    css += [
        f".bob{i} {{ {origin(cx, cy)} animation: bob{i} {2.2 + i * .35:.2f}s ease-in-out {-i * .7:.1f}s infinite alternate; }}",
        f"@keyframes bob{i} {{ from {{ transform: translateY(-1.3%) rotate(-7deg); }} to {{ transform: translateY(1%) rotate(7deg); }} }}",
        f".fall{i} {{ {origin(cx, cy)} animation: fall{i} {T}s infinite; }}",
        f"@keyframes fall{i} {{ 0%, {pct(t0)} {{ transform: none; opacity: 1; animation-timing-function: cubic-bezier(.45,0,.9,.6); }} "
        f"{pct(t0 + FALL * .45)} {{ transform: translate({dx * .38:.1f}px, {dy * .3:.1f}px) rotate({spin * .4:.0f}deg) scale(.85); }} "
        f"{pct(t)} {{ transform: translate({dx:.1f}px, {dy:.1f}px) rotate({spin}deg) scale(.3); opacity: 1; }} "
        f"{pct(t + .005)} {{ transform: translate({dx:.1f}px, {dy:.1f}px) rotate({spin}deg) scale(.1); opacity: 0; }} "
        f"{pct(t + BACK)} {{ transform: scale(0); opacity: 0; }} "
        f"{pct(t + BACK + .005)} {{ transform: scale(0); opacity: 1; animation-timing-function: cubic-bezier(.3,1.6,.6,1); }} "
        f"{pct(t + BACK + .07)}, 100% {{ transform: none; opacity: 1; }} }}",
    ]
    body.append(f'<g class="bob{i}"><g class="fall{i}">{img_tag(stars[i])}</g></g>')

# sparkle burst on the basket at each catch
burst_kf = ["0% { opacity: 0; transform: scale(.3); }"]
for t in CATCH:
    burst_kf += [f"{pct(t - .001)} {{ opacity: 0; transform: scale(.3); }}",
                 f"{pct(t + .01)} {{ opacity: 1; transform: scale(.9); animation-timing-function: ease-out; }}",
                 f"{pct(t + .09)} {{ opacity: 0; transform: scale(1.3); }}"]
burst_kf.append("100% { opacity: 0; }")
css += [f".burst {{ {origin(*BASKET)} opacity: 0; animation: burst {T}s infinite; }}",
        f"@keyframes burst {{ {' '.join(burst_kf)} }}"]
burst = "".join(
    f'<polygon points="{star_pts(bx + 80 * k * math.cos(math.radians(ang)), by + 80 * k * math.sin(math.radians(ang)), r * k, ang)}" '
    f'fill="#FFE14D" stroke="#F2A900" stroke-width="2.5" stroke-linejoin="round"/>'
    for ang, r in [(-150, 30), (-112, 22), (-70, 34), (-30, 24), (-90, 18), (-5, 18), (-172, 20)])

# fox hops at each catch
hop_kf = ["0% { transform: none; }"]
for t in CATCH:
    hop_kf += [f"{pct(t)} {{ transform: none; animation-timing-function: ease-out; }}",
               f"{pct(t + .035)} {{ transform: translateY(-2.5%) scale(.98, 1.03); animation-timing-function: ease-in; }}",
               f"{pct(t + .07)} {{ transform: scale(1.04, .95); }}",
               f"{pct(t + .1)} {{ transform: none; }}"]
hop_kf.append("100% { transform: none; }")
css += [f".fox {{ {origin(545, FEET_Y)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {' '.join(hop_kf)} }}",
        "@keyframes twinkle { 0%, 100% { transform: scale(1) rotate(0deg); opacity: 1; } 50% { transform: scale(.45) rotate(35deg); opacity: .5; } }"]

twinkles = ""
for j, (box, layer) in enumerate(zip(SPARKLES, sparkles)):
    css.append(f".tw{j} {{ {origin(*centre(box))} animation: twinkle {1.3 + (j % 4) * .3:.1f}s ease-in-out {-j * .37:.2f}s infinite; }}")
    twinkles += img_tag(layer, f"tw{j}")

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Acchiappa le stelle" animata: le stelle cadono una alla volta
     nel cestino della volpe. Livelli ricavati dall'immagine Scenario con
     tools/build_stelle.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Stelle">
<style>
  {(chr(10) + "  ").join(css)}
</style>
{twinkles}
<g class="fox">{img_tag(fox)}</g>
<g class="burst">{burst}</g>
{"".join(body)}
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
    prev.alpha_composite(fox)
    prev.save(os.path.join(PREVIEW_DIR, "ste_layer_fox.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

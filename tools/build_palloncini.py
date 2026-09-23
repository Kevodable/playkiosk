"""Split the Scenario bear+balloons image into layers and build palloncini.svg.

The generated strings are erased and redrawn as vector paths, so each held
balloon can sway around the paw that holds it with its string still attached.
The free yellow balloon bobs, pops (burst + confetti, string falls) and
inflates back; the bear jumps at the pop. Usage:
    python3 build_palloncini.py <source image> <out.svg> [preview dir]
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
ring = ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(5)))
darkest = Image.fromarray(np.array(im).min(axis=2).astype("uint8"))
soft = Image.eval(darkest, lambda v: max(0, min(255, int((255 - v) * 255 / 55))))
alpha = Image.composite(soft, fg, ring)
rgba = im.copy()
rgba.putalpha(alpha)

# --- 2. geometry measured on the 1104x832 source
BALLOONS = {  # ellipse box of the balloon, box of its knot
    "red":    ((270, 20, 494, 282), (362, 262, 404, 296)),
    "yellow": ((520, 40, 628, 160), (556, 148, 590, 171)),
    "purple": ((650, 94, 810, 280), (714, 266, 748, 293)),
}
STRING_ERASE = [  # boxes around the generated strings (below the knots)
    (372, 296, 394, 594), (374, 662, 392, 694),      # red, above and below the paw
    (719, 293, 743, 490),                            # purple
    (561, 171, 583, 318),                            # yellow
]
STRINGS = {  # redrawn strings: knot -> end (inside the paw for the held ones)
    "red":    [(381, 294), (377, 450), (383, 640)],
    "purple": [(731, 291), (735, 400), (731, 540)],
    "yellow": [(572, 169), (566, 240), (571, 312)],
}
PIVOTS = {"red": (383, 630), "purple": (732, 528)}    # paws holding a string
STRING_COLOR = "#4A2C22"
STRING_W = 3.5
FEET_Y = 800

def box_mask(box, ellipse=False):
    m = Image.new("L", (W, H), 0)
    (ImageDraw.Draw(m).ellipse if ellipse else ImageDraw.Draw(m).rectangle)(box, fill=255)
    return m

a = rgba.getchannel("A")
strings = Image.new("L", (W, H), 0)
for b in STRING_ERASE:
    strings = ImageChops.lighter(strings, box_mask(b))
taken = strings
layers = {}
for name, (body_box, knot_box) in BALLOONS.items():
    m = ImageChops.lighter(box_mask(body_box, ellipse=True), box_mask(knot_box))
    m = ImageChops.subtract(m, strings)
    taken = ImageChops.lighter(taken, m)
    layer = rgba.copy()
    layer.putalpha(ImageChops.multiply(a, m))
    layers[name] = layer
bear = rgba.copy()
bear.putalpha(ImageChops.multiply(a, ImageChops.invert(taken)))

# --- 3. square canvas
VB = (114, -20, 860)
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

def string_path(name):
    (x0, y0), (xm, ym), (x1, y1) = [to_s(*p) for p in STRINGS[name]]
    # quadratic through the middle point: control = 2*mid - (start+end)/2
    cx, cy = 2 * xm - (x0 + x1) / 2, 2 * ym - (y0 + y1) / 2
    return (f'<path d="M{x0:.1f} {y0:.1f} Q{cx:.1f} {cy:.1f} {x1:.1f} {y1:.1f}" fill="none" '
            f'stroke="{STRING_COLOR}" stroke-width="{STRING_W * k:.2f}" stroke-linecap="round"/>')

def origin(x, y):
    sx, sy = to_s(x, y)
    return f"transform-box: view-box; transform-origin: {sx:.1f}px {sy:.1f}px;"

T = 7                          # one loop
POP = 0.50                     # yellow pops here...
REGROW = 0.76                  # ...and inflates back from here
def pct(f):
    return f"{f * 100:.2f}%"

ycx = (BALLOONS["yellow"][0][0] + BALLOONS["yellow"][0][2]) / 2
ycy = (BALLOONS["yellow"][0][1] + BALLOONS["yellow"][0][3]) / 2
yk = STRINGS["yellow"][0]
bx, by = to_s(ycx, ycy)

css = [
    f".sway-red {{ {origin(*PIVOTS['red'])} animation: sway-red 3.4s ease-in-out infinite alternate; }}",
    "@keyframes sway-red { from { transform: rotate(-3.5deg); } to { transform: rotate(3deg); } }",
    f".sway-purple {{ {origin(*PIVOTS['purple'])} animation: sway-purple 2.8s ease-in-out -1.1s infinite alternate; }}",
    "@keyframes sway-purple { from { transform: rotate(4.5deg); } to { transform: rotate(-3.5deg); } }",
    f".bob {{ {origin(*yk)} animation: bob 2.3s ease-in-out infinite alternate; }}",
    "@keyframes bob { from { transform: translateY(-1.6%) rotate(-5deg); } to { transform: translateY(1.2%) rotate(4deg); } }",
    f".y-balloon {{ {origin(ycx, ycy)} animation: y-balloon {T}s infinite; }}",
    f"@keyframes y-balloon {{ 0%, {pct(POP - .04)} {{ transform: scale(1); opacity: 1; }} "
    f"{pct(POP)} {{ transform: scale(1.16, 1.12); opacity: 1; }} "
    f"{pct(POP + .006)} {{ transform: scale(1.35); opacity: 0; }} "
    f"{pct(REGROW - .001)} {{ transform: scale(.1); opacity: 0; }} "
    f"{pct(REGROW)} {{ transform: scale(.1); opacity: 1; animation-timing-function: cubic-bezier(.3,1.6,.6,1); }} "
    f"{pct(REGROW + .1)}, 100% {{ transform: scale(1); opacity: 1; }} }}",
    f".y-string {{ {origin(*yk)} animation: y-string {T}s infinite; }}",
    f"@keyframes y-string {{ 0%, {pct(POP + .004)} {{ transform: translateY(0) rotate(0); opacity: 1; animation-timing-function: ease-in; }} "
    f"{pct(POP + .09)} {{ transform: translateY(9%) rotate(14deg); opacity: 0; }} "
    f"{pct(REGROW + .02)} {{ transform: translateY(0) rotate(0); opacity: 0; }} "
    f"{pct(REGROW + .08)}, 100% {{ opacity: 1; }} }}",
    f".burst {{ transform-box: view-box; transform-origin: {bx:.1f}px {by:.1f}px; opacity: 0; animation: burst {T}s infinite; }}",
    f"@keyframes burst {{ 0%, {pct(POP)} {{ opacity: 0; transform: scale(.3); }} "
    f"{pct(POP + .008)} {{ opacity: 1; transform: scale(.7); animation-timing-function: ease-out; }} "
    f"{pct(POP + .09)} {{ opacity: 0; transform: scale(1.35); }} 100% {{ opacity: 0; }} }}",
    f".bear {{ {origin(W / 2, FEET_Y)} animation: jump {T}s infinite; }}",
    f"@keyframes jump {{ 0%, {pct(POP + .004)} {{ transform: none; }} "
    f"{pct(POP + .03)} {{ transform: translateY(-2.5%) scale(.98, 1.03); animation-timing-function: ease-in; }} "
    f"{pct(POP + .06)} {{ transform: translateY(0) scale(1.04, .95); }} "
    f"{pct(POP + .09)} {{ transform: translateY(0) scale(.99, 1.01); }} {pct(POP + .12)}, 100% {{ transform: none; }} }}",
]

# burst: short rays + confetti around the yellow balloon's centre
r0, r1 = 26 * k * 1.6, 44 * k * 1.6
rays = "".join(
    f'<line x1="{bx + r0 * math.cos(t):.1f}" y1="{by + r0 * math.sin(t):.1f}" '
    f'x2="{bx + r1 * math.cos(t):.1f}" y2="{by + r1 * math.sin(t):.1f}" '
    f'stroke="#FFB020" stroke-width="5" stroke-linecap="round"/>'
    for t in [math.radians(i * 45 + 22) for i in range(8)])
confetti_cols = ["#E8424F", "#9B5DC9", "#FFD23F", "#3FA7E8", "#FF8A3D", "#58C27D"]
confetti = "".join(
    f'<rect x="{bx + 52 * k * 1.6 * math.cos(math.radians(i * 60 + 5)) - 4:.1f}" '
    f'y="{by + 52 * k * 1.6 * math.sin(math.radians(i * 60 + 5)) - 4:.1f}" width="8" height="8" rx="2" '
    f'fill="{c}" transform="rotate({i * 33} {bx + 52 * k * 1.6 * math.cos(math.radians(i * 60 + 5)):.1f} '
    f'{by + 52 * k * 1.6 * math.sin(math.radians(i * 60 + 5)):.1f})"/>'
    for i, c in enumerate(confetti_cols))
shreds = "".join(
    f'<path d="M{bx + dx:.1f} {by + dy:.1f} q6 -6 12 0" fill="none" stroke="#F4B400" stroke-width="5" stroke-linecap="round"/>'
    for dx, dy in [(-30, -8), (14, 18), (-6, 26)])

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Palloncini" animata: l'orsetto tiene due palloncini che
     ondeggiano; quello giallo libero scoppia e si rigonfia. Livelli
     ricavati dall'immagine Scenario con tools/build_palloncini.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Palloncini">
<style>
  {(chr(10) + "  ").join(css)}
</style>
<g class="bob">
  <g class="y-string">{string_path("yellow")}</g>
  {img_tag(layers["yellow"], "y-balloon")}
</g>
<g class="burst">{rays}{confetti}{shreds}</g>
<g class="bear">
  <g class="sway-red">{string_path("red")}{img_tag(layers["red"])}</g>
  <g class="sway-purple">{string_path("purple")}{img_tag(layers["purple"])}</g>
  {img_tag(bear)}
</g>
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    for name, layer in [("bear", bear)] + list(layers.items()):
        prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
        prev.alpha_composite(layer)
        prev.save(os.path.join(PREVIEW_DIR, f"bal_layer_{name}.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

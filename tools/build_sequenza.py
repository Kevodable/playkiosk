"""Split the Scenario penguin+buttons image into layers and build sequenza.svg.

Four round buttons on a cream panel light up one at a time like a Simon
round - each press sinks the button into its socket, flashes a glow ring
and floats a music note - then the penguin hops for joy. Two different
sequences per loop. Usage:
    python3 build_sequenza.py <source image> <out.svg> [preview dir]
"""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW_DIR = sys.argv[3] if len(sys.argv) > 3 else None

im = Image.open(SRC).convert("RGB")
W, H = im.size

# --- 1. background -> alpha, with soft-edge cleanup (no pale halo on mint)
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
BUTTONS = [  # name, centre, glow colour
    ("blue",   (699, 369), "#6BC3FF"),
    ("red",    (915, 370), "#FF6B6B"),
    ("green",  (700, 580), "#7EE081"),
    ("yellow", (914, 580), "#FFE45C"),
]
R = 74                         # button radius
PANEL = (589, 262, 1014, 681)  # the cream panel: its top edge is too faint
FEET_Y = 725                   # for the flood fill, so it is forced opaque
SOCKET = (226, 216, 200)       # colour left under a pressed button

px0, py0, px1, py1 = PANEL
alpha[py0:py1, px0:px1] = 1.0
rgb[py0:py1, px0:px1] = px[py0:py1, px0:px1]
rgba = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha * 255]).astype("uint8"))
a = rgba.getchannel("A")

def with_alpha(mask):
    layer = rgba.copy()
    layer.putalpha(ImageChops.multiply(a, mask))
    return layer

taken = Image.new("L", (W, H), 0)
buttons = []
for _, (bx, by), _ in BUTTONS:
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse((bx - R - 6, by - R - 6, bx + R + 6, by + R + 8), fill=255)
    taken = ImageChops.lighter(taken, m)
    buttons.append(with_alpha(m))
# the penguin + panel layer keeps the panel under each button, painted as an
# empty socket, so a pressed (shrunk) button looks sunk into the panel
base = rgba.copy()
d = ImageDraw.Draw(base)
for _, (bx, by), _ in BUTTONS:
    d.ellipse((bx - R - 6, by - R - 6, bx + R + 6, by + R + 8), fill=SOCKET + (255,))
panel_m = Image.new("L", (W, H), 0)
ImageDraw.Draw(panel_m).rectangle((px0 - 6, py0 - 6, px1 + 6, py1 + 8), fill=255)
panel = base.copy()
panel.putalpha(ImageChops.multiply(base.getchannel("A"), panel_m))
penguin = base.copy()
penguin.putalpha(ImageChops.multiply(base.getchannel("A"), ImageChops.invert(panel_m)))

# --- 3. square canvas
VB = (37, -85, 1000)
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

# --- 4. timeline: two rounds, each a sequence then a happy hop
T = 7.2
STEP, ON = 0.055, 0.04         # time between presses, how long a press lasts
ROUNDS = [(0.06, [1, 2, 0]), (0.46, [3, 1, 2, 0])]
presses = {i: [] for i in range(len(BUTTONS))}
hops = []
for start, seq in ROUNDS:
    for j, b in enumerate(seq):
        presses[b].append(start + j * STEP)
    hops.append(start + len(seq) * STEP + 0.03)

css, svg_buttons = [], ""
for i, (name, (bx, by), glow) in enumerate(BUTTONS):
    press_kf, glow_kf, note_kf = ["0% { transform: none; }"], ["0% { opacity: 0; transform: scale(.9); }"], ["0% { opacity: 0; }"]
    for t in presses[i]:
        press_kf += [f"{pct(t)} {{ transform: none; }}", f"{pct(t + .008)} {{ transform: scale(.9); }}",
                     f"{pct(t + ON)} {{ transform: scale(.94); }}", f"{pct(t + ON + .012)} {{ transform: none; }}"]
        glow_kf += [f"{pct(t)} {{ opacity: 0; transform: scale(.9); }}",
                    f"{pct(t + .008)} {{ opacity: 1; transform: scale(1); }}",
                    f"{pct(t + ON)} {{ opacity: .8; transform: scale(1.12); }}",
                    f"{pct(t + ON + .02)} {{ opacity: 0; transform: scale(1.25); }}"]
        note_kf += [f"{pct(t)} {{ opacity: 0; transform: translate(0, 0) rotate(0deg); }}",
                    f"{pct(t + .01)} {{ opacity: 1; transform: translate(0, -4%) rotate(-8deg); }}",
                    f"{pct(t + ON + .05)} {{ opacity: 0; transform: translate(3%, -13%) rotate(10deg); }}"]
    press_kf.append("100% { transform: none; }")
    glow_kf.append("100% { opacity: 0; }")
    note_kf.append("100% { opacity: 0; }")
    css += [f".press{i} {{ {origin(bx, by)} animation: press{i} {T}s infinite; }}",
            f"@keyframes press{i} {{ {' '.join(press_kf)} }}",
            f".glow{i} {{ {origin(bx, by)} opacity: 0; animation: glow{i} {T}s infinite; }}",
            f"@keyframes glow{i} {{ {' '.join(glow_kf)} }}",
            f".note{i} {{ opacity: 0; animation: note{i} {T}s infinite; }}",
            f"@keyframes note{i} {{ {' '.join(note_kf)} }}"]
    sx, sy = to_s(bx, by)
    r = R * k
    nx, ny = sx + r * .55, sy - r * .9
    svg_buttons += (
        f'<circle class="glow{i}" cx="{sx:.1f}" cy="{sy:.1f}" r="{r * 1.08:.1f}" fill="none" stroke="{glow}" stroke-width="{r * .28:.1f}"/>'
        f'<g class="press{i}">{img_tag(buttons[i])}'
        f'<circle class="glow{i}" cx="{sx - r * .05:.1f}" cy="{sy - r * .08:.1f}" r="{r * .8:.1f}" fill="url(#shine)"/></g>'
        f'<g class="note{i}"><g transform="translate({nx:.1f} {ny:.1f}) scale({r / 70:.3f})">'
        f'<ellipse cx="-8" cy="22" rx="11" ry="8" transform="rotate(-20 -8 22)" fill="#2B2D42"/>'
        f'<path d="M2 20 V-18 Q14 -12 20 -2" fill="none" stroke="#2B2D42" stroke-width="5" stroke-linecap="round"/></g></g>')

hop_kf = ["0% { transform: none; }"]
spark_kf = ["0% { opacity: 0; transform: scale(.4); }"]
for t in hops:
    hop_kf += [f"{pct(t)} {{ transform: none; animation-timing-function: ease-out; }}",
               f"{pct(t + .04)} {{ transform: translateY(-4%) scale(.97, 1.04); animation-timing-function: ease-in; }}",
               f"{pct(t + .08)} {{ transform: scale(1.05, .94); }}",
               f"{pct(t + .11)} {{ transform: translateY(-1.5%); }}",
               f"{pct(t + .14)} {{ transform: none; }}"]
    spark_kf += [f"{pct(t + .02)} {{ opacity: 0; transform: scale(.4); }}",
                 f"{pct(t + .05)} {{ opacity: 1; transform: scale(1); }}",
                 f"{pct(t + .14)} {{ opacity: 0; transform: scale(1.3) rotate(20deg); }}"]
hop_kf.append("100% { transform: none; }")
spark_kf.append("100% { opacity: 0; }")
css += [f".penguin {{ {origin(270, FEET_Y)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {' '.join(hop_kf)} }}",
        f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
        f"@keyframes spark {{ {' '.join(spark_kf)} }}"]

def star_pts(cx, cy, r, rot=0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = math.radians(rot - 90 + i * 36)
        pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t):.1f}")
    return " ".join(pts)

sparks = "".join(
    f'<polygon class="spark" points="{star_pts(*to_s(x, y), r * k, rot)}" fill="#FFD23F" '
    f'stroke="#2B2D42" stroke-width="3" stroke-linejoin="round"/>'
    for x, y, r, rot in [(140, 150, 30, 10), (420, 85, 24, -15), (560, 200, 20, 20), (80, 380, 18, 0)])

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Sequenza colori" animata: i bottoni si accendono in sequenza e
     il pinguino esulta. Livelli ricavati dall'immagine Scenario con
     tools/build_sequenza.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Sequenza">
<defs><radialGradient id="shine" cx=".4" cy=".35" r=".7">
  <stop offset="0" stop-color="#FFFFFF" stop-opacity=".95"/>
  <stop offset=".55" stop-color="#FFFFFF" stop-opacity=".45"/>
  <stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/>
</radialGradient></defs>
<style>
  {(chr(10) + "  ").join(css)}
</style>
<g class="penguin">{img_tag(penguin)}</g>
{img_tag(panel)}
{svg_buttons}
{sparks}
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
    prev.alpha_composite(penguin)
    prev.save(os.path.join(PREVIEW_DIR, "seq_base.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

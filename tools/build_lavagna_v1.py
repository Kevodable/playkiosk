"""Build the animated lavagna.svg from the (already transparent) chalkboard art.

The board comes alive: every chalk doodle is cut out on its own layer and
moves (sun wobbles, heart beats, star twinkles, tree sways, spiral turns,
house hops), the colourful dashes around the board pulse, and the child's
hand scribbles - rocking around the sleeve, which stays cut at the right
edge - puffing chalk dust. The board under every moving piece is rebuilt
(normalized-convolution fill) so nothing leaves a hole. Usage:
    python3 build_lavagna.py <source 1024x1024 RGBA> <out.svg> [preview dir]
"""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW_DIR = sys.argv[3] if len(sys.argv) > 3 else None

im = Image.open(SRC).convert("RGBA")
W, H = im.size
px = np.array(im).astype(float)
r, g, b, a = px[..., 0], px[..., 1], px[..., 2], px[..., 3]
mx, mn = px[..., :3].max(axis=2), px[..., :3].min(axis=2)

# --- chalk vs board: board is dark green, chalk is bright or strongly coloured
board_green = (g > r + 10) & (g > b) & (mx < 130)
chalk = (a > 200) & ((mx > 140) | ((mx - mn) > 90)) & ~board_green

def box_mask(box):
    m = np.zeros((H, W), bool)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = True
    return m

def poly_mask(pts):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.array(m) > 0

def dilate(m, n):
    return np.array(Image.fromarray(m.astype("uint8") * 255).filter(ImageFilter.MaxFilter(n * 2 + 1))) > 0

# --- 2. pieces (boxes measured on the 1024x1024 source)
DOODLES = {  # name: box, pivot, animation
    "sun":    ((60, 60, 480, 432), (265, 245)),
    "heart":  ((528, 108, 772, 302), (680, 212)),
    "star":   ((788, 188, 962, 392), (878, 292)),
    "house":  ((58, 438, 282, 742), (175, 742)),
    "spiral": ((168, 688, 462, 892), (330, 790)),
    "tree":   ((668, 658, 902, 962), (800, 955)),
}
DASHES = {  # the kid-drawn accents around the board
    "d1": ((28, 0, 122, 84), (75, 45)),
    "d2": ((888, 8, 1002, 102), (945, 60)),
    "d3": ((908, 388, 982, 452), (945, 420)),
    "d4": ((0, 798, 82, 922), (40, 860)),
    "d5": ((928, 878, 1022, 982), (975, 930)),
}
HAND_POLY = [(704, 436), (745, 422), (800, 414), (855, 420), (925, 468), (1024, 552),
             (1024, 910), (895, 905), (880, 700), (800, 585), (745, 515), (704, 480)]
PIVOT = (1090, 760)            # hand rocks around a point past the sleeve cut
CHALK_TIP = (716, 455)

skin = (r > 120) & (g > 90) & (r > g + 25) & (r > b + 40)
sleeve = (b > g + 30) & (b > r + 60)
stick = (mn > 175) & box_mask((700, 420, 845, 525))
hand_m = poly_mask(HAND_POLY) & (skin | sleeve | stick) & (a > 10)
hand_m = np.array(Image.fromarray(hand_m.astype("uint8") * 255)
                  .filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))) > 0
hand_m &= poly_mask(HAND_POLY)

# each doodle is one chalk colour: filter by it so a box never grabs a
# neighbouring doodle (the waves run close to the sun, spiral and tree)
yellow = (r > 150) & (g > 120) & (b < 130) & (r > b + 60)
red = (r > 140) & (g < 130) & (r > g + 50)
blue = (b > r + 30) & (b > g)
green = (g > r + 20) & (g > b) & (mx > 110)
COLOUR = {"sun": yellow, "heart": red, "star": blue, "house": blue, "spiral": green, "tree": green}

pieces = {}
for name, (box, _) in list(DOODLES.items()) + list(DASHES.items()):
    m = chalk & box_mask(box) & ~hand_m
    if name in COLOUR:
        m &= dilate(COLOUR[name], 2)
    pieces[name] = dilate(m, 1) & (a > 10) & box_mask(box) & ~hand_m

# --- 3. board: remove moving pieces, rebuild what was under them
hole = hand_m.copy()
for name in DOODLES:
    hole |= dilate(pieces[name], 3)
known = ~hole
def fill(radius):
    pm = Image.fromarray((known * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(radius))
    w = np.array(pm).astype(float) / 255
    out = np.zeros_like(px)
    for c in range(4):
        ch = Image.fromarray((px[..., c] * known).clip(0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(radius))
        out[..., c] = np.array(ch).astype(float) / np.maximum(w, 1e-3)
    return out, w
f1, w1 = fill(10)
f2, w2 = fill(40)
filled = np.where((w1 > 0.08)[..., None], f1, f2)
rng = np.random.default_rng(7)
noise = rng.normal(0, 4, (H, W, 1))                     # a little chalkboard grain
board = px.copy()
board[hole] = (filled + noise * (filled[..., 3:4] > 128))[hole]
board[hand_m & (np.arange(W)[None, :] > 996), 3] = 0     # sleeve past the board edge
for name in DASHES:                                      # dashes: just cut out
    board[pieces[name], 3] = 0
board = board.clip(0, 255)

def layer_from(mask):
    out = px.copy()
    out[..., 3] = np.where(mask, px[..., 3], 0)
    return Image.fromarray(out.clip(0, 255).astype("uint8"))

# --- 4. SVG
S = 768
k = S / W
def b64(img):
    img = img.resize((S, S), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=90, method=6)
    return base64.b64encode(buf.getvalue()).decode()

def img_tag(img, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<image{c} width="{S}" height="{S}" href="data:image/webp;base64,{b64(img)}"/>'

def origin(x, y):
    return f"transform-box: view-box; transform-origin: {x * k:.1f}px {y * k:.1f}px;"

ANIM = {
    "sun":    ("3.2s ease-in-out infinite alternate", "from { transform: rotate(-9deg) scale(.97); } to { transform: rotate(9deg) scale(1.03); }"),
    "heart":  ("1.6s ease-in-out infinite", "0%, 100% { transform: scale(1); } 15% { transform: scale(1.14); } 30% { transform: scale(1); } 45% { transform: scale(1.1); } 60% { transform: scale(1); }"),
    "star":   ("2.2s ease-in-out infinite", "0%, 100% { transform: rotate(0deg) scale(1); } 50% { transform: rotate(14deg) scale(1.12); }"),
    "house":  ("3.6s ease-in-out infinite", "0%, 70%, 100% { transform: none; } 78% { transform: scale(1.05, .93); } 86% { transform: translateY(-4%) scale(.97, 1.04); } 93% { transform: scale(1.02, .98); }"),
    "spiral": ("4s ease-in-out infinite alternate", "from { transform: rotate(-16deg); } to { transform: rotate(16deg); }"),
    "tree":   ("2.8s ease-in-out infinite alternate", "from { transform: rotate(-4deg); } to { transform: rotate(4deg); }"),
}
css = []
for name, (_, pivot) in DOODLES.items():
    timing, kf = ANIM[name]
    css += [f".{name} {{ {origin(*pivot)} animation: {name} {timing}; }}", f"@keyframes {name} {{ {kf} }}"]
for i, (name, (_, pivot)) in enumerate(DASHES.items()):
    css.append(f".{name} {{ {origin(*pivot)} animation: pulse 1.4s ease-in-out {-i * .45:.2f}s infinite; }}")
css.append("@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.18); opacity: .75; } }")
# hand: short scribbles around the pivot, with a pause
css += [f".hand {{ {origin(*PIVOT)} animation: scribble 2.4s ease-in-out infinite; }}",
        "@keyframes scribble { 0%, 55%, 100% { transform: rotate(0deg); } 60% { transform: rotate(1.6deg) translateY(-.6%); } "
        "65% { transform: rotate(-.8deg) translateY(.5%); } 70% { transform: rotate(1.4deg) translateY(-.4%); } "
        "75% { transform: rotate(-.6deg) translateY(.6%); } 80% { transform: rotate(1deg); } 88% { transform: rotate(0deg); } }",
        ".dust { transform-box: fill-box; transform-origin: center; opacity: 0; animation: dust 2.4s ease-out infinite; }",
        "@keyframes dust { 0%, 58% { opacity: 0; transform: translate(0, 0) scale(.5); } 64% { opacity: .9; } "
        "90% { opacity: 0; transform: translate(-3%, -4%) scale(1.3); } 100% { opacity: 0; } }"]
tx, ty = CHALK_TIP[0] * k, CHALK_TIP[1] * k
dust = "".join(
    f'<circle class="dust" style="animation-delay:{d:.2f}s" cx="{tx + dx * k:.1f}" cy="{ty + dy * k:.1f}" r="{rr * k:.1f}" fill="#FFFFFF" opacity=".8"/>'
    for dx, dy, rr, d in [(-8, -6, 7, 0), (-22, 4, 5, .12), (-4, -24, 6, .22), (-26, -18, 4, .3), (6, -14, 4, .06)])

body = img_tag(Image.fromarray(board.astype("uint8")))
body += "".join(img_tag(layer_from(pieces[n]), n) for n in DOODLES)
body += "".join(img_tag(layer_from(pieces[n]), n) for n in DASHES)
body += f'<g class="hand">{img_tag(layer_from(hand_m))}</g>{dust}'

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Lavagna" animata: i disegni col gesso prendono vita e la mano
     scarabocchia. Generata con tools/build_lavagna.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Lavagna">
<style>
  {(chr(10) + "  ").join(css)}
</style>
{body}
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

if PREVIEW_DIR:
    for name, arr in [("board", board), ("hand", np.array(layer_from(hand_m)).astype(float))]:
        prev = Image.new("RGBA", (W, H), (200, 240, 220, 255))
        prev.alpha_composite(Image.fromarray(arr.astype("uint8")))
        prev.convert("RGB").save(os.path.join(PREVIEW_DIR, f"lav_{name}.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes")

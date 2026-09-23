"""Split talpe.png into body + arm layers and build an animated SVG icon."""
import base64, io, math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageChops

SRC = os.path.expanduser("~/Downloads/talpe.png")
OUT = sys.argv[1] if len(sys.argv) > 1 else "talpe.svg"
PREVIEW_DIR = os.path.dirname(os.path.abspath(__file__))

im = Image.open(SRC).convert("RGB")
W, H = im.size

# --- 1. background -> alpha (flood fill from the border, so white eyes/teeth stay)
flood = im.copy()
MAGENTA = (255, 0, 255)
for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
    if flood.getpixel(seed) != MAGENTA:
        ImageDraw.floodfill(flood, seed, MAGENTA, thresh=60)
bg = Image.eval(ImageChops.difference(flood, Image.new("RGB", (W, H), MAGENTA)).convert("L"),
                lambda v: 255 if v < 8 else 0)
fg = ImageChops.invert(bg)
# soften the rim: pixels just inside the edge get alpha from their darkness
ring = ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(5)))
lum = im.convert("L")
soft = Image.eval(lum, lambda v: max(0, min(255, int((255 - v) * 255 / 120))))
alpha = Image.composite(soft, fg, ring)
rgba = im.copy()
rgba.putalpha(alpha)

# --- 2. arm + mallet region (measured on the 1024x1024 source)
PIVOT = (325, 610)           # shoulder
ARM_POLY = [(283, 662), (368, 556), (335, 470), (380, 410), (420, 370),
            (480, 330), (500, 280), (520, 20), (60, 20), (60, 700)]
SHOULDER_R = 78              # body keeps the arm pixels this close to the pivot

arm_mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(arm_mask).polygon(ARM_POLY, fill=255)

stub = Image.new("L", (W, H), 0)
px, py = PIVOT
ImageDraw.Draw(stub).ellipse((px - SHOULDER_R, py - SHOULDER_R, px + SHOULDER_R, py + SHOULDER_R), fill=255)
stub = stub.filter(ImageFilter.GaussianBlur(3))

a = rgba.getchannel("A")
arm = rgba.copy()
arm.putalpha(ImageChops.multiply(a, arm_mask))
body_keep = ImageChops.lighter(ImageChops.invert(arm_mask), stub)
body = rgba.copy()
body.putalpha(ImageChops.multiply(a, body_keep))

# dark outline around the shoulder stub only (hidden under the arm at rest,
# visible when the arm swings away) - drawn behind the body layer
ba = body.getchannel("A")
ring_zone = Image.new("L", (W, H), 0)
ImageDraw.Draw(ring_zone).ellipse((px - SHOULDER_R - 12, py - SHOULDER_R - 12,
                                   px + SHOULDER_R + 12, py + SHOULDER_R + 12), fill=255)
outline_a = ImageChops.multiply(ba.filter(ImageFilter.MaxFilter(9)), ring_zone)
outline_a = ImageChops.multiply(outline_a, ImageChops.multiply(arm_mask, a))   # only under the arm itself
outline = Image.new("RGBA", (W, H), (46, 26, 14, 0))
outline.putalpha(outline_a)
outline.alpha_composite(body)
body = outline

# --- 3. place on a square canvas with room for the swing (mallet goes left)
VB = (-140, 20, 1000)         # x0, y0, size in source px
S = 640                      # output px
scale = S / VB[2]

def place(layer):
    canvas = Image.new("RGBA", (VB[2], VB[2]), (0, 0, 0, 0))
    canvas.paste(layer, (-VB[0], -VB[1]), layer)
    return canvas.resize((S, S), Image.LANCZOS)

body_s, arm_s = place(body), place(arm)
pivot_s = ((px - VB[0]) * scale, (py - VB[1]) * scale)

def b64(img):
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=88, method=6)
    return base64.b64encode(buf.getvalue()).decode()

# impact stars: where the mallet face lands at the bottom of the swing
SMASH = -38
face = (185, 185)            # left face of the mallet head, source px
ang = math.radians(SMASH)
dx, dy = face[0] - px, face[1] - py
hit = (px + dx * math.cos(ang) - dy * math.sin(ang), py + dx * math.sin(ang) + dy * math.cos(ang))
hit_s = ((hit[0] - VB[0]) * scale, (hit[1] - VB[1]) * scale)

def star(cx, cy, r, rot=0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = math.radians(rot - 90 + i * 36)
        pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t):.1f}")
    return " ".join(pts)

hx, hy = hit_s
stars = "".join(
    f'<polygon points="{star(hx + ox, hy + oy, r, rot)}" fill="#FFD23F" stroke="#3A2210" stroke-width="4" stroke-linejoin="round"/>'
    for ox, oy, r, rot in [(-22, -6, 26, 10), (10, -50, 18, -15), (6, 36, 16, 20)]
)

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Icona "Acchiappa la Talpa" animata: la talpa batte il martello.
     Livelli ricavati da talpe.png (Scenario): corpo fisso + braccio col
     martello che ruota attorno alla spalla. Rigenerabile con build_talpe.py. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" role="img" aria-label="Talpe">
<style>
  .mole {{ transform-box: view-box; transform-origin: {S/2:.0f}px {S*0.9:.0f}px; animation: squash 2.4s infinite; }}
  .arm  {{ transform-box: view-box; transform-origin: {pivot_s[0]:.1f}px {pivot_s[1]:.1f}px; animation: swing 2.4s infinite; }}
  .pow  {{ transform-box: view-box; transform-origin: {hx:.1f}px {hy:.1f}px; opacity: 0; animation: pow 2.4s infinite; }}
  @keyframes swing {{
    0%, 28%  {{ transform: rotate(0deg); animation-timing-function: ease-in-out; }}
    42%      {{ transform: rotate(9deg); animation-timing-function: cubic-bezier(.6,0,1,.6); }}
    50%      {{ transform: rotate({SMASH}deg); animation-timing-function: ease-out; }}
    56%      {{ transform: rotate({SMASH + 9}deg); animation-timing-function: ease-in; }}
    61%      {{ transform: rotate({SMASH + 1}deg); animation-timing-function: ease-in-out; }}
    84%,100% {{ transform: rotate(0deg); }}
  }}
  @keyframes squash {{
    0%, 48%  {{ transform: scale(1, 1); }}
    52%      {{ transform: scale(1.04, .95); }}
    58%      {{ transform: scale(.98, 1.02); }}
    66%,100% {{ transform: scale(1, 1); }}
  }}
  @keyframes pow {{
    0%, 49%  {{ opacity: 0; transform: scale(.3); }}
    52%      {{ opacity: 1; transform: scale(1.1); }}
    64%      {{ opacity: 1; transform: scale(1); }}
    72%,100% {{ opacity: 0; transform: scale(.8); }}
  }}
</style>
<g class="mole">
  <image width="{S}" height="{S}" href="data:image/webp;base64,{b64(body_s)}"/>
  <image class="arm" width="{S}" height="{S}" href="data:image/webp;base64,{b64(arm_s)}"/>
</g>
<g class="pow">{stars}</g>
</svg>
'''
with open(OUT, "w") as f:
    f.write(svg)

# previews: rest pose and smash pose composited, for a visual check
for name, deg in [("rest", 0), ("smash", SMASH), ("windup", 9)]:
    frame = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    frame.alpha_composite(body_s)
    frame.alpha_composite(arm_s.rotate(-deg, resample=Image.BICUBIC, center=pivot_s))
    frame.save(os.path.join(PREVIEW_DIR, f"preview_{name}.png"))
print("ok", OUT, os.path.getsize(OUT), "bytes; pivot", pivot_s, "hit", hit_s)

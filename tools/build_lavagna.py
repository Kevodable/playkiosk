"""Build the animated lavagna.svg from the Scenario kitten + empty board image.

The board is empty on purpose: chalk doodles are VECTOR paths that draw
themselves one stroke at a time (sun, heart, wavy line, star) with a light
chalk-texture filter, the matching chalk stick in the tray wiggles before
its colour is used, the kitten "writes" at each doodle and hops when the
board is full, then an eraser sweeps it clean. (build_lavagna_v1.py made
the previous icon, from the hand-drawing-on-a-chalkboard art.) Usage:
    python3 build_lavagna.py <source image> <out.svg>
"""
import math, sys
import numpy as np
from iconkit import (load_cutout, layer, connected, mask_box, fill_holes, dilate, Canvas, pct,
                     hop_keyframes, sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
# white pockets enclosed by the easel legs, the ledge, the kitten and the shadow
px, rgba = load_cutout(SRC, seeds=[(650, 620), (480, 610), (600, 600), (700, 600), (760, 630)])
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)

# --- geometry measured on the 1104x832 source
BOARD = (440, 188, 866, 522)           # inner green area used for drawing
STICKS = {"pink": (744, 455, 830, 560), "yellow": (795, 452, 876, 560)}
FEET = (330, 668)

green = (g > r + 15) & (g > b) & (px.max(axis=2) < 170)
wood = (r > 120) & (g < 170) & (b >= 55) & (b < 120) & ((r - g) > 30) & ((r - g) < 85)
shadow = (yy > 630) & (sat < 45) & (r > 170)
stick_colour = {"pink": (r > 200) & (g < 170) & (b > 90), "yellow": (r > 200) & (g > 150) & (b < 120)}

# sticks: their colour plus the dark outline around it (not wood, not board)
stick_m = {}
for n, box in STICKS.items():
    core = mask_box(px.shape, box) & stick_colour[n] & (rgba[..., 3] > 0)
    stick_m[n] = dilate(core, 7) & mask_box(px.shape, box) & ~green & ~wood & (rgba[..., 3] > 0)
stick_m["yellow"] &= ~stick_m["pink"]
sticks = {n: layer(rgba, m) for n, m in stick_m.items()}

# kitten: its own colours connected to the body, a thin rim for its outlines,
# plus whatever it encloses (eyes, mouth)
fur = (r > 195) & (b < 110) & (g > 70) & (g < 215)                 # orange + stripes
cream = (r > 235) & (g > 205) & (b > 120) & (b < 215)
pinkish = (r > 200) & (g < 190) & (b > 110) & (r - g > 40)
chalk_white = (px.min(axis=2) > 205)
core = ((fur | cream | pinkish | chalk_white) & ~wood & ~green & (rgba[..., 3] > 0) & (xx < 600)
        & ~stick_m["pink"] & ~stick_m["yellow"])
# stripes and outlines split the fur into islands: bridge them, then keep
# only what is connected to the body
kitten_m = dilate(core, 4) & ~green & ~wood & (rgba[..., 3] > 0) & ~shadow
kitten_m = connected(kitten_m, (300, 500))
outside = connected(~kitten_m, (0, 0))
kitten_m = ~outside & (rgba[..., 3] > 0) & ~shadow
kitten_m |= (xx < 388) & (rgba[..., 3] > 0) & ~shadow        # whiskers/tail tips; frame starts at 393
kitten = layer(rgba, kitten_m)
pink_m, yellow_m = stick_m["pink"], stick_m["yellow"]

board = layer(rgba, ~kitten_m & ~pink_m & ~yellow_m)
solid = (green | wood) & (rgba[..., 3] > 250)
FRAME = (393, 140, 912, 588)            # board + frame + ledge (legs excluded)
in_frame = mask_box(px.shape, FRAME)
board = fill_holes(board, (kitten_m & in_frame) | dilate(pink_m, 2) | dilate(yellow_m, 2),
                   radii=(6, 20), known=solid)
board[kitten_m & ~in_frame & (yy < 640), 3] = 0     # behind the kitten, outside the frame: empty
board = fill_holes(board, kitten_m & (yy > 640), radii=(8, 25))      # ground shadow under the feet

# --- vector doodles (source coordinates -> canvas)
c = Canvas((157, 30, 780))
def P(x, y):
    X, Y = c.pt(x, y)
    return f"{X:.1f} {Y:.1f}"

def sun_paths(cx, cy, rad):
    out = [f"M{P(cx + rad, cy)} A{rad * c.k:.1f} {rad * c.k:.1f} 0 1 1 {P(cx + rad - .1, cy - 1)}"]
    for i in range(8):
        a = math.radians(i * 45)
        out.append(f"M{P(cx + (rad + 10) * math.cos(a), cy + (rad + 10) * math.sin(a))} "
                   f"L{P(cx + (rad + 30) * math.cos(a), cy + (rad + 30) * math.sin(a))}")
    out.append(f"M{P(cx - 16, cy + 8)} Q{P(cx, cy + 24)} {P(cx + 16, cy + 8)}")        # smile
    return out

def heart_path(cx, cy, s):
    return [f"M{P(cx, cy + s * .55)} C{P(cx - s * 1.1, cy - s * .1)} {P(cx - s * .55, cy - s * .95)} {P(cx, cy - s * .35)} "
            f"C{P(cx + s * .55, cy - s * .95)} {P(cx + s * 1.1, cy - s * .1)} {P(cx, cy + s * .55)}"]

def star_path(cx, cy, rad):
    pts = []
    for i in range(10):
        rr = rad if i % 2 == 0 else rad * .45
        a = math.radians(-90 + i * 36)
        pts.append(P(cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return ["M" + " L".join(pts) + " Z"]

def wave_path(x0, x1, y, amp):
    n = 4
    seg = (x1 - x0) / n
    d = f"M{P(x0, y)}"
    for i in range(n):
        d += f" Q{P(x0 + seg * (i + .5), y + (amp if i % 2 == 0 else -amp))} {P(x0 + seg * (i + 1), y)}"
    return [d]

DOODLES = [  # name, paths, colour, start, duration, stick to lift, x (for the eraser)
    ("sun", sun_paths(560, 272, 36), "#FFE66B", 0.05, 0.13, "yellow", 560),
    ("heart", heart_path(718, 272, 58), "#FF9EC4", 0.21, 0.10, "pink", 718),
    ("wave", wave_path(585, 745, 438, 18), "#9EF59A", 0.34, 0.08, None, 665),
    ("star", star_path(808, 395, 52), "#FFFFFF", 0.45, 0.11, "yellow", 808),
]
T = 7.2
CHEER = 0.60
ERASE0, ERASE1 = 0.74, 0.90
SW = 9 * c.k                           # chalk stroke width

css = []
doodles_svg = ""
for name, paths, colour, t0, dur, stick, xpos in DOODLES:
    n = len(paths)
    # erased when the eraser reaches its x position (it sweeps left to right)
    te = ERASE0 + (ERASE1 - ERASE0) * (xpos - BOARD[0]) / (BOARD[2] - BOARD[0])
    css.append(f".{name} {{ animation: fade-{name} {T}s infinite; }}")
    css.append(f"@keyframes fade-{name} {{ 0%, {pct(te - .01)} {{ opacity: 1; }} {pct(te + .02)}, 100% {{ opacity: 0; }} }}")
    group = ""
    for i, d in enumerate(paths):
        s0 = t0 + dur * i / n
        s1 = t0 + dur * (i + 1) / n
        css.append(f".{name}{i} {{ stroke-dasharray: 100; stroke-dashoffset: 100; animation: draw-{name}{i} {T}s linear infinite; }}")
        css.append(f"@keyframes draw-{name}{i} {{ 0%, {pct(s0)} {{ stroke-dashoffset: 100; }} {pct(s1)}, 100% {{ stroke-dashoffset: 0; }} }}")
        group += (f'<path class="{name}{i}" pathLength="100" d="{d}" fill="none" stroke="{colour}" '
                  f'stroke-width="{SW:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    doodles_svg += f'<g class="{name}">{group}</g>'

# sticks wiggle just before their colour is drawn
for sname in STICKS:
    kf = ["0% { transform: none; }"]
    for _, _, _, t0, dur, stick, _ in DOODLES:
        if stick == sname:
            kf += [f"{pct(t0 - .04)} {{ transform: none; }}", f"{pct(t0 - .025)} {{ transform: rotate(-7deg); }}",
                   f"{pct(t0 - .01)} {{ transform: rotate(5deg); }}", f"{pct(t0 + .005)} {{ transform: rotate(-4deg); }}",
                   f"{pct(t0 + .02)} {{ transform: none; }}"]
    kf.append("100% { transform: none; }")
    bx = STICKS[sname]
    css += [f".st-{sname} {{ {c.origin((bx[0] + bx[2]) / 2, bx[3])} animation: st-{sname} {T}s infinite; }}",
            f"@keyframes st-{sname} {{ {' '.join(kf)} }}"]

# kitten: small writing wiggle during each doodle, hops when the board is full
wig = ["0% { transform: none; }"]
for _, _, _, t0, dur, _, _ in DOODLES:
    wig += [f"{pct(t0)} {{ transform: none; }}", f"{pct(t0 + dur * .25)} {{ transform: rotate(-2.5deg); }}",
            f"{pct(t0 + dur * .5)} {{ transform: rotate(1deg); }}", f"{pct(t0 + dur * .75)} {{ transform: rotate(-2deg); }}",
            f"{pct(t0 + dur)} {{ transform: none; }}"]
wig.append("100% { transform: none; }")
css += [f".kwig {{ {c.origin(*FEET)} animation: kwig {T}s infinite; }}", f"@keyframes kwig {{ {' '.join(wig)} }}",
        f".khop {{ {c.origin(*FEET)} animation: khop {T}s infinite; }}",
        f"@keyframes khop {{ {hop_keyframes([CHEER, CHEER + .09], lift='4%')} }}",
        f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
        f"@keyframes spark {{ 0%, {pct(CHEER)} {{ opacity: 0; transform: scale(.3); }} "
        f"{pct(CHEER + .03)} {{ opacity: 1; transform: scale(1.1); }} {pct(CHEER + .1)} {{ opacity: 1; transform: scale(1); }} "
        f"{pct(CHEER + .14)}, 100% {{ opacity: 0; transform: scale(.8); }} }}"]

# eraser: wooden block with grey felt, zig-zags across the board left to right
ex0, ex1 = c.pt(BOARD[0] + 40, 0)[0], c.pt(BOARD[2] - 40, 0)[0]
ey_top, ey_bot = c.pt(0, 290)[1], c.pt(0, 420)[1]
ew, eh = 80 * c.k, 38 * c.k
css += [f".eraser {{ opacity: 0; animation: eraser {T}s ease-in-out infinite; }}",
        f"@keyframes eraser {{ 0%, {pct(ERASE0 - .02)} {{ opacity: 0; transform: translate({ex0:.1f}px, {ey_top:.1f}px); }} "
        f"{pct(ERASE0)} {{ opacity: 1; transform: translate({ex0:.1f}px, {ey_top:.1f}px) rotate(-6deg); }} "
        f"{pct(ERASE0 + (ERASE1 - ERASE0) * .33)} {{ transform: translate({ex0 + (ex1 - ex0) * .33:.1f}px, {ey_bot:.1f}px) rotate(6deg); }} "
        f"{pct(ERASE0 + (ERASE1 - ERASE0) * .66)} {{ transform: translate({ex0 + (ex1 - ex0) * .66:.1f}px, {ey_top:.1f}px) rotate(-6deg); }} "
        f"{pct(ERASE1)} {{ opacity: 1; transform: translate({ex1:.1f}px, {ey_bot:.1f}px) rotate(6deg); }} "
        f"{pct(ERASE1 + .03)}, 100% {{ opacity: 0; transform: translate({ex1:.1f}px, {ey_bot:.1f}px); }} }}"]
eraser = (f'<g class="eraser"><rect x="{-ew / 2:.1f}" y="{-eh / 2:.1f}" width="{ew:.1f}" height="{eh:.1f}" rx="{eh * .25:.1f}" '
          f'fill="#C98A52" stroke="#5B3A1E" stroke-width="3"/>'
          f'<rect x="{-ew / 2:.1f}" y="{eh * .05:.1f}" width="{ew:.1f}" height="{eh * .45:.1f}" rx="{eh * .15:.1f}" '
          f'fill="#6B7280" stroke="#3F4550" stroke-width="3"/></g>')

defs = ('<defs><filter id="chalk" x="-5%" y="-5%" width="110%" height="110%">'
        '<feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" seed="4" result="n"/>'
        '<feDisplacementMap in="SourceGraphic" in2="n" scale="3.5" xChannelSelector="R" yChannelSelector="G"/>'
        '</filter></defs>\n')
kx, ky = c.pt(330, 330)
sparks = sparkle_burst(kx, ky, 165 * c.k, [22, 16, 26, 16, 22], "spark")
body = (c.image(board) + f'<g filter="url(#chalk)" opacity=".93">{doodles_svg}</g>' + eraser
        + c.image(sticks["pink"], "st-pink") + c.image(sticks["yellow"], "st-yellow")
        + f'<g class="khop"><g class="kwig">{c.image(kitten)}</g></g>' + sparks)
svg = c.svg("Lavagna", "Icona \"Lavagna\" animata: i disegni col gesso si tracciano da soli, il gattino esulta "
            "e il cancellino pulisce. Generata dall'immagine Scenario con tools/build_lavagna.py.", css, body, defs)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes")

"""Build the animated puzzle.svg (Rompicapo scorrevole) from the Scenario turtle image.

A 3x3 wooden tray with one empty slot (middle right). Tiles slide like the
real game: the heart tile slides down into the gap, the circle tile slides
right into the new gap, then both slide back - puzzle solved: sparkles
and the turtle hops. Every slot's floor is a copy of the real empty slot,
so a tile sliding away reveals a believable empty slot. Usage:
    python3 build_puzzle.py <source image> <out.svg>
"""
import sys
import numpy as np
from iconkit import (load_cutout, to_img, layer, mask_box, fill_holes, dilate, Canvas, pct,
                     hop_keyframes, sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
px, rgba = load_cutout(SRC, seeds=[(425, 520), (425, 600), (425, 660)])  # pocket under the arm
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]

# --- geometry measured on the 1104x832 source
COLS = [(489, 639), (643, 792), (798, 946)]
ROWS = [(198, 350), (351, 506), (508, 662)]
EMPTY = (1, 2)                                  # row, col of the empty slot
TRAY = (438, 139, 1008, 722)
HAND = (428, 368, 482, 452)                     # turtle's pointing hand over the frame
FEET = (240, 720)

def cell(rw, cl):
    return (COLS[cl][0], ROWS[rw][0], COLS[cl][1], ROWS[rw][1])

# tray with every slot emptied: paste the real empty slot's floor everywhere
tray = rgba.copy()
ex0, ey0, ex1, ey1 = cell(*EMPTY)
floor = rgba[ey0:ey1, ex0:ex1].copy()
tiles = {}
for rw in range(3):
    for cl in range(3):
        if (rw, cl) == EMPTY:
            continue
        x0, y0, x1, y1 = cell(rw, cl)
        tiles[(rw, cl)] = layer(rgba, mask_box(px.shape, (x0, y0, x1, y1)))
        tray[y0:y1, x0:x1] = np.array(to_img(floor).resize((x1 - x0, y1 - y0))).astype(float)

# turtle vs tray: the pointing hand sits over the tray frame
green = (g > r + 10) & (g > b + 30)
turtle_m = (np.arange(W)[None, :] < TRAY[0] - 6) | (mask_box(px.shape, HAND) & green)
turtle_m &= rgba[..., 3] > 0
# the ground shadow stays put (it spans turtle and tray)
shadow = (np.arange(H)[:, None] > 690) & ~green & (r > 190)
turtle_m &= ~shadow
turtle = layer(rgba, turtle_m)
tray_m = ~turtle_m
tray = layer(tray, tray_m)
tray = fill_holes(tray, dilate(mask_box(px.shape, HAND) & green, 2), radii=(6, 20))

# --- animation
c = Canvas((52, -40, 980))
T = 6.4
DX = (COLS[1][0] - COLS[0][0]) * c.k
DY = (ROWS[1][0] - ROWS[0][0]) * c.k
SLIDE = 0.08
# (tile, start, dx, dy): heart down, circle right, circle back, heart back up
MOVES = [((0, 2), 0.10, 0, DY), ((0, 1), 0.28, DX, 0), ((0, 1), 0.52, 0, 0), ((0, 2), 0.70, 0, 0)]
SOLVED = 0.80

css = []
for key in tiles:
    kf = ["0% { transform: translate(0, 0); }"]
    pos = (0, 0)
    for tile, t, dx, dy in MOVES:
        if tile != key:
            continue
        kf += [f"{pct(t)} {{ transform: translate({pos[0]:.1f}px, {pos[1]:.1f}px); animation-timing-function: cubic-bezier(.4,0,.3,1.25); }}",
               f"{pct(t + SLIDE)} {{ transform: translate({dx:.1f}px, {dy:.1f}px); }}"]
        pos = (dx, dy)
    kf.append("100% { transform: translate(0, 0); }")
    if len(kf) > 2:
        css += [f".t{key[0]}{key[1]} {{ animation: t{key[0]}{key[1]} {T}s infinite; }}",
                f"@keyframes t{key[0]}{key[1]} {{ {' '.join(kf)} }}"]

nod = ["0% { transform: none; }"]
for _, t, _, _ in MOVES:
    nod += [f"{pct(t)} {{ transform: none; }}", f"{pct(t + .03)} {{ transform: rotate(-3deg); }}",
            f"{pct(t + .07)} {{ transform: none; }}"]
nod.append("100% { transform: none; }")
css += [f".turtle {{ {c.origin(*FEET)} animation: nod {T}s infinite; }}",
        f"@keyframes nod {{ {' '.join(nod)} }}",
        f".hopper {{ {c.origin(*FEET)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {hop_keyframes([SOLVED])} }}",
        f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
        f"@keyframes spark {{ 0%, {pct(SOLVED)} {{ opacity: 0; transform: scale(.3); }} "
        f"{pct(SOLVED + .03)} {{ opacity: 1; transform: scale(1.1); }} {pct(SOLVED + .1)} {{ opacity: 1; transform: scale(1); }} "
        f"{pct(SOLVED + .15)}, 100% {{ opacity: 0; transform: scale(.8); }} }}"]

tcx, tcy = c.pt((TRAY[0] + TRAY[2]) / 2, (TRAY[1] + TRAY[3]) / 2)
sparks = sparkle_burst(tcx, tcy, (TRAY[2] - TRAY[0]) * c.k * .56, [22, 16, 26, 18, 24, 16], "spark")

body = c.image(tray)
body += "".join(c.image(tl, f"t{k0}{k1}") for (k0, k1), tl in tiles.items())
body += f'<g class="hopper"><g class="turtle">{c.image(turtle)}</g></g>{sparks}'
svg = c.svg("Rompicapo", "Icona \"Rompicapo\" animata: le tessere scivolano come nel gioco. "
            "Generata dall'immagine Scenario con tools/build_puzzle.py.", css, body)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes")

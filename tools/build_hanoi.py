"""Build the animated hanoi.svg from the Scenario elephant + three-peg image.

The four rings sit on the MIDDLE peg (that is how the art came out). The
top two (yellow, red) play a real little Tower of Hanoi: yellow -> left,
red -> right, yellow -> right (on red); the elephant cheers; then they go
back the same way. A ring lifts above the peg's ball, travels, and drops
onto its slot. The middle peg hidden behind the two rings is rebuilt from
its visible part, so it shows correctly when they leave. Usage:
    python3 build_hanoi.py <source image> <out.svg>
"""
import sys
import numpy as np
from iconkit import (load_cutout, layer, mask_box, fill_holes, Canvas, pct, hop_keyframes,
                     sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]
sat = px.max(axis=2) - px.min(axis=2)

# --- geometry measured on the 1104x832 source
PEG_X = {"L": 571, "M": 676, "R": 781}
RING_X = (638, 715)                        # ring extent around the middle peg
RINGS = {"Y": (468, 511), "R": (511, 552)}  # y bands of the two moving rings
SLOT_Y = [614, 572, 531, 490]              # ring centres from the bottom up
LIFT_Y = 345                               # clears the balls on top of the pegs
PEG_REF = (455, 666, 685)                  # clean peg row (y, x0, x1) above the rings
PEG_LOW = (660, 665, 689)                  # peg row below the rings
ELEPHANT_X = 470
FEET = (330, 740)

# the two moving rings
ring_m = {n: mask_box(px.shape, (RING_X[0], y0, RING_X[1], y1)) & (rgba[..., 3] > 0) for n, (y0, y1) in RINGS.items()}
rings = {n: layer(rgba, m) for n, m in ring_m.items()}

# board: without the two rings; the middle peg under them redrawn row by row
board = rgba.copy()
gone = ring_m["Y"] | ring_m["R"]
board[gone, 3] = 0
ref_y, rx0, rx1 = PEG_REF
ref = rgba[ref_y, rx0 - 2:rx1 + 3]
for y in range(RINGS["Y"][0], RINGS["R"][1]):
    t = (y - ref_y) / (PEG_LOW[0] - ref_y)
    x0 = PEG_REF[1] + (PEG_LOW[1] - PEG_REF[1]) * t
    x1 = PEG_REF[2] + (PEG_LOW[2] - PEG_REF[2]) * t
    n = int(round(x1 - x0)) + 5
    cols = np.linspace(0, len(ref) - 1, n)
    row = np.array([ref[int(round(c))] for c in cols])
    xs = int(round(x0)) - 2
    board[y, xs:xs + n] = row

shadow = (yy > 700) & (sat < 40) & (r < 225) & (r > 150)
elephant_m = (xx < ELEPHANT_X) & (rgba[..., 3] > 0) & ~shadow
elephant = layer(rgba, elephant_m)
board[elephant_m, 3] = 0
board = fill_holes(board, elephant_m & (yy > 700), radii=(8, 25), known=shadow & (rgba[..., 3] > 200))   # its ground shadow

# --- animation
c = Canvas((148, 140, 800))
T = 8
MOVE = 0.09
# (ring, from peg, from slot, to peg, to slot, start)
MOVES = [("Y", "M", 3, "L", 0, 0.06), ("R", "M", 2, "R", 0, 0.17), ("Y", "L", 0, "R", 1, 0.28),
         ("Y", "R", 1, "L", 0, 0.58), ("R", "R", 0, "M", 2, 0.69), ("Y", "L", 0, "M", 3, 0.80)]
CHEER = 0.40
HOME = {"Y": ("M", 3), "R": ("M", 2)}

def offset(ring, peg, slot):
    """translate (canvas px) from the ring's home to (peg, slot)."""
    hp, hs = HOME[ring]
    return ((PEG_X[peg] - PEG_X[hp]) * c.k, (SLOT_Y[slot] - SLOT_Y[hs]) * c.k)

css = []
for ring in RINGS:
    kf = ["0% { transform: translate(0px, 0px); }"]
    for rg, fp, fs, tp, ts, t in MOVES:
        if rg != ring:
            continue
        ax, ay = offset(ring, fp, fs)
        bx, by = offset(ring, tp, ts)
        lift = (LIFT_Y - SLOT_Y[HOME[ring][1]]) * c.k
        kf += [f"{pct(t)} {{ transform: translate({ax:.1f}px, {ay:.1f}px); animation-timing-function: ease-out; }}",
               f"{pct(t + MOVE * .3)} {{ transform: translate({ax:.1f}px, {lift:.1f}px); animation-timing-function: ease-in-out; }}",
               f"{pct(t + MOVE * .65)} {{ transform: translate({bx:.1f}px, {lift:.1f}px); animation-timing-function: ease-in; }}",
               f"{pct(t + MOVE)} {{ transform: translate({bx:.1f}px, {by:.1f}px); }}",
               f"{pct(t + MOVE + .015)} {{ transform: translate({bx:.1f}px, {by - 4:.1f}px); }}",
               f"{pct(t + MOVE + .03)} {{ transform: translate({bx:.1f}px, {by:.1f}px); }}"]
    kf.append("100% { transform: translate(0px, 0px); }")
    css += [f".ring-{ring} {{ animation: ring-{ring} {T}s infinite; }}", f"@keyframes ring-{ring} {{ {' '.join(kf)} }}"]

css += [f".elephant {{ {c.origin(*FEET)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {hop_keyframes([CHEER, CHEER + .1], lift='5%')} }}",
        f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
        f"@keyframes spark {{ 0%, {pct(CHEER)} {{ opacity: 0; transform: scale(.3); }} "
        f"{pct(CHEER + .03)} {{ opacity: 1; transform: scale(1.1); }} {pct(CHEER + .12)} {{ opacity: 1; transform: scale(1); }} "
        f"{pct(CHEER + .16)}, 100% {{ opacity: 0; transform: scale(.8); }} }}"]

sx, sy = c.pt(PEG_X["R"], 520)
sparks = sparkle_burst(sx, sy, 120 * c.k, [22, 16, 26, 16, 22], "spark")
ex, ey = c.pt(320, 560)
sparks += sparkle_burst(ex, ey, 150 * c.k, [18, 14, 20], "spark")
# red ring first so the yellow one is drawn on top when they stack
body = (c.image(board) + c.image(rings["R"], "ring-R") + c.image(rings["Y"], "ring-Y")
        + f'<g class="elephant">{c.image(elephant)}</g>' + sparks)
svg = c.svg("Torre di Hanoi", "Icona \"Torre di Hanoi\" animata: gli anelli si spostano tra i pioli e "
            "l'elefantino esulta. Generata dall'immagine Scenario con tools/build_hanoi.py.", css, body)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes")

"""Build the animated tris.svg from the Scenario frog + grid image.

The X and O tokens float above the grid like two piles; copies of them
fly in turns into the grid cells (X, O, X, O), then the frog hops for joy
with sparkles and the board clears. The generator drew three vertical
bars, so the four clean inner cells (2x2) are used. Usage:
    python3 build_tris.py <source image> <out.svg>
"""
import sys
import numpy as np
from iconkit import (load_cutout, layer, mask_box, fill_holes, dilate, Canvas, pct,
                     hop_keyframes, sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
# white pockets enclosed by the grid bars, the frog's arm and the ground shadow
POCKETS = [(648, 442), (818, 442), (648, 627), (818, 627), (648, 690), (818, 690),
           (965, 442), (965, 627), (522, 442), (522, 620), (522, 690), (648, 300), (818, 300)]
px, rgba = load_cutout(SRC, seeds=POCKETS)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]

# --- geometry measured on the 1104x832 source
X_BOX, O_BOX = (500, 98, 648, 252), (736, 82, 922, 264)
CELLS = {"A2": (648, 442), "B2": (818, 442), "A3": (648, 627), "B3": (818, 627)}
BAR_ENDS = [(488, 320, 549, 392), (488, 494, 549, 564)]   # grid bar tips left of bar A
FEET = (330, 725)
TOKEN_SCALE = 0.62

green = (g > r + 15) & (g > b + 15)
purple = (b > g + 30) & (r > g + 15) & (px.max(axis=2) < 235)
shadow = (yy > 690) & ~green & (np.abs(g - b) < 22) & (b > r)

frog_m = ((xx < 549) | (green & (xx < 605))) & (rgba[..., 3] > 0) & ~shadow
for box in BAR_ENDS:
    frog_m &= ~(mask_box(px.shape, box) & ~green)
frog_m &= ~mask_box(px.shape, X_BOX)
frog = layer(rgba, frog_m)

x_tok = layer(rgba, mask_box(px.shape, X_BOX) & ~frog_m)
o_tok = layer(rgba, mask_box(px.shape, O_BOX))
rest_m = ~frog_m & ~mask_box(px.shape, X_BOX) & ~mask_box(px.shape, O_BOX)
board = layer(rgba, rest_m)
# the ground shadow under the frog (hidden by its feet) is rebuilt for the hop
board = fill_holes(board, frog_m & (yy > 680), radii=(8, 25))
# the frog's hand covers a bit of the first bar: rebuild it for the hop
board = fill_holes(board, dilate(frog_m & (xx >= 549), 2), radii=(6, 18))

# --- animation
c = Canvas((40, -60, 1000))
T = 6.4
MOVES = [("x", "A2", 0.10), ("o", "B3", 0.25), ("x", "A3", 0.40), ("o", "B2", 0.55)]
FLY = 0.07
WIN = 0.68
CLEAR = 0.88

def centre(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

css = [
    f".pile-x {{ {c.origin(*centre(X_BOX))} animation: bobx 2.2s ease-in-out infinite alternate; }}",
    "@keyframes bobx { from { transform: translateY(-2%) rotate(-6deg); } to { transform: translateY(1%) rotate(6deg); } }",
    f".pile-o {{ {c.origin(*centre(O_BOX))} animation: bobo 2.6s ease-in-out -.8s infinite alternate; }}",
    "@keyframes bobo { from { transform: translateY(1%) rotate(5deg); } to { transform: translateY(-2%) rotate(-5deg); } }",
]
moves_svg = ""
for i, (tok, cell, t) in enumerate(MOVES):
    box = X_BOX if tok == "x" else O_BOX
    (sx, sy), (tx, ty) = c.pt(*centre(box)), c.pt(*CELLS[cell])
    dx, dy = tx - sx, ty - sy
    css += [f".m{i} {{ {c.origin(*centre(box))} opacity: 0; animation: m{i} {T}s infinite; }}",
            f"@keyframes m{i} {{ 0%, {pct(t - .001)} {{ opacity: 0; transform: none; }} "
            f"{pct(t)} {{ opacity: 1; transform: none; animation-timing-function: ease-out; }} "
            f"{pct(t + FLY * .5)} {{ transform: translate({dx * .5:.1f}px, {dy * .5 - 40:.1f}px) scale(.85) rotate({'-' if i % 2 else ''}20deg); animation-timing-function: ease-in; }} "
            f"{pct(t + FLY)} {{ opacity: 1; transform: translate({dx:.1f}px, {dy:.1f}px) scale({TOKEN_SCALE}); }} "
            f"{pct(t + FLY + .02)} {{ transform: translate({dx:.1f}px, {dy:.1f}px) scale({TOKEN_SCALE * 1.12:.3f}); }} "
            f"{pct(t + FLY + .04)} {{ transform: translate({dx:.1f}px, {dy:.1f}px) scale({TOKEN_SCALE}); }} "
            f"{pct(CLEAR)} {{ opacity: 1; transform: translate({dx:.1f}px, {dy:.1f}px) scale({TOKEN_SCALE}); }} "
            f"{pct(CLEAR + .05)}, 100% {{ opacity: 0; transform: translate({dx:.1f}px, {dy:.1f}px) scale(.2); }} }}"]
    moves_svg += c.image(x_tok if tok == "x" else o_tok, f"m{i}")

css += [f".frog {{ {c.origin(*FEET)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {hop_keyframes([WIN, WIN + .1], lift='4%')} }}",
        f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
        f"@keyframes spark {{ 0%, {pct(WIN)} {{ opacity: 0; transform: scale(.3); }} "
        f"{pct(WIN + .03)} {{ opacity: 1; transform: scale(1.1); }} {pct(WIN + .14)} {{ opacity: 1; transform: scale(1); }} "
        f"{pct(WIN + .19)}, 100% {{ opacity: 0; transform: scale(.8); }} }}"]

gx, gy = c.pt(740, 480)
sparks = sparkle_burst(gx, gy, 250 * c.k, [22, 16, 26, 18, 24, 16], "spark")
body = (c.image(board) + moves_svg + c.image(x_tok, "pile-x") + c.image(o_tok, "pile-o")
        + f'<g class="frog">{c.image(frog)}</g>' + sparks)
svg = c.svg("Tris", "Icona \"Tris\" animata: X e O si alternano nella griglia e la rana esulta. "
            "Generata dall'immagine Scenario con tools/build_tris.py.", css, body)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes")

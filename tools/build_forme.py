"""Build the animated forme.svg (Abbina le forme) from the Scenario bunny image.

The generator drew three ROUND holes; the middle and right ones are
covered with wood and redrawn as a square and a triangle hole, so each
block has its own. The blocks (red circle, blue cube, yellow pyramid) hop
one at a time onto their hole and drop in with a pop of sparkles; after
the third the bunny hops and the blocks pop back on top. Usage:
    python3 build_forme.py <source image> <out.svg>
"""
import sys
import numpy as np
from iconkit import (load_cutout, layer, mask_box, mask_ellipse, fill_holes, dilate, Canvas,
                     pct, hop_keyframes, sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]

# --- geometry measured on the 1104x832 source
BLOCKS = {  # box of the block, box of its shadow on the board, target hole centre
    "circle":   ((562, 442, 670, 552), (546, 494, 682, 588), (602, 628)),
    "square":   ((684, 444, 782, 547), (668, 494, 792, 584), (721, 628)),
    "triangle": ((791, 437, 912, 542), (784, 496, 920, 580), (840, 627)),
}
HOLE_R = 45
BOARD_X = 505                  # bunny is left of this
FEET = (330, 745)

EDGE = ((548, 500), (932, 481))          # board top edge, left and right
OUTLINE, BEVEL = (150, 104, 58), (252, 202, 141)
def edge_y(x):
    (x0, y0), (x1, y1) = EDGE
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

# blocks: everything in their box above the board edge; below it, not wood
wood = (r > g) & (g > b) & ((r - b) > 60) & ((r - b) < 150) & ((g - b) > 25)
on_face = yy >= edge_y(xx) + 2
block_m = {n: mask_box(px.shape, bx) & (rgba[..., 3] > 0) & ~(wood & on_face) for n, (bx, _, _) in BLOCKS.items()}
blocks = {n: layer(rgba, m) for n, m in block_m.items()}

shadow = (yy > 725) & (b > g) & (r > g) & ((px.max(axis=2) - px.min(axis=2)) < 45)   # grey-lilac ground shadow
bunny_m = (xx < BOARD_X) & (rgba[..., 3] > 0) & ~shadow
bunny = layer(rgba, bunny_m)

# board: without blocks, their shadows, and the two holes to be reshaped
hole = np.zeros((H, W), bool)
for n, (bx, sh, _) in BLOCKS.items():
    hole |= mask_box(px.shape, bx) | mask_box(px.shape, sh)
board = layer(rgba, ~bunny_m)
# the ground shadow under the bunny (hidden by its feet) is rebuilt for the hop
board = fill_holes(board, bunny_m & (yy > 700), radii=(8, 25))

# under the blocks: wood face filled from around, then the board's top edge
# redrawn with its measured profile (dark outline, light bevel, face) along
# the edge's slope; above the edge stays empty
board = fill_holes(board, hole, radii=(10, 30), grain=3, known=(board[..., 3] > 250) & wood & on_face)
ys, xs = np.nonzero(hole)
e = edge_y(xs)
above, line, bevel = ys < e - 1, (ys >= e - 1) & (ys < e + 2), (ys >= e + 2) & (ys < e + 4)
board[ys[above], xs[above], 3] = 0
board[ys[~above], xs[~above], 3] = 255                 # the wood face is solid
board[ys[line], xs[line]] = OUTLINE + (255,)
board[ys[bevel], xs[bevel]] = BEVEL + (255,)
# the redrawn holes' old round shape: smooth wood over it
round_holes = np.zeros((H, W), bool)
for n in ("square", "triangle"):
    cx, cy = BLOCKS[n][2]
    round_holes |= mask_ellipse(px.shape, (cx - HOLE_R - 6, cy - HOLE_R - 6, cx + HOLE_R + 6, cy + HOLE_R + 6))
board = fill_holes(board, round_holes, radii=(10, 30), grain=3, known=(board[..., 3] > 250) & wood & on_face)

# --- animation
c = Canvas((77, -5, 900))
T = 6.4
DROP = {"circle": 0.10, "square": 0.30, "triangle": 0.50}
CHEER = 0.62
BACK = 0.84

def centre(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)

css = []
body_blocks = ""
for n, (bx, _, (hx, hy)) in BLOCKS.items():
    t = DROP[n]
    (sx, sy), (tx, ty) = c.pt(*centre(bx)), c.pt(hx, hy)
    dx, dy = tx - sx, ty - sy
    css += [f".b-{n} {{ {c.origin(*centre(bx))} animation: b-{n} {T}s infinite; }}",
            f"@keyframes b-{n} {{ 0%, {pct(t)} {{ transform: none; opacity: 1; animation-timing-function: ease-out; }} "
            f"{pct(t + .05)} {{ transform: translate({dx * .5:.1f}px, {dy * .5 - 60 * c.k:.1f}px) rotate(-10deg); animation-timing-function: ease-in; }} "
            f"{pct(t + .09)} {{ transform: translate({dx:.1f}px, {dy - 10 * c.k:.1f}px) scale(.8); opacity: 1; }} "
            f"{pct(t + .12)} {{ transform: translate({dx:.1f}px, {dy + 6 * c.k:.1f}px) scale(.45, .3); opacity: 0; }} "
            f"{pct(BACK)} {{ transform: scale(0); opacity: 0; }} "
            f"{pct(BACK + .005)} {{ transform: scale(0); opacity: 1; animation-timing-function: cubic-bezier(.3,1.6,.6,1); }} "
            f"{pct(BACK + .07)}, 100% {{ transform: none; opacity: 1; }} }}",
            f".p-{n} {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: p-{n} {T}s infinite; }}",
            f"@keyframes p-{n} {{ 0%, {pct(t + .11)} {{ opacity: 0; transform: scale(.3); }} "
            f"{pct(t + .13)} {{ opacity: 1; transform: scale(1.1); }} {pct(t + .2)}, 100% {{ opacity: 0; transform: scale(1.3); }} }}"]
    body_blocks += c.image(blocks[n], f"b-{n}")

# vector holes for the square and the triangle, in the style of the round one
def hole_svg(n):
    cx, cy = c.pt(*BLOCKS[n][2])
    R = HOLE_R * c.k * 0.95
    if n == "square":
        outer = f'<rect x="{cx - R:.1f}" y="{cy - R:.1f}" width="{2 * R:.1f}" height="{2 * R:.1f}" rx="{R * .18:.1f}"'
        inner = f'<rect x="{cx - R * .72:.1f}" y="{cy - R * .55:.1f}" width="{R * 1.62:.1f}" height="{R * 1.5:.1f}" rx="{R * .12:.1f}"'
    else:
        pts = [(cx, cy - R * 1.05), (cx + R * 1.12, cy + R * .9), (cx - R * 1.12, cy + R * .9)]
        ipts = [(cx + R * .1, cy - R * .5), (cx + R * .85, cy + R * .78), (cx - R * .6, cy + R * .78)]
        outer = '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '" stroke-linejoin="round"'
        inner = '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in ipts) + '" stroke-linejoin="round"'
    return (f'{outer} fill="#7D4A35" stroke="#6A3C2A" stroke-width="{3 * c.k * 1.5:.1f}"/>'
            f'{inner} fill="#5E3527"/>')

sparks = ""
for n, (_, _, (hx, hy)) in BLOCKS.items():
    x, y = c.pt(hx, hy)
    sparks += sparkle_burst(x, y, 62 * c.k, [16, 12, 18, 12, 15], f"p-{n}")

css += [f".bunny {{ {c.origin(*FEET)} animation: hop {T}s infinite; }}",
        f"@keyframes hop {{ {hop_keyframes([CHEER, CHEER + .1], lift='4%')} }}"]

body = (c.image(board) + hole_svg("square") + hole_svg("triangle") + body_blocks
        + f'<g class="bunny">{c.image(bunny)}</g>' + sparks)
svg = c.svg("Forme", "Icona \"Abbina le forme\" animata: i blocchi entrano nel loro buco e il coniglietto esulta. "
            "Generata dall'immagine Scenario con tools/build_forme.py.", css, body)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes")

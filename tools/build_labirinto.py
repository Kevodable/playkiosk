"""Build the animated labirinto.svg from the Scenario mouse + maze image.

The maze corridor (cream) is a closed loop. A glowing ball starts at the
bottom-left corner (next to the mouse), runs clockwise along the middle
of the corridor - leaving a trail - to the spot nearest the cheese; the
cheese jumps with sparkles and the mouse hops. The route is computed from
the image (BFS on the eroded corridor, with the loop cut at the bottom so
it goes the long way round), so it never crosses a wall. Usage:
    python3 build_labirinto.py <source image> <out.svg>
"""
import sys
from collections import deque
import numpy as np
from iconkit import (load_cutout, layer, mask_box, fill_holes, erode, Canvas, pct,
                     hop_keyframes, sparkle_burst)

SRC, OUT = sys.argv[1], sys.argv[2]
px, rgba = load_cutout(SRC)
H, W = px.shape[:2]
r, g, b = px[..., 0], px[..., 1], px[..., 2]
xx = np.arange(W)[None, :]
yy = np.arange(H)[:, None]

# --- geometry measured on the 1104x832 source
MAZE = (400, 170, 930, 690)
CHEESE = (738, 158, 902, 298)
START, END = (447, 620), (880, 372)
CUT = (560, 580, 620, 660)          # blocks the short way round (bottom corridor)
HAND = (352, 478, 428, 552)         # mouse's pointing hand over the maze wall
FEET = (270, 740)

sat = px.max(axis=2) - px.min(axis=2)
cream = (r > 190) & (g > 180) & (b > 130) & (r >= b) & (r - b < 100) & (r - g < 30)
corridor = cream & mask_box(px.shape, MAZE) & ~mask_box(px.shape, CHEESE)

# --- route: BFS on a 4x-downsampled, eroded corridor with the loop cut
F = 4
band = erode(corridor, 9) & ~mask_box(px.shape, CUT)
small = band[:H // F * F, :W // F * F].reshape(H // F, F, W // F, F).mean(axis=(1, 3)) > 0.5

def nearest(p):
    ys, xs = np.nonzero(small)
    i = np.argmin((xs * F - p[0]) ** 2 + (ys * F - p[1]) ** 2)
    return (ys[i], xs[i])

start, end = nearest(START), nearest(END)
prev = {start: None}
q = deque([start])
while q:
    y, x = q.popleft()
    if (y, x) == end:
        break
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (y + dy, x + dx)
        if 0 <= n[0] < small.shape[0] and 0 <= n[1] < small.shape[1] and small[n] and n not in prev:
            prev[n] = (y, x)
            q.append(n)
route = []
node = end
while node is not None:
    route.append((node[1] * F + F / 2, node[0] * F + F / 2))
    node = prev[node]
route = np.array(route[::-1], float)
# smooth the staircase and thin it out
k = 5
sm = np.array([route[max(0, i - k):i + k + 1].mean(axis=0) for i in range(len(route))])
sm[0], sm[-1] = route[0], route[-1]
pts = sm[::3].tolist() + [sm[-1].tolist()]

# --- layers
mouse_colour = (sat < 60) | ((r > g + 40) & (r > b))        # greys, whites, pinks
shadow = (yy > 700) & (sat < 40) & (r > 150) & (r < 225)     # light ground shadow, not the grey feet
mouse_m = ((xx < 356) | (mask_box(px.shape, HAND) & mouse_colour & ~(g > r + 20))) & (rgba[..., 3] > 0) & ~shadow
mouse = layer(rgba, mouse_m)
cheese_m = mask_box(px.shape, CHEESE) & (r > 200) & (g > 110) & (b < 140) & (r > b + 80)
cheese_m |= mask_box(px.shape, CHEESE) & (r > 150) & (g < 120) & (b < 80)     # its holes / outline
cheese = layer(rgba, cheese_m)
maze = layer(rgba, ~mouse_m & ~cheese_m)
teal = (g > r + 40) & (b > r + 30)
# the whole cheese box (cheese + its shadow on the wall) becomes plain wall
maze = fill_holes(maze, (mouse_m & mask_box(px.shape, HAND)) | (mask_box(px.shape, CHEESE) & ~corridor), radii=(6, 18),
                  known=teal & (rgba[..., 3] > 250))
maze = fill_holes(maze, mouse_m & (yy > 690), radii=(8, 25))   # ground shadow under the feet

# --- SVG
c = Canvas((40, 0, 950))
T = 6.4
GO, ARRIVE, FADE = 0.06, 0.62, 0.86
path_d = "M" + " L".join(f"{c.pt(x, y)[0]:.1f} {c.pt(x, y)[1]:.1f}" for x, y in pts)
corr_w = 46 * c.k

css = [
    f".trail {{ stroke-dasharray: 100; stroke-dashoffset: 100; animation: trail {T}s linear infinite; }}",
    f"@keyframes trail {{ 0%, {pct(GO)} {{ stroke-dashoffset: 100; opacity: 1; }} {pct(ARRIVE)} {{ stroke-dashoffset: 0; opacity: 1; }} "
    f"{pct(FADE)} {{ stroke-dashoffset: 0; opacity: 1; }} {pct(FADE + .08)}, 100% {{ stroke-dashoffset: 0; opacity: 0; }} }}",
    f".ball {{ opacity: 0; animation: ball {T}s infinite; }}",
    f"@keyframes ball {{ 0%, {pct(GO - .03)} {{ opacity: 0; }} {pct(GO)} {{ opacity: 1; }} {pct(ARRIVE)} {{ opacity: 1; }} "
    f"{pct(ARRIVE + .03)}, 100% {{ opacity: 0; }} }}",
    f".cheese {{ {c.origin((CHEESE[0] + CHEESE[2]) / 2, CHEESE[3])} animation: cheese {T}s infinite; }}",
    f"@keyframes cheese {{ 0%, {pct(ARRIVE)} {{ transform: none; }} {pct(ARRIVE + .03)} {{ transform: translateY(-6%) rotate(-8deg) scale(1.08); }} "
    f"{pct(ARRIVE + .07)} {{ transform: scale(1.05, .95); }} {pct(ARRIVE + .1)} {{ transform: translateY(-2%) rotate(5deg); }} "
    f"{pct(ARRIVE + .14)}, 100% {{ transform: none; }} }}",
    f".mouse {{ {c.origin(*FEET)} animation: hop {T}s infinite; }}",
    f"@keyframes hop {{ {hop_keyframes([ARRIVE + .02, ARRIVE + .12], lift='4%')} }}",
    f".spark {{ transform-box: fill-box; transform-origin: center; opacity: 0; animation: spark {T}s infinite; }}",
    f"@keyframes spark {{ 0%, {pct(ARRIVE)} {{ opacity: 0; transform: scale(.3); }} "
    f"{pct(ARRIVE + .03)} {{ opacity: 1; transform: scale(1.1); }} {pct(ARRIVE + .12)} {{ opacity: 1; transform: scale(1); }} "
    f"{pct(ARRIVE + .17)}, 100% {{ opacity: 0; transform: scale(.8); }} }}",
]
defs = ('<defs><radialGradient id="glow"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".35" stop-color="#FFE45C"/>'
        '<stop offset=".7" stop-color="#FFB020" stop-opacity=".9"/><stop offset="1" stop-color="#FFB020" stop-opacity="0"/></radialGradient></defs>\n')
ball_r = corr_w * .42
ball = (f'<g class="ball"><circle r="{ball_r * 1.8:.1f}" fill="url(#glow)" opacity=".55"/>'
        f'<circle r="{ball_r:.1f}" fill="#FFD23F" stroke="#E08A00" stroke-width="2.5"/>'
        f'<circle cx="{-ball_r * .35:.1f}" cy="{-ball_r * .35:.1f}" r="{ball_r * .3:.1f}" fill="#FFFFFF" opacity=".9"/>'
        f'<animateMotion dur="{T}s" repeatCount="indefinite" calcMode="linear" keyPoints="0;0;1;1" '
        f'keyTimes="0;{GO};{ARRIVE};1" path="{path_d}"/></g>')
trail = (f'<path class="trail" pathLength="100" d="{path_d}" fill="none" stroke="#FFB020" stroke-opacity=".75" '
         f'stroke-width="{corr_w * .32:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
cx_, cy_ = c.pt((CHEESE[0] + CHEESE[2]) / 2, (CHEESE[1] + CHEESE[3]) / 2)
sparks = sparkle_burst(cx_, cy_, 95 * c.k, [18, 14, 22, 14, 18], "spark")
body = (c.image(maze) + trail + ball + c.image(cheese, "cheese")
        + f'<g class="mouse">{c.image(mouse)}</g>' + sparks)
svg = c.svg("Labirinto", "Icona \"Labirinto\" animata: la pallina percorre il labirinto fino al formaggio. "
            "Generata dall'immagine Scenario con tools/build_labirinto.py.", css, body, defs)
open(OUT, "w").write(svg)
print("ok", OUT, len(svg), "bytes", "route points", len(pts))

"""Shared helpers for the tools/build_<game>.py animated-icon scripts.

The older scripts (talpe, memory, palloncini, frutta, stelle, sequenza,
lavagna) are standalone; newer ones import this instead of repeating it.
"""
import base64, io, math
from PIL import Image, ImageDraw, ImageFilter, ImageChops
import numpy as np


def load_cutout(path, thresh=40, rim=5, seeds=()):
    """Scenario image on white -> (RGB float array, RGBA Image).

    Background is flood-filled from the corners (and extra `seeds` for
    enclosed white pockets). The `rim`-wide edge gets alpha from how far it
    is from white and is un-premultiplied, so no pale halo shows on the
    mint menu background.
    """
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):          # already transparent: flatten on white first
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert("RGB")
    W, H = im.size
    flood = im.copy()
    magenta = (255, 0, 255)
    for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)] + list(seeds):
        # only start from background-white pixels (a seed on the subject would eat it)
        if min(im.getpixel(seed)) > 238 and flood.getpixel(seed) != magenta:
            ImageDraw.floodfill(flood, seed, magenta, thresh=thresh)
    fg = Image.eval(ImageChops.difference(flood, Image.new("RGB", (W, H), magenta)).convert("L"),
                    lambda v: 0 if v < 8 else 255)
    ring = np.array(ImageChops.subtract(fg, fg.filter(ImageFilter.MinFilter(rim)))) > 0
    px = np.array(im).astype(float)
    edge_a = np.clip((255 - px.min(axis=2)) / 110, 0, 1)
    alpha = np.where(np.array(fg) > 0, 1.0, 0.0)
    alpha[ring] = edge_a[ring]
    safe = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.where(ring[..., None], (px - 255 * (1 - alpha[..., None])) / safe, px)
    rgba = np.dstack([rgb.clip(0, 255), alpha * 255])
    return px, rgba


def to_img(arr):
    return Image.fromarray(np.asarray(arr).clip(0, 255).astype("uint8"))


def mask_poly(shape, pts):
    H, W = shape[:2]
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.array(m) > 0


def mask_box(shape, box):
    H, W = shape[:2]
    m = np.zeros((H, W), bool)
    x0, y0, x1, y1 = box
    m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def mask_ellipse(shape, box):
    H, W = shape[:2]
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    return np.array(m) > 0


def dilate(m, n):
    return np.array(Image.fromarray(m.astype("uint8") * 255).filter(ImageFilter.MaxFilter(n * 2 + 1))) > 0


def erode(m, n):
    return np.array(Image.fromarray(m.astype("uint8") * 255).filter(ImageFilter.MinFilter(n * 2 + 1))) > 0


def connected(mask, seed):
    """Pixels of `mask` 4-connected to `seed` (x, y)."""
    from collections import deque
    H, W = mask.shape
    out = np.zeros_like(mask, dtype=bool)
    x, y = seed
    if not mask[y, x]:
        return out
    out[y, x] = True
    q = deque([(y, x)])
    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not out[ny, nx]:
                out[ny, nx] = True
                q.append((ny, nx))
    return out


def layer(rgba, mask):
    """Copy of rgba keeping only `mask` (bool) visible."""
    out = rgba.copy()
    out[..., 3] = np.where(mask, rgba[..., 3], 0)
    return out


def _box(a, r, axis):
    """Moving average of width 2r+1 along `axis` (edges clamped), via cumsum."""
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / (2 * r + 1)


def blur(a, sigma):
    """Float Gaussian-ish blur (3 box passes per axis) of a 2D or HxWxC array."""
    r = max(1, int(round((np.sqrt(4 * sigma * sigma + 1) - 1) / 2)))
    out = a.astype(float)
    for _ in range(3):
        out = _box(_box(out, r, 0), r, 1)
    return out


def fill_holes(rgba, hole, radii=(8, 30), grain=0, known=None):
    """Fill `hole` pixels from their surroundings (normalized convolution).

    Good for rebuilding a flat-ish surface (wood, board, wall) under a
    piece that moves away. Alpha is filled too, so holes at the edge of an
    object fade out rather than grow a coloured blob. Pass `known` to fill
    only from chosen pixels (e.g. opaque ones, for a solid surface).
    """
    known = ~hole if known is None else known & ~hole

    def conv(rad):
        # float blur: an 8-bit blur of the numerator loses everything where
        # few known pixels are near, and dividing by a tiny weight then turns
        # that rounding error into black / saturated garbage
        w = blur(known.astype(float), rad)
        f = blur(rgba * known[..., None], rad) / np.maximum(w, 1e-6)[..., None]
        return f, w

    # small radius where there is enough known surface nearby, else a wider one
    best, w_small = conv(radii[0])
    for rad in radii[1:]:
        f, _ = conv(rad)
        best = np.where((w_small > 0.08)[..., None], best, f)
    out = rgba.copy()
    if grain:
        best[..., :3] += np.random.default_rng(3).normal(0, grain, best[..., :3].shape)
    out[hole] = best[hole]
    return out.clip(0, 255)


class Canvas:
    """Square SVG canvas cut from the source: VB = (x0, y0, size) in source px."""

    def __init__(self, vb, size=640, quality=90):
        self.x0, self.y0, self.n = vb
        self.S = size
        self.k = size / self.n
        self.quality = quality

    def pt(self, x, y):
        return ((x - self.x0) * self.k, (y - self.y0) * self.k)

    def b64(self, arr):
        img = to_img(arr) if not isinstance(arr, Image.Image) else arr
        canvas = Image.new("RGBA", (self.n, self.n), (0, 0, 0, 0))
        canvas.paste(img, (-self.x0, -self.y0), img)
        canvas = canvas.resize((self.S, self.S), Image.LANCZOS)
        buf = io.BytesIO()
        canvas.save(buf, "WEBP", quality=self.quality, method=6)
        return base64.b64encode(buf.getvalue()).decode()

    def image(self, arr, cls="", extra=""):
        c = f' class="{cls}"' if cls else ""
        return f'<image{c}{extra} width="{self.S}" height="{self.S}" href="data:image/webp;base64,{self.b64(arr)}"/>'

    def origin(self, x, y):
        sx, sy = self.pt(x, y)
        return f"transform-box: view-box; transform-origin: {sx:.1f}px {sy:.1f}px;"

    def svg(self, label, comment, css, body, defs=""):
        css_txt = "\n  ".join(css)
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- {comment} -->\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.S} {self.S}" role="img" aria-label="{label}">\n'
                f'{defs}<style>\n  {css_txt}\n</style>\n{body}\n</svg>\n')


def pct(f):
    return f"{max(0, min(1, f)) * 100:.2f}%"


def star_pts(cx, cy, r, rot=0):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        t = math.radians(rot - 90 + i * 36)
        pts.append(f"{cx + rr * math.cos(t):.1f},{cy + rr * math.sin(t):.1f}")
    return " ".join(pts)


def hop_keyframes(times, lift="3%"):
    """Squash-and-hop keyframes at each fraction in `times` (for a character)."""
    kf = ["0% { transform: none; }"]
    for t in times:
        kf += [f"{pct(t)} {{ transform: none; animation-timing-function: ease-out; }}",
               f"{pct(t + .035)} {{ transform: translateY(-{lift}) scale(.98, 1.03); animation-timing-function: ease-in; }}",
               f"{pct(t + .07)} {{ transform: scale(1.04, .95); }}",
               f"{pct(t + .1)} {{ transform: none; }}"]
    kf.append("100% { transform: none; }")
    return " ".join(kf)


def sparkle_burst(cx, cy, radius, sizes, cls, stroke="#2B2D42"):
    """Ring of little yellow stars around (cx, cy), all with class `cls`."""
    out = ""
    n = len(sizes)
    for i, r in enumerate(sizes):
        ang = -90 + (i - (n - 1) / 2) * (300 / max(n - 1, 1))
        x = cx + radius * math.cos(math.radians(ang))
        y = cy + radius * math.sin(math.radians(ang))
        out += (f'<polygon class="{cls}" points="{star_pts(x, y, r, ang)}" fill="#FFD23F" '
                f'stroke="{stroke}" stroke-width="3" stroke-linejoin="round"/>')
    return out

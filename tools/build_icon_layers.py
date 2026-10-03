#!/usr/bin/env python3
"""Icone del menu "a livelli": dalle icone animate SVG (games/assets/icons/
<id>.svg) genera una versione che anima la GPU, con lo stesso aspetto.

Perche': un SVG animato dentro <img> viene ridisegnato dal processore a ogni
frame (sul Pi: menu a ~156% di CPU, 82 C). Qui ogni pezzo animato solo con
transform/opacity diventa un livello HTML che il compositor di Chromium muove
sulla GPU senza ridisegnarlo; i pezzi fermi diventano SVG statici (disegnati
una volta). I pezzi con animazioni che la GPU non sa fare (stroke-dashoffset,
animateMotion) restano piccoli SVG animati: solo loro si ridisegnano.

Uscita, per ogni icona: games/assets/icons-gpu/<id>/
  icon.html   frammento (stile con classi/keyframes prefissati + markup)
  cN.svg      livelli SVG (statici o, per i pezzi "raster", animati)
L'ombra in rilievo viene aggiunta da tools/build_icon_shadows.py.

Gli SVG originali NON vengono toccati: la shell usa questa versione solo con
"iconMode": "layers" nel config del tenant.

Uso: python3 tools/build_icon_layers.py [id ...]   (senza id: tutte)
"""
import json, os, re, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIOSK = os.path.join(ROOT, "kiosk")
SRC = os.path.join(KIOSK, "games", "assets", "icons")
OUT = os.path.join(KIOSK, "games", "assets", "icons-gpu")
URL_BASE = "games/assets/icons-gpu"      # relativo alla shell (kiosk/index.html)
SVG_NS = "http://www.w3.org/2000/svg"
NS = "{%s}" % SVG_NS
VB = 640.0                               # viewBox di tutte le icone
COMPOSITE_PROPS = {"transform", "opacity", "animation-timing-function"}
SMIL = {"animate", "animateMotion", "animateTransform", "set"}

ET.register_namespace("", SVG_NS)


def local(tag):
    return tag.split("}")[-1]


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".")


# ------------------------------------------------------------------ CSS
def parse_style(css):
    """-> (rules {classe: {prop: valore}}, keyframes {nome: corpo})"""
    keyframes = {}
    def grab(m):
        keyframes[m.group(1)] = m.group(2)
        return ""
    rest = re.sub(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*\s*)\}", grab, css)
    rules = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", rest):
        decls = {}
        for d in body.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decls[k.strip()] = v.strip()
        for cls in sel.split(","):
            cls = cls.strip()
            assert re.fullmatch(r"\.[\w-]+", cls), "selettore non gestito: " + cls
            rules.setdefault(cls[1:], {}).update(decls)
    return rules, keyframes


def keyframe_props(body):
    return set(p.strip() for p in re.findall(r"([a-z-]+)\s*:", body))


def anim_names(decls, keyframes):
    a = decls.get("animation", "") + " " + decls.get("animation-name", "")
    return [t for t in re.split(r"[\s,]+", a) if t in keyframes]


# ------------------------------------------------------------------ bbox (fill-box)
def numbers(s):
    return [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", s)]


def bbox(el):
    t = local(el.tag)
    assert "transform" not in el.attrib, "fill-box con transform non gestito"
    if t == "polygon" or t == "polyline":
        n = numbers(el.get("points"))
        xs, ys = n[0::2], n[1::2]
    elif t == "circle":
        cx, cy, r = (float(el.get(k, 0)) for k in ("cx", "cy", "r"))
        xs, ys = [cx - r, cx + r], [cy - r, cy + r]
    elif t == "ellipse":
        cx, cy, rx, ry = (float(el.get(k, 0)) for k in ("cx", "cy", "rx", "ry"))
        xs, ys = [cx - rx, cx + rx], [cy - ry, cy + ry]
    elif t == "rect":
        x, y, w, h = (float(el.get(k, 0)) for k in ("x", "y", "width", "height"))
        xs, ys = [x, x + w], [y, y + h]
    elif t == "line":
        xs = [float(el.get("x1", 0)), float(el.get("x2", 0))]
        ys = [float(el.get("y1", 0)), float(el.get("y2", 0))]
    elif t == "path":
        d = el.get("d")
        assert not re.search(r"[a-zA-Z]", re.sub(r"[MLZ]", "", d)), "path non M/L: " + d[:40]
        n = numbers(d)
        xs, ys = n[0::2], n[1::2]
    elif t == "g":
        boxes = [bbox(c) for c in el if local(c.tag) not in SMIL]
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))
    else:
        raise AssertionError("bbox non gestito per " + t)
    return min(xs), min(ys), max(xs), max(ys)


def spills(el):
    """Il contenuto esce da 0..640? (es. il cancellino della lavagna, disegnato
    attorno a 0,0 e portato in posizione dall'animazione)."""
    if local(el.tag) == "image":
        return False
    try:
        x0, y0, x1, y1 = bbox(el)
    except AssertionError:
        return True             # forma non misurabile: livello grande per sicurezza
    return x0 < 0 or y0 < 0 or x1 > VB or y1 > VB


def origin_pct(decls, el):
    """transform-origin SVG (view-box o fill-box) -> % del livello 640x640."""
    box = decls.get("transform-box", "view-box")
    o = decls.get("transform-origin", "0 0").replace("center", "50%")
    parts = o.split()
    if len(parts) == 1:
        parts.append("50%")
    if box == "view-box":
        b = (0.0, 0.0, VB, VB)
    else:
        assert box == "fill-box", box
        b = bbox(el)
    out = []
    for i, p in enumerate(parts[:2]):
        lo, hi = b[i], b[i + 2]
        if p.endswith("%"):
            v = lo + (hi - lo) * float(p[:-1]) / 100
        elif p.endswith("px"):
            v = lo + float(p[:-2])
        else:
            v = lo + float(p)
        out.append(fmt(v / VB * 100) + "%")
    return " ".join(out)


def px_to_pct(body):
    """translate in unita' del viewBox -> % del livello (640 = 100%)."""
    def conv(m):
        return fmt(float(m.group(1)) / VB * 100) + "%"
    def fix(m):
        return m.group(1) + "(" + re.sub(r"(-?\d*\.?\d+)px", conv, m.group(2)) + ")"
    out = re.sub(r"(translate[XY]?)\(([^)]*)\)", fix, body)
    assert "px" not in re.sub(r"[^;{}]*stroke[^;{}]*", "", out), "px rimasti: " + out[:80]
    return out


def svg_transform_css(t):
    """Attributo transform SVG -> transform CSS su un livello 640x640
    (traslazioni in %, perche' 640 unita' = 100% del livello)."""
    out = []
    for fn, args in re.findall(r"(\w+)\(([^)]*)\)", t):
        n = numbers(args)
        if fn == "translate":
            out.append("translate(%s%%, %s%%)" % (fmt(n[0] / VB * 100), fmt((n[1] if len(n) > 1 else 0) / VB * 100)))
        elif fn == "rotate":
            if len(n) == 3:
                cx, cy = fmt(n[1] / VB * 100), fmt(n[2] / VB * 100)
                out.append("translate(%s%%, %s%%) rotate(%sdeg) translate(-%s%%, -%s%%)" % (cx, cy, fmt(n[0]), cx, cy))
            else:
                out.append("rotate(%sdeg)" % fmt(n[0]))
        elif fn == "scale":
            out.append("scale(%s, %s)" % (fmt(n[0]), fmt(n[1] if len(n) > 1 else n[0])))
        elif fn == "matrix":
            out.append("translate(%s%%, %s%%) matrix(%s, %s, %s, %s, 0, 0)" % (
                fmt(n[4] / VB * 100), fmt(n[5] / VB * 100), *map(fmt, n[:4])))
        else:
            raise AssertionError("transform non gestito: " + fn)
    return " ".join(out)


# ------------------------------------------------------------------ conversione
class Icon:
    def __init__(self, gid):
        self.id = gid
        text = open(os.path.join(SRC, gid + ".svg"), encoding="utf-8").read()
        self.root = ET.fromstring(text)
        assert self.root.get("viewBox") == "0 0 640 640", self.root.get("viewBox")
        css = "".join(s.text or "" for s in self.root.iter(NS + "style"))
        self.rules, self.keyframes = parse_style(css)
        self.defs = [c for c in self.root if local(c.tag) == "defs"]
        self.chunks = []        # (nome file, testo svg)
        self.css = []           # regole per i livelli div
        self.used_frames = set()
        self.raster_classes = set()

    # -- classificazione
    def classes(self, el):
        return [c for c in el.get("class", "").split() if c]

    def animated(self, el):
        if any(local(c.tag) in SMIL for c in el):
            return True
        return any(anim_names(self.rules.get(c, {}), self.keyframes) for c in self.classes(el))

    def composite_ok(self, el):
        if any(local(c.tag) in SMIL for c in el):
            return False
        for c in self.classes(el):
            for name in anim_names(self.rules.get(c, {}), self.keyframes):
                if not keyframe_props(self.keyframes[name]) <= COMPOSITE_PROPS:
                    return False
        return True


    def has_animated_desc(self, el):
        return any(self.animated(d) for d in el.iter() if d is not el)

    # -- uscita
    def chunk(self, elements, wrap_attrs, animated, big=False):
        """Un livello SVG 640x640 con gli elementi dati (copie). big: dentro
        un gruppo trasformato le coordinate possono uscire da 0..640 (anche
        negative): il livello copre allora -640..1280 (3x per lato)."""
        n = len(self.chunks) + 1
        name = "c%d.svg" % n
        big = big or any(spills(e) for e in elements)
        vb = "-640 -640 1920 1920" if big else "0 0 640 640"
        svg = ET.Element(NS + "svg", {"viewBox": vb})
        if animated:
            st = ET.SubElement(svg, NS + "style")
            st.text = self.raster_css(elements)
        for d in self.defs:
            svg.append(d)
        parent = svg
        for attrs in wrap_attrs:
            parent = ET.SubElement(parent, NS + "g", attrs)
        for e in elements:
            parent.append(e)
        text = ET.tostring(svg, encoding="unicode")
        self.chunks.append((name, text))
        return '<img class="L%s" src="%s/%s/%s" alt="">' % (" Lx" if big else "", URL_BASE, self.id, name)

    def raster_css(self, elements):
        """Regole e keyframes originali per le classi usate negli elementi."""
        used = set()
        for e in elements:
            for d in e.iter():
                used.update(self.classes(d))
        out = []
        for c in sorted(used):
            if c in self.rules:
                out.append(".%s { %s }" % (c, "; ".join("%s: %s" % kv for kv in self.rules[c].items())))
                self.raster_classes.add(c)
                for name in anim_names(self.rules[c], self.keyframes):
                    out.append("@keyframes %s {%s}" % (name, self.keyframes[name]))
        return "\n".join(out)

    def strip(self, el, drop_class):
        """Copia senza la classe (le sue animazioni passano al div)."""
        import copy
        e = copy.deepcopy(el)
        if drop_class:
            e.attrib.pop("class", None)
        return e

    def div_rule(self, el):
        """Classe CSS del div: origine, animazione, opacita' iniziale."""
        decls = {}
        for c in self.classes(el):
            decls.update(self.rules.get(c, {}))
        cls = "%s--%s-%d" % (self.id, "-".join(self.classes(el)), len(self.css) + 1)
        props = ["transform-origin: " + origin_pct(decls, el)]
        for k, v in decls.items():
            if k in ("transform-box", "transform-origin"):
                continue
            if k in ("animation", "animation-name"):
                for name in anim_names(decls, self.keyframes):
                    v = re.sub(r"(?<![\w-])%s(?![\w-])" % re.escape(name), "%s--%s" % (self.id, name), v)
                    self.used_frames.add(name)
            props.append("%s: %s" % (k, px_to_pct(v)))
        if el.get("opacity"):
            props.append("opacity: " + el.get("opacity"))
        self.css.append(".ig-%s .%s { %s; }" % (self.id, cls, "; ".join(props)))
        return cls

    def convert_children(self, parent, wrap_attrs, big=False):
        """Figli di un contenitore -> markup (sequenze statiche raggruppate)."""
        html, run = [], []
        def flush():
            if run:
                html.append(self.chunk(list(run), wrap_attrs, False, big))
                run.clear()
        for el in parent:
            t = local(el.tag)
            if t in ("style", "defs", "title", "desc"):
                continue
            if not self.animated(el) and not self.has_animated_desc(el):
                run.append(self.strip(el, False))
                continue
            flush()
            html.append(self.convert(el, wrap_attrs, big))
        flush()
        return "\n".join(html)

    def convert(self, el, wrap_attrs, big=False):
        t = local(el.tag)
        # pezzo con animazioni non da GPU (o con discendenti cosi'): SVG animato
        if self.animated(el) and not self.composite_ok(el):
            return self.chunk([self.strip(el, False)], wrap_attrs, True, big)
        if not self.animated(el):
            # contenitore statico con figli animati: si scende, portando con
            # se' i suoi attributi di gruppo
            assert t == "g", "contenitore statico non-g: " + t
            attrs = {k: v for k, v in el.attrib.items() if k != "class"}
            if "transform" in attrs:
                # il transform del gruppo vale PRIMA delle animazioni dei
                # figli: diventa un livello con transform CSS fisso, e i figli
                # vivono nel suo sistema di coordinate (come in SVG)
                cls = "%s--t%d" % (self.id, len(self.css) + 1)
                props = ["transform-origin: 0 0", "transform: " + svg_transform_css(attrs.pop("transform"))]
                if "opacity" in attrs:
                    props.append("opacity: " + attrs.pop("opacity"))
                self.css.append(".ig-%s .%s { %s; }" % (self.id, cls, "; ".join(props)))
                inner = self.convert_children(el, wrap_attrs + ([attrs] if attrs else []), True)
                return '<div class="L %s">\n%s\n</div>' % (cls, inner)
            return self.convert_children(el, wrap_attrs + ([attrs] if attrs else []), big)
        # livello animato sulla GPU
        cls = self.div_rule(el)
        anim_transform = any("transform" in keyframe_props(self.keyframes[n])
                             for c in self.classes(el)
                             for n in anim_names(self.rules.get(c, {}), self.keyframes))
        inner_wrap = list(wrap_attrs)
        own = {}
        if el.get("transform") and not anim_transform:
            own["transform"] = el.get("transform")
        if el.get("filter"):
            own["filter"] = el.get("filter")
        if own:
            inner_wrap.append(own)
        if t == "g":
            inner = self.convert_children(el, inner_wrap, big)
        else:
            leaf = self.strip(el, True)
            leaf.attrib.pop("opacity", None)            # gia' sul div
            if anim_transform:
                leaf.attrib.pop("transform", None)      # come in SVG: vince la CSS
            inner = self.chunk([leaf], inner_wrap, False, big)
        return '<div class="L %s">\n%s\n</div>' % (cls, inner)

    def build(self):
        art = self.convert_children(self.root, [])
        frames = []
        for name in sorted(self.used_frames):
            frames.append("@keyframes %s--%s {%s}" % (self.id, name, px_to_pct(self.keyframes[name])))
        style = "\n".join(self.css + frames)
        return ('<style>\n%s\n</style>\n<div class="ig-art">\n%s\n</div>\n' % (style, art))


def main():
    manifest = json.load(open(os.path.join(KIOSK, "manifest", "manifest.json"), encoding="utf-8"))
    games = manifest["games"] if isinstance(manifest, dict) else manifest
    ids = sys.argv[1:] or [g["id"] for g in games]
    for gid in ids:
        icon = Icon(gid)
        frag = icon.build()
        d = os.path.join(OUT, gid)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            if re.fullmatch(r"c\d+\.svg", f):
                os.remove(os.path.join(d, f))
        for name, text in icon.chunks:
            with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        # elenco dei pezzi "raster" (per tools/check_icon_layers.py)
        with open(os.path.join(d, "raster.json"), "w", encoding="utf-8") as fh:
            json.dump({"classes": sorted(icon.raster_classes),
                       "chunks": [n for n, t in icon.chunks if "<style>" in t]}, fh)
        with open(os.path.join(d, "icon.html"), "w", encoding="utf-8") as fh:
            fh.write("<!-- Generato da tools/build_icon_layers.py da icons/%s.svg: non modificare a mano -->\n" % gid)
            fh.write(frag)
        divs = frag.count('<div class="L ')
        raster = sum(1 for n, t in icon.chunks if "<style>" in t)
        print("%-11s livelli GPU %2d, SVG statici %2d, SVG animati %d %s" % (
            gid, divs, len(icon.chunks) - raster, raster,
            ("(" + ", ".join(sorted(icon.raster_classes)) + ")") if raster else ""))


if __name__ == "__main__":
    main()

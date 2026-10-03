#!/usr/bin/env python3
"""Ombra "in rilievo" gia' disegnata per le icone a livelli.

Oggi la shell mette su ogni icona 3 drop-shadow (bordo chiaro sopra,
spessore scuro sotto, ombra portata): con l'icona animata vanno ricalcolate a
ogni frame (~55% di GPU sul Pi). Qui le disegna Chrome una volta sola, con lo
STESSO filtro della shell (letto da kiosk/index.html), alla dimensione reale
sul kiosk (1920x1080, icona da 309.5 px) e a risoluzione doppia.

Ogni pezzo ha la SUA ombra, che si muove con lui: per ogni livello di
icons-gpu/<id>/icon.html (radice e ogni div animato) si disegna col filtro il
suo contenuto fermo, si toglie il contenuto e resta l'ombra (sN.webp,
ritagliata). Nel frammento si aggiunge uno strato d'ombre (.ig-shade) con la
stessa struttura e le stesse animazioni dei livelli, sotto l'icona: le ombre
seguono i pezzi, sulla GPU, senza essere ricalcolate.

Differenze (minime) rispetto al filtro di oggi: dove le ombre di due pezzi si
sovrappongono fuori dall'icona sono un po' piu' scure; i pezzi "raster"
(SVG animati: gesso, tagli della frutta, pallina del labirinto) non hanno
ombra propria.

Prima: tools/build_icon_layers.py (rigenera icon.html senza ombre).
Uso: python3 tools/build_icon_shadows.py [id ...]   (senza id: tutte)
"""
import json, os, re, subprocess, sys, tempfile, time
from html.parser import HTMLParser
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIOSK = os.path.join(ROOT, "kiosk")
OUT = os.path.join(KIOSK, "games", "assets", "icons-gpu")
URL_BASE = "games/assets/icons-gpu"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ICON_PX = 309.515625     # lato dell'icona nel menu a 1920x1080 (misurato nella shell)
SCALE = 2                # risoluzione doppia
SHADE_START = "<!-- ombre: tools/build_icon_shadows.py -->"


def shell_filter():
    """Il filtro di .tile__icon-img, preso dalla shell: un'unica fonte."""
    html = open(os.path.join(KIOSK, "index.html"), encoding="utf-8").read()
    m = re.search(r"\.tile__icon-img\{.*?filter:\s*(.*?);", html, re.S)
    return " ".join(m.group(1).split())


class Tree(HTMLParser):
    """Struttura dei livelli di .ig-art: nodi {cls, imgs, children}."""
    def __init__(self):
        super().__init__()
        self.root = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            node = {"cls": a.get("class", ""), "imgs": [], "children": []}
            if self.root is None and "ig-art" in node["cls"].split():
                self.root = node
            elif self.stack:
                self.stack[-1]["children"].append(node)
            if self.root is not None:
                self.stack.append(node)
        elif tag == "img" and self.stack:
            self.stack[-1]["imgs"].append(a)

    def handle_endtag(self, tag):
        if tag == "div" and self.stack:
            self.stack.pop()


def knockout(with_f, without_f):
    """R = S sopra L  ->  L = (R - S) / (1 - aS), in premoltiplicato."""
    r = np.asarray(with_f).astype(np.float64) / 255
    s = np.asarray(without_f).astype(np.float64) / 255
    ar, as_ = r[..., 3:4], s[..., 3:4]
    rp, sp = r[..., :3] * ar, s[..., :3] * as_
    keep = 1 - as_
    with np.errstate(divide="ignore", invalid="ignore"):
        al = np.clip(np.where(keep > 0.02, (ar - as_) / keep, 0), 0, 1)
        lp = np.where(keep > 0.02, (rp - sp) / keep, 0)
        lc = np.where(al > 0.004, lp / al, 0)
    out = np.concatenate([np.clip(lc, 0, 1), al], axis=2)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8))


def main():
    m = json.load(open(os.path.join(KIOSK, "manifest", "manifest.json"), encoding="utf-8"))
    ids = sys.argv[1:] or [g["id"] for g in (m["games"] if isinstance(m, dict) else m)]
    tmp = tempfile.mkdtemp()

    # 1) per ogni icona, i gruppi da ombreggiare: il contenuto fermo di ogni
    #    livello (i suoi <img> statici, senza i livelli figli)
    jobs, trees = [], {}
    for gid in ids:
        d = os.path.join(OUT, gid)
        html = open(os.path.join(d, "icon.html"), encoding="utf-8").read()
        html = re.sub(re.escape(SHADE_START) + r".*?(?=<div class=\"ig-art\">)", "", html, flags=re.S)
        raster = set(json.load(open(os.path.join(d, "raster.json")))["chunks"])
        t = Tree()
        t.feed(html)
        n = 0
        def walk(node):
            nonlocal n
            node["static"] = [i for i in node["imgs"] if i["src"].rsplit("/", 1)[-1] not in raster]
            if node["static"]:
                n += 1
                node["shade"] = "s%d" % n
                jobs.append({"id": gid, "name": node["shade"], "imgs": node["static"]})
            for c in node["children"]:
                walk(c)
        walk(t.root)
        trees[gid] = (html, t.root)
    with open(os.path.join(tmp, "jobs.json"), "w") as fh:
        json.dump(jobs, fh)

    # 2) Chrome: ogni gruppo col filtro della shell e senza
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8080", "--bind", "127.0.0.1"],
                           cwd=KIOSK, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                               "--user-data-dir=" + os.path.join(tmp, "prof"), "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        subprocess.run(["node", os.path.join(ROOT, "tools", "build_icon_shadows.mjs"), tmp,
                        shell_filter(), str(ICON_PX), str(SCALE)], check=True)
    finally:
        chrome.terminate()
        srv.terminate()

    # 3) ombra = filtro meno contenuto, ritagliata; strato .ig-shade nel frammento
    side = ICON_PX * SCALE                  # lato dell'icona nelle foto (che partono da -1 lato)
    pos = lambda v: "%.3f%%" % ((v - side) / side * 100)
    size = lambda v: "%.3f%%" % (v / side * 100)
    for gid in ids:
        d = os.path.join(OUT, gid)
        for f in os.listdir(d):
            if re.fullmatch(r"s\d+\.webp", f) or f == "shadow.webp":
                os.remove(os.path.join(d, f))
        html, root = trees[gid]
        total = 0
        def shade(node):
            nonlocal total
            parts = []
            if node.get("shade"):
                a = Image.open(os.path.join(tmp, "%s-%s-with.png" % (gid, node["shade"]))).convert("RGBA")
                b = Image.open(os.path.join(tmp, "%s-%s-without.png" % (gid, node["shade"]))).convert("RGBA")
                sh = knockout(a, b)
                box = sh.getchannel("A").point(lambda v: 255 if v > 2 else 0).getbbox()
                if box:
                    sh = sh.crop(box)
                    path = os.path.join(d, node["shade"] + ".webp")
                    sh.save(path, "WEBP", quality=90, method=6)
                    total += os.path.getsize(path)
                    parts.append('<img class="S" src="%s/%s/%s.webp" alt="" style="left:%s;top:%s;width:%s;height:%s">' % (
                        URL_BASE, gid, node["shade"], pos(box[0]), pos(box[1]),
                        size(box[2] - box[0]), size(box[3] - box[1])))
            for c in node["children"]:
                parts.append(shade(c))
            inner = "\n".join(p for p in parts if p)
            if node is root:
                return inner
            return '<div class="%s">\n%s\n</div>' % (node["cls"], inner)
        layer = shade(root)
        art = html.index('<div class="ig-art">')
        out = html[:art] + SHADE_START + '\n<div class="ig-shade">\n' + layer + "\n</div>\n" + html[art:]
        with open(os.path.join(d, "icon.html"), "w", encoding="utf-8") as fh:
            fh.write(out)
        print("%-11s ombre %2d  %d KB" % (gid, len([j for j in jobs if j["id"] == gid]), total // 1024))


if __name__ == "__main__":
    main()

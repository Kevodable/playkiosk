#!/usr/bin/env python3
"""Flipbook per i pezzi "raster" delle icone a livelli.

I pezzi con animazioni che la GPU non sa fare (gesso della lavagna che si
disegna, tagli della frutta, pallina e scia del labirinto) restano SVG
animati (img.R): la pagina li ridisegna a ogni frame e, cosi', rifa' il
lavoro su TUTTA l'icona a ogni frame (sul Pi: menu a livelli 197% di CPU,
55% senza questi pezzi).

Qui Chrome disegna i fotogrammi del pezzo originale (FPS al secondo, alla
dimensione reale sul kiosk), quelli uguali si tengono una volta sola, si
ritagliano e si mettono in un'unica immagine (fN.webp). Nel frammento il
pezzo diventa un riquadro che "sfoglia" l'immagine con un'animazione
transform a scatti: la fa la GPU, senza ridisegnare.

Ordine: tools/build_icon_layers.py -> questo -> tools/build_icon_shadows.py
Uso: python3 tools/build_icon_flipbooks.py [id ...]   (senza id: tutte)
"""
import json, os, re, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIOSK = os.path.join(ROOT, "kiosk")
OUT = os.path.join(KIOSK, "games", "assets", "icons-gpu")
URL_BASE = "games/assets/icons-gpu"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ICON_PX = 309.515625     # lato dell'icona nel menu a 1920x1080 (come build_icon_shadows.py)
FPS = 30
MAX_SHEET = 4096         # lato massimo dell'immagine (limite delle texture GPU)


def duration(svg_text):
    """Durata del ciclo del pezzo (CSS e SMIL): devono coincidere."""
    durs = set(float(d) for d in re.findall(r"animation:\s*[\w-]+\s+([\d.]+)s", svg_text))
    durs |= set(float(d) for d in re.findall(r'dur="([\d.]+)s"', svg_text))
    assert len(durs) == 1, "durate diverse nello stesso pezzo: %s" % sorted(durs)
    return durs.pop()


def main():
    m = json.load(open(os.path.join(KIOSK, "manifest", "manifest.json"), encoding="utf-8"))
    ids = sys.argv[1:] or [g["id"] for g in (m["games"] if isinstance(m, dict) else m)]
    tmp = tempfile.mkdtemp()
    jobs = []
    for gid in ids:
        d = os.path.join(OUT, gid)
        for name in json.load(open(os.path.join(d, "raster.json")))["chunks"]:
            text = open(os.path.join(d, name), encoding="utf-8").read()
            dur = duration(text)
            big = "-640 -640 1920 1920" in text
            n = int(round(dur * FPS))
            jobs.append({"id": gid, "chunk": name, "dur": dur, "big": big,
                         "times": [round(i / FPS, 4) for i in range(n)]})
    if not jobs:
        return
    with open(os.path.join(tmp, "jobs.json"), "w") as fh:
        json.dump(jobs, fh)

    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8080", "--bind", "127.0.0.1"],
                           cwd=KIOSK, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                               "--user-data-dir=" + os.path.join(tmp, "prof"), "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        subprocess.run(["node", os.path.join(ROOT, "tools", "build_icon_flipbooks.mjs"), tmp,
                        str(ICON_PX)], check=True)
    finally:
        chrome.terminate()
        srv.terminate()

    for gid in ids:
        d = os.path.join(OUT, gid)
        path = os.path.join(d, "icon.html")
        html = open(path, encoding="utf-8").read()
        css = []
        for k, job in enumerate([j for j in jobs if j["id"] == gid], 1):
            frames = [np.asarray(Image.open(os.path.join(tmp, "%s-%s-%d.png" % (gid, job["chunk"], i))).convert("RGBA"))
                      for i in range(len(job["times"]))]
            # riquadro comune: tutto cio' che compare in almeno un fotogramma
            alpha = np.max(np.stack([f[..., 3] for f in frames]), axis=0)
            ys, xs = np.nonzero(alpha > 0)
            x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
            crops = [f[y0:y1, x0:x1] for f in frames]
            # fotogrammi uguali una volta sola; sequenza = indice per istante
            uniq, seq = [], []
            for c in crops:
                for i, u in enumerate(uniq):
                    if np.array_equal(c, u):
                        seq.append(i)
                        break
                else:
                    uniq.append(c)
                    seq.append(len(uniq) - 1)
            w, h = x1 - x0, y1 - y0
            cols = max(1, min(len(uniq), MAX_SHEET // w))
            rows = -(-len(uniq) // cols)
            assert rows * h <= MAX_SHEET, "%s %s: immagine troppo grande" % (gid, job["chunk"])
            sheet = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
            for i, u in enumerate(uniq):
                sheet.paste(Image.fromarray(u), ((i % cols) * w, (i // cols) * h))
            fname = "f%d.webp" % k
            sheet.save(os.path.join(d, fname), "WEBP", lossless=True, method=6)
            # keyframes a scatti: cambia solo quando cambia il fotogramma
            name = "%s--f%d" % (gid, k)
            steps, last = [], None
            for i, fr in enumerate(seq):
                if fr != last:
                    steps.append("%s%% { transform: translate(%s%%, %s%%); }" % (
                        fmt(i / len(seq) * 100), fmt(-(fr % cols) / cols * 100), fmt(-(fr // cols) / rows * 100)))
                    last = fr
            steps.append("100%% { transform: translate(%s%%, %s%%); }" % (
                fmt(-(seq[-1] % cols) / cols * 100), fmt(-(seq[-1] // cols) / rows * 100)))
            css.append(".ig-%s .%s-img { width: %s%%; height: %s%%; animation: %s %ss step-end infinite; }" % (
                gid, name, cols * 100, rows * 100, name, fmt(job["dur"])))
            css.append("@keyframes %s { %s }" % (name, " ".join(steps)))
            # posizione del riquadro in % del lato dell'icona (le foto partono da -1 lato se "big")
            off = ICON_PX if job["big"] else 0
            pos = lambda v: "%s%%" % fmt((v - off) / ICON_PX * 100)
            size = lambda v: "%s%%" % fmt(v / ICON_PX * 100)
            div = ('<div class="F" style="left:%s;top:%s;width:%s;height:%s">'
                   '<img class="%s-img" src="%s/%s/%s" alt=""></div>') % (
                pos(x0), pos(y0), size(w), size(h), name, URL_BASE, gid, fname)
            old = re.search(r'<img class="L[^"]* R" src="%s/%s/%s" alt="">' % (
                re.escape(URL_BASE), gid, re.escape(job["chunk"])), html)
            assert old, "pezzo non trovato in icon.html: " + job["chunk"]
            html = html.replace(old.group(0), div)
            os.remove(os.path.join(d, job["chunk"]))
            print("%-11s %-8s %3d fotogrammi, %3d diversi, %dx%d px, %d KB" % (
                gid, job["chunk"], len(seq), len(uniq), w, h, os.path.getsize(os.path.join(d, fname)) // 1024))
        if css:
            html = html.replace("</style>", "\n".join(css) + "\n</style>", 1)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            # nessun pezzo raster rimasto: il controllo di fedelta' confronta tutto
            with open(os.path.join(d, "raster.json"), "w", encoding="utf-8") as fh:
                json.dump({"classes": [], "chunks": []}, fh)


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


if __name__ == "__main__":
    main()

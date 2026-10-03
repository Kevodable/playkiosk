#!/usr/bin/env python3
"""Controllo di fedelta' delle icone a livelli contro gli SVG originali.

Avvia un server locale su kiosk/ e Chrome headless, fotografa originale e
versione a livelli negli stessi istanti (tools/check_icon_layers.mjs) e
confronta pixel per pixel. Per ogni icona stampa la peggiore differenza tra
gli istanti; le immagini (e le differenze amplificate) restano nella
cartella indicata per guardarle a occhio.

Uso: python3 tools/check_icon_layers.py <cartella uscita> [id ...]
"""
import json, os, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    out = os.path.abspath(sys.argv[1])
    ids = sys.argv[2:]
    if not ids:
        m = json.load(open(os.path.join(ROOT, "kiosk/manifest/manifest.json")))
        ids = [g["id"] for g in (m["games"] if isinstance(m, dict) else m)]
    prof = tempfile.mkdtemp()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8080", "--bind", "127.0.0.1"],
                           cwd=os.path.join(ROOT, "kiosk"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                               "--user-data-dir=" + prof, "--hide-scrollbars", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        subprocess.run(["node", os.path.join(ROOT, "tools/check_icon_layers.mjs"), out, *ids], check=True)
    finally:
        chrome.terminate(); srv.terminate()
    print("\n%-11s %10s %10s  %s" % ("icona", "px diversi", "diff media", "istante peggiore"))
    for gid in ids:
        worst = (0, 0, None)
        for f in sorted(os.listdir(out)):
            if not f.startswith(gid + "-orig-"):
                continue
            t = f[len(gid + "-orig-"):-4]
            a = np.asarray(Image.open(os.path.join(out, f)).convert("RGB")).astype(int)
            b = np.asarray(Image.open(os.path.join(out, "%s-layers-%s.png" % (gid, t))).convert("RGB")).astype(int)
            d = np.abs(a - b).max(axis=2)
            frac = (d > 40).mean() * 100
            if frac >= worst[0]:
                worst = (frac, d.mean(), t)
            Image.fromarray(np.clip(d * 4, 0, 255).astype("uint8")).save(os.path.join(out, "%s-diff-%s.png" % (gid, t)))
        print("%-11s %9.2f%% %10.2f  t=%ss" % (gid, worst[0], worst[1], worst[2]))


if __name__ == "__main__":
    main()

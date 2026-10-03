#!/usr/bin/env python3
"""Disegna un filtro CSS (drop-shadow, bagliori...) dentro un'immagine.

Un filtro CSS su qualcosa che si muove viene ricalcolato a ogni frame
(CLAUDE.md sez. 6b, regola 3). Qui Chrome disegna l'immagine con il filtro,
alla dimensione d'uso, una volta sola, e salva il risultato con un margine
trasparente intorno (dove cadono bagliore e ombra): nel gioco si usa la
nuova immagine, piu' grande del margine, e si toglie il filtro.

Il filtro e' disegnato prima di trasformazioni e rotazioni, come fa il
browser: una rotazione dell'elemento ruota anche l'ombra, come prima.

Uso: python3 tools/bake_filter.py --filter "<filtro css>" --size <px> \\
        --pad <frazione del lato> [--scale N] [--suffix _bagliore] img1 [img2 ...]
Uscita: accanto a ogni immagine, <nome><suffix>.webp (lato = size*(1+2*pad)*scale).
"""
import argparse, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", required=True)
    ap.add_argument("--size", type=float, required=True, help="lato dell'elemento in px CSS")
    ap.add_argument("--pad", type=float, required=True, help="margine per lato, in frazione del lato")
    ap.add_argument("--scale", type=float, default=2, help="risoluzione (px immagine per px CSS)")
    ap.add_argument("--suffix", default="_filtro")
    ap.add_argument("images", nargs="+")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    jobs = []
    for img in a.images:
        path = os.path.abspath(img)
        base, _ = os.path.splitext(path)
        jobs.append({"src": path, "out": base + a.suffix + ".png"})
    import json
    with open(os.path.join(tmp, "jobs.json"), "w") as fh:
        json.dump(jobs, fh)
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                               "--allow-file-access-from-files",
                               "--user-data-dir=" + os.path.join(tmp, "prof"), "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        subprocess.run(["node", os.path.join(ROOT, "tools", "bake_filter.mjs"), tmp, a.filter,
                        str(a.size), str(a.pad), str(a.scale)], check=True)
    finally:
        chrome.terminate()
    from PIL import Image
    for j in jobs:
        im = Image.open(j["out"]).convert("RGBA")
        out = j["out"][:-4] + ".webp"
        im.save(out, "WEBP", lossless=True, method=6)
        os.remove(j["out"])
        print("%s -> %s  %dx%d  %d KB" % (os.path.basename(j["src"]), os.path.basename(out),
                                         im.width, im.height, os.path.getsize(out) // 1024))


if __name__ == "__main__":
    main()

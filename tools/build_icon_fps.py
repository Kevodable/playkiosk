#!/usr/bin/env python3
"""Varianti delle icone a livelli con le animazioni a FPS fotogrammi al secondo.

Sul Pi ogni fotogramma in cui qualcosa si muove costa (menu a livelli: 57%
di CPU a 60 fps). Qui ogni animazione viene ricampionata da Chrome a FPS
valori al secondo (stessa curva, stessi tempi) e riscritta come keyframes a
scatti: lo schermo cambia solo FPS volte al secondo invece di 60.

Uscita: games/assets/icons-gpu/<id>/icon-fps<FPS>.html (stesso frammento,
keyframes ricampionati). icon.html resta com'e'.

Dopo: tools/build_icon_layers.py, build_icon_flipbooks.py, build_icon_shadows.py.
Uso: python3 tools/build_icon_fps.py <fps> [id ...]
"""
import json, os, re, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIOSK = os.path.join(ROOT, "kiosk")
OUT = os.path.join(KIOSK, "games", "assets", "icons-gpu")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def fmt(v):
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


def main():
    fps = int(sys.argv[1])
    m = json.load(open(os.path.join(KIOSK, "manifest", "manifest.json"), encoding="utf-8"))
    ids = sys.argv[2:] or [g["id"] for g in (m["games"] if isinstance(m, dict) else m)]
    tmp = tempfile.mkdtemp()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8080", "--bind", "127.0.0.1"],
                           cwd=KIOSK, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333",
                               "--user-data-dir=" + os.path.join(tmp, "prof"), "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        subprocess.run(["node", os.path.join(ROOT, "tools", "build_icon_fps.mjs"), tmp, str(fps), *ids],
                       check=True)
    finally:
        chrome.terminate()
        srv.terminate()

    for gid in ids:
        sampled = json.load(open(os.path.join(tmp, gid + ".json")))
        html = open(os.path.join(OUT, gid, "icon.html"), encoding="utf-8").read()
        kept = 0
        for name, a in sampled.items():
            frames, last = [], None
            n = len(a["samples"])
            for i, v in enumerate(a["samples"]):
                if v != last:           # valore uguale al precedente: nessun fotogramma nuovo
                    decl = "; ".join("%s: %s" % kv for kv in sorted(v.items()))
                    frames.append("%s%% { %s; animation-timing-function: step-end; }" % (fmt(i / n * 100), decl))
                    last = v
            frames.append("100%% { %s; }" % "; ".join("%s: %s" % kv for kv in sorted(last.items())))
            kept += len(frames)
            new = "@keyframes %s { %s }" % (name, " ".join(frames))
            html, count = re.subn(r"@keyframes %s \{(?:[^{}]*\{[^{}]*\})*\s*\}" % re.escape(name),
                                  lambda _m: new, html)
            assert count == 1, "%s: keyframes %s trovati %d volte" % (gid, name, count)
        path = os.path.join(OUT, gid, "icon-fps%d.html" % fps)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html.replace("Generato da tools/build_icon_layers.py",
                                  "Generato da tools/build_icon_fps.py (%d fps) da icon.html di tools/build_icon_layers.py" % fps, 1))
        print("%-11s %2d animazioni, %4d fotogrammi chiave" % (gid, len(sampled), kept))


if __name__ == "__main__":
    main()

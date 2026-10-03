// Parte "browser" di tools/build_icon_shadows.py: per ogni gruppo di
// jobs.json (il contenuto fermo di un livello di un'icona) fotografa quel
// contenuto col filtro della shell e senza, su fondo trasparente, in un
// viewport 1920x1080 (le misure in vmin del filtro valgono come sul kiosk).
// La foto copre l'icona +-1 lato (i livelli "grandi" escono dal quadrato).
// Uso: node build_icon_shadows.mjs <cartella> <filtro> <lato px> <scala>
import { readFileSync, writeFileSync } from "node:fs";

const [dir, filter, sidePx, scale] = process.argv.slice(2);
const SIDE = Number(sidePx), X = 600, Y = 380;
const BASE = "http://127.0.0.1:8080/";
const jobs = JSON.parse(readFileSync(`${dir}/jobs.json`, "utf8"));

const tab = await (await fetch("http://127.0.0.1:9333/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
let seq = 0;
const pending = {};
ws.onmessage = (e) => { const d = JSON.parse(e.data); if (d.id && pending[d.id]) pending[d.id](d); };
await new Promise((r) => (ws.onopen = r));
const send = (method, params = {}) =>
  new Promise((r) => { pending[++seq] = r; ws.send(JSON.stringify({ id: seq, method, params })); });
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result.result.value;
};
await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: Number(scale), mobile: false });
await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });

for (const job of jobs) {
  const imgs = job.imgs.map((i) => `<img class="${i.class}" src="${i.src}" alt="">`).join("");
  for (const withFilter of [true, false]) {
    // come nella shell: il filtro e' sul riquadro dell'icona, i livelli dentro
    const html = `<base href="${BASE}"><style>html,body{margin:0;background:transparent}
      #ic{position:absolute;left:${X}px;top:${Y}px;width:${SIDE}px;height:${SIDE}px;${withFilter ? "filter:" + filter : ""}}
      .L{position:absolute;inset:0;width:100%;height:100%}
      .Lx{left:-100%;top:-100%;width:300%;height:300%}</style>
      <div id="ic">${imgs}</div>`;
    await send("Page.navigate", { url: BASE + "games/assets/" });
    await new Promise((r) => setTimeout(r, 200));
    await evaluate(`document.open(); document.write(${JSON.stringify(html)}); document.close(); 0`);
    const broken = await evaluate(`Promise.all(Array.from(document.images).map(i => i.decode().then(() => 0, () => 1)))
      .then(a => a.reduce((x, y) => x + y, 0))`);
    if (broken) throw new Error(`${job.id} ${job.name}: ${broken} immagini non caricate`);
    await evaluate(`Promise.resolve()
      .then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 100)))))`);
    const shot = await send("Page.captureScreenshot", {
      format: "png",
      clip: { x: X - SIDE, y: Y - SIDE, width: 3 * SIDE, height: 3 * SIDE, scale: 1 },
    });
    writeFileSync(`${dir}/${job.id}-${job.name}-${withFilter ? "with" : "without"}.png`, Buffer.from(shot.result.data, "base64"));
  }
}
await fetch("http://127.0.0.1:9333/json/close/" + tab.id);
process.exit(0);

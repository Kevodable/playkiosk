// Parte "browser" di tools/bake_filter.py: ogni immagine di jobs.json,
// alla dimensione d'uso e col filtro CSS, fotografata su fondo trasparente
// con un margine intorno.
// Uso: node bake_filter.mjs <cartella> <filtro> <lato px> <pad> <scala>
import { readFileSync, writeFileSync } from "node:fs";

const [dir, filter, sizeArg, padArg, scaleArg] = process.argv.slice(2);
const SIZE = Number(sizeArg), PAD = Number(padArg) * SIZE, X = 400, Y = 300;
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
await send("Emulation.setDeviceMetricsOverride", { width: 1200, height: 900, deviceScaleFactor: Number(scaleArg), mobile: false });
await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });

for (const job of jobs) {
  const data = readFileSync(job.src).toString("base64");
  const type = job.src.endsWith(".png") ? "png" : "webp";
  const html = `<style>html,body{margin:0;background:transparent}
    img{position:absolute;left:${X}px;top:${Y}px;width:${SIZE}px;height:${SIZE}px;filter:${filter}}</style>
    <img src="data:image/${type};base64,${data}">`;
  await send("Page.navigate", { url: "about:blank" });
  await evaluate(`document.open(); document.write(${JSON.stringify(html)}); document.close(); 0`);
  const ok = await evaluate(`document.images[0].decode().then(() => 1, () => 0)`);
  if (!ok) throw new Error("immagine non caricata: " + job.src);
  await evaluate(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 100))))`);
  const shot = await send("Page.captureScreenshot", {
    format: "png",
    clip: { x: X - PAD, y: Y - PAD, width: SIZE + 2 * PAD, height: SIZE + 2 * PAD, scale: 1 },
  });
  writeFileSync(job.out, Buffer.from(shot.result.data, "base64"));
}
await fetch("http://127.0.0.1:9333/json/close/" + tab.id);
process.exit(0);

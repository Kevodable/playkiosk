// Parte "browser" di tools/build_icon_flipbooks.py: per ogni pezzo di
// jobs.json, il suo SVG animato (inline, quindi pilotabile) viene fermato a
// ogni istante e fotografato alla dimensione reale sul kiosk, fondo
// trasparente. La foto copre il quadrato dell'icona, o +-1 lato se il pezzo
// e' "grande" (viewBox -640..1280).
// Uso: node build_icon_flipbooks.mjs <cartella> <lato px>
import { readFileSync, writeFileSync } from "node:fs";

const [dir, sidePx] = process.argv.slice(2);
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
await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });

for (const job of jobs) {
  const svg = (await (await fetch(`${BASE}games/assets/icons-gpu/${job.id}/${job.chunk}`)).text());
  const box = job.big
    ? `left:${X - SIDE}px;top:${Y - SIDE}px;width:${3 * SIDE}px;height:${3 * SIDE}px`
    : `left:${X}px;top:${Y}px;width:${SIDE}px;height:${SIDE}px`;
  const html = `<base href="${BASE}"><style>html,body{margin:0;background:transparent}
    #ic{position:absolute;${box}} #ic svg{display:block;width:100%;height:100%}</style>
    <div id="ic">${svg}</div>`;
  await send("Page.navigate", { url: BASE + "games/assets/" });
  await new Promise((r) => setTimeout(r, 200));
  await evaluate(`document.open(); document.write(${JSON.stringify(html)}); document.close(); 0`);
  await new Promise((r) => setTimeout(r, 200));
  const clip = job.big
    ? { x: X - SIDE, y: Y - SIDE, width: 3 * SIDE, height: 3 * SIDE, scale: 1 }
    : { x: X, y: Y, width: SIDE, height: SIDE, scale: 1 };
  for (let i = 0; i < job.times.length; i++) {
    const t = job.times[i];
    await evaluate(`(() => {
      document.getAnimations().forEach(a => { a.pause(); a.currentTime = ${t * 1000}; });
      document.querySelectorAll("svg").forEach(s => { if (s.pauseAnimations) { s.pauseAnimations(); s.setCurrentTime(${t}); } });
      return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 30))));
    })()`);
    const shot = await send("Page.captureScreenshot", { format: "png", clip });
    writeFileSync(`${dir}/${job.id}-${job.chunk}-${i}.png`, Buffer.from(shot.result.data, "base64"));
  }
  console.log(job.id, job.chunk, job.times.length, "fotogrammi");
}
await fetch("http://127.0.0.1:9333/json/close/" + tab.id);
process.exit(0);

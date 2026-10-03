// Parte "browser" di tools/build_icon_fps.py: carica il frammento di
// un'icona a livelli in un riquadro di 640 px, e per ogni animazione CSS
// (per nome di @keyframes) legge transform/opacity calcolati a ogni
// 1/fps di secondo. Le traslazioni sono restituite in % del riquadro
// dell'elemento animato (come nel frammento), cosi' valgono a ogni dimensione.
// Uso: node build_icon_fps.mjs <cartella> <fps> <id> [id ...]
import { writeFileSync } from "node:fs";

const [dir, fpsArg, ...ids] = process.argv.slice(2);
const FPS = Number(fpsArg);
const BASE = "http://127.0.0.1:8080/";

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

for (const id of ids) {
  const frag = await (await fetch(`${BASE}games/assets/icons-gpu/${id}/icon.html`)).text();
  const html = `<base href="${BASE}"><style>
    .ig{position:relative;width:640px;height:640px}
    .ig-shade,.ig-shade .L,.ig-art,.ig-art .L{position:absolute;inset:0;width:100%;height:100%}
    .ig-shade .S{position:absolute} .ig-art .Lx{left:-100%;top:-100%;width:300%;height:300%}
    .ig-art .F{position:absolute;overflow:hidden} .ig-art .F img{position:absolute;left:0;top:0}
    </style><div class="ig ig-${id}">${frag}</div>`;
  await send("Page.navigate", { url: BASE + "games/assets/" });
  await new Promise((r) => setTimeout(r, 200));
  await evaluate(`document.open(); document.write(${JSON.stringify(html)}); document.close(); 0`);
  await new Promise((r) => setTimeout(r, 300));
  const out = await evaluate(`(() => {
    const FPS = ${FPS};
    const anims = document.getAnimations();
    anims.forEach(a => a.pause());
    const byName = {};
    for (const a of anims) {
      if (!a.animationName || byName[a.animationName]) continue;
      const el = a.effect.target;
      const dur = a.effect.getComputedTiming().duration;
      const props = new Set();
      a.effect.getKeyframes().forEach(k => Object.keys(k).forEach(p => {
        if (p === "transform" || p === "opacity") props.add(p);
      }));
      const w = el.offsetWidth || 640, h = el.offsetHeight || 640;
      const samples = [];
      const n = Math.round(dur / 1000 * FPS);
      for (let i = 0; i < n; i++) {
        a.currentTime = i * dur / n;
        const cs = getComputedStyle(el);
        const v = {};
        if (props.has("transform")) {
          const t = cs.transform;
          if (t === "none") v.transform = "none";
          else {
            const m = new DOMMatrixReadOnly(t);
            const r = x => Math.round(x * 10000) / 10000;
            v.transform = "translate(" + r(m.e / w * 100) + "%, " + r(m.f / h * 100) + "%) matrix(" +
              [m.a, m.b, m.c, m.d].map(r).join(", ") + ", 0, 0)";
          }
        }
        if (props.has("opacity")) v.opacity = String(Math.round(parseFloat(cs.opacity) * 1000) / 1000);
        samples.push(v);
      }
      byName[a.animationName] = { dur: dur / 1000, samples };
    }
    return byName;
  })()`);
  writeFileSync(`${dir}/${id}.json`, JSON.stringify(out));
  console.log(id, Object.keys(out).length, "animazioni");
}
await fetch("http://127.0.0.1:9333/json/close/" + tab.id);
process.exit(0);

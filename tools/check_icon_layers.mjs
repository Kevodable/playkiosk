// Controllo di fedelta' delle icone a livelli (tools/build_icon_layers.py):
// per ogni icona, originale (SVG inline) e versione a livelli vengono fermate
// negli stessi istanti dell'animazione e fotografate; il confronto pixel per
// pixel lo fa tools/check_icon_layers.py.
//
// Richiede: Chrome avviato con --remote-debugging-port=9333 e la cartella
// kiosk/ servita su http://127.0.0.1:8080 (vedi check_icon_layers.py, che
// fa tutto da solo).
//
// Uso: node tools/check_icon_layers.mjs <cartella uscita> <id> [id ...]
import { writeFileSync, mkdirSync } from "node:fs";

const [outDir, ...ids] = process.argv.slice(2);
const TIMES = [0, 0.37, 0.8, 1.3, 1.75, 2.05, 2.45, 2.9, 3.6, 4.4, 4.75, 5.1, 5.7, 6.3, 6.85, 7.2, 7.6];
const BASE = "http://127.0.0.1:8080/";
mkdirSync(outDir, { recursive: true });

const tab = await (await fetch("http://127.0.0.1:9333/json/new?about:blank", { method: "PUT" })).json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
let seq = 0;
const pending = {};
const events = [];
ws.onmessage = (e) => {
  const d = JSON.parse(e.data);
  if (d.id && pending[d.id]) pending[d.id](d);
  else if (d.method) events.push(d.method);
};
await new Promise((r) => (ws.onopen = r));
const send = (method, params = {}) =>
  new Promise((r) => {
    pending[++seq] = r;
    ws.send(JSON.stringify({ id: seq, method, params }));
  });
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result.result.value;
};
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 700, height: 700, deviceScaleFactor: 1, mobile: false });

async function load(html) {
  // pagina della stessa origine del server (una data: URL non potrebbe
  // caricare le immagini da http://), poi il contenuto di prova al suo posto
  await send("Page.navigate", { url: BASE + "games/assets/" });
  await new Promise((r) => setTimeout(r, 300));
  await evaluate(`document.open(); document.write(${JSON.stringify(html)}); document.close(); 0`);
  await new Promise((r) => setTimeout(r, 300));
  // aspetta che tutte le immagini (anche quelle negli <img> dei livelli) siano decodificate
  await evaluate(`Promise.all(Array.from(document.images).map(i => i.decode().catch(() => 0)))`);
}

async function shoot(name) {
  const r = await send("Page.captureScreenshot", {
    format: "png",
    clip: { x: 0, y: 0, width: 640, height: 640, scale: 1 },
  });
  writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.result.data, "base64"));
}

// Ferma tutte le animazioni CSS della pagina al tempo t (e SMIL degli svg inline).
const SEEK = (t) => `(() => {
  document.getAnimations().forEach(a => { a.pause(); a.currentTime = ${t * 1000}; });
  document.querySelectorAll("svg").forEach(s => { if (s.pauseAnimations) { s.pauseAnimations(); s.setCurrentTime(${t}); } });
  // due frame + una pausa: le animazioni sulla GPU devono aver applicato la posizione
  return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 120))));
})()`;

for (const id of ids) {
  const svg = await (await fetch(`${BASE}games/assets/icons/${id}.svg`)).text();
  // FRAG=icon-fps30.html (variabile d'ambiente) per controllare una variante
  const frag = await (await fetch(`${BASE}games/assets/icons-gpu/${id}/${process.env.FRAG || "icon.html"}`)).text();
  // pezzi "raster" (SVG animati dentro <img>): il loro tempo non e' pilotabile,
  // quindi si nascondono in entrambe le versioni e si confronta il resto
  const raster = await (await fetch(`${BASE}games/assets/icons-gpu/${id}/raster.json`)).json();
  const hide = raster.classes.map((c) => "." + c).join(",");
  const hideCss = hide ? `${hide}{display:none !important}` : "";
  const head = `<base href="${BASE}"><style>html,body{margin:0;background:#fff}</style>`;

  await load(`${head}<style>${hideCss} svg{display:block;width:640px;height:640px}</style>${svg.replace(/<\?xml[^>]*>/, "")}`);
  for (const t of TIMES) {
    await evaluate(SEEK(t));
    await shoot(`${id}-orig-${t}`);
  }

  const hideImgs = raster.chunks.map((c) => `img[src$="/${id}/${c}"]`).join(",");
  await load(`${head}<style>
      .ig-art{position:relative;width:640px;height:640px}
      .ig-art .L{position:absolute;inset:0;width:100%;height:100%}
      .ig-art .Lx{left:-100%;top:-100%;width:300%;height:300%}
      .ig-shade{display:none}  /* confronto senza ombre: le ombre si guardano nel menu */
      .ig-art .F{position:absolute;overflow:hidden} .ig-art .F img{position:absolute;left:0;top:0}
      ${hideImgs ? hideImgs + "{display:none}" : ""}
    </style><div class="ig-${id}">${frag}</div>`);
  for (const t of TIMES) {
    await evaluate(SEEK(t));
    await shoot(`${id}-layers-${t}`);
  }
  console.log(id, "ok");
}
await fetch("http://127.0.0.1:9333/json/close/" + tab.id);
process.exit(0);

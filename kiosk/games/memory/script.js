/* Memory — sul framework condiviso BB (come gli altri giochi):
   header con "Torna ai giochi", schermata di start per la difficolta',
   overlay di vittoria BB.win, suoni BB.sound. Grafica dall'icona del gufo. */

/* =====================================================================
   CONFIG: numeri e figure del gioco, da ritoccare qui.
   ===================================================================== */
var CONFIG = {
  COPPIE_FACILE: 8,            // 4x4
  COPPIE_DIFFICILE: 18,        // 6x6
  ERRORE_MS: 800,              // quanto restano scoperte due carte diverse
  INATTIVITA_MS: 60000         // senza tocchi: torna al menu giochi
};
// Figure delle carte: img/fig_<nome>.webp (da tools/build_memory_sprites.py);
// finche' l'immagine non c'e' si vede l'emoji di riserva.
var FIGURE = [
  ["mela", "🍎"], ["sole", "☀️"], ["arcobaleno", "🌈"], ["razzo", "🚀"], ["gelato", "🍦"],
  ["papera", "🐤"], ["coccinella", "🐞"], ["pesce", "🐟"], ["dinosauro", "🦕"],
  ["cupcake", "🧁"], ["carota", "🥕"], ["farfalla", "🦋"], ["macchina", "🚗"], ["balena", "🐳"],
  ["albero", "🌳"], ["fragola", "🍓"], ["fiore", "🌸"], ["ombrello", "☂️"]
];

BB.lockScroll();
var info = BB.header("Memory");
BB.idle(CONFIG.INATTIVITA_MS, BB.home);
BB.iconeLivelli();        // icona di start e mascotte finale a livelli GPU (Raspberry)

var board = document.getElementById("board");
var startScreen = document.getElementById("start");

/* ---- Gufo che reagisce (Web Animations: non risente di "riduci movimento") ---- */
var gufo = document.getElementById("gufo");
var gufoAnim = null;
function gufoAnima(frames, ms) {
  if (gufoAnim) gufoAnim.cancel();
  gufoAnim = gufo.animate(frames, { duration: ms, easing: "ease-out" });
}
function gufoSalta() {
  gufoAnima([{ transform: "none" }, { transform: "translateY(-9%) scale(.97,1.04)", offset: .35 },
             { transform: "scale(1.05,.94)", offset: .7 }, { transform: "none" }], 460);
  stelline(4);
}
function gufoPerplesso() {
  gufoAnima([{ transform: "none" }, { transform: "rotate(-7deg)", offset: .25 },
             { transform: "rotate(6deg)", offset: .6 }, { transform: "none" }], 700);
}
function gufoFesta() {
  gufoAnima([{ transform: "none" }, { transform: "translateY(-12%) rotate(-5deg)", offset: .15 },
             { transform: "none", offset: .3 }, { transform: "translateY(-12%) rotate(5deg)", offset: .45 },
             { transform: "none", offset: .6 }, { transform: "translateY(-8%)", offset: .75 }, { transform: "none" }], 1300);
  stelline(8);
}
function stelline(n) {
  var r = gufo.getBoundingClientRect(), st = gufo.parentNode.getBoundingClientRect();
  var cx = r.left - st.left + r.width / 2, cy = r.top - st.top + r.height * .3;
  var svg = "";
  for (var i = 0; i < n; i++) {
    var a = (-160 + i * 140 / Math.max(1, n - 1)) * Math.PI / 180, d = r.width * (.45 + (i % 2) * .12);
    var x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d, R = 14 + (i % 3) * 5, pts = [];
    for (var k = 0; k < 10; k++) {
      var rr = k % 2 ? R * .45 : R, b = (-90 + k * 36) * Math.PI / 180;
      pts.push((x + Math.cos(b) * rr).toFixed(1) + "," + (y + Math.sin(b) * rr).toFixed(1));
    }
    svg += '<polygon points="' + pts.join(" ") + '" fill="#FFD23F" stroke="#3E5FAE" stroke-width="3" stroke-linejoin="round"/>';
  }
  var el = document.createElement("div");
  el.className = "stelline";
  el.innerHTML = '<svg width="1" height="1" style="overflow:visible">' + svg + "</svg>";
  gufo.parentNode.appendChild(el);
  el.animate([{ transform: "scale(.3)", opacity: 0 }, { transform: "scale(1.1)", opacity: 1, offset: .3 },
              { transform: "scale(1) translateY(-20px)", opacity: 0 }], { duration: 800, easing: "ease-out", fill: "forwards" });
  setTimeout(function () { el.remove(); }, 820);
}

var CARD_VALUES = FIGURE.map(function (f) { return { nome: f[0], emoji: f[1] }; });

var flipped = [];
var matchedCount = 0;
var totalPairs = 8;
var moves = 0;
var seconds = 0;
var timer = null;
var lockBoard = false;

function fmt(t) {
  var m = String(Math.floor(t / 60));
  var s = String(t % 60);
  if (m.length < 2) m = "0" + m;
  if (s.length < 2) s = "0" + s;
  return m + ":" + s;
}

function renderStats() {
  info.innerHTML =
    '<span class="mem-stats">' +
      '<span class="mem-stat">🕹️ <b>' + moves + '</b></span>' +
      '<span class="mem-stat">⏱️ <b>' + fmt(seconds) + '</b></span>' +
      '<span class="mem-stat">💎 <b>' + matchedCount + "/" + totalPairs + "</b></span>" +
    "</span>";
}

function startTimer() {
  stopTimer();
  seconds = 0;
  renderStats();
  timer = setInterval(function () { seconds++; renderStats(); }, 1000);
}
function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

function makeCard(card) {
  var el = document.createElement("div");
  el.className = "card";
  el.dataset.key = card.nome;
  el.innerHTML =
    '<div class="card-inner">' +
      '<div class="card-face card-front"></div>' +
      '<div class="card-face card-back"><img src="img/fig_' + card.nome + '.webp" alt=""></div>' +
    "</div>";
  var img = el.querySelector(".card-back img");
  img.onerror = function () { img.replaceWith(document.createTextNode(card.emoji)); };
  el.addEventListener("pointerdown", function () { onCardClick(el); });
  return el;
}

function onCardClick(el) {
  if (lockBoard) return;
  if (el.classList.contains("flipped") || el.classList.contains("matched")) return;
  if (flipped.length === 2) return;

  el.classList.add("flipped");
  BB.sound("pop");
  flipped.push(el);

  if (flipped.length === 2) {
    moves++;
    renderStats();
    checkMatch();
  }
}

function checkMatch() {
  var first = flipped[0], second = flipped[1];
  if (first.dataset.key === second.dataset.key) {
    first.classList.add("matched");
    second.classList.add("matched");
    flipped = [];
    matchedCount++;
    renderStats();
    BB.sound("match");
    if (matchedCount === totalPairs) {
      stopTimer();
      gufoFesta();
      setTimeout(fine, 1300);
    } else {
      gufoSalta();
    }
  } else {
    lockBoard = true;
    BB.sound("error");
    gufoPerplesso();
    first.classList.add("mismatch");
    second.classList.add("mismatch");
    setTimeout(function () {
      first.classList.remove("flipped", "mismatch");
      second.classList.remove("flipped", "mismatch");
      flipped = [];
      lockBoard = false;
    }, CONFIG.ERRORE_MS);
  }
}

function fine() {
  BB.win({
    mascotte: "../assets/icons/memory.svg",
    titolo: "Hai vinto!",
    punteggio: "Mosse: " + moves + " · Tempo: " + fmt(seconds),
    rigioca: function () { startScreen.classList.remove("bb-hidden"); }
  });
}

function nuova(pairs) {
  stopTimer();
  totalPairs = pairs;
  moves = 0;
  matchedCount = 0;
  flipped = [];
  lockBoard = false;

  board.classList.toggle("large", totalPairs > 8);

  var chosen = BB.shuffle(CARD_VALUES.slice()).slice(0, totalPairs);
  var deck = BB.shuffle(chosen.concat(chosen));

  board.innerHTML = "";
  deck.forEach(function (card) { board.appendChild(makeCard(card)); });

  startScreen.classList.add("bb-hidden");
  startTimer();
}

Array.prototype.forEach.call(document.querySelectorAll(".liv-btn"), function (b) {
  b.addEventListener("click", function () { nuova(parseInt(b.dataset.pairs, 10)); });
});

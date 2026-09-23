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

var board = document.getElementById("board");
var startScreen = document.getElementById("start");

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
      setTimeout(fine, 600);
    }
  } else {
    lockBoard = true;
    BB.sound("error");
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

/* Memory — Kids Fun Planet
   Riscritto sul framework condiviso BB (come gli altri giochi):
   header con "Torna ai giochi", schermata di start per la difficoltà,
   overlay di vittoria BB.win, suoni BB.sound. Mantiene solo il logo/banner. */

BB.lockScroll();
var info = BB.header("🎉 Memory");
BB.idle(60000, BB.home);

var board = document.getElementById("board");
var startScreen = document.getElementById("start");

var MASCOTS = [
  { type: "img", value: "assets/mascots/cards/kip.jpg", alt: "Kip" },
  { type: "img", value: "assets/mascots/cards/stella.jpg", alt: "Stella" },
  { type: "img", value: "assets/mascots/cards/bolt.jpg", alt: "Bolt" },
  { type: "img", value: "assets/mascots/cards/bobo.jpg", alt: "Bobo" }
];
var EMOJIS = ["🚀","🌈","🪐","🌟","🛸","🎈","🦄","🍭","🎪","🌻","🐬","🍩","🎨","🐙","🍉","🎠"];
var CARD_VALUES = MASCOTS.concat(EMOJIS.map(function (e) {
  return { type: "emoji", value: e, alt: e };
}));

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

function faceContent(card) {
  if (card.type === "img") {
    return '<img src="' + card.value + '" alt="' + card.alt + '">';
  }
  return card.value;
}

function makeCard(card) {
  var el = document.createElement("div");
  el.className = "card";
  el.dataset.key = card.alt + "|" + card.value;
  el.innerHTML =
    '<div class="card-inner">' +
      '<div class="card-face card-front"></div>' +
      '<div class="card-face card-back">' + faceContent(card) + "</div>" +
    "</div>";
  el.addEventListener("click", function () { onCardClick(el); });
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
    }, 800);
  }
}

function fine() {
  BB.win({
    emoji: "🏆",
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

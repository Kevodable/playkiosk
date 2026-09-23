/* ============================================================================
   shared.js — Utility condivise per i giochi "Kids Fun Planet"
   ----------------------------------------------------------------------------
   Espone un oggetto globale `BB` con:
     BB.home()            → ritorno al launcher (AndroidLauncher.goHome o gallery)
     BB.sound(tipo)       → suoni generati via WebAudio (no file esterni)
     BB.idle(ms, cb)      → callback dopo inattività touch (auto-ritorno)
     BB.fullscreen()      → richiesta fullscreen (best effort)
     BB.lockScroll()      → blocca scroll/gesture sul kiosk
     BB.win(opzioni)      → overlay di vittoria/fine partita
     BB.score(gioco)      → record salvato in localStorage namespaced
   100% vanilla, nessuna dipendenza. Funziona offline.
   ========================================================================== */
(function (window, document) {
  "use strict";

  /* Namespace per le chiavi localStorage, così non collidiamo con altre app */
  var LS_PREFIX = "bb.kidsfunplanet.";

  /* --------------------------------------------------------------------------
     WebAudio: un solo AudioContext condiviso, creato pigramente al primo suono
     (i browser richiedono un gesto utente prima di poter suonare).
     ------------------------------------------------------------------------ */
  var audioCtx = null;
  function getAudioCtx() {
    if (audioCtx) return audioCtx;
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    try { audioCtx = new AC(); } catch (e) { audioCtx = null; }
    return audioCtx;
  }

  /* Suona una sequenza di "note" (frequenza + durata + forma d'onda) */
  function playSequence(notes) {
    var ctx = getAudioCtx();
    if (!ctx) return;
    /* Sblocca il contesto se sospeso (policy autoplay) */
    if (ctx.state === "suspended" && ctx.resume) ctx.resume();

    var t = ctx.currentTime;
    notes.forEach(function (n) {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = n.type || "sine";
      osc.frequency.setValueAtTime(n.freq, t);
      if (n.slideTo) {
        osc.frequency.exponentialRampToValueAtTime(n.slideTo, t + n.dur);
      }
      /* Inviluppo morbido per evitare "click" */
      var vol = n.vol == null ? 0.18 : n.vol;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(vol, t + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + n.dur);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + n.dur + 0.02);
      t += n.dur * (n.gap == null ? 0.9 : n.gap);
    });
  }

  /* Libreria di suoni di gioco */
  var SOUNDS = {
    pop: [{ freq: 520, slideTo: 880, dur: 0.12, type: "triangle", vol: 0.22 }],
    match: [
      { freq: 660, dur: 0.10, type: "sine" },
      { freq: 990, dur: 0.16, type: "sine" }
    ],
    win: [
      { freq: 523, dur: 0.14, type: "triangle" },
      { freq: 659, dur: 0.14, type: "triangle" },
      { freq: 784, dur: 0.14, type: "triangle" },
      { freq: 1047, dur: 0.30, type: "triangle" }
    ],
    error: [{ freq: 200, slideTo: 120, dur: 0.22, type: "sawtooth", vol: 0.16 }]
  };

  /* --------------------------------------------------------------------------
     L'oggetto pubblico BB
     ------------------------------------------------------------------------ */
  var BB = {

    /* Ritorno al launcher: usa il bridge Android se presente, altrimenti
       naviga alla gallery (../index.html). Vedi "contratto" nel README. */
    home: function () {
      try {
        if (window.AndroidLauncher && typeof window.AndroidLauncher.goHome === "function") {
          window.AndroidLauncher.goHome();
          return;
        }
      } catch (e) { /* ignora errori del bridge e usa il fallback */ }
      // Fallback web: torna alla gallery preservando ?client (contesto multi-tenant)
      var client = new URLSearchParams(window.location.search).get("client");
      window.location.href = "../index.html" + (client ? "?client=" + encodeURIComponent(client) : "");
    },

    /* Riproduce un suono di gioco: "pop" | "match" | "win" | "error" */
    sound: function (tipo) {
      var seq = SOUNDS[tipo];
      if (seq) playSequence(seq);
    },

    /* Richiama `cb` dopo `ms` di inattività touch. Ritorna una funzione
       per annullare il watcher. Default 60s. */
    idle: function (ms, cb) {
      ms = ms || 60000;
      var timer = null;
      function reset() {
        if (timer) clearTimeout(timer);
        timer = setTimeout(cb, ms);
      }
      var events = ["pointerdown", "touchstart", "click", "keydown"];
      events.forEach(function (ev) {
        document.addEventListener(ev, reset, { passive: true });
      });
      reset();
      return function cancel() {
        if (timer) clearTimeout(timer);
        events.forEach(function (ev) { document.removeEventListener(ev, reset); });
      };
    },

    /* Richiesta fullscreen "best effort" (alcuni webview la ignorano) */
    fullscreen: function () {
      var el = document.documentElement;
      var fn = el.requestFullscreen || el.webkitRequestFullscreen ||
               el.msRequestFullscreen;
      if (fn) { try { fn.call(el); } catch (e) { /* ignora */ } }
    },

    /* Blocca scroll e gesture di pull-to-refresh tipiche del touch */
    lockScroll: function () {
      document.addEventListener("touchmove", function (e) {
        /* consente lo scroll solo dentro a elementi marcati .bb-scrollable */
        if (!e.target.closest || !e.target.closest(".bb-scrollable")) {
          e.preventDefault();
        }
      }, { passive: false });
      /* Disattiva il menu contestuale da long-press */
      document.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    },

    /* Mostra un overlay di vittoria / fine partita.
       opzioni: { emoji, mascotte, titolo, punteggio, record, rigioca() }
       - "mascotte" (URL immagine, es. una mascotte SVG) ha priorità sull'emoji
       - "Rigioca" chiama opzioni.rigioca() e nasconde l'overlay
       - "Esci" chiama BB.home() */
    win: function (opzioni) {
      opzioni = opzioni || {};
      BB.sound("win");

      var ov = document.getElementById("bb-overlay");
      if (!ov) {
        ov = document.createElement("div");
        ov.id = "bb-overlay";
        ov.className = "bb-overlay";
        document.body.appendChild(ov);
      }
      var righe = "";
      if (opzioni.punteggio != null) {
        righe += '<div class="bb-overlay__score">Punteggio: ' +
                 opzioni.punteggio + "</div>";
      }
      if (opzioni.record != null) {
        righe += '<div class="bb-overlay__score">🏆 Record: ' +
                 opzioni.record + "</div>";
      }
      /* Personaggio: mascotte (immagine) se fornita, altrimenti emoji */
      var personaggio = opzioni.mascotte
        ? '<img class="bb-overlay__mascotte" src="' + opzioni.mascotte + '" alt="">'
        : '<div class="bb-overlay__emoji">' + (opzioni.emoji || "🎉") + "</div>";
      ov.innerHTML =
        '<div class="bb-overlay__card">' +
          personaggio +
          '<div class="bb-overlay__title">' + (opzioni.titolo || "Bravo!") + "</div>" +
          righe +
          '<div class="bb-overlay__actions">' +
            '<button class="bb-btn" id="bb-replay">🔁 Rigioca</button>' +
          "</div>" +
        "</div>";
      ov.hidden = false;

      // Per uscire si usa il pulsante flottante "🏠 Giochi" del launcher (unico).
      ov.querySelector("#bb-replay").addEventListener("click", function () {
        ov.hidden = true;
        if (typeof opzioni.rigioca === "function") opzioni.rigioca();
      });
    },

    /* Nasconde l'overlay vittoria (utile se un gioco lo riusa) */
    closeWin: function () {
      var ov = document.getElementById("bb-overlay");
      if (ov) ov.hidden = true;
    },

    /* Get/set del record per gioco. Senza argomento `valore` legge il record;
       con `valore` lo salva solo se è un nuovo massimo e ritorna il record. */
    score: function (gioco, valore) {
      var key = LS_PREFIX + "score." + gioco;
      var cur = 0;
      try { cur = parseInt(window.localStorage.getItem(key), 10) || 0; }
      catch (e) { cur = 0; }
      if (valore == null) return cur;
      if (valore > cur) {
        try { window.localStorage.setItem(key, String(valore)); } catch (e) {}
        return valore;
      }
      return cur;
    },

    /* Crea l'header standard (pulsante "Torna ai giochi" + titolo + slot info).
       Il pulsante di uscita è nell'header di ogni gioco (non dipende dalla
       permission di overlay del launcher, così è sempre visibile su ogni monitor).
       Ritorna il nodo .bb-header__info per aggiornare punteggi ecc. */
    header: function (titolo, screenEl) {
      screenEl = screenEl || document.querySelector(".bb-screen");
      var h = document.createElement("header");
      h.className = "bb-header";
      h.innerHTML =
        '<button type="button" class="bb-back" id="bb-back">🏠 Torna ai giochi</button>' +
        '<h1 class="bb-header__title">' + (titolo || "") + "</h1>" +
        '<div class="bb-header__info" id="bb-info"></div>';
      screenEl.insertBefore(h, screenEl.firstChild);
      h.querySelector("#bb-back").addEventListener("click", function () { BB.home(); });
      return h.querySelector("#bb-info");
    }
  };

  /* Numero casuale intero in [min, max] — comodo per tutti i giochi */
  BB.rand = function (min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  };

  /* Mischia un array in-place (Fisher–Yates) */
  BB.shuffle = function (arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
  };

  /* Esporta sul global */
  window.BB = BB;

})(window, document);

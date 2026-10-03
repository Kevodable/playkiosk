/* ============================================================================
   shared.js — Utility condivise dai giochi del kiosk
   ----------------------------------------------------------------------------
   Espone un oggetto globale `BB` con:
     BB.home()            → ritorno al launcher (AndroidLauncher.goHome o gallery)
     BB.sound(tipo)       → suoni generati via WebAudio (no file esterni)
     BB.idle(ms, cb)      → callback dopo inattività touch (auto-ritorno)
     BB.fullscreen()      → richiesta fullscreen (best effort)
     BB.lockScroll()      → blocca scroll/gesture sul kiosk
     BB.win(opzioni)      → overlay di vittoria/fine partita
     BB.score(gioco)      → record salvato in localStorage namespaced
     BB.iconeLivelli()    → icone animate a livelli GPU (vedi sotto), per gioco
   100% vanilla, nessuna dipendenza. Funziona offline.
   ========================================================================== */
(function (window, document) {
  "use strict";

  /* Namespace per le chiavi localStorage, così non collidiamo con altre app */
  var LS_PREFIX = "kiosk.";

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
  /* Casetta del pulsante "Torna ai giochi", disegnata nello stile del menu
     (contorno marrone scuro come il davanzale) al posto dell'emoji. */
  var HOME_ICON =
    '<svg class="bb-back__icon" viewBox="0 0 48 48" aria-hidden="true">' +
    '<path d="M24 5 L44 22 L38 22 L38 42 L10 42 L10 22 L4 22 Z" fill="#FFF7E6" ' +
    'stroke="#522C09" stroke-width="3.5" stroke-linejoin="round"/>' +
    '<path d="M6 22 L24 7 L42 22" fill="none" stroke="#E0503A" stroke-width="5" ' +
    'stroke-linecap="round" stroke-linejoin="round"/>' +
    '<rect x="20" y="28" width="9" height="14" rx="2" fill="#BA7831" stroke="#522C09" stroke-width="3"/>' +
    '</svg>';

  /* --------------------------------------------------------------------------
     Icone a livelli GPU. Le <img> con l'icona animata (../assets/icons/<id>.svg)
     sono SVG ridisegnati a ogni frame: sul Raspberry costano molto (e con un
     filtro sopra ancora di piu'). Con BB.iconeLivelli(), se la shell usa
     iconMode "layers", diventano la stessa icona a livelli animati dalla GPU
     (../assets/icons-gpu/<id>/icon.html, vedi tools/build_icon_layers.py),
     che si ferma dopo iconPauseAfterSec senza tocchi e riparte al tocco.
     Fuori dalla shell, con iconMode "svg" o se il frammento non si carica,
     resta l'SVG di sempre.
     ------------------------------------------------------------------------ */
  var livelli = null;         /* { pausa: secondi } quando attive */

  function configShell() {
    try {
      if (window.parent !== window && window.parent.state) return window.parent.state.config;
    } catch (e) { /* non nella shell */ }
    return null;
  }

  /* Ferma le animazioni dell'icona dopo N s senza tocchi (alla posa iniziale),
     al tocco ripartono: come nel menu della shell. */
  function pausaIcona(ig) {
    if (!livelli.pausa) return;
    var timer = null, ferma = false;
    function anims() { return ig.isConnected ? ig.getAnimations({ subtree: true }) : []; }
    function pausa() {
      ferma = true;
      anims().forEach(function (a) { a.pause(); a.currentTime = 0; });
    }
    function sveglia(e) {
      /* solo tocchi veri: gli eventi generati dal codice (es. il segnale
         con cui la modalita' test della shell tiene aperto il gioco) no */
      if (e && !e.isTrusted) return;
      if (!ig.isConnected) {
        ["pointerdown", "touchstart", "click"].forEach(function (ev) {
          document.removeEventListener(ev, sveglia, true);
        });
        clearTimeout(timer);
        return;
      }
      if (ferma) { ferma = false; anims().forEach(function (a) { a.play(); }); }
      clearTimeout(timer);
      timer = setTimeout(pausa, livelli.pausa * 1000);
    }
    ["pointerdown", "touchstart", "click"].forEach(function (ev) {
      document.addEventListener(ev, sveglia, true);
    });
    sveglia();
  }

  /* Sostituisce un'<img> dell'icona animata con la versione a livelli,
     solo quando frammento e immagini sono pronti (niente buchi). */
  function iconaLivelli(img) {
    var m = /assets\/icons\/(\w+)\.svg/.exec(img.getAttribute("src") || "");
    if (!m) return;
    var id = m[1];
    var box = document.createElement("div");
    box.className = img.className + " bb-icona";
    var ig = document.createElement("div");
    ig.className = "ig ig-" + id;
    box.appendChild(ig);
    fetch("../assets/icons-gpu/" + id + "/icon.html")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        /* i percorsi del frammento sono relativi alla shell */
        ig.innerHTML = html.replace(/games\/assets\/icons-gpu\//g, "../assets/icons-gpu/");
        return Promise.all(Array.prototype.map.call(ig.querySelectorAll("img"), function (i) {
          return i.decode().catch(function () {});
        }));
      })
      .then(function () {
        if (!img.isConnected) return;
        img.replaceWith(box);
        pausaIcona(ig);
      })
      .catch(function () { /* resta l'SVG */ });
  }

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
      // Fallback web: torna alla gallery preservando ?tenant (contesto multi-tenant)
      var tenant = new URLSearchParams(window.location.search).get("tenant");
      window.location.href = "../index.html" + (tenant ? "?tenant=" + encodeURIComponent(tenant) : "");
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

      /* Con le icone a livelli: mascotte a livelli, e lo sfondo dietro il
         velo sfocato si ferma (altrimenti la sfocatura a tutto schermo si
         ricalcola a ogni frame); riparte con "Rigioca". */
      var fermate = [];
      if (livelli) {
        Array.prototype.forEach.call(ov.querySelectorAll("img"), iconaLivelli);
        document.getAnimations().forEach(function (a) {
          var el = a.effect && a.effect.target;
          if (el && !ov.contains(el) && a.playState === "running") { a.pause(); fermate.push(a); }
        });
      }

      // Per uscire si usa il pulsante flottante "🏠 Giochi" del launcher (unico).
      ov.querySelector("#bb-replay").addEventListener("click", function () {
        ov.hidden = true;
        fermate.forEach(function (a) { a.play(); });
        if (typeof opzioni.rigioca === "function") opzioni.rigioca();
      });
    },

    /* Icone a livelli GPU per questo gioco (vedi "Icone a livelli GPU" sopra):
       da chiamare una volta, dopo che il markup del gioco c'e'. */
    iconeLivelli: function () {
      var cfg = configShell();
      if (!cfg || cfg.iconMode !== "layers") return;
      livelli = { pausa: cfg.iconPauseAfterSec || 0 };
      Array.prototype.forEach.call(document.querySelectorAll("img"), iconaLivelli);
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
        '<button type="button" class="bb-back" id="bb-back">' + HOME_ICON + 'Torna ai giochi</button>' +
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

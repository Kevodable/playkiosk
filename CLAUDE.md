# KFP Kiosk — Contesto di progetto

> File di contesto letto da Claude Code a ogni sessione. Contiene la logica
> generale, l'architettura e le decisioni prese. Serve a chiunque (umano o CLI)
> per capire l'idea e procedere in coerenza.
>
> **MANUTENZIONE:** aggiorna la sezione "Stato attuale" e il "Log decisioni" a
> ogni modifica significativa. Le sezioni strategiche/architetturali (1-7, 10-11)
> cambiano SOLO quando cambia davvero una decisione.

---

## 1. Cos'è il prodotto
Kiosk touch per bambini, da mettere dove i bambini si annoiano (ristoranti dopo
mangiato, sale d'attesa). Il touch è **gratis per il bambino**, pagato dal
**locale** a canone fisso mensile (amenity, non a gettoniera). Prodotto di
**proprietà e produzione di Big Ben Matic**.

**Brand-neutral per design:** nessuna identità cablata nel codice. Il branding
(nome, logo, mascotte, colori, font) è un livello per-cliente iniettato via
config. "Kids Fun Planet" + mascotte Kip/Stella/Bolt/Bobo = brand di un CLIENTE
(Fun Planet srl), non del prodotto: vive solo nel tenant `funplanet`. Il brand di
produzione (legato a Big Ben) è previsto ma non ancora definito: finché non c'è,
l'UI base resta generica. Navy `#07091a` / giallo `#f5c800` = tool interni Big
Ben, NON prodotto customer-facing.

## 2. Modello di business e canali
Tre canali: (1) **noleggio diretto** a canone fisso in zona; (2)
**rivenditori/operatori** fuori zona (rinoleggiano ai clienti finali) con fee di
piattaforma per monitor attivo/mese; (3) **acquisto hardware** autonomo con
giochi base posseduti per sempre.

**Regola cardine (non violabile):** il base è sempre posseduto/permanente, nessun
kill-switch; mai hardware + canone obbligatorio alla stessa persona; add-on solo
opzionali.

## 3. Tier e catalogo
Tier = **bundle di giochi diversi** (base / pro / ultimate), NON edizioni dello
stesso gioco. `tier` è **metadata** nel manifest; l'enforcement dei diritti è
compito del **backend**, non della shell. La shell mostra SOLO i giochi in
`enabledGames` del tenant.
- Canale noleggio diretto → **griglia pulita**, solo giochi abilitati, nessun
  lucchetto davanti al bambino.
- "Vetrina coi bloccati" (mostrare pro/ultimate lucchettati) → parcheggiata come
  futuro **flag di config** `showLockedGames`, pensata per il canale rivenditori.

## 4. Architettura brand-neutral / multi-tenant
- **Shell condivisa unica** + `tenants/<id>/config.json` + `tenants/<id>/assets/`.
  Un solo codice per tutti i tenant.
- Tenant selezionato via `?tenant=<id>` nell'URL, fallback a `default`.
- `default` = look neutro, nessun brand. `funplanet` = isola TUTTO il brand KFP.
- Tutto tematizzabile via token nel config: colori, logo, mascotte, font, sfondo,
  immagine pulsante. Se un asset manca, fallback neutro senza rompersi.
- Il prodotto ha un suo **set di personaggi base** (la famiglia di animali delle
  icone), tenant-agnostico.

## 5. Target hardware e runtime
- Produzione: **Raspberry Pi 5** (ARM64, Raspberry Pi OS Lite, SSD NVMe) +
  monitor touch ~22" (1920×1080, **orizzontale**), **solo Chromium**
  (cage, kiosk). Vedi sez. 5b.
- Android NON è più target di produzione. **Safari NON è più un target**: niente
  più verifiche di compatibilità Safari.
- **Offline-first RESTA** (kiosk servito in locale da Caddy su 127.0.0.1):
  niente CDN, librerie e font in **locale** nel repo.

## 5b. Dispositivo target: Raspberry Pi 5
Primo kiosk prototipo (`kiosk-dev-01`): Raspberry Pi 5, Raspberry Pi OS Lite
64-bit (Trixie), **cage + Chromium kiosk** servito da **Caddy** su
`http://127.0.0.1:8080` (release in `/srv/kiosk/releases/vN`, symlink
`/srv/kiosk/current`). Sul Pi va **solo** il contenuto di `kiosk/`, mai la repo.
Setup, deploy/rollback, diagnostica e roadmap: `docs/raspberry-pi-setup.md`;
file di configurazione versionati (fonte di verita'): `device/pi/`.
Niente segreti in repo (password, chiavi, auth key Tailscale, IP).

## 5c. Backend centrale (hosting) — decisioni 2026-10-14
Serve SOLO alla parte centrale (i kiosk restano offline-first): telemetria
(eventi d'uso + righe di salute dei Pi), in futuro dashboard della flotta,
config dei tenant e diritti sui giochi (tier). Anteprima web: GitHub Pages.
- **Hosting:** Aruba **Linux Easy** (condiviso): PHP 8.0-8.5, MySQL (5
  database, 1 GB, ampliabile a pagamento), cron, backup 1-7 giorni,
  datacenter in Italia. **Niente SSH** (c'e' solo in Linux Advanced): file via
  FTP/FTPS, database creati dal pannello Aruba. Scelto rispetto a Serverplan
  (piu' caro su 3 anni) e ai fornitori con rincari forti al rinnovo.
- **Dominio:** **`benbenplay.com`** (preso). Nome generico, non del
  cliente. `benbenplay.it/.eu/.net` erano liberi al 2026-10-04.
- **Divisione dei compiti:** l'utente fa acquisto, login al pannello Aruba e a
  phpMyAdmin, creazione del database e dell'accesso FTP, e salva le
  credenziali in un file **fuori dalla repo** (`~/.config/playkiosk/`,
  permessi solo utente). Claude non entra in pannelli web con password e le
  password non passano dalla chat. Claude scrive il backend PHP, lo schema e
  le migrazioni (eseguite sul server da una pagina protetta: il database di
  un hosting condiviso di solito non accetta connessioni esterne), lo script
  di deploy via FTPS che legge le credenziali da quel file, i collaudi e il
  lato kiosk (`telemetry()`, timer di salute).
- **Database pensato per durare** (1 GB per tutta la flotta): righe compatte
  (kiosk come id numerico, eventi come codici brevi, ~60 byte/riga); salute
  riassunta (una riga all'ora con media/massimo + una subito in caso di
  allarme: temperatura alta, throttling) invece di una ogni 5 minuti; dati
  grezzi tenuti **60-90 giorni** poi riassunti per giorno (partite per gioco,
  durata media, temperatura massima) e cancellati; archivio facoltativo dei
  grezzi in file compressi nello spazio web. Stima: qualche MB per kiosk
  all'anno (salvando tutto grezzo sarebbero ~95 MB per kiosk all'anno).

## 6. Vincoli tecnici
- Shell in **HTML single-file**, niente build tool / bundler.
- **JS solo ASCII**: vale per la **logica** JS (nomi, operatori, stringhe
  tecniche come chiavi e percorsi), come igiene contro bug da caratteri strani.
  Emoji e accenti nel **testo visibile** (punteggi, messaggi, titoli) e nei
  commenti sono ok. Non è più un vincolo di compatibilità (Safari non è target).
- Deploy di **produzione**: solo `kiosk/` sul Pi, in `/srv/kiosk/releases/vN`
  (vedi `docs/raspberry-pi-setup.md`). **GitHub Pages** (auto-deploy da `main`,
  account kevodable, `.nojekyll`) = anteprima.
- **Telemetria:** una funzione `telemetry(event, payload)` → oggi `console.log`
  di `{ts, tenantId, deviceUuid, event, ...}`, con cucitura TODO per POST al
  backend futuro (PHP+MySQL su Aruba, vedi sez. 5c). `deviceUuid` in `localStorage`. Eventi:
  app_start, attract_view, menu_view, game_open, game_close(+durationMs),
  idle_return, error.

## 6b. Animazioni e prestazioni (Raspberry Pi) — regole per shell e giochi
Il costo non e' QUANTE cose si muovono ma COME (misure 2026-10-03, vedi log):
cio' che la GPU muove senza ridisegnare costa poco (menu con ~300 animazioni:
57% di CPU), cio' che va ridisegnato a ogni frame costa moltissimo e trascina
tutta la pagina (7 pezzi cosi': menu da 55% a 197%). Finche' qualcosa si
muove Chromium ridisegna lo schermo 60 volte al secondo (costo fisso
10-25%); tutto fermo = ~0.
1. **Muovere solo con `transform` e `opacity`** elementi/immagini (sprite
   WebP). Mai animare `width/height/top/left/margin`, colori, `box-shadow`,
   `filter`, `stroke-dashoffset`.
2. **Niente SVG animati** (CSS/SMIL dentro un `<img>` o inline): vengono
   ridisegnati a ogni frame. Le icone del menu passano da
   `tools/build_icon_layers.py` per questo.
3. **Ombre, bagliori, contorni: disegnati nelle immagini**, non calcolati da
   filtri CSS su cose che si muovono.
4. **Effetti che la GPU non sa fare** (linea che si disegna, percorso
   curvo...): fotogrammi gia' pronti sfogliati con `transform` a scatti
   (flipbook, vedi `tools/build_icon_flipbooks.py`).
5. **Canvas:** ridisegnare solo quando cambia qualcosa, non a ogni frame.
6. **Fermarsi quando si aspetta:** animazioni di contorno in pausa dopo
   qualche secondo senza tocchi (come `iconPauseAfterSec` nel menu).
7. **Ridurre i fotogrammi al secondo NON serve** (animazioni a scatti a
   30/20 fps: stesso costo, Chromium ridisegna comunque a 60).
8. **Misurare prima di considerarlo finito:** `kiosk-perf run game:<id>` sul
   Pi (modalita' test, `docs/raspberry-pi-setup.md` §4.1). Budget: sotto il
   **60-70% di CPU** mentre si gioca, a riposo il piu' vicino possibile a 0.
Il raffreddamento conta quanto il software: nel totem il Pi 5 va con
dissipatore e ventola (Active Cooler) e un minimo di ricircolo d'aria.

## 7. Struttura repo
Cartelle:
- `_legacy/` — vecchia repo, **SOLA LETTURA**, sorgente da cui pescare i 12
  giochi. Non va nel deploy.
- `kiosk/` — il prodotto:
  - `index.html` — la shell (menu)
  - `games/` — i 12 giochi + `games/assets/` condivisi (shared.css, shared.js/BB)
  - `games/index.html` — relay: il bottone home interno dei giochi manda un
    postMessage al parent (shell) senza modificare i giochi
  - `manifest/manifest.json` — UNICA fonte di verità dei 12 giochi (id, cartella,
    tier, active, icona locale, titolo i18n, titleColor, ...)
  - `tenants/default/` e `tenants/funplanet/` — `config.json` + `assets/`
  - `.nojekyll`
- `docs/` — documentazione (setup del Pi); `device/pi/` — config di sistema del
  kiosk, fonte di verità. Nessuna delle due va sul dispositivo.
- Branch: `main` e' la base; per un lavoro nuovo si apre un `feature/<nome>` da
  `main` e lo si riunisce a fine lavoro. Committare i punti buoni.

## 8. Shell / menu — design attuale
- Flusso: **attract loop** (tap sblocca audio → menu) → **menu** (griglia) →
  **gioco** in **iframe** fullscreen stessa origine (si torna al menu SOLO col
  pulsante "Torna ai giochi" nell'header del gioco, niente overlay della shell) →
  **idle return** dopo `idleTimeoutSec` → torna all'attract.
- Griglia **scrollabile** in verticale (il catalogo crescerà oltre i 12), sfondo
  **fisso** dietro, ultima fila "peek" per invitare a scrollare. Colonne/gap come
  variabili CSS.
- **Tile "nude" (default):** solo l'**icona animata** del gioco + il **titolo**
  sotto. Una sola icona per tile, centrata nel quadrato con la stessa aria su
  ogni lato (`--tile-icon-inset`), uniforme su tutte. Nessun pulsante dietro.
- **Pulsante/cornice = token OPZIONALE per-tenant:** `button.image` nel config.
  Se impostato → ogni tile ha la cornice e l'icona vive nella **content-box**
  misurata su quell'immagine (`button.contentBox`, 4 inset). Se `null`/vuoto →
  tile nude. Il pulsante di legno `tile-button.png` è **ritirato come default**
  ma resta disponibile (misure già nel config di `default`).
- **Icone:** **animate**, SVG autocontenuti con i livelli WebP incorporati e
  animazioni CSS; generate da `tools/build_<gioco>.py` a partire dall'arte
  Scenario (sorgenti in `tools/art/`). **Versione a livelli GPU** (per il
  Raspberry): `games/assets/icons-gpu/<id>/`, generata dagli SVG con
  `tools/build_icon_layers.py` + `tools/build_icon_flipbooks.py` (i pezzi che
  la GPU non sa animare, es. il gesso, diventano fotogrammi sfogliati) +
  `tools/build_icon_shadows.py` (ombre gia'
  disegnate, una per pezzo, che si muovono col pezzo), fedelta' verificata
  con `tools/check_icon_layers.py`. Scelta col token `iconMode` nel config
  del tenant: `"layers"` o `"svg"` (= SVG originali, il ritorno indietro).
  **Ogni modifica a un SVG va rigenerata** coi tre script, in quell'ordine.
  **Pausa delle icone** (`iconPauseAfterSec` nel config, su default 10): dopo
  N s senza tocchi le icone a livelli tornano alla posa iniziale e si
  fermano, al primo tocco ripartono (0/assente = mai).
- **Titolo:** sotto l'icona, scritto **come nel manifest** (maiuscole e
  minuscole: le minuscole di Bold Doodle sono piu' morbide, niente maiuscolo
  forzato). Colore **acceso/saturo per gioco** (`titleColor` nel manifest) +
  contorno scuro sottile (1px) + ombra morbida.
- **Font:** quello del tenant (`font` nel config, file in
  `tenants/<id>/assets/fonts/`) su **tutte le scritte**, shell e giochi. Su
  default e' **Bold Doodle** (woff2/woff locali; licenza free anche
  commerciale; **NON ha le lettere accentate**: "a'" & co. escono col font di
  sistema).
- **Sfondo:** `background.jpg` (1920×1080 JPG sRGB, ~130 KB): cielo menta con
  colline, nuvole e arcobaleno ai bordi, centro calmo per non distrarre dalle
  icone; fisso dietro la griglia, con velo `overlay` dal config. Sorgente
  Scenario in `tools/art/sfondo_menu.png`.
- **Icone in rilievo:** ogni icona e' "disegnata sul vetro", in rilievo (bordo
  chiaro sopra, spessore scuro sotto, ombra portata). Vale sia col vetro sia
  con la finestra.
- **Finestra (token opzionale per-tenant, ATTIVA su default):**
  `window.image` nel config = cornice a finestra **sopra** la griglia; la
  griglia si restringe all'apertura (`window.contentBox`, 4 inset in % misurati
  sull'immagine) e le tile scorrono **dietro** il telaio.
  - Su default: `window-v2.webp` (1920x1080 WebP con alpha) = architrave menta,
    stipiti menta, davanzale di legno; apertura **1763x853 px**. Generata da
    `tools/build_finestra_v2.py` dall'arte Scenario
    `tools/art/finestra_menu_v2.png` (apertura magenta piena): scontorno,
    persiane/cerniere/vasi tolti, banda centrale allargata, taglio 16:9. Lo
    script stampa il contentBox da copiare nel config.
  - `window.zoom` (+ `originY`) ingrandisce la finestra oltre i bordi dello
    schermo; su v2 e' 1 (il taglio e' gia' nell'immagine).
  - La v1 (`window.webp`, finestra bianca con ante a vetri,
    `tools/build_finestra.py`) resta come asset: valori in `_previous` nel
    config.
- **Vetro (senza finestra):** `window.image: null` → niente cornice, il menu e'
  un **vetro** davanti allo sfondo (velo leggero, riflessi diagonali, bordo
  luminoso: livello `.menu__glass`). Con la finestra il vetro e' spento.
- **Header dei giochi** (`games/assets/shared.css` + `BB.header()` in
  `shared.js`, uguale per tutti e 12): fascia menta con profilo teal (come
  l'architrave), griglia a 3 colonne:
  - sinistra: pulsante **"Torna ai giochi"** di legno (come il davanzale),
    casetta disegnata in SVG, >= 64px. E' l'**unico** modo per tornare al menu
    (il pulsante "Menu" della shell non c'e' piu');
  - centro (dello schermo): titolo del gioco col `titleColor`;
  - destra: punteggio/tempo in teal scuro.
  Font e colore li passa la **shell** all'iframe al load (`styleGameFrame()`:
  `@font-face` del tenant + `--bb-title-font`, `--bb-title-color`). Gioco
  aperto da solo, fuori dalla shell → font di sistema e colori di fallback.
- **Cache:** ogni gioco ha un `version` nel manifest, aggiunto all'URL
  dell'iframe (`?v=`); le icone hanno `?v=` nel path; `shared.css`/`shared.js`
  hanno `?v=` nel link di ogni gioco. Alzarli a ogni modifica.

## 9. I 12 giochi + re-skin
Giochi: memory, talpe, palloncini, frutta, stelle, sequenza, lavagna, labirinto,
forme, puzzle, tris, hanoi.

- **De-brandizzazione: FATTA su tutti e 12** (2026-09-24): nessun gioco usa piu'
  le mascotte Fun Planet. **Re-skin grafico fatto su tutti e 12**: ogni gioco ha la
  grafica del suo animale (i personaggi base del prodotto), numeri in `CONFIG`
  in cima al file, sprite da `tools/build_<gioco>_sprites.py`. La cartella delle
  vecchie mascotte (`games/assets/mascotte/`) e' stata eliminata.
- **Metodo (obbligatorio):** UN gioco alla volta, mai tutti insieme, mai auto
  mode. Per ciascuno: inventario → arte in Scenario coerente → verifica asset →
  il CLI monta senza rompere il gameplay → test → commit.
- **Pilota:** Acchiappa la Talpa (`feature/talpe-reskin`).
- **Delicati (per ultimi):** Memory e Puzzle — lì la mascotte era il CONTENUTO
  del gioco (carte da abbinare / immagine da ricomporre), non decorazione.

## 10. Specifiche asset (standard)
- **Sfondo:** 1920×1080, JPG sRGB, <400KB, centro calmo, dettaglio ai bordi (il
  `cover` taglia i bordi: niente di essenziale lì).
- **Pulsante:** quadrato PNG, esterno trasparente, interno pieno.
- **Finestra:** da Scenario in 16:9 con l'apertura riempita di un **colore
  piatto** (magenta) da scontornare; mai traversine davanti ai giochi. Asset
  finale 1920x1080 WebP con alpha, apertura trasparente.
- **Icone/loghi gioco:** quadrato PNG trasparente, leggibili in piccolo (~200px),
  stile comune (blocco-stile fisso riusato per tutti e 12 → famiglia coerente).
- **Font:** woff2 + woff LOCALI, licenza libera per uso commerciale (OFL o
  equivalente). MAI versioni demo "personal use only".
- **Regola d'oro per cambiare grafica:** immagine → **sostituisci il file**
  (stesso nome, stessa cartella); testo/numero/colore → **config.json**;
  gioco/tier/titolo → **manifest**. Il codice non si tocca. Eccezioni: cambio
  FORMA del pulsante o della finestra → rimisurare la content-box (4 inset).

## 11. Metodo di lavoro (divisione strumenti)
- **Chat:** brief, decisioni, bivi strategici, misure su file
  (trasparenza/peso/dimensioni/licenze).
- **Scenario.com:** creazione asset visivi.
- **CLI (Claude Code):** sviluppo funzionale, taratura, deploy.
- Auto mode **SPENTO** per modifiche importanti e sui giochi. Committare spesso.
  **Misurare coi numeri, non a occhio.** Un problema alla volta.

---

## Log decisioni
- Look pulsante **uniforme** (immagine unica completa), niente colore per-gioco.
- Colore spostato dal fondo del pulsante al **titolo** (acceso/saturo per gioco).
- **Safari abbandonato** come target: solo Chromium. Offline-first resta (Raspberry Pi 5).
- Font: **Bold Doodle** (free anche commerciale, no accenti); dal 2026-09-24
  su tutte le scritte, non solo sui titoli.
- Re-skin giochi con la **famiglia di animali** (de-brandizzazione deluxe);
  pilota: Acchiappa la Talpa.
- 2026-09-22 — Icone del menu **animate** (SVG con livelli WebP), dall'arte
  Scenario; titoli in **maiuscolo**; sfondo menu **menta** (`background-soft`)
  con **cornice 3D**.
- 2026-09-23 — **Tile nude** (icona animata + titolo) come default; pulsante di
  legno **ritirato come default**, resta token opzionale `button.image` per-tenant.
- 2026-09-23 — Memory rifatto **prima** del previsto (non per ultimo): carte con
  18 **figure nuove** disegnate (Scenario) al posto delle mascotte.
- 2026-09-23 — Pulizia brand: prefisso localStorage **`kiosk.`** (record
  azzerati, ok pre-lancio); un solo parametro **`?tenant=`** anche nei giochi;
  eliminati asset/manifest KFP orfani del memory.
- 2026-09-23 — Regola **ASCII** chiarita: vale per la logica JS; emoji/accenti
  nel testo visibile ok.
- 2026-09-23 — I giochi ignorano "riduci movimento" del sistema (animazioni con
  durate inline/Web Animations): sul kiosk devono animarsi sempre.
- 2026-09-23 — Versione per gioco nel manifest (`version` → `?v=`) contro la
  cache del browser.

- 2026-09-23 — Acchiappa-stelle rifatto: la volpe col cestino segue il dito,
  stelle sorridenti dell'icona; speciale = **pioggia di stelle** periodica.
- 2026-09-23 — Sequenza colori rifatta: pinguino + pannello dell'icona;
  **seconda possibilita'** (2 errori, al primo si ripete la sequenza) e il
  pinguino **indica** il tasto che si accende (scia dalla pinna).
- 2026-09-23 — Labirinto rifatto: topo e formaggio dell'icona, muri turchesi e
  corridoi crema; il topo si **trascina** e i muri lo **fermano** (niente
  cancellazione); **3 labirinti in fila** di dimensione crescente.
- 2026-09-24 — Abbina le forme rifatto: coniglio dell'icona, tavola di legno e
  7 blocchi disegnati in vettoriale; **calamita** (basta lasciare la forma vicino
  al suo buco) e **aiutino** (dopo 2 errori il buco giusto lampeggia).
- 2026-09-24 — Tris rifatto: rana, gettoni X/O e griglia viola dell'icona;
  **sfida alla rana** al meglio di 3 (la rana pensa e salta) e **linea magica**
  sul tris.
- 2026-09-24 — Torre di Hanoi rifatta: elefantino dell'icona, aste e anelli
  vettoriali; l'anello si **solleva e vola ad arco** sull'asta scelta (mossa non
  valida: rimbalza) e pulsante **Aiuto** che indica la prossima mossa ottimale.
- 2026-09-24 — Rompicapo rifatto: tartaruga dell'icona, vassoio di legno;
  immagini = le scene della **famiglia di animali** (una a caso per partita),
  tessere che **scorrono**, pulsante **Sbircia**, numeri solo nel facile.
  Re-skin fatto su 11 giochi; resta la Lavagna.
- 2026-09-24 — Eliminata `games/assets/mascotte/` (non piu' usata).
- 2026-09-24 — Lavagna rifatta: gattino dell'icona, lavagna verde con cornice e
  mensola di legno coi gessetti; **sagome da ricalcare** (sole, cuore, stella,
  casa, pesce, fiore) e **timbri** (stella, cuore, fiore). Re-skin dei 12 giochi
  completato.
- 2026-09-24 — Nuovo sfondo menu da Scenario, a norma sez. 10 (1920×1080 JPG
  sRGB, 132 KB); sostituisce `background-soft.webp` (1344×768 WebP).
- 2026-09-24 — Catena dei branch unita in `main` (fast-forward, nessun conflitto).
- 2026-09-24 — Eliminati i branch `feature/*` (gia' tutti in `main`); sez. 7
  aggiornata: si lavora da `main` con branch `feature/<nome>` temporanei.
- 2026-09-24 — Fix idle: i tocchi dentro l'iframe del gioco ora azzerano il
  timer (prima si tornava all'attract dopo 75 s anche giocando).
- 2026-09-24 — Menu: **tolta la cornice 3D**; al suo posto effetto **vetro di
  finestra** (icone in rilievo sul vetro, sfondo visto attraverso).
- 2026-09-24 — **Cornice a finestra** (Scenario) come token opzionale
  `window.image`, attiva su `default`; reversibile mettendo `null`.
- 2026-09-24 — Finestra v1 **zoomata** (`window.zoom` 1.2) perche' occupava
  troppo schermo; poi messa **in standby** (`window.image: null`).
- 2026-09-24 — Finestra **v2** riattivata su default (nuova arte Scenario:
  persiane di legno aperte, architrave menta, davanzale coi vasi). Poi, su
  richiesta, sempre meno persiana fino a toglierla del tutto, e via cerniere e
  vasi: cornice = architrave, stipiti, davanzale; apertura 1763x853 px.
  La v1 resta come asset (`window.webp`, valori in `_previous`).
- 2026-09-24 — **Header dei giochi** nello stile della finestra (fascia menta,
  pulsante di legno, titolo Bold Doodle col colore del gioco); tolto il
  pulsante "Menu" della shell: resta solo "Torna ai giochi" a sinistra.
- 2026-09-24 — Font del tenant (Bold Doodle) su **tutte le scritte**, shell e
  giochi (non piu' solo i titoli); contorno scritte ridotto a 1px. Le lettere
  accentate (es. "difficolta'") escono col font di sistema: Bold Doodle non le ha.
- 2026-09-24 — Tolto il **maiuscolo forzato** da nomi dei giochi, titolo
  dell'header e pulsante: si scrive come nel manifest (piace di piu').
- 2026-09-30 — Primo kiosk **prototipo su Raspberry Pi 5** (cage + Chromium +
  Caddy locale): documentato in `docs/raspberry-pi-setup.md`, config in
  `device/pi/` (branch `docs/raspberry-pi-setup`).
- 2026-09-30 — Uniti in `main` (fast-forward) `feature/menu-vetro`,
  `feature/header-giochi` e `docs/raspberry-pi-setup`.
- 2026-09-30 — Verifiche sul prototipo Pi tutte ok (boot, crash, stacco di
  corrente, touch come `touch`, audio, emoji e accenti). Monitor **orizzontale**.
- 2026-09-30 — **Script di deploy** `device/pi/deploy.sh` (dal Mac): release
  `r-<data>-<commit>`, switch atomico di `current`, restart, rollback, tiene 5
  release. Provato sul prototipo.
- 2026-09-30 — Revisione doc del Pi: `rsync` tra i pacchetti, chiave SSH
  generata prima dell'Imager, procedura di **recupero accesso SSH**. File di
  `device/pi/` **allineati al prototipo** (collaudato); restano 2 migliorie da
  applicare sul Pi: `bind 127.0.0.1` nel Caddyfile (oggi Caddy ascolta su
  `*:8080`, porta aperta alla LAN) ed errore chiaro se manca Chromium.
- 2026-10-03 — Misura del consumo: sul Pi il menu fermo porta Chromium a
  ~120% di CPU e il SoC a 74 C (attract: ~10% e 58 C, GPU attiva). Invece di
  un test usa e getta, **strumento fisso** su ogni kiosk: `kiosk-perf`
  (misure, salute) + timer `kiosk-health` (una riga nel journal ogni 5 min) +
  **modalita' test** della shell (`?perf=1`), spenta di default, accesa solo
  da file-interruttore sul Pi (`kiosk-perf on` + restart), mai dal touch.
  Branch `feature/perf-tools` (da `docs/pi-review`).

- 2026-10-03 — **Icone a livelli GPU** (branch `feature/icone-gpu`): stesse
  icone, ma ogni pezzo animato e' un livello che anima il compositor
  (niente ridisegno a ogni frame) e le 3 drop-shadow sono ombre gia'
  disegnate che seguono i pezzi. Fedelta' misurata pixel per pixel
  (<= 0,35% di pixel diversi, solo bordi). Reversibile: `iconMode: "svg"` nel
  config (gli SVG originali non sono toccati) o rollback della release.

- 2026-10-03 — Misure sul Pi delle icone a livelli: prima versione 224%
  (19 pezzi SVG animati ridisegnati a ogni frame trascinano tutta la pagina),
  con i flipbook **56%** e 62 C (da 156% e 75-84 C). Ombre: costo ~0.
  Animazioni a 30/20 fps: nessun guadagno (Chromium ridisegna a 60 finche'
  un'animazione corre), tolte. Scelta A+B: tenere le icone a livelli e
  **fermarle dopo 10 s senza tocchi**.

- 2026-10-03 — Fix: con le icone a livelli i clic finivano sulle tile
  vicine (livelli 3x, ombre e flipbook sporgono, trasparenti ma cliccabili):
  `pointer-events: none` sulle icone, il clic arriva sempre alla tile sotto.

- 2026-10-03 — **Palloncini** (primo gioco col metodo di misura): il costo
  era nelle schermate di contorno, non nella partita. Icona SVG animata con
  drop-shadow sulla schermata iniziale, mascotte SVG + velo sfocato con le
  nuvole in moto dietro sulla finale. `BB.iconeLivelli()` (shared.js,
  attivabile per gioco): icone a livelli GPU con pausa, sfondo fermo sotto
  il velo. Misure (CPU Chromium): iniziale 75% -> 22%, finale 43% -> 5%,
  partita 54% invariata (palloncini mossi dal JS a ogni frame: nel budget).

- 2026-10-03 — **Memory**: `BB.iconeLivelli()` attivo. Schermata iniziale
  42% -> 0,4% (icona a livelli, in pausa dopo 10 s); partita ~2% (carte
  ferme finche' nessuno le gira).

- 2026-10-03 — **Talpe**: `BB.iconeLivelli()` attivo. Schermata iniziale
  35% -> 0,4%; partita ~8% (invariata).

- 2026-10-03 — `BB.iconeLivelli()` attivo su tutti gli 11 giochi con
  l'icona animata (la Lavagna non ce l'ha). Schermate iniziali, CPU Chromium
  SVG -> livelli: Frutta 53->0,6, Stelle 71->26, Sequenza 59->0,4,
  Labirinto 60->0,5, Forme 49->0,4, Rompicapo 34->0,5, Tris 78->0,4,
  Hanoi 55->0,4 (%). Partite avviate e lasciate senza tocchi: quasi tutte
  ~0,4%, Frutta 36%, **Stelle 105% (oltre il budget)**: stelle che cadono
  con drop-shadow sfocato (bagliore) mosse a ogni frame + 28 stelline di
  sfondo animate con box-shadow.

- 2026-10-03 — **Acchiappa-stelle**: bagliore delle stelle disegnato negli
  sprite (`tools/bake_filter.py`, nuovo: un filtro CSS cotto in un'immagine)
  invece del drop-shadow su stelle in movimento; stelline di sfondo in pausa
  sulla schermata iniziale (`BB.pausaDecorazioni`, nuovo). Partita 105% ->
  56%, schermata iniziale 26% -> 0,5%. Tutti i giochi ora nel budget.

- 2026-10-03 — Repository pubblicato su GitHub: **Kevodable/playkiosk**
  (pubblico, nome neutro), con tutto il contenuto (anche `_legacy` e il
  tenant `funplanet`: scelta dell'utente). `.gitignore`: `.DS_Store`,
  `.claude/`, cache Python.

- 2026-10-14 — **Backend centrale:** scelto Aruba Linux Easy, dominio
  `benbenplay.com` (sez. 5c): criteri del database e divisione dei compiti
  (credenziali fuori repo, niente login di Claude nei pannelli web).

## Stato attuale
- **Shell/menu:** tile nude (icona animata in rilievo + titolo), sfondo a
  norma, **cornice a finestra v2** (architrave, stipiti, davanzale) su default;
  senza finestra il menu mostra il vetro. Pulsante legno = token opzionale.
- **Giochi:** re-skin **completo su tutti e 12**; **header nuovo** nello stile
  della finestra, un solo pulsante per tornare ai giochi. Il Rompicapo usa come
  immagini da ricomporre le scene della famiglia di animali.
- **Font:** Bold Doodle su tutte le scritte, contorno 1px, niente maiuscolo
  forzato.
- **Icone:** tutte e 12 animate (`tools/build_<gioco>.py`).
- **Branch:** solo `main`, tutto unito (fino a revisione doc del Pi,
  `kiosk-perf`, icone a livelli GPU); branch `feature/*` e `docs/*` eliminati.
  **Remote GitHub:** `origin` = https://github.com/Kevodable/playkiosk
  (**pubblico**, primo push 2026-10-03). GitHub Pages non ancora attivato.
- **Dispositivo:** prototipo Raspberry Pi 5 `kiosk-dev-01` funzionante, tutte le
  verifiche ok (vedi `docs/raspberry-pi-setup.md`). Deploy con
  `device/pi/deploy.sh` (dal Mac: release versionate, rollback); roadmap di
  sez. 5 del doc: fatto il punto 4 (script di deploy), il resto da fare.
  Migliorie applicate sul Pi il 2026-10-03: Caddy solo su `127.0.0.1:8080`
  (verificato: dal Mac la porta non risponde), `kiosk-browser.sh` nuovo,
  `kiosk-perf` e timer di salute.
- **Prestazioni (menu):** risolto. Icone a livelli GPU (`iconMode:
  "layers"`, con flipbook e ombre per pezzo) + pausa dopo 10 s senza tocchi.
  Misure sul Pi all'aria aperta (CPU Chromium, 100% = 1 core): menu animato
  **56-58% / 60-62 C** (prima 156% / 75-84 C con throttling), menu lasciato
  solo **0,5% / 54 C**, attract 11% / 58 C. Ritorno indietro: `iconMode:
  "svg"` o rollback della release. `kiosk-perf` + timer `kiosk-health`
  installati sul prototipo; modalita' test SPENTA.
- **Da fare (prestazioni):** prova nel totem chiuso (`journalctl -t
  kiosk-health`, totem non ancora pronto). **Giochi:** tutti nel budget
  (schermate iniziali ~0,5% dopo la pausa; partite senza tocchi: quasi tutte
  ~0,4%, Frutta 36%, Palloncini 54%, Acchiappa-stelle 56%).
- **Backend:** hosting Aruba Linux Easy + `benbenplay.com` (sez. 5c).
  Prossimo passo: attivazione, poi database e accesso FTP dal pannello
  (utente), file delle credenziali fuori repo, poi backend e telemetria.
- **Aperti:**
  - accenti non coperti da Bold Doodle (es. "difficolta'" in 9 giochi):
    riscrivere senza accento o trovare un font simile con gli accenti;
  - maiuscole dei titoli nel manifest non uniformi ("Acchiappa la Talpa" vs
    "Scoppia i palloncini").

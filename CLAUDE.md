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
- Produzione: **mini PC Linux (x86 N100) + monitor touch ~22" (1920×1080,
  landscape)**, **solo Chromium**.
- Sviluppo/test su Mac con **Chromium**.
- Android NON è più target di produzione. **Safari NON è più un target**: niente
  più verifiche di compatibilità Safari.
- **Offline-first RESTA** (legato all'N100, non a Safari): niente CDN, librerie e
  font in **locale** nel repo.

## 6. Vincoli tecnici
- Shell in **HTML single-file**, niente build tool / bundler.
- **JS solo ASCII**: vale per la **logica** JS (nomi, operatori, stringhe
  tecniche come chiavi e percorsi), come igiene contro bug da caratteri strani.
  Emoji e accenti nel **testo visibile** (punteggi, messaggi, titoli) e nei
  commenti sono ok. Non è più un vincolo di compatibilità (Safari non è target).
- Deploy su **GitHub Pages** (account kevodable), sottocartelle separate, serve
  `.nojekyll`.
- **Telemetria:** una funzione `telemetry(event, payload)` → oggi `console.log`
  di `{ts, tenantId, deviceUuid, event, ...}`, con cucitura TODO per POST al
  backend futuro (PHP+MySQL su Aruba). `deviceUuid` in `localStorage`. Eventi:
  app_start, attract_view, menu_view, game_open, game_close(+durationMs),
  idle_return, error.

## 7. Struttura repo
Due cartelle:
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
  - `.nojekyll`, `README.md`
- Branch: `feature/shell` (shell), `feature/<gioco>-reskin` (re-skin per gioco).
  Committare i punti buoni.

## 8. Shell / menu — design attuale
- Flusso: **attract loop** (tap sblocca audio → menu) → **menu** (griglia) →
  **gioco** in **iframe** fullscreen stessa origine con overlay HOME della shell →
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
  Scenario (sorgenti in `tools/art/`).
- **Titolo:** sotto l'icona, **MAIUSCOLO** (`text-transform`, i testi nel
  manifest restano normali). Font **Bold Doodle** (woff2/woff locali; licenza
  free anche commerciale; NON ha glifi accentati). Colore **acceso/saturo per
  gioco** (`titleColor` nel manifest) + contorno scuro + ombra morbida.
- **Sfondo:** `background-soft.webp` (menta pastello con doodle discreti, per non
  distrarre dalle icone), fisso dietro la griglia, con velo `overlay` dal config.
- **Cornice 3D del menu:** bordo menta rialzato intorno allo schermo, sopra la
  griglia (le tile scorrono "sotto", come dietro una finestra).
- **Cache:** ogni gioco ha un `version` nel manifest, aggiunto all'URL
  dell'iframe (`?v=`); le icone hanno `?v=` nel path. Alzarli a ogni modifica.

## 9. I 12 giochi + re-skin (fase in corso)
Giochi: memory, talpe, palloncini, frutta, stelle, sequenza, lavagna, labirinto,
forme, puzzle, tris, hanoi.

- **De-brandizzazione (in corso):** fatta su talpe, palloncini, frutta, memory,
  stelle, sequenza, labirinto, forme; gli altri 3 contengono ancora le vecchie mascotte Fun Planet
  (kip/stella/bolt/bobo). Vanno **rifatti** con grafica
  coerente all'icona-animale di ogni gioco (i personaggi base del prodotto):
  questo toglie il brand vecchio E alza la qualità al livello dell'icona.
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
- **Icone/loghi gioco:** quadrato PNG trasparente, leggibili in piccolo (~200px),
  stile comune (blocco-stile fisso riusato per tutti e 12 → famiglia coerente).
- **Font:** woff2 + woff LOCALI, licenza libera per uso commerciale (OFL o
  equivalente). MAI versioni demo "personal use only".
- **Regola d'oro per cambiare grafica:** immagine → **sostituisci il file**
  (stesso nome, stessa cartella); testo/numero/colore → **config.json**;
  gioco/tier/titolo → **manifest**. Il codice non si tocca. Unica eccezione:
  cambio FORMA del pulsante → rimisurare la content-box (4 inset).

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
- **Safari abbandonato** come target: solo Chromium. Offline-first resta (N100).
- Font titoli: **Bold Doodle** (free anche commerciale, no accenti).
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

## Stato attuale
- **Shell/menu:** tile nude (icona animata + titolo maiuscolo), sfondo menta,
  cornice 3D, font + colori titoli. Pulsante legno = token opzionale.
  Aperto: lo sfondo attuale è **1344×768 WebP**, sotto la specifica della sez. 10
  (1920×1080 JPG) — da rigenerare o aggiornare la specifica.
- **Icone:** tutte e 12 animate (`tools/build_<gioco>.py`).
- **Giochi:** de-brand **fatto** su talpe, palloncini, frutta, memory, stelle,
  sequenza, labirinto, forme
  (grafica dall'icona, numeri in `CONFIG` in cima a ogni gioco, sprite da
  `tools/build_<gioco>_sprites.py`). **Restano:** puzzle, tris, hanoi (usano ancora le mascotte vecchie).
- **Branch:** catena talpe → palloncini → frutta → memory → cleanup-brand →
  stelle → sequenza → labirinto → `feature/forme-reskin` (punta). `feature/shell`/`main` non contengono ancora `kiosk/`: da fondere.

# Kiosk su Raspberry Pi 5 — setup, deploy, diagnostica

Documento del **primo prototipo** funzionante (`kiosk-dev-01`). I file di
configurazione versionati sono in [`device/pi/`](../device/pi/README.md): sono
la fonte di verità, sul Pi si copiano da lì.

> Niente segreti in questo documento né in `device/pi/`: niente password,
> chiavi SSH, auth key Tailscale, indirizzi IP.

---

## 1. Architettura del dispositivo

```
 boot ─► systemd (default: graphical.target)
          ├─ caddy.service ─────► HTTP solo su 127.0.0.1:8080
          │                        serve /srv/kiosk/current  (Cache-Control: no-cache)
          └─ kiosk.service ─────► utente "kiosk", tty1, PAM "cage"
                                   cage (compositor Wayland a singola app)
                                    └─ /usr/local/bin/kiosk-browser.sh
                                        └─ chromium --kiosk ... http://127.0.0.1:8080
                                    Restart=always, RestartSec=3
```

| Livello            | Scelta                                                                 |
|--------------------|------------------------------------------------------------------------|
| Hardware           | Raspberry Pi 5; scheda SD sul prototipo, **SSD NVMe** previsto in produzione |
| OS                 | Raspberry Pi OS **Lite 64-bit** (Debian **Trixie**), niente desktop     |
| Compositor         | **cage**: una sola app a schermo intero, niente desktop né barre       |
| Browser            | **Chromium** in modalità kiosk, backend Wayland (ozone)                |
| Server locale      | **Caddy** su `127.0.0.1:8080`, `bind 127.0.0.1` (non raggiungibile dalla rete; vedi nota in §2.6) |
| Utente di runtime  | `kiosk`: gruppi `video render input audio`, **senza password né sudo** |
| Utente admin       | prototipo: `kiosk-dev-01` (temporaneo). Produzione: utente admin fisso uguale su tutti i kiosk |
| Hostname           | prototipo: `kiosk-dev-01`. Produzione: hostname unico per unità         |
| Accesso remoto     | SSH **solo chiave** (`PasswordAuthentication no`, da cloud-init); **Tailscale** attivo. Raspberry Pi Connect **non** attivo |

Perché un server locale e non `file://`: la shell carica `manifest.json` e
`config.json` con `fetch()`, apre i giochi in iframe della **stessa origine** e
usa `localStorage`; con `file://` Chromium blocca o isola tutte e tre le cose.

### Percorsi

| Percorso                              | Cosa                                                        |
|---------------------------------------|-------------------------------------------------------------|
| `/srv/kiosk/releases/v0/`             | pagina di test touch                                        |
| `/srv/kiosk/releases/v1/`             | contenuto di `kiosk/` di questa repo                        |
| `/srv/kiosk/releases/r-AAAAMMGG-HHMMSS-<commit>/` | release create da `deploy.sh` (ne tiene 5)   |
| `/srv/kiosk/current`                  | **symlink** alla release attiva (Caddy serve questo)        |
| `/etc/caddy/Caddyfile`                | ← `device/pi/Caddyfile`                                     |
| `/etc/systemd/system/kiosk.service`   | ← `device/pi/kiosk.service`                                 |
| `/etc/pam.d/cage`                     | ← `device/pi/pam-cage`                                      |
| `/usr/local/bin/kiosk-browser.sh`     | ← `device/pi/kiosk-browser.sh`                              |
| `/usr/local/bin/kiosk-perf`           | ← `device/pi/kiosk-perf` (misure e salute, §4.1)            |
| `/etc/systemd/system/kiosk-health.*`  | ← `device/pi/kiosk-health.service` / `.timer`               |
| `/srv/kiosk/perf.on`                  | interruttore della modalità test (assente = kiosk normale)  |
| `/etc/ssh/sshd_config.d/50-cloud-init.conf` | SSH solo chiave (scritto da cloud-init, non versionato) |
| `/home/kiosk/.config/chromium/`       | profilo Chromium: qui vivono `localStorage` (deviceUuid, record dei giochi) |

---

## 2. Installazione passo passo

Riproduce il prototipo da zero. `<admin>` = utente amministratore, `<host>` =
hostname dell'unità.

### 2.1 Scheda SD / disco

1. **Prima dell'Imager, sul Mac:** se non hai già una chiave, generala.

   ```sh
   ssh-keygen -t ed25519                         # -> ~/.ssh/id_ed25519(.pub)
   ssh-add --apple-use-keychain ~/.ssh/id_ed25519  # solo se ha una passphrase
   cat ~/.ssh/id_ed25519.pub                     # da incollare nell'Imager
   ```

2. **Raspberry Pi Imager** → *Raspberry Pi OS Lite (64-bit)* (Trixie).
3. Impostazioni personalizzate: hostname `<host>`, utente `<admin>` con
   password, **SSH con sola chiave pubblica**: incolla il **contenuto** di
   `~/.ssh/id_ed25519.pub` (la chiave pubblica, mai quella privata), locale
   e fuso orario. Imager scrive tutto via cloud-init, compreso
   `50-cloud-init.conf` con `PasswordAuthentication no`.
4. Primo avvio, poi dal Mac: `ssh <admin>@<host>.local`. Se la chiave non
   viene accettata: §2.8.

### 2.2 Sistema e pacchetti

```sh
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y cage chromium caddy rsync fonts-noto-color-emoji fonts-dejavu-core
```

`rsync` serve sul Pi per `deploy.sh` (§3.1): su Lite non c'è (sul prototipo
era stato installato a mano).

I due pacchetti di font sono **obbligatori** (vedi §6): Raspberry Pi OS Lite non
ha font emoji (i giochi usano emoji nel testo visibile) e Bold Doodle non ha le
lettere accentate, che escono col font di sistema. Dopo l'installazione:
`sudo systemctl restart kiosk.service`.

### 2.3 Tailscale

```sh
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up          # login interattivo (in futuro: pre-auth key, §5)
```

Poi, nella console di amministrazione Tailscale, **disattivare la key expiry**
del dispositivo (ancora da fare sul prototipo).

### 2.4 Utente di runtime `kiosk`

```sh
sudo useradd --create-home --groups video,render,input,audio kiosk
# nessuna password (account bloccato) e nessun sudo: non aggiungerlo a "sudo"
```

### 2.5 Cartelle dei contenuti

```sh
sudo mkdir -p /srv/kiosk/releases
sudo chown -R <admin>:<admin> /srv/kiosk      # il deploy via rsync entra come <admin>
```

Caricare almeno una release (vedi §3) e creare il symlink:

```sh
sudo ln -sfn /srv/kiosk/releases/v1 /srv/kiosk/current
```

### 2.6 File di configurazione

Dal Mac, dalla radice della repo:

```sh
scp -r device/pi <admin>@<host>.local:~/pi
```

Sul Pi:

```sh
sudo install -m 644 ~/pi/Caddyfile        /etc/caddy/Caddyfile
sudo install -m 644 ~/pi/kiosk.service    /etc/systemd/system/kiosk.service
sudo install -m 644 ~/pi/pam-cage         /etc/pam.d/cage
sudo install -m 755 ~/pi/kiosk-browser.sh /usr/local/bin/kiosk-browser.sh
sudo systemctl daemon-reload
sudo systemctl reload caddy
sudo systemctl set-default graphical.target
sudo systemctl enable --now kiosk.service
```

Nota: il Caddyfile ha `bind 127.0.0.1`. L'indirizzo del sito
(`http://127.0.0.1:8080`) filtra solo l'host delle richieste: senza `bind`
Caddy ascolta su tutte le interfacce e la porta 8080 risponde dalla rete (con
una pagina vuota). Controllo sul Pi: `ss -ltn | grep 8080` deve mostrare
`127.0.0.1:8080`, non `*:8080`.

### 2.7 Verifiche

| Verifica                                   | Esito prototipo |
|--------------------------------------------|-----------------|
| Avvio automatico al boot                   | ✅ ok           |
| Rilancio automatico dopo crash di Chromium | ✅ ok           |
| I giochi si aprono                         | ✅ ok           |
| Emoji e lettere accentate a schermo        | ✅ ok           |
| Ripartenza dopo stacco di corrente         | ✅ ok           |
| Precisione touch (`pointerType` touch vs mouse) | ✅ ok, arriva come `touch` |
| Audio                                      | ✅ ok           |
| Orientamento monitor                       | ✅ orizzontale (landscape) |

### 2.8 Recupero accesso SSH

Se la chiave non è entrata (chiave sbagliata o incollata male nell'Imager),
SSH rifiuta tutto perché `50-cloud-init.conf` ha `PasswordAuthentication no`.
Procedura usata sul prototipo, con **tastiera e monitor sul Pi** (login su
tty come `<admin>`):

```sh
# sul Pi: riabilita la password SOLO temporaneamente
echo 'PasswordAuthentication yes' | sudo tee /etc/ssh/sshd_config.d/00-temp.conf
sudo systemctl restart ssh
sudo sshd -T | grep -i passwordauthentication   # deve dire "yes"
```

Il nome **deve finire in `.conf`** (altrimenti sshd lo ignora) e deve venire
**prima** di `50-cloud-init.conf` in ordine alfabetico: sshd tiene il primo
valore che trova, quindi `00-` vince su `50-`.

```sh
# dal Mac: copia la chiave (chiede la password dell'admin)
ssh-copy-id -i ~/.ssh/id_ed25519.pub <admin>@<host>.local
ssh <admin>@<host>.local                          # deve entrare senza password
```

```sh
# sul Pi: torna a solo chiave
sudo rm /etc/ssh/sshd_config.d/00-temp.conf
sudo systemctl restart ssh
sudo sshd -T | grep -i passwordauthentication   # deve dire "no"
```

Nota: la tastiera sul Pi serve **prima** di installare il kiosk (§2.6): con
`kiosk.service` attivo tty1 è di cage e il cambio di terminale è disattivato
(§4), quindi non c'è un login locale.

---

## 3. Deploy e rollback

**Regola:** sul dispositivo va **solo** il contenuto di `kiosk/`, mai la repo
(niente `.git`, `CLAUDE.md`, `.claude`, `tools`, `_legacy`, `docs`, `device`).

### 3.1 Deploy con lo script (consigliato)

`device/pi/deploy.sh` si lancia **dal Mac** (non va copiato sul Pi):

```sh
device/pi/deploy.sh                 # deploy: nuova release + switch + restart
device/pi/deploy.sh list            # release sul Pi, * = attiva
device/pi/deploy.sh rollback        # torna alla release precedente
device/pi/deploy.sh rollback v1     # ... o a una release per nome
KIOSK_HOST=<admin>@<host>.local device/pi/deploy.sh   # altro kiosk
```

Cosa fa il deploy:

1. controlla in locale `kiosk/index.html`, `manifest.json` e i `config.json`
   dei tenant (JSON valido); avvisa se `kiosk/` ha modifiche non committate
   (la release prende il suffisso `-dirty`);
2. sul Pi verifica che `/srv/kiosk` e `releases/` siano scrivibili dall'admin;
3. rsync **solo** di `kiosk/` (con `--delete`, senza `.DS_Store`) in una
   cartella nuova `releases/r-AAAAMMGG-HHMMSS-<commit>`;
4. permessi di lettura per tutti, switch **atomico** del symlink `current`
   (`ln -sfn … current.new` + `mv -T`);
5. `sudo systemctl restart kiosk.service` (`ssh -t`: se sudo chiede la
   password la si digita), poi controlla che Caddy serva `/` e il manifest;
6. tiene le ultime `KIOSK_KEEP` release dello script (default 5), mai quella
   attiva; le release fatte a mano (`v0`, `v1`, …) non vengono mai toccate.

Il rollback senza nome va alla release dello script precedente a quella
attiva; se l'attiva è una release a mano (es. `v1`) bisogna dare il nome.

Prerequisiti sul Pi: `/srv/kiosk` e `/srv/kiosk/releases` di proprietà
dell'admin (§2.5; sul prototipo erano di root: `sudo chown <admin>:<admin>
/srv/kiosk /srv/kiosk/releases`), `curl` installato (c'è già su Lite), sudo
per l'admin.

Provato sul prototipo il 2026-09-30: deploy (file identici a `kiosk/`, niente
`.DS_Store`, kiosk riavviato), rollback per nome e senza nome, errore corretto
quando non c'è una release precedente.

### 3.2 Deploy manuale (come fatto sul prototipo prima dello script)

Dalla cartella `kiosk/`:

```sh
rsync -av --exclude '.DS_Store' ./ kiosk-dev-01@kiosk-dev-01.local:/srv/kiosk/releases/v1/
```

Poi sul Pi:

```sh
sudo pkill chromium        # kiosk.service lo rilancia in 3 s
```

Nota: così si **sovrascrive la release attiva** (v1): durante la copia la shell
può vedere file misti, e non resta una versione precedente per il rollback.
Inoltre senza `--delete` i file tolti dalla repo restano sul Pi.

### 3.3 Deploy manuale con release versionata

```sh
# dal Mac, cartella kiosk/: nuova cartella vN
rsync -av --delete --exclude '.DS_Store' ./ <admin>@<host>.local:/srv/kiosk/releases/v2/
# sul Pi: switch del symlink e restart
sudo ln -sfn /srv/kiosk/releases/v2 /srv/kiosk/current
sudo pkill chromium
```

### 3.4 Rollback manuale

```sh
ls /srv/kiosk/releases/                              # release disponibili
sudo ln -sfn /srv/kiosk/releases/v1 /srv/kiosk/current
sudo pkill chromium
```

Caddy segue il symlink a ogni richiesta e manda `Cache-Control: no-cache`:
non serve riavviarlo né svuotare la cache di Chromium. I `?v=` del manifest
restano utili per la cache sul Mac e su GitHub Pages.

---

## 4. Diagnostica

```sh
systemctl status kiosk.service              # stato di cage + Chromium
journalctl -u kiosk.service -b              # log del kiosk dall'ultimo boot
journalctl -u kiosk.service -b -1           # ... dal boot precedente (es. dopo stacco corrente)
systemctl status caddy.service
journalctl -u caddy.service -b
curl -sI http://127.0.0.1:8080/             # risponde? c'e' Cache-Control: no-cache?
readlink -f /srv/kiosk/current              # quale release e' attiva
systemctl get-default                       # deve essere graphical.target
chromium --version
tailscale status
vcgencmd measure_temp                       # temperatura SoC
vcgencmd get_throttled                      # 0x0 = nessun sottovoltaggio / throttling
```

Riavvio del solo kiosk: `sudo systemctl restart kiosk.service`.
cage parte senza `-s`: il cambio di terminale (`Ctrl+Alt+Fn`) è disattivato,
si interviene via SSH/Tailscale.

### 4.1 Misure di prestazioni e salute (`kiosk-perf`)

Strumento fisso su ogni kiosk (`device/pi/kiosk-perf`), solo lettura. CPU in
% di un core (il Pi 5 ha 4 core: massimo 400%).

```sh
kiosk-perf sample -s 60      # stato attuale: CPU sistema e processi Chromium
                             # (gpu-process, renderer, browser), cage,
                             # temperatura, clock ARM/GPU, throttling
kiosk-perf health            # una riga (la stessa del timer)
journalctl -t kiosk-health   # storico: una riga ogni 5 min (kiosk-health.timer);
                             # sopra 75 C o con throttling = warning
journalctl -t kiosk-health -p warning   # solo gli avvisi
```

**Modalità test della shell** (per confrontare gli stati in modo ripetibile):

```sh
kiosk-perf on                              # crea /srv/kiosk/perf.on
sudo systemctl restart kiosk.service       # la shell si apre con ?perf=1 (badge "PERF" in basso a destra)
kiosk-perf run                             # sequenza standard: attract, menu, game:memory,
                                           # menu-static (icone ferme), menu-noshadow (senza ombre)
kiosk-perf run -s 60 --settle 150 menu game:talpe   # stati a scelta
kiosk-perf run menu-svg menu-layers        # confronto icone: SVG originali / livelli GPU
                                           # (iconMode forzato solo per quello stato)
kiosk-perf run --settle 20 -s 30 menu-only:talpe menu-only:lavagna   # costo di una sola icona
kiosk-perf run menu-noraster               # icone a livelli senza i pezzi ridisegnati a ogni frame
kiosk-perf run menu-turns:3                # solo 3 icone animate alla volta, a turno ogni 4 s
kiosk-perf run --settle 30 menu-idle       # menu lasciato solo: icone in pausa dopo iconPauseAfterSec
                                           # (negli altri stati del menu la pausa e' spenta)
kiosk-perf off && sudo systemctl restart kiosk.service   # SEMPRE alla fine
```

Per ogni stato: la shell lo applica e lo conferma (canale su
`127.0.0.1:8081`, aperto solo durante `run`), poi assestamento (`--settle`,
default 150 s, perché la temperatura sale lentamente) e misura (`-s`, default
60 s); alla fine un riepilogo. Senza conferma entro 20 s `run` si ferma
(modalità non accesa, kiosk non riavviato, gioco inesistente). Una misura
disturbata è marcata **SCARTATA** (con il motivo): la shell riporta lo
schermo che mostra davvero e i tocchi/tasti ricevuti, e se cambiano durante
assestamento o misura, o la shell smette di rispondere, il numero non vale.
Durante `run` non toccare il kiosk (né tastiere o mouse collegati). In modalità
test il ritorno all'attract per inattività è spento solo negli stati imposti
da `run`; dal touch la modalità non si attiva mai.

---

## 5. Roadmap (pianificata, **non** ancora implementata)

1. **Chromium bloccato:** `sudo apt-mark hold chromium` (e dipendenze
   `chromium-common` ecc.); aggiornamenti solo dopo test su un'unità di prova.
2. **Watchdog hardware** (il Pi 5 ha il watchdog del SoC, via
   `RuntimeWatchdogSec` di systemd) + **riavvio notturno** programmato (timer
   systemd).
3. **Root in sola lettura** (overlayfs) con una **partizione dati scrivibile**
   per `config.json` e la coda della telemetria.
   Attenzione: anche il **profilo Chromium** (`/home/kiosk/.config/chromium`)
   deve stare sulla partizione dati, altrimenti a ogni riavvio si perdono
   `localStorage` → **nuovo `deviceUuid`** e record dei giochi azzerati.
4. **Script di deploy:** ✅ fatto e provato sul prototipo
   (`device/pi/deploy.sh`, vedi §3.1).
5. **Immagine master "sigillata"** con script di primo avvio: hostname e UUID
   dal **numero di serie** del Pi, rigenerazione chiavi SSH host e
   `machine-id`, join Tailscale con **pre-auth key** (fornita al momento, mai
   nella repo). In seguito l'immagine si costruisce con **rpi-image-gen**.

---

## 6. Compatibilità dell'app (`kiosk/`) con il Pi

Verifica statica del 2026-09-30 sul contenuto di `kiosk/`:

- ✅ `kiosk/index.html` presente: Caddy la serve su `/`.
- ✅ Nessuna risorsa da internet: niente CDN, script, CSS, font o immagini
  remote. Font del tenant in locale (`tenants/default/assets/fonts/`). Gli unici
  `http://` sono i namespace `xmlns` degli SVG (non sono richieste di rete).
- ✅ Nessun percorso fuori da `kiosk/`: tutti i `../` restano dentro `kiosk/games/`.
  Tutti i file referenziati esistono.
- ✅ Rete: le uniche richieste sono `fetch` locali di `manifest.json` e
  `config.json` (con fallback se mancano). La telemetria oggi è solo
  `console.log`; nessuna chiamata Apps Script. `localStorage` e `AudioContext`
  sono protetti da `try/catch`.
- ✅ **Emoji nel testo visibile** (pulsanti livello, contatori, 🏆, carte del
  Memory ecc.): Raspberry Pi OS **Lite** non ha un font emoji → senza
  `fonts-noto-color-emoji` escono quadratini. Installato nella procedura (§2.2).
- ✅ **Lettere accentate**: Bold Doodle non le ha, escono col font di sistema;
  `fonts-dejavu-core` installato nella procedura (§2.2).
  Controllo sul Pi: `fc-list | grep -iE 'emoji|dejavu'`.
- ✅ Audio: si sblocca col primo tocco sull'attract (policy autoplay di
  Chromium); verificato sul Pi.

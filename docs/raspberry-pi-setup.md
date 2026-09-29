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
| Server locale      | **Caddy** su `127.0.0.1:8080` (non raggiungibile dalla rete)           |
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
| `/srv/kiosk/releases/vN/`             | release successive (una cartella per versione)              |
| `/srv/kiosk/current`                  | **symlink** alla release attiva (Caddy serve questo)        |
| `/etc/caddy/Caddyfile`                | ← `device/pi/Caddyfile`                                     |
| `/etc/systemd/system/kiosk.service`   | ← `device/pi/kiosk.service`                                 |
| `/etc/pam.d/cage`                     | ← `device/pi/pam-cage`                                      |
| `/usr/local/bin/kiosk-browser.sh`     | ← `device/pi/kiosk-browser.sh`                              |
| `/etc/ssh/sshd_config.d/50-cloud-init.conf` | SSH solo chiave (scritto da cloud-init, non versionato) |
| `/home/kiosk/.config/chromium/`       | profilo Chromium: qui vivono `localStorage` (deviceUuid, record dei giochi) |

---

## 2. Installazione passo passo

Riproduce il prototipo da zero. `<admin>` = utente amministratore, `<host>` =
hostname dell'unità.

### 2.1 Scheda SD / disco

1. **Raspberry Pi Imager** → *Raspberry Pi OS Lite (64-bit)* (Trixie).
2. Impostazioni personalizzate: hostname `<host>`, utente `<admin>` con
   password, **SSH con sola chiave pubblica** (incolla la tua chiave), locale
   e fuso orario. Imager scrive tutto via cloud-init, compreso
   `50-cloud-init.conf` con `PasswordAuthentication no`.
3. Primo avvio, poi dal Mac: `ssh <admin>@<host>.local`.

### 2.2 Sistema e pacchetti

```sh
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y cage chromium caddy fonts-noto-color-emoji fonts-dejavu-core
```

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
| Orientamento monitor (verticale/orizzontale) | ⏳ non deciso  |

---

## 3. Deploy e rollback

**Regola:** sul dispositivo va **solo** il contenuto di `kiosk/`, mai la repo
(niente `.git`, `CLAUDE.md`, `.claude`, `tools`, `_legacy`, `docs`, `device`).

### 3.1 Deploy attuale (manuale, dal Mac)

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

### 3.2 Deploy con release versionata (procedura consigliata, manuale)

```sh
# dal Mac, cartella kiosk/: nuova cartella vN
rsync -av --delete --exclude '.DS_Store' ./ <admin>@<host>.local:/srv/kiosk/releases/v2/
# sul Pi: switch del symlink e restart
sudo ln -sfn /srv/kiosk/releases/v2 /srv/kiosk/current
sudo pkill chromium
```

### 3.3 Rollback

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
4. **Script di deploy:** nuova release versionata, rsync solo di `kiosk/`
   (con `--delete`, senza `.DS_Store`), switch del symlink **atomico**
   (`ln -s … current.new && mv -T current.new current`), restart di Chromium,
   comando di rollback, pulizia delle release vecchie.
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

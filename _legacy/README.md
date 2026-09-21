# Fun Planet touch

Launcher Android in **modalità kiosk** per i monitor touch dei parchi giochi
**"Fun Planet"**. Mostra solo i giochi scelti dal gestore e, quando il bambino
chiude un gioco, torna da solo alla griglia. Gira come **launcher predefinito**
+ **Device Owner** (lock task), con branding "Kids Fun Planet" (logo arcobaleno,
colori pastello).

- **Package Android:** `it.bigbenmatic.gamelauncher`
- **Config remota (GitHub Pages):**
  `https://kevodable.github.io/Fun-Planet-touch/launcher/config.json`

## Struttura del repository

- [`android/`](android/) — progetto Android completo (Kotlin / Jetpack Compose).
  Vedi [`android/README.md`](android/README.md) per build, attivazione kiosk
  (Device Owner) e dettagli sulla gestione remota della flotta.
- [`launcher/`](launcher/) — contenuti statici da pubblicare su **GitHub Pages**:
  - `config.json` — configurazione della flotta (defaults + override per
    `deviceId`); pubblica e quindi senza segreti veri.
  - `admin.html` — **pannello di controllo web** per modificare `config.json` da
    interfaccia grafica (moduli per giochi, branding, kiosk, manutenzione, Wi-Fi,
    app da installare). Incrementa da solo `configVersion` e salva committando su
    GitHub tramite un token personale (memorizzato solo nel browser).
    URL: `https://kevodable.github.io/Fun-Planet-touch/launcher/admin.html`
  - `apps-script/Code.gs` — ricevitore di telemetria (Google Apps Script →
    Google Sheet), con istruzioni di deploy nel file stesso.

## Funzionalità principali

- Launcher kiosk con Device Owner / lock task, immersive fullscreen, ritorno
  automatico alla griglia, area genitori protetta da PIN.
- Gestione remota della flotta:
  1. **Config remota** scaricata da GitHub Pages all'avvio e ogni
     `pollIntervalMinutes` (merge defaults + override per `deviceId`,
     versioning su `configVersion`, cache offline-first).
  2. **Identità dispositivo** — UUID stabile + schermata Diagnostica protetta
     da PIN.
  3. **Telemetria** — heartbeat + report completi verso Google Apps Script,
     con coda offline e retry, non bloccante.
- Idle timeout, Wi-Fi con failover (rete "lifeline" on-device + reti del locale
  da `config.json`).

## GitHub Pages

I contenuti di `launcher/` vanno serviti tramite GitHub Pages dal branch `main`
(root), così che `config.json` sia raggiungibile all'URL indicato sopra. Il
percorso dedicato `/launcher/` evita conflitti con eventuali contenuti nella root.

## Vincoli importanti

- `config.json` su GitHub Pages è **pubblico**: non inserire segreti veri. La
  password Wi-Fi del locale lì è leggibile da chiunque (usare una rete dedicata).
  La Wi-Fi *lifeline* resta solo on-device.
- Piena compatibilità con Device Owner / lock task: nulla deve rompere il kiosk.
  Polling config e telemetria girano su coroutine nell'`Application` (`FleetApp`),
  non legati a una singola Activity.

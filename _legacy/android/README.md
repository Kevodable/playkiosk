# Kids Fun Planet — Launcher Android per bambini

App Android pensata per essere installata su un monitor/tablet Android collocato in un parchetto giochi. Sostituisce il launcher di sistema con una schermata semplice e colorata (logo "Kids Fun Planet") che mostra solo i giochi gratuiti scelti dal gestore. Quando il bambino chiude il gioco (o preme il tasto Home), l'app torna automaticamente alla schermata con l'elenco dei giochi.

## Come funziona

- L'app si registra come **launcher predefinito** (categoria `HOME`), oltre che come normale app. Al primo avvio del dispositivo (o disinstallando/disabilitando temporaneamente l'altro launcher) Android chiederà di scegliere il launcher predefinito: selezionare "Kids Fun Planet" e impostarlo come predefinito ("sempre").
- Perché Android torna da solo alla griglia: quando l'app launcher è quella predefinita, la sua Activity resta in fondo allo stack. Quando il gioco lanciato viene chiuso (back ripetuto, uscita dal gioco, crash) o quando si preme il tasto Home, il sistema riporta automaticamente in primo piano la nostra schermata, senza bisogno di codice aggiuntivo.
- Nessuna icona di altre app o barra di sistema è visibile: l'interfaccia è a schermo intero (immersive mode).

## Modalità Kiosk (Device Owner) — guida passo-passo

Per bloccare davvero il tablet sull'app (niente Home, niente Recenti, niente barra
notifiche, nessun'altra app apribile a parte i giochi scelti), l'app va registrata come
**Device Owner** del tablet, che abilita la **Lock Task Mode** di Android. Questo sblocca anche
l'**installazione remota silenziosa degli APK** (i `managedApps` dal pannello). È una procedura
**una tantum**, su un tablet **dedicato solo a questo uso**.

### Prerequisiti (importante)

- Un **tablet dedicato**, **senza nessun account Google** configurato. Se ne ha già uno, serve un
  **reset alle impostazioni di fabbrica** e, durante la configurazione iniziale, **saltare**
  l'aggiunta dell'account Google. Questo è il motivo di errore più comune: il comando fallisce se
  esiste anche un solo account.
- Un **PC** (Windows/Mac/Linux) con **ADB** installato — fa parte degli
  [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)
  (scarica lo zip, estrai, e da quella cartella esegui i comandi `adb`).
- Un **cavo USB** dati.

### Passaggi

1. **Attiva le Opzioni sviluppatore sul tablet**: Impostazioni → *Info sul telefono/tablet* →
   tocca **7 volte** "Numero build" finché compare "Sei uno sviluppatore".
2. **Attiva il Debug USB**: Impostazioni → Sistema → Opzioni sviluppatore → **Debug USB** → ON.
3. **Collega** il tablet al PC via USB e, sul tablet, **autorizza** la richiesta di debug
   ("Consenti debug USB?" → Consenti).
4. **Verifica la connessione** dal PC:
   ```
   adb devices
   ```
   Deve elencare un dispositivo con stato `device` (se dice `unauthorized`, riguarda il popup sul tablet).
5. **Installa l'app** (o aggiornala):
   ```
   adb install -r app-debug.apk
   ```
6. **Registra l'app come Device Owner**:
   ```
   adb shell dpm set-device-owner it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver
   ```
   Deve rispondere **`Success: Device owner set...`**.
7. **(Consigliato) Concedi il permesso per il pulsante "Torna ai giochi" flottante**, così
   funziona dentro il kiosk senza passare dalle impostazioni:
   ```
   adb shell appops set it.bigbenmatic.gamelauncher SYSTEM_ALERT_WINDOW allow
   ```
   (# 4.) (facoltativo) rendilo la Home
adb shell cmd package set-home-activity it.bigbenmatic.gamelauncher/.MainActivity

8. **Apri l'app**: nella schermata Impostazioni (tieni premuta l'icona ⚙️ → PIN) vedrai la
   modalità kiosk attiva. Da ora il tablet resta bloccato sull'app e sui giochi consentiti.

### Manutenzione

- Per installare giochi dal Play Store o cambiare impostazioni di sistema: apri l'area genitori
  col PIN e usa **"Sblocca temporaneamente"** (sospende il blocco finché non rientri nell'app).
- I giochi che ospiti tu (APK) puoi installarli **da remoto** dal pannello, sezione
  *App da installare* (`managedApps`), senza toccare il tablet.

### Risoluzione problemi

- **`set-device-owner` → "not allowed..." / "already has an account"**: sul tablet esiste un
  account o un profilo. Fai un **reset di fabbrica**, salta l'account durante il setup, e ripeti
  dal passo 1.
- **`adb` non riconosciuto**: stai eseguendo il comando fuori dalla cartella *platform-tools*
  (oppure ADB non è nel PATH).
- **Rimuovere il Device Owner** (per dismettere il tablet):
  ```
  adb shell dpm remove-active-admin it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver
  ```

> Senza Device Owner l'app funziona comunque come **launcher predefinito a schermo intero** (buona
> protezione per l'uso quotidiano: si torna ai giochi col tasto Home), ma un utente esperto
> potrebbe raggiungere le impostazioni di sistema, e l'**installazione remota degli APK non è
> disponibile** (richiede i privilegi di Device Owner).

## Configurazione dei giochi (per il gestore/genitore)

1. Installare dal Google Play Store i giochi gratuiti desiderati sul dispositivo, normalmente.
2. Aprire "Kids Fun Planet" e tenere premuto il logo per accedere all'area riservata.
3. Inserire il PIN (default `1234`, modificabile nelle impostazioni).
4. Selezionare con le checkbox quali app devono apparire ai bambini.
5. (Opzionale) Cambiare il PIN per maggiore sicurezza.

## Build del progetto

Questo repository contiene il progetto Gradle/Kotlin completo (cartella `android/`). Per generare l'APK:

1. Apri la cartella `android/` con **Android Studio** (versione recente, es. 2024.x) — Android Studio scaricherà/genererà automaticamente il Gradle Wrapper e le dipendenze.
2. Collega il dispositivo/monitor Android (o un emulatore) e premi **Run**, oppure genera l'APK con `Build > Build Bundle(s) / APK(s) > Build APK(s)`.
3. Installa l'APK sul monitor del parchetto (es. tramite ADB: `adb install app-debug.apk`).
4. Imposta l'app come launcher predefinito quando richiesto dal sistema (Impostazioni > App > App predefinite > App Home, su alcuni dispositivi).

### Da riga di comando (con Android SDK installato)

```
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

> Nota: la cartella non include il file binario `gradlew`/`gradle-wrapper.jar`: Android Studio lo rigenera automaticamente all'apertura del progetto. In alternativa, eseguire `gradle wrapper` una volta con Gradle installato localmente.

## Requisiti minimi

- Android 7.0 (API 24) o superiore.
- I giochi mostrati devono essere già installati sul dispositivo (scaricati da Google Play); l'app non li scarica automaticamente.

## Gestione remota della flotta

I monitor possono essere gestiti da remoto senza recarsi sul posto, anche dopo
l'attivazione del device-owner. Il sistema è composto da tre moduli.

### Modulo 1 — Configurazione remota (`config.json` su GitHub Pages)

- L'app scarica `config.json` all'avvio e poi lo ricontrolla ogni `pollIntervalMinutes`
  (default 15, letto dal file stesso).
- L'URL è impostato in `ConfigRepository.kt` (`FLEET_CONFIG_URL`). Il file di esempio è
  in `launcher/config.json` di questo repository, pensato per essere pubblicato su
  **GitHub Pages** sotto il percorso dedicato `/launcher/` per non entrare in conflitto
  con il sito esistente nella root del repo (`index.html`).
- **Logica di merge** (rispettata esattamente): si parte da `defaults`; si cerca il proprio
  `deviceId` nella mappa `devices`; se presente, i campi indicati per quel dispositivo
  sovrascrivono i default (quelli non indicati restano ai default). Per l'array `games`, le
  voci per-dispositivo sono parziali (`id` + campi cambiati come `visible`/`order`): la
  definizione completa (`package`, `displayName`, `iconUrl`) viene da `defaults.games` e
  viene "patchata".
- **Versioning**: si confronta `configVersion` con quello salvato localmente; se uguale si
  salta, se diverso si applica, si persiste e si logga.
- Cosa si controlla da remoto: elenco/visibilità/ordine/nome+icona/categoria dei giochi,
  branding (logo/colori/sfondo/lingua), layout griglia (colonne, etichette), comportamento
  kiosk (PIN di uscita, auto-launch di un singolo gioco), stato operativo (active/maintenance
  + messaggio), banner promozionali.
- **Offline-first**: l'ultima config valida viene messa in cache e riusata se la rete non è
  disponibile, così il monitor continua a funzionare anche scollegato.

### Modulo 2 — ID dispositivo + schermata Diagnostica

- Al primo avvio viene generato un UUID stabile (`DeviceIdManager`), persistito e incluso in
  ogni download config e in ogni invio di telemetria.
- Una schermata **Diagnostica** (raggiungibile da Impostazioni, quindi protetta dal PIN)
  mostra: `deviceId`, etichetta, versione app, `configVersion` attiva, ultimo contatto
  telemetria, stato connessione. Serve per leggere l'ID sul dispositivo (senza ADB) e
  aggiungerlo alla mappa `devices` del `config.json`.

### Modulo 3 — Telemetria (Google Apps Script → Google Sheet)

GitHub Pages è statico e non può ricevere dati, quindi la telemetria **non** va su github.io:
il ricevitore è un **Google Apps Script** che scrive su un Google Sheet (gratuito, senza
server, consultabile da telefono).

- L'app invia: **heartbeat** leggero ogni `heartbeatIntervalMinutes` (default 5) e un
  **report completo** ogni `reportIntervalMinutes` (default 30) con batteria, uptime e
  conteggio lanci per gioco dall'ultimo report.
- Gli invii sono **resilienti**: i payload vengono accodati localmente e ritrasmessi quando
  torna la rete; non bloccano mai la UI (girano su thread di background nell'`Application`).
- Codice ricevitore e istruzioni di deploy: `launcher/apps-script/Code.gs`. In sintesi: nuovo
  Google Sheet → Estensioni > Apps Script → incolla `Code.gs` → esegui `setup` → distribuisci
  come "App web" (accesso: Chiunque) → copia l'URL `/exec` in `config.json` →
  `defaults.telemetry.reportUrl`.
- **Alert Telegram**: predisposto ma non attivo (funzione `checkOfflineMonitors` in `Code.gs`),
  da completare lato script ricevente quando servirà.

### Wi-Fi con failover (rete locale + rete di salvataggio)

Il monitor può connettersi a due tipi di rete, con failover automatico gestito da Android:

- **Wi-Fi di salvataggio (lifeline)**: si imposta una volta sola **sul dispositivo**, dalla
  schermata Diagnostica (protetta da PIN). È salvata solo in locale e **non viene mai inviata
  online**. È l'ancora di salvezza.
- **Wi-Fi del locale (non-default)**: arriva da `config.json` (`defaults.network.wifiNetworks`,
  override possibile per dispositivo) ed è aggiornabile **da remoto**.

Avendo entrambe configurate, Android si connette automaticamente a quella disponibile. Così, se
il locale cambia le credenziali Wi-Fi, il monitor resta online tramite la lifeline, scarica il
nuovo `config.json` con le credenziali aggiornate e si riconnette da solo — senza interventi sul
posto.

> ⚠️ **Perché la lifeline deve stare sul dispositivo e non nel config remoto:** se il monitor non
> avesse alcuna rete funzionante non potrebbe scaricare `config.json`, quindi non potrebbe
> ottenere le credenziali Wi-Fi da lì (problema dell'uovo e la gallina). La lifeline locale rompe
> questo stallo.

> ⚠️ **Sicurezza:** `config.json` su GitHub Pages è **pubblico**. La password della Wi-Fi del
> locale inserita lì è leggibile da chiunque conosca l'URL. Usa una rete dedicata e non riutilizzare
> quella password per altri servizi. La lifeline (locale) resta invece privata.

> ℹ️ La gestione programmatica del Wi-Fi varia molto tra versioni Android e produttori e **non è
> stato possibile testarla su un dispositivo reale** in questo ambiente: verifica sul tablet di
> destinazione. Su Android 10+ l'API a "suggerimenti" non forza il cambio immediato ma lascia che
> sia il sistema a connettersi automaticamente.

### Compatibilità device-owner / lock task

- Polling config e telemetria girano nell'oggetto `Application` (`FleetApp`) su coroutine di
  background: non interferiscono con `startLockTask`/`stopLockTask` né con la griglia. Il
  kiosk resta integro.
- La allow-list del lock task (`setLockTaskPackages`) viene tenuta sincronizzata con i giochi
  effettivamente mostrati (remoti o locali), così i giochi gestiti da remoto restano lanciabili
  dentro il kiosk.
- **Installazione/aggiornamento APK silenzioso** via `PackageInstaller` sotto device-owner:
  **implementato** (`ApkInstaller`, `InstallResultReceiver`). Quando l'app è Device Owner gli
  APK vengono scaricati e installati/aggiornati senza alcun popup, quindi anche con il kiosk
  attivo. Due usi:
  - **Auto-update del launcher** — `defaults.update` (`latestVersionCode`/`apkUrl`/`silentInstall`):
    se `silentInstall` è `true` e `latestVersionCode` è maggiore della versione installata, il
    launcher si aggiorna da solo al poll successivo.
  - **App/giochi gestiti** — `defaults.managedApps` (o override per dispositivo): lista di APK che
    la flotta deve tenere installati o rimuovere. Ogni voce: `packageName`, `apkUrl`,
    `versionCode` (0 = installa solo se assente; >0 = reinstalla quando l'installato è più vecchio),
    `sha256` (opzionale ma consigliato: `config.json` è pubblico) e `action` (`install` |
    `uninstall`). I pacchetti gestiti installati vengono aggiunti automaticamente alla allow-list
    del lock task, così restano lanciabili dentro il kiosk.
  - **Installazione manuale al volo**: dalla schermata Diagnostica (protetta da PIN) c'è un campo
    "Installa app (APK da URL)" per provare un APK senza PC e senza aspettare il poll.

  > I **titoli del Play Store** non si possono "spingere" da remoto (servirebbe Managed Google
  > Play/EMM): vanno installati una volta sul posto sbloccando temporaneamente il kiosk, poi si
  > gestiscono da remoto. Il meccanismo `managedApps` riguarda **APK ospitati da noi** (es. su
  > GitHub Pages in `launcher/apk/`) o forniti dall'operatore.
- `idleTimeoutSeconds` è **attivo**: dopo quel numero di secondi senza interazioni su una
  schermata diversa dalla griglia (Impostazioni/PIN/Diagnostica), l'app torna automaticamente
  alla griglia pulita. Non disturba né la griglia né un gioco in corso (mentre un gioco è in
  primo piano, il launcher è in HOME dietro di esso). Imposta `0` per disattivarlo.
- `sessionLimitSeconds` è **attivo** (`SessionTimer`): quando un gioco viene aperto parte un
  conto alla rovescia; allo scadere il launcher torna in primo piano, terminando la sessione.
  Vale il limite **per-gioco** (`games[].sessionLimitSeconds`) se impostato, altrimenti quello
  **globale** (`kiosk.sessionLimitSeconds`); `0` = nessun limite. Tutto regolabile da remoto dal
  pannello.
- **Pulsante "Torna ai giochi" flottante** (`FloatingHomeButton`): un overlay sopra i giochi che
  riporta alla griglia con un tocco (trascinabile). Indispensabile in kiosk, dove Home/Back sono
  bloccati. Richiede il permesso "Mostra sopra le altre app" (vedi passo 7 della guida Device
  Owner, oppure il pulsante dedicato nella schermata Diagnostica).
- `maxVolumePercent`, `brightnessPercent` sono letti dalla config e nel modello dati, ma il loro
  enforcement attivo (volume/luminosità) non è ancora cablato: predisposto, da completare.

## Possibili estensioni future (non incluse)

- Enforcement di volume massimo e luminosità da config.
- Alert Telegram lato Apps Script per monitor offline/crash.

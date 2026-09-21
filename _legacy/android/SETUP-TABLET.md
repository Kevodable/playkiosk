# Prova su un tablet — installazione APK + Device Owner (kiosk)

Guida per la **prima prova** su un singolo tablet, collegato via cavo USB a un
Mac. Obiettivo: installare il launcher e renderlo **Device Owner**, così il
kiosk (lock task) si attiva da solo e i giochi web girano dentro la WebView
interna.

> Nota: il kiosk (blocco a schermo intero) si attiva **automaticamente quando
> l'app è Device Owner** — non serve toccare `kiosk.enabled` nel config.

---

## 0) Prerequisiti sul Mac

- **Android Platform Tools** (contiene `adb`). Se non li hai:
  ```bash
  brew install --cask android-platform-tools
  ```
  Verifica: `adb version`

## 1) Prepara il tablet

1. **Impostazioni → Info sul telefono/tablet →** tocca 7 volte *Numero build*
   per sbloccare le **Opzioni sviluppatore**.
2. In **Opzioni sviluppatore** attiva **Debug USB**.
3. **IMPORTANTISSIMO per il Device Owner:** rimuovi **tutti gli account**
   (Google e altri) da *Impostazioni → Account*. Se resta anche un solo
   account, il comando `set-device-owner` fallisce.
   - Ideale: tablet appena resettato di fabbrica e **non** configurato con un
     account Google.
4. Collega il tablet al Mac con il cavo. Sul tablet autorizza il computer
   ("Consenti debug USB?").

Verifica la connessione:
```bash
adb devices
# deve elencare il tuo tablet come "device" (non "unauthorized")
```

## 2) Procurati l'APK

**Via più semplice (consigliata): usa l'APK già pubblicato.** Nel repo c'è sempre
l'ultima versione firmata, la stessa che ricevono i tablet via OTA:

```
launcher/apk/launcher-latest.apk
```
oppure scaricabile da:
```
https://kevodable.github.io/Fun-Planet-touch/launcher/apk/launcher-latest.apk
```
È firmato con la **chiave di debug stabile** (stessa firma di tutti gli OTA finora),
quindi va bene sia per la prima installazione sia per gli aggiornamenti.

> **Attuale: `versionCode = 9` (versionName 1.8).** Verifica sempre che il numero qui
> e in `config.json → defaults.update.latestVersionCode` coincidano.

**In alternativa, ricompila** (utile solo se modifichi il codice). Con Android Studio:
apri `android/`, attendi il *Gradle sync*, poi **Build → Build APK(s)** → l'output è
`android/app/build/outputs/apk/debug/app-debug.apk`. Oppure da CLI dopo il primo sync:
```bash
cd android
./gradlew assembleDebug
```

## 3) Installa l'APK sul tablet

```bash
# dal Mac, usa l'APK pubblicato o l'app-debug.apk appena buildato
adb install -r launcher-latest.apk
```
`-r` reinstalla mantenendo i dati se l'app c'è già.

## 4) Imposta il launcher come DEVICE OWNER

```bash
adb shell dpm set-device-owner it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver
```
Risposta attesa:
```
Success: Device owner set to package it.bigbenmatic.gamelauncher
```
Se vedi *"…because there are already some accounts on the device"* → torna al
punto 1.3 (rimuovi TUTTI gli account) e ripeti.

## 5) Rendi il launcher la Home (così parte da solo)

Apri l'app una volta (o premi il tasto Home e scegli "Kids Fun Planet" come
predefinita). Su molti dispositivi funziona anche:
```bash
adb shell cmd package set-home-activity it.bigbenmatic.gamelauncher/.MainActivity
```

## 6) Verifica

```bash
# Conferma che è Device Owner
adb shell dpm list-owners
# Stato completo delle policy (cerca "Device Owner")
adb shell dumpsys device_policy | grep -i "owner"
# Versione installata (deve essere 9)
adb shell dumpsys package it.bigbenmatic.gamelauncher | grep versionCode
```
A questo punto: apri un gioco dalla griglia → si apre la WebView a tutto
schermo; **← Esci** (o il pulsante flottante) torna alla griglia. Il tasto Home
di sistema è bloccato dal lock task.

> Permesso "Mostra sopra le altre app" per il pulsante flottante "Torna ai
> giochi": vai in *Impostazioni del launcher → Diagnostica → Attiva permesso*
> (o concedilo dalle impostazioni Android).

---

## Disattivare il Device Owner (per smontare la prova)

Il Device Owner **non** si rimuove con una semplice disinstallazione. Opzioni:

```bash
# Tentativo via adb (funziona su build di test / alcune ROM):
adb shell dpm remove-active-admin it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver
```
Se fallisce, l'unico modo sicuro per togliere il Device Owner è un
**ripristino di fabbrica** del tablet. Tienine conto prima di usarlo su un
dispositivo "importante".

---

## Aggiornamenti successivi (OTA, senza cavo)

Dopo questa prima installazione manuale, gli aggiornamenti arrivano **da soli** via
`config.json` — **ma solo se l'app è Device Owner** (senza Device Owner il self-update
non parte e Android non consente l'installazione silenziosa). Flusso:

1. Alza `versionCode` in `android/app/build.gradle.kts` (es. 9 → 10) e builda l'APK
   (stessa chiave di firma di quello già installato, altrimenti l'OTA viene rifiutato).
2. Copia l'APK in `launcher/apk/launcher-latest.apk` (l'URL in `config.json →
   defaults.update.apkUrl`).
3. Imposta `defaults.update.latestVersionCode` al nuovo numero (es. 10), incrementa
   `configVersion` e pubblica (merge in `great-meitner`).
4. Al prossimo poll della config, i tablet Device Owner si aggiornano in silenzio.

> **Attuale: app `versionCode = 9` (1.8), config `latestVersionCode = 9`.**
> Da v9 in poi il launcher è multi-tenant (router `launcher/fleet.json`): un tablet non
> mappato vede comunque la config di Big Ben. Vedi `launcher/clients/README.md`.

### Distribuzione finale: usa l'APK di release
La **keystore di release** ora esiste (vedi `android/SIGNING.md`, SHA-256 `e12c01bb…`).
Per i **monitor definitivi**: prima installazione via cavo con l'**APK di release**
(`assembleRelease`, oppure il file `launcher-release-v9.apk` fornito a Kevin), poi
provisioning Device Owner come sopra. Gli OTA successivi vanno firmati con la **stessa**
chiave di release. I 2 tablet di **test** restano sulla firma di *debug* (`c23a3cc0…`);
per allinearli alla release serve factory reset + reinstallazione.

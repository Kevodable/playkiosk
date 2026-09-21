# Preparazione di un nuovo touch — guida rapida

Tutti i passaggi per portare un touch **da zero** al kiosk funzionante:
reset di fabbrica → modalità sviluppatore → collegamento del PC via **cavo o WiFi**
→ comandi `adb` per installare il launcher e renderlo **Device Owner**.

> Versione di riferimento: app **v13 / 2.2** · pacchetto `it.bigbenmatic.gamelauncher`.
> Guida gemella più discorsiva: `android/SETUP-TABLET.md`. Versione web (con checklist):
> pagina "Preparazione di un nuovo touch" pubblicata come Artifact.

---

## 1) Cosa ti serve

- Un **PC** (Mac/Windows/Linux) con **Android Platform Tools** (contiene `adb`).
- Un **cavo USB‑C** — *oppure* PC e touch sulla **stessa rete WiFi** (collegamento senza cavo).
- L'**APK del launcher** (per i monitor definitivi usa quello di **release**).

```bash
# installa adb (una volta sola)
# macOS
brew install --cask android-platform-tools
# Windows: scarica "SDK Platform-Tools" da developer.android.com
adb version   # verifica che risponda
```

APK:
```
launcher/apk/launcher-latest.apk
# oppure:
https://kevodable.github.io/Fun-Planet-touch/launcher/apk/launcher-latest.apk
```

> ⚠︎ **Monitor definitivi = APK di release.** Girano sulla chiave di release
> (SHA‑256 `e12c01bb…`): solo così ricevono gli aggiornamenti **OTA**. La keystore
> di release è fuori dal repo e **va backuppata per sempre** (senza, non si possono
> più firmare update). I 2 tablet di test sono su firma *debug* e restano legacy.

## 2) Reset di fabbrica

Parti sempre da un dispositivo **pulito**:
`Impostazioni → Sistema → Opzioni di ripristino → Cancella tutti i dati (ripristino dati di fabbrica)`.

Motivo: il Device Owner si può impostare **solo su un dispositivo senza account**;
il reset è il modo più sicuro per partire senza account e senza residui.

## 3) Prima accensione — NIENTE account Google

1. Scegli la lingua e vai avanti.
2. Quando chiede l'**account Google**, tocca **Salta / Ignora**. *Non* aggiungere account.
3. Puoi connetterti al WiFi (serve solo per gli aggiornamenti di sistema), ma **non fare il login**.
4. Salta impronte/PIN opzionali fino alla Home.

> ⚠︎ **Punto più importante:** se resta anche **un solo account**, il comando
> `set-device-owner` (passo 7) **fallisce**. `Impostazioni → Account` deve essere vuoto.

## 4) Attiva le Opzioni sviluppatore

1. `Impostazioni → Info sul dispositivo`.
2. Tocca **Numero build** **7 volte** di fila.
3. Le **Opzioni sviluppatore** compaiono in `Impostazioni → Sistema`.

## 5) Attiva il debug

In **Opzioni sviluppatore**:
- **Debug USB** — sempre utile (per il cavo, o per avviare il WiFi con il metodo `tcpip`).
- **ADB di rete / Debug wireless** — per collegarti **senza cavo**. Il nome cambia:
  sui **monitor/signage** (anche Android 9/10) è spesso un interruttore *"ADB di rete" /
  "ADB over network"*; su Android **11+** è *"Debug wireless"* con abbinamento a codice.

## 6) Collega il PC al touch

Scegli una strada. Alla fine `adb devices` deve mostrare il dispositivo come **device**
(non `unauthorized`). **L'adb via WiFi funziona su tutte le versioni di Android**
(Android 9 compreso): cambia solo *come* si accende.

**Strada A — via cavo USB (più semplice).** Collega il cavo; sul touch conferma
**"Consenti debug USB?" → Consenti** (spunta "sempre da questo computer").
```bash
adb devices
```

**Strada B — via WiFi.** Tre modi, secondo cosa offre il dispositivo:

1. **Interruttore "ADB di rete / ADB over network"** (comune sui monitor, **anche
   Android 9/10**): attivalo e collegati direttamente, *niente cavo*.
   ```bash
   adb connect 192.168.1.50:5555   # IP da Impostazioni → Info → Stato
   ```
2. **Android 11+ — "Debug wireless" con codice:**
   ```bash
   # sul touch: Debug wireless → "Abbina dispositivo con codice"
   #   → mostra IP:PORTA + un codice a 6 cifre
   adb pair 192.168.1.50:37123     # incolla il codice
   adb connect 192.168.1.50:41579  # porta del Debug wireless (diversa da quella di pairing)
   ```
3. **Nessun toggle di rete — metodo `tcpip`** (vale ovunque, anche Android 9): serve
   il cavo **un solo istante** per dare il via, poi lo stacchi.
   ```bash
   # touch collegato via cavo:
   adb tcpip 5555
   # scollega il cavo, poi (IP da Impostazioni → Info → Stato):
   adb connect 192.168.1.50:5555
   # non conosci l'IP? col cavo attaccato: adb shell ip route
   ```

## 7) Installa il launcher e rendilo Device Owner

```bash
# 1) installa (-r reinstalla senza perdere i dati)
adb install -r launcher-latest.apk

# 2) rendilo Device Owner (attiva il kiosk)
adb shell dpm set-device-owner it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver
```
Risposta attesa:
```
Success: Device owner set to package it.bigbenmatic.gamelauncher
```
Errore *"…there are already some accounts"* → torna al passo 3, svuota
`Impostazioni → Account`, ripeti.

> Quando l'app è Device Owner il **kiosk** (lock task) parte da solo: non serve
> toccare `kiosk.enabled` nel config.

## 8) Imposta il launcher come Home

Apri l'app una volta e scegli **Kids Fun Planet** come Home *predefinita*, oppure:
```bash
adb shell cmd package set-home-activity it.bigbenmatic.gamelauncher/.MainActivity
```

## 9) Verifica finale

```bash
# è Device Owner? (cerca la riga "Device Owner: …gamelauncher…")
adb shell "dumpsys device_policy | grep -i owner"
# versione installata (deve mostrare versionCode=13)
adb shell "dumpsys package it.bigbenmatic.gamelauncher | grep versionCode"
```

> **🪟 Windows:** `grep` non esiste. Tieni il comando **tra virgolette** come sopra (così
> `grep` gira dentro il dispositivo — vale anche su Mac/Linux), **oppure** usa `findstr`:
> `adb shell dumpsys device_policy | findstr /i owner`.
> Nota: `dpm list-owners` non è supportato da tutti gli Android → usa `dumpsys device_policy`.
Sul touch: apri un gioco → si apre a tutto schermo; **🏠 Torna ai giochi** riporta
alla griglia; il tasto Home di sistema è bloccato. ✔︎ Pronto.

> **Consigliato:** in `Impostazioni del launcher → Diagnostica` copia l'**ID dispositivo (UUID)**
> e aggiungilo nel pannello admin (sezione *Dispositivi*) per assegnare **locale e branding**
> (logo, sfondo, nome). Senza mappatura, il touch mostra la configurazione predefinita.

---

## Checklist

- [ ] Reset di fabbrica eseguito
- [ ] Prima accensione **senza** account Google
- [ ] Opzioni sviluppatore attive (7 tap)
- [ ] Debug USB (e/o wireless) attivo
- [ ] PC collegato — `adb devices` mostra "device"
- [ ] APK installato
- [ ] Device Owner impostato ("Success…")
- [ ] Launcher impostato come Home
- [ ] Verifica OK + ID dispositivo registrato nel pannello

## Riferimento comandi

| Comando | Cosa fa |
|---|---|
| `adb devices` | Elenca i dispositivi collegati |
| `adb install -r file.apk` | Installa/aggiorna il launcher |
| `adb shell dpm set-device-owner …/.DeviceOwnerReceiver` | Attiva il kiosk (Device Owner) |
| `adb shell "dumpsys device_policy \| grep -i owner"` | Conferma che è Device Owner (Windows: `findstr /i owner`) |
| `adb tcpip 5555` | Abilita adb via WiFi (via cavo, una volta) |
| `adb connect IP:5555` | Collega via WiFi |
| `adb pair IP:PORTA` | Abbina (Debug wireless, Android 11+) |
| `adb disconnect` | Chiude le connessioni WiFi |
| `adb shell ip route` | Trova l'IP del touch |
| `adb reboot` | Riavvia il dispositivo |

## Smontare = reset di fabbrica

Il Device Owner **non** si toglie disinstallando l'app. Si può tentare con
`adb shell dpm remove-active-admin it.bigbenmatic.gamelauncher/.DeviceOwnerReceiver`,
ma su molte ROM l'unico modo sicuro è un nuovo **ripristino di fabbrica**.

# Firma del launcher — keystore di release

Questo documento spiega come è firmato l'APK del launcher e le regole per non
perdere mai la possibilità di aggiornare la flotta.

## Identità della chiave di release (definitiva)

- **Alias:** `bigbenmatic`
- **Algoritmo:** RSA 4096, validità ~27 anni
- **SHA-256:** `e12c01bbd4943b2916cebe006371575f832375a281f390c7692e861b75f0e19b`
- **SHA-1:** `a4dce5aa191c3f4dde80fe6e06ddfc573290abba`

> Questa impronta è l'identità permanente dell'app sui dispositivi. Tutti gli
> aggiornamenti OTA futuri **devono** essere firmati con questa stessa chiave,
> altrimenti Android li rifiuta.

## Dove vive la keystore (NON nel repo)

Il file `release.keystore` e le password **non sono versionati** (vedi
`.gitignore`). Sono custoditi da Kevin (consegnati a parte, con più backup).

Per buildare una release su una macchina col progetto:

1. Copia la keystore in `android/app/release.keystore`.
2. Crea `android/keystore.properties` partendo da `keystore.properties.example`:
   ```
   storeFile=release.keystore
   storePassword=<password>
   keyAlias=bigbenmatic
   keyPassword=<password>
   ```
3. Builda:
   ```
   cd android
   ./gradlew :app:assembleRelease
   ```
   APK firmato in `android/app/build/outputs/apk/release/app-release.apk`.

Se `keystore.properties` non c'è, la release ricade sulla **firma di debug**
(così la build non fallisce mai in ambienti senza segreti).

## Debug vs release: la regola che conta

Android accetta un aggiornamento **solo se firmato con la stessa chiave** di
quello installato. Debug (`c23a3cc0…`) e release (`e12c01bb…`) sono chiavi
diverse, quindi:

- **Monitor definitivi** → prima installazione (via cavo) con l'**APK di release**.
  Da lì in poi gli OTA con chiave di release funzionano da soli.
- **Passare un device già installato da debug a release** → NON è un semplice
  update: serve disinstallare/reinstallare. Se il device è Device Owner,
  in pratica = **factory reset + provisioning** con l'APK di release.
- I 2 tablet di test attuali sono firmati debug: vanno reinstallati con la
  release quando si allineano ai monitor veri (sono di test, nessun problema).

## Regole d'oro (durabilità)

1. **Backup multipli** del file keystore + password (password manager + copia
   offline). Senza, non si aggiornano più i device firmati con essa.
2. **Mai** committare keystore o password.
3. **Stessa chiave per sempre**, per tutta la vita della flotta.

## Cutover OTA su chiave di release (quando si va in produzione)

Oggi `launcher/apk/launcher-latest.apk` (l'OTA dei tablet di test) è **debug**.
Quando i monitor definitivi saranno su release, l'APK servito da
`config.update.apkUrl` dovrà essere **release**. Strategia consigliata: quando
tutta la flotta in campo è su chiave di release, sostituire
`launcher-latest.apk` con la build di release e proseguire con quella.

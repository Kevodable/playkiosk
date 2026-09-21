# Clienti (multi-tenant)

Ogni cliente/location ha il proprio **manifest** sotto `launcher/clients/<clientId>/`.
Gli stessi monitor (hardware Big Ben in leasing) servono clienti diversi senza duplicare
il codice dei giochi: i giochi restano in `big-ben-giochi/`, ogni cliente sceglie quali
**abilitare** (`visible`) e con quale **branding** mostrarli.

## Come funziona (flusso device)

1. Il launcher genera un **UUID** stabile per device.
2. Scarica il **router** `launcher/fleet.json` e cerca il proprio UUID in `devices`.
   - Se trovato → usa `manifestUrl`/`clientId`/`locationId` di quella voce.
   - Se assente (o router irraggiungibile) → usa `default` = **Big Ben Matic** (cliente zero,
     punta all'attuale `launcher/config.json`). Così i monitor già installati non cambiano nulla.
3. Scarica il manifest risolto (stesso schema di `config.json`) e procede come sempre.
4. `clientId`/`locationId` finiscono nella **telemetria** (filtrabile per cliente).

## Aggiungere un nuovo cliente

1. **Crea la cartella** `launcher/clients/<clientId>/` copiando `ristorante-demo/` come base.
2. **`config.json`**: imposta `branding` (logo, palette, titolo), e per ogni gioco `visible: true/false`
   per definire il sottoinsieme abilitato. `update`/`telemetry` restano uguali a Big Ben
   (stesso APK firmato con la stessa chiave, stesso endpoint Apps Script).
3. **`giochi.json`** (gallery web, opzionale): la versione per browser del sottoinsieme.
4. **Registra i device** in `launcher/fleet.json` → `devices`:
   ```json
   "UUID-DEL-DEVICE": {
     "clientId": "<clientId>",
     "locationId": "<clientId>-sede1",
     "manifestUrl": "https://kevodable.github.io/Fun-Planet-touch/launcher/clients/<clientId>/config.json"
   }
   ```
   L'UUID si legge sul device in **Diagnostica → ID dispositivo**.
5. Pubblica (merge in `great-meitner`).

## Versioning e cache

- `fleet.json` ha il suo `routerVersion`; ogni manifest cliente ha il suo `configVersion`.
- Il launcher riapplica un manifest solo se il suo `configVersion` cambia: **ad ogni modifica
  incrementa `configVersion`** del file cliente toccato.

## Retrocompatibilità / sicurezza

- Finché un device non è elencato in `fleet.json`, vede esattamente la config di Big Ben.
- Se `fleet.json` o il manifest cliente sono irraggiungibili, il launcher usa l'ultima copia
  in cache (offline-first) e, in mancanza, il `config.json` legacy.

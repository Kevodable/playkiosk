/**
 * Ricevitore telemetria per la flotta "Kids Fun Planet".
 *
 * GitHub Pages è statico e NON può ricevere dati POST: questo Google Apps Script
 * fa da endpoint. Riceve i JSON inviati dai monitor (heartbeat e report completi)
 * e li accoda come righe in un Google Sheet, che funge da dashboard consultabile
 * anche da telefono. Gratuito, senza server da mantenere.
 *
 * --- DEPLOY (una tantum) ---
 * 1. Crea un nuovo Google Sheet (es. "Flotta Kids Fun Planet").
 * 2. Menu Estensioni > Apps Script: incolla questo file (Code.gs).
 * 3. Salva. Esegui una volta la funzione `setup` (autorizza i permessi quando richiesto):
 *    crea i fogli "Telemetria" e "StatoDispositivi" con le intestazioni.
 * 4. Pulsante "Esegui distribuzione" > "Nuova distribuzione" > tipo "App web".
 *      - Esegui come: Me stesso
 *      - Chi ha accesso: Chiunque
 *    Copia l'URL che termina con /exec.
 * 5. Incolla quell'URL in config.json -> defaults.telemetry.reportUrl
 *
 * --- ALERT (predisposto, NON attivo) ---
 * La funzione `checkOfflineMonitors` è già pronta ma NON schedulata: quando vorrai
 * gli alert Telegram per "monitor offline da X ore" / crash, imposta un trigger a
 * tempo su questa funzione e completa la chiamata `sendTelegramAlert`.
 */

var SHEET_TELEMETRY = 'Telemetria';
var SHEET_STATUS = 'StatoDispositivi';

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    appendTelemetryRow_(ss, data);
    upsertDeviceStatus_(ss, data);
    return jsonOutput_({ ok: true });
  } catch (err) {
    return jsonOutput_({ ok: false, error: String(err) });
  }
}

function appendTelemetryRow_(ss, data) {
  var sheet = ss.getSheetByName(SHEET_TELEMETRY) || createTelemetrySheet_(ss);
  var topGames = '';
  if (data.topGames && data.topGames.length) {
    topGames = data.topGames.map(function (g) { return g.id + ':' + g.launches; }).join(', ');
  }
  sheet.appendRow([
    new Date(),                       // ricevuto il
    data.type || '',                  // heartbeat | report
    data.deviceId || '',
    data.clientId || '',              // multi-tenant: cliente
    data.locationId || '',            // multi-tenant: location
    data.label || '',
    data.timestamp || '',
    data.appVersion != null ? data.appVersion : '',
    data.configVersion != null ? data.configVersion : '',
    data.batteryPercent != null ? data.batteryPercent : '',
    data.uptimeSeconds != null ? data.uptimeSeconds : '',
    topGames,
  ]);
}

/** Mantiene una riga per dispositivo con l'ultimo stato noto (per la dashboard). */
function upsertDeviceStatus_(ss, data) {
  var sheet = ss.getSheetByName(SHEET_STATUS) || createStatusSheet_(ss);
  var ids = sheet.getRange(2, 1, Math.max(sheet.getLastRow() - 1, 0), 1).getValues();
  var rowIndex = -1;
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === data.deviceId) { rowIndex = i + 2; break; }
  }
  var values = [
    data.deviceId || '',
    data.clientId || '',
    data.locationId || '',
    data.label || '',
    new Date(),
    data.appVersion != null ? data.appVersion : '',
    data.configVersion != null ? data.configVersion : '',
    data.batteryPercent != null ? data.batteryPercent : '',
  ];
  if (rowIndex === -1) {
    sheet.appendRow(values);
  } else {
    sheet.getRange(rowIndex, 1, 1, values.length).setValues([values]);
  }
}

function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName(SHEET_TELEMETRY)) createTelemetrySheet_(ss);
  if (!ss.getSheetByName(SHEET_STATUS)) createStatusSheet_(ss);
}

function createTelemetrySheet_(ss) {
  var sheet = ss.insertSheet(SHEET_TELEMETRY);
  sheet.appendRow([
    'Ricevuto il', 'Tipo', 'Device ID', 'Cliente', 'Location', 'Etichetta', 'Timestamp dispositivo',
    'App version', 'Config version', 'Batteria %', 'Uptime (s)', 'Giochi (id:lanci)',
  ]);
  sheet.setFrozenRows(1);
  return sheet;
}

function createStatusSheet_(ss) {
  var sheet = ss.insertSheet(SHEET_STATUS);
  sheet.appendRow([
    'Device ID', 'Cliente', 'Location', 'Etichetta', 'Ultimo contatto', 'App version', 'Config version', 'Batteria %',
  ]);
  sheet.setFrozenRows(1);
  return sheet;
}

function jsonOutput_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * PREDISPOSTO ma non attivo. Scorre StatoDispositivi e individua i monitor non
 * più visti da oltre `maxHoursOffline` ore. Per attivare gli alert: crea un trigger
 * a tempo su questa funzione e implementa sendTelegramAlert_ con il tuo bot token.
 */
function checkOfflineMonitors() {
  var maxHoursOffline = 3;
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_STATUS);
  if (!sheet || sheet.getLastRow() < 2) return;
  // Colonne: 1=Device ID, 2=Cliente, 3=Location, 4=Etichetta, 5=Ultimo contatto
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, 5).getValues();
  var now = new Date().getTime();
  rows.forEach(function (r) {
    var deviceId = r[0], clientId = r[1], locationId = r[2], label = r[3];
    var lastSeen = r[4] ? new Date(r[4]).getTime() : 0;
    var hours = (now - lastSeen) / 3600000;
    if (hours > maxHoursOffline) {
      var who = (clientId || '?') + (locationId ? '/' + locationId : '') + ' — ' + (label || deviceId);
      // sendTelegramAlert_('Monitor offline: ' + who + ' da ' + Math.round(hours) + 'h');
    }
  });
}

// function sendTelegramAlert_(message) {
//   var token = 'INSERISCI_BOT_TOKEN';
//   var chatId = 'INSERISCI_CHAT_ID';
//   UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
//     method: 'post',
//     payload: { chat_id: chatId, text: message },
//   });
// }

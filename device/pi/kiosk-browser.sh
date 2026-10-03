#!/bin/sh
# Avvio di Chromium in kiosk -> sul Pi: /usr/local/bin/kiosk-browser.sh (chmod 755)
# Lo lancia cage (kiosk.service). Apre la shell servita da Caddy in locale.
# Su Trixie il binario e' "chromium"; "chromium-browser" e' il ripiego per le
# immagini che usano ancora quel nome. Se non c'e' nessuno dei due, errore
# chiaro nel journal invece di un exec a vuoto.
BROWSER=$(command -v chromium || command -v chromium-browser) || {
  echo "kiosk-browser: chromium non trovato" >&2
  exit 1
}
# Modalita' test (kiosk-perf on): la shell si apre con ?perf=1 e si lascia
# pilotare da "kiosk-perf run". Spenta = file assente = kiosk normale.
URL=http://127.0.0.1:8080/
[ -e /srv/kiosk/perf.on ] && URL="$URL?perf=1"
exec "$BROWSER" \
  --kiosk \
  --ozone-platform=wayland \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --overscroll-history-navigation=0 \
  --disable-pinch \
  --password-store=basic \
  --check-for-update-interval=31536000 \
  "$URL"

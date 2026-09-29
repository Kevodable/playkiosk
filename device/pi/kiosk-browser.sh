#!/bin/sh
# Avvio di Chromium in kiosk -> sul Pi: /usr/local/bin/kiosk-browser.sh (chmod 755)
# Lo lancia cage (kiosk.service). Apre la shell servita da Caddy in locale.
set -eu

URL="http://127.0.0.1:8080"

# Su Debian Trixie il pacchetto/binario e' "chromium"; "chromium-browser"
# resta come ripiego per le immagini che usano ancora quel nome.
if command -v chromium >/dev/null 2>&1; then
	BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
	BROWSER=chromium-browser
else
	echo "kiosk-browser: chromium non trovato" >&2
	exit 1
fi

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

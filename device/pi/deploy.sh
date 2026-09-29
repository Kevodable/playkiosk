#!/usr/bin/env bash
# Deploy del kiosk sul Raspberry Pi -> si lancia dal Mac, dalla radice della repo
# o da qualsiasi cartella (trova da solo kiosk/).
#
#   device/pi/deploy.sh [deploy]          nuova release + switch + restart
#   device/pi/deploy.sh list              release sul Pi (* = attiva)
#   device/pi/deploy.sh rollback [nome]   torna alla release precedente (o a "nome")
#
# Host: variabile KIOSK_HOST (utente@host), default il prototipo.
#   KIOSK_HOST=admin@kiosk-042.local device/pi/deploy.sh
# Release da tenere dopo un deploy: KIOSK_KEEP (default 5).
#
# Sul Pi va SOLO il contenuto di kiosk/. Ogni deploy crea
# /srv/kiosk/releases/r-AAAAMMGG-HHMMSS-<commit>, sposta in modo atomico il
# symlink /srv/kiosk/current e riavvia kiosk.service. Le release a mano
# (v0, v1, ...) non vengono mai cancellate.
set -euo pipefail

HOST="${KIOSK_HOST:-kiosk-dev-01@kiosk-dev-01.local}"
KEEP="${KIOSK_KEEP:-5}"
BASE=/srv/kiosk

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO/kiosk"

die() { echo "deploy: $*" >&2; exit 1; }

# Comandi eseguiti sul Pi. $1 = azione, poi argomenti.
remote() {
	ssh "$HOST" sh -s -- "$@" <<'EOF'
set -eu
BASE=/srv/kiosk
REL="$BASE/releases"
cur() { basename "$(readlink "$BASE/current" 2>/dev/null || echo -)"; }
# release create dallo script, in ordine cronologico (il nome e' ordinabile)
auto() { ls -1 "$REL" | grep '^r-[0-9]\{8\}-[0-9]\{6\}-' | sort || true; }
switch() {
	[ -f "$REL/$1/index.html" ] || { echo "manca $REL/$1/index.html" >&2; exit 1; }
	# symlink nuovo + rename: lo switch e' atomico, Caddy non vede mai il vuoto
	ln -sfn "releases/$1" "$BASE/current.new"
	mv -T "$BASE/current.new" "$BASE/current"
	echo "attiva: $1"
}
case "$1" in
check)
	[ -d "$REL" ] && [ -w "$REL" ] || { echo "$REL non esiste o non e' scrivibile" >&2; exit 1; }
	[ -w "$BASE" ] || { echo "$BASE non e' scrivibile (serve per lo switch del symlink)" >&2; exit 1; }
	[ ! -e "$REL/$2" ] || { echo "la release $2 esiste gia'" >&2; exit 1; }
	;;
activate)
	chmod -R a+rX "$REL/$2"
	switch "$2"
	;;
prune)
	keep="$2"; c="$(cur)"
	n="$(auto | wc -l)"
	auto | head -n "$(( n > keep ? n - keep : 0 ))" | while read -r r; do
		[ "$r" = "$c" ] && continue
		rm -rf "${REL:?}/$r" && echo "eliminata: $r"
	done
	;;
list)
	c="$(cur)"
	ls -1 "$REL" | while read -r r; do
		if [ "$r" = "$c" ]; then echo "* $r"; else echo "  $r"; fi
	done
	;;
rollback)
	c="$(cur)"
	if [ -n "${2:-}" ]; then
		target="$2"
	else
		target="$(auto | awk -v c="$c" '$0 == c { print prev; exit } { prev = $0 }')"
		[ -n "$target" ] || { echo "nessuna release precedente a $c: indicala per nome (vedi list)" >&2; exit 1; }
	fi
	[ "$target" != "$c" ] || { echo "$target e' gia' attiva" >&2; exit 1; }
	switch "$target"
	;;
health)
	sleep 2
	curl -fsS -o /dev/null http://127.0.0.1:8080/ \
		&& curl -fsS -o /dev/null http://127.0.0.1:8080/manifest/manifest.json \
		&& echo "Caddy risponde: ok" \
		|| { echo "ATTENZIONE: Caddy non serve la release (rollback: deploy.sh rollback)" >&2; exit 1; }
	;;
*)
	echo "azione sconosciuta: $1" >&2; exit 1
	;;
esac
EOF
}

restart() {
	# -t: se sudo chiede la password, la si digita qui
	ssh -t "$HOST" sudo systemctl restart kiosk.service
	remote health
}

cmd_deploy() {
	[ -f "$SRC/index.html" ] || die "manca $SRC/index.html"
	python3 -m json.tool "$SRC/manifest/manifest.json" >/dev/null || die "manifest.json non valido"
	for c in "$SRC"/tenants/*/config.json; do
		python3 -m json.tool "$c" >/dev/null || die "$c non valido"
	done

	local rev dirty=""
	rev="$(git -C "$REPO" rev-parse --short HEAD)"
	if [ -n "$(git -C "$REPO" status --porcelain -- kiosk)" ]; then
		dirty="-dirty"
		echo "deploy: attenzione, kiosk/ ha modifiche non committate (release marcata -dirty)"
	fi
	local name="r-$(date +%Y%m%d-%H%M%S)-$rev$dirty"

	echo "deploy: $name -> $HOST"
	remote check "$name"
	rsync -rlt --delete --exclude '.DS_Store' "$SRC/" "$HOST:$BASE/releases/$name/"
	remote activate "$name"
	restart
	remote prune "$KEEP"
}

cmd_rollback() {
	remote rollback "${1:-}"
	restart
}

case "${1:-deploy}" in
deploy)   cmd_deploy ;;
list)     remote list ;;
rollback) cmd_rollback "${2:-}" ;;
*)        die "uso: $0 [deploy|list|rollback [nome]]" ;;
esac

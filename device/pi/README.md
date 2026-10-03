# device/pi — configurazione del kiosk Raspberry Pi 5

Fonte di verità versionata dei file di sistema del kiosk. Sul Pi si modificano
**qui** e poi si copiano, mai il contrario. Procedura completa (installazione,
deploy, rollback, diagnostica): [`docs/raspberry-pi-setup.md`](../../docs/raspberry-pi-setup.md).

| File in repo        | Destinazione sul Pi                  | Proprietario / permessi | Dopo la copia                                         |
|---------------------|--------------------------------------|-------------------------|-------------------------------------------------------|
| `Caddyfile`         | `/etc/caddy/Caddyfile`               | root:root 644           | `sudo systemctl reload caddy`                         |
| `kiosk.service`     | `/etc/systemd/system/kiosk.service`  | root:root 644           | `sudo systemctl daemon-reload && sudo systemctl restart kiosk.service` |
| `pam-cage`          | `/etc/pam.d/cage`                    | root:root 644           | effetto al prossimo avvio di `kiosk.service`          |
| `kiosk-browser.sh`  | `/usr/local/bin/kiosk-browser.sh`    | root:root 755           | `sudo systemctl restart kiosk.service`                |
| `kiosk-perf`        | `/usr/local/bin/kiosk-perf`          | root:root 755           | nessuno (misure; vedi doc §4.1)                       |
| `kiosk-health.service` | `/etc/systemd/system/kiosk-health.service` | root:root 644     | `sudo systemctl daemon-reload`                        |
| `kiosk-health.timer`   | `/etc/systemd/system/kiosk-health.timer`   | root:root 644     | `sudo systemctl enable --now kiosk-health.timer`      |
| `deploy.sh`         | **non va sul Pi**: si lancia dal Mac | —                       | `device/pi/deploy.sh [deploy\|list\|rollback [nome]]` |

Installazione di tutti i file (dal Pi, con la cartella `device/pi/` copiata in `~/pi`):

```sh
sudo install -m 644 ~/pi/Caddyfile        /etc/caddy/Caddyfile
sudo install -m 644 ~/pi/kiosk.service    /etc/systemd/system/kiosk.service
sudo install -m 644 ~/pi/pam-cage         /etc/pam.d/cage
sudo install -m 755 ~/pi/kiosk-browser.sh /usr/local/bin/kiosk-browser.sh
sudo install -m 755 ~/pi/kiosk-perf       /usr/local/bin/kiosk-perf
sudo install -m 644 ~/pi/kiosk-health.service ~/pi/kiosk-health.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiosk-health.timer
sudo systemctl reload caddy
sudo systemctl restart kiosk.service
```

## Note

- **Allineati al prototipo** `kiosk-dev-01` (2026-10-03): tutti i file di
  questa cartella sono installati sul Pi (Caddy con `bind 127.0.0.1`,
  `kiosk-browser.sh` con l'interruttore della modalità test, `kiosk-perf`,
  timer `kiosk-health`).
  Confronto: `ssh <admin>@<host> cat /etc/caddy/Caddyfile | diff -I '^ *#' - device/pi/Caddyfile`.
- **Niente segreti** in questa cartella: niente password, chiavi, auth key
  Tailscale, IP. L'accesso SSH (solo chiave) lo imposta cloud-init
  (`/etc/ssh/sshd_config.d/50-cloud-init.conf`), fuori dalla repo.
- Sul Pi va **solo** il contenuto di `kiosk/` (in `/srv/kiosk/releases/vN/`), mai
  la repo: niente `.git`, `CLAUDE.md`, `.claude`, `tools`, `_legacy`, `docs`,
  `device`.

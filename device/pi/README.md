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
| `deploy.sh`         | **non va sul Pi**: si lancia dal Mac | —                       | `device/pi/deploy.sh [deploy\|list\|rollback [nome]]` |

Installazione di tutti i file (dal Pi, con la cartella `device/pi/` copiata in `~/pi`):

```sh
sudo install -m 644 ~/pi/Caddyfile        /etc/caddy/Caddyfile
sudo install -m 644 ~/pi/kiosk.service    /etc/systemd/system/kiosk.service
sudo install -m 644 ~/pi/pam-cage         /etc/pam.d/cage
sudo install -m 755 ~/pi/kiosk-browser.sh /usr/local/bin/kiosk-browser.sh
sudo systemctl daemon-reload
sudo systemctl reload caddy
sudo systemctl restart kiosk.service
```

## Note

- Questi file sono stati **ricostruiti dalla descrizione** del prototipo
  `kiosk-dev-01`, non copiati dal dispositivo. Prima di sovrascrivere, fare un
  confronto con quelli sul Pi, per esempio
  `ssh <admin>@<host> cat /etc/systemd/system/kiosk.service | diff - device/pi/kiosk.service`,
  e riportare qui le differenze buone.
- **Niente segreti** in questa cartella: niente password, chiavi, auth key
  Tailscale, IP. L'accesso SSH (solo chiave) lo imposta cloud-init
  (`/etc/ssh/sshd_config.d/50-cloud-init.conf`), fuori dalla repo.
- Sul Pi va **solo** il contenuto di `kiosk/` (in `/srv/kiosk/releases/vN/`), mai
  la repo: niente `.git`, `CLAUDE.md`, `.claude`, `tools`, `_legacy`, `docs`,
  `device`.

# oc8 – Q-MED-Arbeitsstand

Fork von [oc8-ai/oc8](https://github.com/oc8-ai/oc8), eigene Arbeit auf Branch `qmed`.

## Starten

```bash
colima start                 # Container-Runtime (6 CPU / 8 GB)
cd ~/claude/oc8
./scripts/quickstart.sh      # Modus wählen: 3 = Dev (nur localhost)
```

Danach: <http://localhost> — Dev-Login ohne Passwort (als `org_admin`).

Neustart ohne Quickstart (Dev-Overlay nicht vergessen!):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Sicherheit: nur localhost

In `.env` (gitignored, lokal) muss stehen:

```
OC8_HTTP_PORT=127.0.0.1:80
OC8_HTTPS_PORT=127.0.0.1:443
```

Sonst veröffentlicht Colima Port 80/443 im ganzen LAN, und der Dev-Login braucht kein Passwort.
Nach einem frischen Clone oder wenn `.env` neu erzeugt wurde, diese Zeilen neu setzen.

## Stoppen

```bash
docker compose down          # Container stoppen, Daten (Volumes) bleiben
colima stop                  # VM stoppen
```

## Upstream-Updates holen

```bash
git fetch upstream
git checkout main && git merge --ff-only upstream/main && git push origin main
git checkout qmed && git merge main
```

## Konvention

Eigene Dateien nur unter `qmed/` und `thoughts/`. Upstream-Ordner (`docs/`, `scripts/`, …) nur anfassen, wenn eine Erweiterung es wirklich erfordert.

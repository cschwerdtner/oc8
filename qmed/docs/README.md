# oc8 – Q-MED-Arbeitsstand

Fork von [oc8-ai/oc8](https://github.com/oc8-ai/oc8), eigene Arbeit auf Branch `qmed`.

## Starten

```bash
colima start                 # Container-Runtime (6 CPU / 8 GB)
cd ~/claude/oc8
./scripts/quickstart.sh      # Modus wählen: 3 = Dev (nur localhost)
```

Danach: <http://localhost> — Dev-Login ohne Passwort (als `org_admin`).

Neustart ohne Quickstart — `COMPOSE_FILE` in `.env` lädt Dev-Modus + Q-MED-Overlay automatisch:

```bash
docker compose up -d
```

Nach einem `quickstart.sh`-Lauf einmal `docker compose up -d` hinterher (Quickstart kennt das Overlay nicht).

## LLM: lokales Ollama

Ollama läuft auf dem Mac (nicht im Container), Modell `qwen3:30b-a3b`. Kein Cloud-Key nötig.

```bash
ollama list                  # qwen3:30b-a3b muss da sein
```

Nach `oc8 seed --reset` die ACME-Agents wieder auf Qwen umhängen (Seed schreibt `mistral:latest`):

```bash
docker compose exec -T postgres psql -U oc8_migrate -d oc8 -c "
  UPDATE model_config SET model='qwen3:30b-a3b', display_name='Qwen3 30B-A3B (lokal)' WHERE provider='Ollama';
  UPDATE agent SET model_config_id=(SELECT id FROM model_config WHERE provider='Ollama' LIMIT 1);"
```

## Sicherheit: nur localhost

In `.env` (gitignored, lokal) muss stehen:

```
OC8_HTTP_PORT=127.0.0.1:80
OC8_HTTPS_PORT=127.0.0.1:443
OC8_OLLAMA_BASE_URL=http://host.docker.internal:11434
OC8_DEFAULT_MODEL=qwen3:30b-a3b
COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml:qmed/compose.qmed.yml
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

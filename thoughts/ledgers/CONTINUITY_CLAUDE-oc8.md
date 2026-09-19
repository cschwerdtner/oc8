# CONTINUITY — oc8

## Goal
oc8 (Agent-Orchestrierung, https://oc8.ai, LGPL-3.0) lokal betreiben und für Q-MED gezielt
erweitern, ohne den Anschluss an Upstream zu verlieren.

Fertig für Phase 1, wenn: Fork steht, Stack läuft lokal (Dev-Modus), UI unter localhost
erreichbar, Doku-Grundgerüst committet.

## Constraints
- Fork `cschwerdtner/oc8`; `origin` = Fork, `upstream` = `oc8-ai/oc8`.
- `main` = Spiegel von Upstream (nur `--ff-only`), eigene Arbeit auf Branch `qmed`.
- Eigene Dateien nur unter `qmed/` (Wiki, Tooling) und `thoughts/`. Upstream-`docs/` und
  `scripts/` nicht anfassen → konfliktfreie Merges.
- Laufzeit: Colima (Profil `default`, 6 CPU / 8 GB), kein Docker Desktop installiert.
- Dev-Modus = Login ohne Passwort → **nur localhost**, nie exponieren.
- `.env` enthält generierte Secrets, ist gitignored — nie committen.
- `.env` muss `OC8_HTTP_PORT=127.0.0.1:80` + `OC8_HTTPS_PORT=127.0.0.1:443` enthalten (Colima bindet sonst LAN-weit).
- LGPL: Änderungen an oc8 selbst offenlegen, falls an Dritte verteilt.

## Key Decisions
Siehe Entscheidungs-Log in `qmed/specs/2026-09-19-setup-fork-und-lokaler-betrieb-design.html`.

## State
- Done:
  - [x] Fork + Clone + `upstream`-Remote + Branch `qmed` (2026-09-19)
  - [x] Colima mit 6 CPU / 8 GB gestartet
  - [x] HTML-Doc-Wiki unter `qmed/` (Hook-Pfade angepasst), erste Spec + README
  - [x] Quickstart Dev-Modus: 11 Container laufen, http://localhost → 200
  - [x] Caddy auf 127.0.0.1 gebunden (war im LAN offen!), in `.env`
- Now: [→] Commit auf `qmed`, Push zum Fork
- Next: ARCHITECTURE.md / AGENTS.md lesen, Erweiterungspunkte identifizieren
- Remaining:
  - [ ] Erste Q-MED-Erweiterung planen (`create_plan`)

## Open Questions
- UNCONFIRMED: Welche Erweiterungen konkret? (Christoph: „ich will es sicher erweitern")
- UNCONFIRMED: Später produktiv im Community-Modus, auf welchem Host?

## Working Set
- Repo: `~/claude/oc8`, Branch `qmed`
- Start: `colima start && ./scripts/quickstart.sh`
- Stop: `docker compose down && colima stop`
- Wikis: `qmed/specs/index.html`, `qmed/docs/index.html`

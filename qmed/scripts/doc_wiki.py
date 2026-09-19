"""
doc_wiki.py — Generator für das Doku-Wiki (Markdown → HTML im Q-MED-CI).

Schwester von spec_wiki.py: während das Spec-Wiki handgeschriebene HTML-Specs
indiziert, rendert das Doku-Wiki die Markdown-Quellen unter docs/ in lesbares
HTML. Die .md bleibt die Quelle — sie wird base64-UTF8 in eine HTML-Hülle
(_doc_template.html) eingebettet und beim Öffnen von doc.js mit marked.js
gerendert (file://-tauglich, kein Server, kein pip-Paket nötig).

USAGE:
    python3 scripts/doc_wiki.py build [--config .doc-wiki.json]

Liest .doc-wiki.json (index/templates/assets/categories). Stdlib only.

Was build macht:
  1. Geteilte Assets (logo.png, spec.css) aus dem Spec-Wiki synchronisieren.
  2. Pro konfigurierter .md eine .html neben der Quelle generieren.
  3. docs/index.html aus index.template.html generieren (Kacheln nach Bereich).
"""
import argparse
import base64
import html as _html
import json
import os
import re
import shutil
import subprocess
from datetime import date as _date
from pathlib import Path


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve(repo_root, rel):
    return Path(repo_root) / rel


# --------------------------------------------------------------------------- #
# Quell-Discovery: aus categories[] die Liste der .md-Dateien (in Reihenfolge)
# --------------------------------------------------------------------------- #
def collect_sources(cfg, repo_root):
    """-> [(category_name, [abs Path, ... in stabiler Reihenfolge]), ...]."""
    out = []
    seen = set()
    for cat in cfg["categories"]:
        name = cat["name"]
        files = []
        # Explizite Datei-Liste (Reihenfolge wie angegeben)
        for rel in cat.get("files", []):
            p = _resolve(repo_root, rel)
            if p.exists() and p.suffix == ".md" and p not in seen:
                files.append(p); seen.add(p)
        # Scan-Verzeichnisse (rekursiv, natürlich sortiert nach Pfad)
        for d in cat.get("scan", []):
            base = _resolve(repo_root, d)
            if not base.exists():
                continue
            for p in sorted(base.rglob("*.md"), key=lambda x: _natural_key(x.as_posix())):
                if p not in seen:
                    files.append(p); seen.add(p)
        out.append((name, files))
    return out


def _natural_key(s):
    """Natürliche Sortierung: '02_x' vor '10_x'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# --------------------------------------------------------------------------- #
# Titel + Beschreibung aus Markdown ziehen
# --------------------------------------------------------------------------- #
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def extract_title_desc(md_text, fallback_name):
    lines = md_text.splitlines()
    title = None
    i = 0
    n = len(lines)
    # 1. Titel = erste H1/H2-Zeile (überspringe HTML-Kommentare/Frontmatter)
    while i < n:
        line = lines[i].strip()
        m = re.match(r"^#{1,2}\s+(.*)", line)
        if m:
            title = _strip_md_inline(m.group(1))
            i += 1
            break
        i += 1
    if not title:
        title = _humanize(fallback_name)
        i = 0  # ohne Titelzeile: Beschreibung von Anfang an suchen

    # 2. Beschreibung = erster Prosa-Absatz nach dem Titel
    desc_parts = []
    while i < n:
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            if desc_parts:
                break          # Absatz-Ende
            continue
        if _FENCE_RE.match(line):  # Code-Fence komplett überspringen
            while i < n and not _FENCE_RE.match(lines[i].strip()):
                i += 1
            i += 1
            continue
        # Block-Marker, die kein Prosa-Absatz sind → überspringen, weitersuchen
        if re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>|<!--|!\[|\[!|---|===|\*\*\*)", line):
            if desc_parts:
                break
            continue
        desc_parts.append(_strip_md_inline(line))

    desc = " ".join(desc_parts).strip()
    desc = re.sub(r"\s+", " ", desc)
    if len(desc) > 200:
        desc = desc[:197].rstrip() + "…"
    return title, desc


def _strip_md_inline(s):
    """Markdown-Inline-Auszeichnung für Klartext (Kachel) entfernen."""
    s = re.sub(r"`([^`]*)`", r"\1", s)                     # `code`
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)               # **bold**
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", s)      # *italic*
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)         # [text](url)
    s = re.sub(r"[_~]", "", s)
    return s.strip()


def _humanize(name):
    name = re.sub(r"\.md$", "", name)
    name = re.sub(r"^\d+[_-]", "", name)
    return name.replace("_", " ").replace("-", " ").strip().capitalize()


# --------------------------------------------------------------------------- #
# Git-Datum pro Datei (Aktualität für Sortierung)
# --------------------------------------------------------------------------- #
def git_file_date(repo_root, path):
    """(YYYY-MM-DD, unix_ts) des letzten Commits der Datei; Fallback Datei-mtime."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs %ct", "--", str(path)],
            cwd=str(repo_root), capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            cs, _, ct = out.partition(" ")
            return cs, int(ct or 0)
    except Exception:
        pass
    try:
        ts = int(path.stat().st_mtime)
        return _date.fromtimestamp(ts).isoformat(), ts
    except OSError:
        return "", 0


def git_short_hash(repo_root):
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "nogit"


# --------------------------------------------------------------------------- #
# Rendern: Einzelseite + Index-Kacheln
# --------------------------------------------------------------------------- #
def _fill(template, mapping):
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def render_page(template, *, title, desc, path, category, key, back, assets,
                md_b64, stamp, project):
    return _fill(template, {
        "project": _html.escape(project),
        "title": _html.escape(title),
        "desc": _html.escape(desc) or "&nbsp;",
        "path": _html.escape(path),
        "category": _html.escape(category),
        "key": _html.escape(key),
        "back": back,
        "assets": assets,
        "md_b64": md_b64,
        "stamp": _html.escape(stamp),
    })


def render_tile(item):
    esc = _html.escape
    datum = esc(item.get("datum", "") or "")
    modul = esc(item.get("category", "") or "")
    titel = esc(item.get("title", ""))
    desc = esc(item.get("desc", "")) or "&nbsp;"
    mtime = int(item.get("mtime", 0) or 0)
    date_chip = f'\n      <span class="badge date" title="Zuletzt geändert">{datum}</span>' if datum else ""
    modul_chip = f'\n      <span class="badge modul" title="Bereich">{modul}</span>' if modul else ""
    return (
        f'<a class="spec-tile" href="{esc(item["href"])}"'
        f' data-datum="{datum}" data-mtime="{mtime}" data-modul="{modul}" data-titel="{titel.lower()}">\n'
        f'  <div class="tile-head">\n'
        f'    <span class="tile-title">{titel}</span>\n'
        f'    <span class="tile-chips">{date_chip}{modul_chip}\n'
        f'    </span>\n'
        f'  </div>\n'
        f'  <div class="tile-desc">{desc}</div>\n'
        f'  <div class="tile-foot"><code>{esc(item["path"])}</code></div>\n'
        f'</a>'
    )


def render_grid(groups):
    parts = []
    for name, items in groups:
        if not items:
            continue
        tiles = "\n".join(render_tile(it) for it in items)
        parts.append(
            f'<div class="module-group">\n'
            f'  <h3>{_html.escape(name)}</h3>\n'
            f'  <div class="specs-grid">\n{tiles}\n  </div>\n'
            f'</div>'
        )
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def sync_shared_assets(cfg, repo_root):
    src = cfg.get("shared_assets_src")
    if not src:
        return
    src_dir = _resolve(repo_root, src)
    dst_dir = _resolve(repo_root, cfg["assets"])
    dst_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("logo.png", "spec.css"):
        s = src_dir / fname
        if s.exists():
            shutil.copy2(s, dst_dir / fname)


def cmd_build(config_path, repo_root="."):
    cfg = load_config(config_path)
    repo_root = Path(repo_root)
    index_path = _resolve(repo_root, cfg["index"])
    assets_dir = _resolve(repo_root, cfg["assets"])
    page_tpl = _resolve(repo_root, cfg["page_template"]).read_text(encoding="utf-8")
    index_tpl = _resolve(repo_root, cfg["index_template"]).read_text(encoding="utf-8")

    sync_shared_assets(cfg, repo_root)

    sources = collect_sources(cfg, repo_root)
    groups = []
    total = 0
    for category, files in sources:
        items = []
        for src in files:
            md_text = src.read_text(encoding="utf-8")
            title, desc = extract_title_desc(md_text, src.name)
            datum, mtime = git_file_date(repo_root, src)
            html_path = src.with_suffix(".html")
            rel_src = src.relative_to(repo_root).as_posix()

            assets_rel = os.path.relpath(assets_dir, html_path.parent).replace(os.sep, "/")
            back_rel = os.path.relpath(index_path, html_path.parent).replace(os.sep, "/")
            md_b64 = base64.b64encode(md_text.encode("utf-8")).decode("ascii")

            page_html = render_page(
                page_tpl, title=title, desc=desc, path=rel_src, category=category,
                key=src.stem, back=back_rel, assets=assets_rel, md_b64=md_b64,
                stamp=f"{datum}" if datum else "neu",
                project=cfg.get("project", "Projekt"),
            )
            html_path.write_text(page_html, encoding="utf-8")
            total += 1

            items.append({
                "title": title, "desc": desc, "category": category,
                "datum": datum, "mtime": mtime,
                "href": os.path.relpath(html_path, index_path.parent).replace(os.sep, "/"),
                "path": rel_src,
            })
        groups.append((category, items))

    grid = render_grid(groups)
    html_out = index_tpl.replace("{{docs_grid}}", grid)
    html_out = html_out.replace("{{generated}}", _date.today().isoformat())
    html_out = html_out.replace("{{spec_index_href}}", cfg.get("spec_index_href", "#"))
    html_out = html_out.replace("{{project}}", cfg.get("project", "Projekt"))
    index_path.write_text(html_out, encoding="utf-8")
    print(f"[doc-wiki] {total} Seiten generiert, Index: {index_path.relative_to(repo_root)}")
    return index_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Doku-Wiki Generator (Markdown → HTML)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("build")
    p_b.add_argument("--config", default=".doc-wiki.json")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        cmd_build(args.config)


if __name__ == "__main__":
    main()

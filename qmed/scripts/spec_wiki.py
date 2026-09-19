"""
spec_wiki.py — Generator/Stamper/Migrator für das lebendige HTML-Spec-Wiki.

USAGE:
    python3 scripts/spec_wiki.py build-index [--config .spec-wiki.json]
    python3 scripts/spec_wiki.py stamp <file.html> [<file.html> ...] [--config ...]
    python3 scripts/spec_wiki.py migrate [--config ...] [--from-index <index.html>]

Liest .spec-wiki.json (index/scan/assets/module_order). Stdlib only.
"""
import json
import re

_META_RE = re.compile(
    r'<script[^>]*id=["\']spec-meta["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

def parse_spec_meta(html_text):
    """Extrahiert den #spec-meta JSON-Block. None, wenn nicht vorhanden/ungültig."""
    m = _META_RE.search(html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None


from pathlib import Path

import os

def rel_assets(spec_path, assets_dir):
    """Relativer POSIX-Pfad vom Spec-Verzeichnis zum Assets-Verzeichnis."""
    rel = os.path.relpath(Path(assets_dir), Path(spec_path).parent)
    return Path(rel).as_posix()


def load_config(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))

def find_specs(scan_dirs):
    """Alle *.html unter den scan_dirs, ohne index.html, _template.html, assets/."""
    out = []
    for d in scan_dirs:
        d = Path(d)
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.html")):
            if p.name in ("index.html", "_template.html"):
                continue
            if "assets" in p.parts:
                continue
            out.append(p)
    return out


import html as _html

_STAMP_RE = re.compile(r"<!--STAMP-->.*?<!--/STAMP-->", re.DOTALL)


def _module_from_h3(h3_inner: str) -> str:
    """Extrahiert den sauberen Modul-Namen aus dem Inneren eines <h3>-Tags.
    Entfernt Badge-Spans, restliche Tags, dekodiert HTML-Entities und normalisiert Whitespace."""
    s = re.sub(r"<span\b[^>]*>.*?</span>", "", h3_inner, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def stamp_text(text, date, short_hash):
    """Ersetzt den Inhalt zwischen <!--STAMP--> und <!--/STAMP-->. Idempotent.
    Operiert rein als String-Replace -> vorhandene CRLF bleiben unangetastet."""
    repl = f"<!--STAMP-->Stand: {date} · {short_hash}<!--/STAMP-->"
    if _STAMP_RE.search(text):
        return _STAMP_RE.sub(lambda _: repl, text)
    return text  # kein Marker -> nichts tun (Stamp ist opt-in via Marker im Template)

_STATUS_BADGE = {  # Status -> Badge-Klasse (siehe spec.css)
    "freigegeben": "warn", "umgesetzt": "good", "implementiert": "good",
    "aktuell": "good", "offen": "", "zur review": "", "lebend": "", "doku": "",
}

def _badge_class(status):
    return _STATUS_BADGE.get((status or "").lower(), "")

def render_tile(item):
    esc = _html.escape
    cls = _badge_class(item.get("status"))
    foot = esc(item.get("footnote", "")) or "&nbsp;"
    datum = esc(item.get("datum", "") or "")
    modul = esc(item.get("modul", "") or "")
    titel = esc(item.get("titel", ""))
    mtime = int(item.get("_mtime", 0) or 0)
    # data-Attribute: vom Sort-Skript in spec.js gelesen. data-mtime (Datei-
    # Mtime, Epoch) ist der Tie-Break bei gleichem Datum -> zuletzt bearbeitete
    # Spec steht im "Neueste"-Modus oben (gleichtägige Specs sonst nur alphabetisch).
    date_chip = f'\n      <span class="badge date" title="Datum">{datum}</span>' if datum else ""
    modul_chip = f'\n      <span class="badge modul" title="Modul">{modul}</span>' if modul else ""
    return (
        f'<a class="spec-tile" href="{esc(item["_href"])}"'
        f' data-datum="{datum}" data-mtime="{mtime}" data-modul="{modul}" data-titel="{titel.lower()}">\n'
        f'  <div class="tile-head">\n'
        f'    <span class="tile-title">{titel}</span>\n'
        f'    <span class="tile-chips">\n'
        f'      <span class="{("badge " + cls).strip()}">{esc(item.get("status",""))}</span>'
        f'{date_chip}'
        f'{modul_chip}\n'
        f'    </span>\n'
        f'  </div>\n'
        f'  <div class="tile-desc">{esc(item.get("beschreibung",""))}</div>\n'
        f'  <div class="tile-foot"><code>{esc(item["_path"])}</code>'
        f'<span>·</span><span>{foot}</span></div>\n'
        f'</a>'
    )

def render_grid(groups):
    parts = []
    for modul, specs in groups:
        tiles = "\n".join(render_tile(s) for s in specs)
        parts.append(
            f'<div class="module-group">\n'
            f'  <h3>{_html.escape(modul)}</h3>\n'
            f'  <div class="specs-grid">\n{tiles}\n  </div>\n'
            f'</div>'
        )
    return "\n".join(parts)


def group_specs(items, module_order):
    """-> [(modul, [items nach datum desc]), ...]. Bekannte Module zuerst (module_order),
    unbekannte alphabetisch hinten."""
    by_mod = {}
    for it in items:
        by_mod.setdefault(it.get("modul", "Sonstige"), []).append(it)
    known = [m for m in module_order if m in by_mod]
    rest = sorted(m for m in by_mod if m not in module_order)
    result = []
    for mod in known + rest:
        specs = sorted(by_mod[mod],
                       key=lambda s: (s.get("datum", ""), s.get("_mtime", 0)),
                       reverse=True)
        result.append((mod, specs))
    return result


import subprocess
from datetime import date as _date

def git_short_hash(repo_root):
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(repo_root), capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "nogit"

def _resolve(repo_root, rel):
    return Path(repo_root) / rel

def cmd_build_index(config_path, repo_root="."):
    cfg = load_config(config_path)
    repo_root = Path(repo_root)
    scan = [_resolve(repo_root, s) for s in cfg["scan"]]
    assets_dir = _resolve(repo_root, cfg["assets"])
    index_path = _resolve(repo_root, cfg["index"])
    items = []
    for sp in find_specs(scan):
        meta = parse_spec_meta(sp.read_text(encoding="utf-8"))
        if not meta:
            print(f"[build-index] skip (kein #spec-meta): {sp.name}")
            continue
        meta = dict(meta)
        meta["_href"] = os.path.relpath(sp, index_path.parent).replace(os.sep, "/")
        meta["_path"] = sp.relative_to(repo_root).as_posix()
        try:
            meta["_mtime"] = int(sp.stat().st_mtime)
        except OSError:
            meta["_mtime"] = 0
        items.append(meta)
    groups = group_specs(items, cfg.get("module_order", []))
    grid = render_grid(groups)
    template = (assets_dir / "index.template.html").read_text(encoding="utf-8")
    html_out = template.replace("{{specs_grid}}", grid)
    html_out = html_out.replace("{{generated}}", _date.today().isoformat())
    html_out = html_out.replace("{{doc_index_href}}", cfg.get("doc_index_href", "#"))
    html_out = html_out.replace("{{project}}", cfg.get("project", "Projekt"))
    html_out = html_out.replace("{{index_path}}", cfg.get("index", ""))
    index_path.write_text(html_out, encoding="utf-8")
    return index_path

def cmd_stamp(files, repo_root="."):
    sh = git_short_hash(repo_root)
    today = _date.today().isoformat()
    for f in files:
        p = Path(f)
        text = p.read_text(encoding="utf-8")
        p.write_text(stamp_text(text, today, sh), encoding="utf-8")


_TILE_RE = re.compile(
    r'<a class="spec-tile" href="(?P<href>[^"]+)">.*?'
    r'<span class="tile-title">(?P<titel>.*?)</span>.*?'
    r'<span class="badge[^"]*">(?P<badge>.*?)</span>.*?'
    r'<div class="tile-desc">(?P<desc>.*?)</div>.*?'
    r'<code>(?P<path>[^<]+)</code>(?:.*?<span>·</span><span>(?P<foot>.*?)</span>)?',
    re.DOTALL,
)

def _clean_text(s):
    """Tags entfernen, HTML-Entities entschärfen, Whitespace normalisieren.
    Verhindert, dass doppelt-escapte Entities (z. B. &amp;amp;) oder Badge-Markup
    im generierten Index landen. NBSP (&nbsp;) wird zu leerem String normalisiert."""
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()

def _split_badge(badge):
    """'freigegeben · 2026-05-13' -> ('freigegeben', '2026-05-13')."""
    txt = _clean_text(badge)
    if "·" in txt:
        status, _, datum = txt.partition("·")
        m = re.search(r"\d{4}-\d{2}-\d{2}", datum)
        return status.strip(), (m.group(0) if m else "")
    return txt, ""

def parse_index_tiles(index_html, modul=None):
    out = []
    for m in _TILE_RE.finditer(index_html):
        status, datum = _split_badge(m.group("badge"))
        out.append({
            "titel": _clean_text(m.group("titel")),
            "status": status, "datum": datum, "modul": modul or "Sonstige",
            "beschreibung": _clean_text(m.group("desc")),
            "footnote": _clean_text(m.group("foot")),
            "_href": m.group("href"), "_path": m.group("path").strip(),
        })
    return out

def inject_meta_and_assets(html_text, meta, assets_rel):
    meta_block = (
        '<script type="application/json" id="spec-meta">\n'
        + json.dumps({k: meta[k] for k in
                      ("titel","modul","status","datum","beschreibung") if k in meta}
                     | ({"footnote": meta["footnote"]} if meta.get("footnote") else {}),
                     ensure_ascii=False, indent=2)
        + '\n</script>'
    )
    link = f'<link rel="stylesheet" href="{assets_rel}/spec.css" />'
    out = re.sub(r"<style>.*?</style>", link, html_text, count=1, flags=re.DOTALL)
    out = re.sub(r"<script>.*?</script>",
                 f'<script src="{assets_rel}/spec.js" defer></script>',
                 out, count=1, flags=re.DOTALL)
    if 'id="spec-meta"' not in out:
        out = out.replace("</head>", meta_block + "\n</head>", 1)
    return out

_BACKLINK = '<a class="back" href="index.html">← Spec-Wiki</a>'

def cmd_migrate(config_path, from_index=None, repo_root="."):
    cfg = load_config(config_path)
    repo_root = Path(repo_root)
    index_path = _resolve(repo_root, from_index or cfg["index"])
    assets_dir = _resolve(repo_root, cfg["assets"])
    index_html = index_path.read_text(encoding="utf-8")
    # Modul-Kontext: pro <h3>-Block die folgenden Tiles diesem Modul zuordnen
    meta_by_path = {}
    for block in re.split(r'<div class="module-group">', index_html)[1:]:
        h3 = re.search(r"<h3>(.*?)</h3>", block, re.DOTALL)
        modul = _module_from_h3(h3.group(1)) if h3 else "Sonstige"
        for t in parse_index_tiles(block, modul=modul):
            meta_by_path[t["_path"]] = t
    skipped = []
    for sp in find_specs([_resolve(repo_root, s) for s in cfg["scan"]]):
        rel = sp.relative_to(repo_root).as_posix()
        meta = meta_by_path.get(rel)
        if not meta:
            skipped.append(rel); continue
        html_text = sp.read_text(encoding="utf-8")
        out = inject_meta_and_assets(html_text, meta, rel_assets(sp, assets_dir))
        if _BACKLINK not in out:  # Back-Link nach <body ...> einfügen, falls Header existiert
            out = re.sub(r'(<header class="page">\s*<div class="inner">)',
                         r'\1\n    ' + _BACKLINK, out, count=1)
        sp.write_text(out, encoding="utf-8")
    if skipped:
        print("[migrate] ohne Index-Eintrag (manuell prüfen):")
        for s in skipped: print("   ", s)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Spec-Wiki Generator/Stamper/Migrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_idx = sub.add_parser("build-index"); p_idx.add_argument("--config", default=".spec-wiki.json")
    p_st = sub.add_parser("stamp"); p_st.add_argument("files", nargs="+"); p_st.add_argument("--config", default=".spec-wiki.json")
    p_mig = sub.add_parser("migrate"); p_mig.add_argument("--config", default=".spec-wiki.json"); p_mig.add_argument("--from-index", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "build-index":
        cmd_build_index(args.config)
    elif args.cmd == "stamp":
        cmd_stamp(args.files)
    elif args.cmd == "migrate":
        cmd_migrate(args.config, args.from_index)  # Task 12

if __name__ == "__main__":
    main()

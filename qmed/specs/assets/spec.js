// spec.js — geteiltes Script für das lebendige HTML-Spec-Wiki
// Quelle: extrahiert aus 2026-05-22-lebendiges-html-spec-wiki-design.html
// KEY wird dynamisch aus <body data-spec-key> oder dem Dateinamen abgeleitet.
(function () {
  const KEY = (document.body.getAttribute("data-spec-key")
               || location.pathname.split("/").pop() || "spec") + ":v1";
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; } };
  const save = (s) => localStorage.setItem(KEY, JSON.stringify(s));
  const state = load();
  state.checks = state.checks || {};

  // Notiz-Drawer-Felder (Freitext + Einreich-Formular)
  document.querySelectorAll(".note-drawer [data-k]").forEach((el) => {
    const k = el.getAttribute("data-k");
    if (state[k] != null) el.value = state[k];
    el.addEventListener("input", () => { state[k] = el.value; save(state); });
  });

  // Entscheidungs-Checkboxen (persönlicher „gesichtet"-Marker)
  document.querySelectorAll("li.decision").forEach((li) => {
    const id = li.getAttribute("data-d");
    const box = li.querySelector(".d-check");
    if (!id || !box) return;
    box.checked = !!state.checks[id];
    li.classList.toggle("checked", box.checked);
    box.addEventListener("change", () => {
      state.checks[id] = box.checked;
      li.classList.toggle("checked", box.checked);
      save(state);
    });
  });

  // Drawer auf/zu (nicht-modal: Lesen bleibt möglich)
  const fab = document.getElementById("note-fab");
  const drawer = document.getElementById("note-drawer");
  const closeBtn = document.getElementById("note-close");
  const setOpen = (v) => {
    drawer.classList.toggle("open", v);
    fab.setAttribute("aria-expanded", String(v));
    drawer.setAttribute("aria-hidden", String(!v));
    if (v) drawer.querySelector("textarea")?.focus();
  };
  fab?.addEventListener("click", () => setOpen(!drawer.classList.contains("open")));
  closeBtn?.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });

  // Entscheidung → Markdown
  const btn = document.getElementById("copy-decision");
  const fb = document.getElementById("copy-feedback");
  btn?.addEventListener("click", async () => {
    const title = (state["d-title"] || "").trim();
    const why = (state["d-why"] || "").trim();
    if (!title) { fb.textContent = "  Titel fehlt"; return; }
    const today = new Date().toISOString().slice(0, 10);
    const md = `- **${today} · ${title}** — ${why || "(Begründung ergänzen)"} (Quelle: Browser-Notiz)`;
    try { await navigator.clipboard.writeText(md); fb.textContent = "  kopiert ✓"; }
    catch { fb.textContent = "  " + md; }
  });

  // Q-MED-Logo zentral in den Seiten-Header injizieren (Index + alle Specs).
  // Pfad wird aus dem eigenen <script src> abgeleitet, funktioniert daher auch
  // für Specs in Modul-Unterordnern (../specs/assets/spec.js → ../specs/assets/logo.png).
  const headerInner = document.querySelector("header.page .inner");
  const ownScript = document.querySelector('script[src$="spec.js"]');
  if (headerInner && ownScript && !headerInner.querySelector(".brand-logo")) {
    const logoSrc = ownScript.getAttribute("src").replace(/spec\.js$/, "logo.png");
    const wrap = document.createElement("div");
    wrap.className = "brand-logo";
    const img = document.createElement("img");
    img.src = logoSrc;
    img.alt = "Q-MED";
    wrap.appendChild(img);
    headerInner.prepend(wrap);
  }

  // Spec-Wiki-Index: Sortier-Toolbar (Nach Modul / Neueste / Älteste).
  // Default ist die generierte Modul-Gruppierung. Im Datum-Modus werden alle
  // Tiles in einen flachen Grid umgehängt und die <h3>-Modul-Header ausgeblendet.
  const sortBar = document.getElementById("spec-sort");
  const sortHost = document.querySelector(".modules-host");
  if (sortBar && sortHost) {
    const SORT_KEY = "spec-wiki:sort:v1";
    const moduleGroups = Array.from(sortHost.querySelectorAll(".module-group"));
    // Originaler DOM-Anker pro Tile merken, damit Restore deterministisch ist.
    const originals = Array.from(sortHost.querySelectorAll(".spec-tile")).map((tile) => ({
      tile, parent: tile.parentElement, nextSibling: tile.nextElementSibling,
    }));
    const flatGrid = document.createElement("div");
    flatGrid.className = "specs-grid specs-grid-flat";
    flatGrid.hidden = true;
    sortHost.appendChild(flatGrid);

    const applySort = (mode) => {
      if (mode === "module") {
        originals.forEach(({ tile, parent, nextSibling }) => {
          // nextSibling kann durch vorherigen Flat-Sort kein Kind mehr von parent
          // sein (es wurde selbst in flatGrid verschoben). insertBefore(x, null)
          // = appendChild(x), also fallback-safe.
          const anchor = nextSibling && nextSibling.parentNode === parent ? nextSibling : null;
          parent.insertBefore(tile, anchor);
        });
        flatGrid.hidden = true;
        moduleGroups.forEach((g) => { g.hidden = false; });
      } else {
        const tiles = originals.map((o) => o.tile).slice();
        tiles.sort((a, b) => {
          const da = a.dataset.datum || "";
          const db = b.dataset.datum || "";
          if (da === db) {
            // Tie-Break bei gleichem Datum: Datei-Mtime (zuletzt bearbeitet
            // zuerst im Neueste-Modus), erst danach Titel alphabetisch.
            const ma = +(a.dataset.mtime || 0), mb = +(b.dataset.mtime || 0);
            if (ma !== mb) return mode === "datum-desc" ? mb - ma : ma - mb;
            return (a.dataset.titel || "").localeCompare(b.dataset.titel || "");
          }
          return mode === "datum-desc" ? db.localeCompare(da) : da.localeCompare(db);
        });
        tiles.forEach((t) => flatGrid.appendChild(t));
        moduleGroups.forEach((g) => { g.hidden = true; });
        flatGrid.hidden = false;
      }
      sortBar.querySelectorAll("button[data-sort]").forEach((b) => {
        b.setAttribute("aria-pressed", b.dataset.sort === mode ? "true" : "false");
      });
      try { localStorage.setItem(SORT_KEY, mode); } catch { /* private mode */ }
    };

    sortBar.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-sort]");
      if (btn) applySort(btn.dataset.sort);
    });

    let saved = "module";
    try { saved = localStorage.getItem(SORT_KEY) || "module"; } catch { /* ignore */ }
    if (!["module", "datum-desc", "datum-asc"].includes(saved)) saved = "module";
    applySort(saved);
  }
})();

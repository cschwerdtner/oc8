// doc.js — das eine Script fürs Doku-Wiki.
// Drei Aufgaben, je nach Seite:
//   1. Q-MED-Logo in den Header injizieren (immer, wie spec.js)
//   2. Doku-Einzelseite: eingebettetes Markdown (#doc-source, base64) rendern
//   3. Doku-Index: Sortier-Toolbar (Nach Modul / Neueste / Älteste) — aus spec.js
(function () {
  "use strict";

  // ---------- 1. Q-MED-Logo zentral injizieren ----------
  // Pfad aus dem eigenen <script src> ableiten → funktioniert in jedem Unterordner.
  (function injectLogo() {
    const headerInner = document.querySelector("header.page .inner");
    const ownScript = document.querySelector('script[src$="doc.js"]');
    if (!headerInner || !ownScript || headerInner.querySelector(".brand-logo")) return;
    const logoSrc = ownScript.getAttribute("src").replace(/doc\.js$/, "logo.png");
    const wrap = document.createElement("div");
    wrap.className = "brand-logo";
    const img = document.createElement("img");
    img.src = logoSrc;
    img.alt = "Q-MED";
    wrap.appendChild(img);
    headerInner.prepend(wrap);
  })();

  // ---------- 2. Markdown-Einzelseite rendern ----------
  (function renderDoc() {
    const src = document.getElementById("doc-source");
    const target = document.getElementById("doc-content");
    if (!src || !target) return;

    // Markdown ist base64-UTF8-eingebettet (robust gegen </script>, Unicode).
    let md = "";
    try {
      const b64 = src.textContent.trim();
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      md = new TextDecoder("utf-8").decode(bytes);
    } catch (e) {
      target.innerHTML = '<p class="empty">Markdown-Quelle konnte nicht dekodiert werden.</p>';
      return;
    }

    if (typeof marked === "undefined") {
      target.textContent = md; // Fallback: roher Text, falls marked nicht lud
      return;
    }
    marked.setOptions({ gfm: true, breaks: false, headerIds: true, mangle: false });
    target.innerHTML = marked.parse(md);

    // 2a. Interne .md-Links auf die generierten .html umbiegen (Anchor/Query erhalten).
    target.querySelectorAll("a[href]").forEach((a) => {
      const h = a.getAttribute("href") || "";
      if (/^(https?:|mailto:|#|\/\/)/i.test(h)) return;
      a.setAttribute("href", h.replace(/\.md(#.*)?(\?.*)?$/i, ".html$1$2"));
    });

    // 2b. Syntax-Highlighting.
    if (typeof hljs !== "undefined") {
      target.querySelectorAll("pre code").forEach((block) => {
        try { hljs.highlightElement(block); } catch (e) { /* unbekannte Sprache → roh lassen */ }
      });
    }

    // 2c. Klickbare Anker an Überschriften (Deep-Links).
    target.querySelectorAll("h2[id], h3[id]").forEach((h) => {
      h.style.cursor = "pointer";
      h.title = "Link zu diesem Abschnitt kopieren";
      h.addEventListener("click", () => {
        const url = location.href.split("#")[0] + "#" + h.id;
        history.replaceState(null, "", "#" + h.id);
        if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {});
      });
    });

    // 2d. Wenn die Seite mit einem #anchor geöffnet wurde, dorthin scrollen
    // (nach dem Render, da die Ziel-IDs erst jetzt existieren).
    if (location.hash) {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) el.scrollIntoView();
    }
  })();

  // ---------- 3. Doku-Index: Sortier-Toolbar (1:1 aus spec.js) ----------
  (function indexSort() {
    const sortBar = document.getElementById("spec-sort");
    const sortHost = document.querySelector(".modules-host");
    if (!sortBar || !sortHost) return;

    const SORT_KEY = "doc-wiki:sort:v1";
    const moduleGroups = Array.from(sortHost.querySelectorAll(".module-group"));
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
  })();
})();

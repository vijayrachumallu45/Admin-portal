(function () {
  const table = document.querySelector(".knowledge_articles-table");
  if (!table) {
    return;
  }
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  rows.forEach(function (row, index) {
    row.setAttribute("data-knowledge_articles-index", String(index));
  });
  document.querySelectorAll(".knowledge_articles-table tbody tr").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const link = row.querySelector("a");
      if (link) {
        window.location.href = link.getAttribute("href");
      }
    });
  });
  const hero = document.querySelector(".knowledge_articles-hero");
  if (hero) {
    hero.classList.add("is-ready");
  }
  window.NexusModules = window.NexusModules || {};
  window.NexusModules['knowledge_articles'] = {
    title: 'Knowledge Base',
    rowCount: rows.length,
    accent: '#38bdf8',
    markAttention: function () {
      rows.forEach(function (row) {
        const text = row.textContent || "";
        if (text.indexOf("suspended") >= 0 || text.indexOf("failed") >= 0) {
          row.classList.add("is-hot");
        }
      });
    }
  };
  window.NexusModules['knowledge_articles'].markAttention();
})();

(function (global) {
  const ns = (global.NexusModules = global.NexusModules || {});
  const current = ns['knowledge_articles'] || {};
  current.filterHint = function (value) {
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".knowledge_articles-table tbody tr").forEach(function (row) {
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    });
  };
  current.highlightStatus = function () {
    document.querySelectorAll(".knowledge_articles-table tbody tr").forEach(function (row) {
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {
        row.classList.add("is-hot");
      }
    });
  };
  current.title = 'Knowledge Base';
  current.readyAt = Date.now();
  ns['knowledge_articles'] = current;
  current.highlightStatus();
})(window);

(function () {
  const table = document.querySelector(".inventory_lots-table");
  if (!table) {
    return;
  }
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  rows.forEach(function (row, index) {
    row.setAttribute("data-inventory_lots-index", String(index));
  });
  document.querySelectorAll(".inventory_lots-table tbody tr").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const link = row.querySelector("a");
      if (link) {
        window.location.href = link.getAttribute("href");
      }
    });
  });
  const hero = document.querySelector(".inventory_lots-hero");
  if (hero) {
    hero.classList.add("is-ready");
  }
  window.NexusModules = window.NexusModules || {};
  window.NexusModules['inventory_lots'] = {
    title: 'Inventory Lots',
    rowCount: rows.length,
    accent: '#22d3ee',
    markAttention: function () {
      rows.forEach(function (row) {
        const text = row.textContent || "";
        if (text.indexOf("suspended") >= 0 || text.indexOf("failed") >= 0) {
          row.classList.add("is-hot");
        }
      });
    }
  };
  window.NexusModules['inventory_lots'].markAttention();
})();

(function (global) {
  const ns = (global.NexusModules = global.NexusModules || {});
  const current = ns['inventory_lots'] || {};
  current.filterHint = function (value) {
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".inventory_lots-table tbody tr").forEach(function (row) {
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    });
  };
  current.highlightStatus = function () {
    document.querySelectorAll(".inventory_lots-table tbody tr").forEach(function (row) {
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {
        row.classList.add("is-hot");
      }
    });
  };
  current.title = 'Inventory Lots';
  current.readyAt = Date.now();
  ns['inventory_lots'] = current;
  current.highlightStatus();
})(window);

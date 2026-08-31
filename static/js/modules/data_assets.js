(function () {
  const table = document.querySelector(".data_assets-table");
  if (!table) {
    return;
  }
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  rows.forEach(function (row, index) {
    row.setAttribute("data-data_assets-index", String(index));
  });
  document.querySelectorAll(".data_assets-table tbody tr").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const link = row.querySelector("a");
      if (link) {
        window.location.href = link.getAttribute("href");
      }
    });
  });
  const hero = document.querySelector(".data_assets-hero");
  if (hero) {
    hero.classList.add("is-ready");
  }
  window.NexusModules = window.NexusModules || {};
  window.NexusModules['data_assets'] = {
    title: 'Data Catalog',
    rowCount: rows.length,
    accent: '#a5b4fc',
    markAttention: function () {
      rows.forEach(function (row) {
        const text = row.textContent || "";
        if (text.indexOf("suspended") >= 0 || text.indexOf("failed") >= 0) {
          row.classList.add("is-hot");
        }
      });
    }
  };
  window.NexusModules['data_assets'].markAttention();
})();

(function (global) {
  const ns = (global.NexusModules = global.NexusModules || {});
  const current = ns['data_assets'] || {};
  current.filterHint = function (value) {
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".data_assets-table tbody tr").forEach(function (row) {
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    });
  };
  current.highlightStatus = function () {
    document.querySelectorAll(".data_assets-table tbody tr").forEach(function (row) {
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {
        row.classList.add("is-hot");
      }
    });
  };
  current.title = 'Data Catalog';
  current.readyAt = Date.now();
  ns['data_assets'] = current;
  current.highlightStatus();
})(window);

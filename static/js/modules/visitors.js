(function () {
  const table = document.querySelector(".visitors-table");
  if (!table) {
    return;
  }
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  rows.forEach(function (row, index) {
    row.setAttribute("data-visitors-index", String(index));
  });
  document.querySelectorAll(".visitors-table tbody tr").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const link = row.querySelector("a");
      if (link) {
        window.location.href = link.getAttribute("href");
      }
    });
  });
  const hero = document.querySelector(".visitors-hero");
  if (hero) {
    hero.classList.add("is-ready");
  }
  window.NexusModules = window.NexusModules || {};
  window.NexusModules['visitors'] = {
    title: 'Visitor Desk',
    rowCount: rows.length,
    accent: '#fdba74',
    markAttention: function () {
      rows.forEach(function (row) {
        const text = row.textContent || "";
        if (text.indexOf("suspended") >= 0 || text.indexOf("failed") >= 0) {
          row.classList.add("is-hot");
        }
      });
    }
  };
  window.NexusModules['visitors'].markAttention();
})();

(function (global) {
  const ns = (global.NexusModules = global.NexusModules || {});
  const current = ns['visitors'] || {};
  current.filterHint = function (value) {
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".visitors-table tbody tr").forEach(function (row) {
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    });
  };
  current.highlightStatus = function () {
    document.querySelectorAll(".visitors-table tbody tr").forEach(function (row) {
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {
        row.classList.add("is-hot");
      }
    });
  };
  current.title = 'Visitor Desk';
  current.readyAt = Date.now();
  ns['visitors'] = current;
  current.highlightStatus();
})(window);

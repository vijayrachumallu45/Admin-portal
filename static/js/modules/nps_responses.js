(function () {
  const table = document.querySelector(".nps_responses-table");
  if (!table) {
    return;
  }
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  rows.forEach(function (row, index) {
    row.setAttribute("data-nps_responses-index", String(index));
  });
  document.querySelectorAll(".nps_responses-table tbody tr").forEach(function (row) {
    row.addEventListener("dblclick", function () {
      const link = row.querySelector("a");
      if (link) {
        window.location.href = link.getAttribute("href");
      }
    });
  });
  const hero = document.querySelector(".nps_responses-hero");
  if (hero) {
    hero.classList.add("is-ready");
  }
  window.NexusModules = window.NexusModules || {};
  window.NexusModules['nps_responses'] = {
    title: 'NPS Responses',
    rowCount: rows.length,
    accent: '#a3e635',
    markAttention: function () {
      rows.forEach(function (row) {
        const text = row.textContent || "";
        if (text.indexOf("suspended") >= 0 || text.indexOf("failed") >= 0) {
          row.classList.add("is-hot");
        }
      });
    }
  };
  window.NexusModules['nps_responses'].markAttention();
})();

(function (global) {
  const ns = (global.NexusModules = global.NexusModules || {});
  const current = ns['nps_responses'] || {};
  current.filterHint = function (value) {
    const q = String(value || "").toLowerCase();
    document.querySelectorAll(".nps_responses-table tbody tr").forEach(function (row) {
      const hay = (row.textContent || "").toLowerCase();
      row.style.display = !q || hay.indexOf(q) >= 0 ? "" : "none";
    });
  };
  current.highlightStatus = function () {
    document.querySelectorAll(".nps_responses-table tbody tr").forEach(function (row) {
      const text = row.textContent || "";
      if (/expired|failed|rejected|lost|critical/i.test(text)) {
        row.classList.add("is-hot");
      }
    });
  };
  current.title = 'NPS Responses';
  current.readyAt = Date.now();
  ns['nps_responses'] = current;
  current.highlightStatus();
})(window);

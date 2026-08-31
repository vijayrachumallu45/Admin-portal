(function () {
  const toasts = document.querySelectorAll(".toast");
  toasts.forEach(function (node) {
    window.setTimeout(function () {
      node.style.opacity = "0";
    }, 4200);
  });
  const nav = document.querySelector(".sidenav nav");
  if (nav) {
    const active = window.location.pathname;
    nav.querySelectorAll("a").forEach(function (link) {
      const href = link.getAttribute("href") || "";
      if (href !== "/" && active.indexOf(href) === 0) {
        link.style.background = "rgba(62, 224, 197, 0.12)";
      }
    });
  }
})();

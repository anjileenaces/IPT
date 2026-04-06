(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("pawcare-theme");
  if (stored === "dark" || stored === "light") {
    root.setAttribute("data-theme", stored);
  }
  function syncToggle() {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    const dark = root.getAttribute("data-theme") === "dark";
    btn.textContent = dark ? "☀️" : "🌙";
    btn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  }
  syncToggle();
  document.getElementById("themeToggle")?.addEventListener("click", function () {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("pawcare-theme", next);
    syncToggle();
  });
})();

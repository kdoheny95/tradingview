(() => {
  const STORAGE_KEY = "resume-theme";
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const printBtn = document.getElementById("print-btn");
  const yearEl = document.getElementById("year");

  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
  const stored = localStorage.getItem(STORAGE_KEY);
  const initial = stored || (prefersDark.matches ? "dark" : "light");
  applyTheme(initial);

  toggle.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
  });

  prefersDark.addEventListener("change", (e) => {
    if (localStorage.getItem(STORAGE_KEY)) return;
    applyTheme(e.matches ? "dark" : "light");
  });

  printBtn.addEventListener("click", () => window.print());

  yearEl.textContent = new Date().getFullYear();

  function applyTheme(mode) {
    root.dataset.theme = mode;
    toggle.setAttribute("aria-pressed", mode === "dark" ? "true" : "false");
  }
})();

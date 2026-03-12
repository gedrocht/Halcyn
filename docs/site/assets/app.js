(function () {
  const storageKey = "halcyn-docs-theme";
  const root = document.documentElement;

  function applyTheme(theme) {
    if (theme === "light") {
      root.setAttribute("data-theme", "light");
    } else {
      root.removeAttribute("data-theme");
    }
  }

  const savedTheme = window.localStorage.getItem(storageKey) || "dark";
  applyTheme(savedTheme);

  document.addEventListener("DOMContentLoaded", function () {
    const button = document.querySelector("[data-theme-toggle]");
    if (button) {
      button.addEventListener("click", function () {
        const nextTheme = root.getAttribute("data-theme") === "light" ? "dark" : "light";
        applyTheme(nextTheme);
        window.localStorage.setItem(storageKey, nextTheme);
      });
    }

    const page = document.body.getAttribute("data-page");
    if (page) {
      for (const link of document.querySelectorAll("[data-nav-link]")) {
        if (link.getAttribute("data-nav-link") === page) {
          link.classList.add("active");
        }
      }
    }
  });
})();


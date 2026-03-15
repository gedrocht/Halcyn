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

  function currentPageName() {
    const explicitPage = document.body.getAttribute("data-page");
    if (explicitPage) {
      return explicitPage;
    }

    const pathName = window.location.pathname.split("/").pop() || "index.html";
    return pathName.replace(/\.html$/, "") || "index";
  }

  function normalizeLinkTarget(link) {
    const href = link.getAttribute("href");
    if (!href || href.startsWith("http") || href.startsWith("/") || href.startsWith("#")) {
      return null;
    }

    return href.replace(/\.html$/, "");
  }

  function applyNavigationState() {
    const page = currentPageName();

    for (const link of document.querySelectorAll(".nav-card a[href]")) {
      const targetPage = normalizeLinkTarget(link);
      const isCurrentPage = targetPage === page;

      link.classList.toggle("active", isCurrentPage);
      if (isCurrentPage) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    }
  }

  function fallbackCopyText(text) {
    return new Promise(function (resolve, reject) {
      const temporaryTextArea = document.createElement("textarea");
      temporaryTextArea.value = text;
      temporaryTextArea.setAttribute("readonly", "");
      temporaryTextArea.style.position = "absolute";
      temporaryTextArea.style.left = "-9999px";
      document.body.appendChild(temporaryTextArea);
      temporaryTextArea.select();

      const copySucceeded = document.execCommand("copy");
      document.body.removeChild(temporaryTextArea);

      if (copySucceeded) {
        resolve();
      } else {
        reject(new Error("Copy command was rejected."));
      }
    });
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }

    return fallbackCopyText(text);
  }

  function enhanceCodeBlocks() {
    for (const codeElement of document.querySelectorAll("pre > code")) {
      const preElement = codeElement.parentElement;
      if (!preElement || preElement.querySelector(".code-copy-button")) {
        continue;
      }

      preElement.classList.add("has-copy-button");

      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "code-copy-button";
      copyButton.textContent = "Copy";
      copyButton.setAttribute("aria-label", "Copy this code sample to the clipboard");

      let resetTimer = 0;
      copyButton.addEventListener("click", async function () {
        window.clearTimeout(resetTimer);

        try {
          const codeText = codeElement.innerText.replace(/\n$/, "");
          await copyText(codeText);
          copyButton.textContent = "Copied";
          copyButton.dataset.copyState = "copied";
        } catch (error) {
          console.error(error);
          copyButton.textContent = "Failed";
          copyButton.dataset.copyState = "failed";
        }

        resetTimer = window.setTimeout(function () {
          copyButton.textContent = "Copy";
          copyButton.dataset.copyState = "";
        }, 1800);
      });

      preElement.appendChild(copyButton);
    }
  }

  const savedTheme = window.localStorage.getItem(storageKey) || "dark";
  applyTheme(savedTheme);

  document.addEventListener("DOMContentLoaded", function () {
    const themeButton = document.querySelector("[data-theme-toggle]");
    if (themeButton) {
      themeButton.addEventListener("click", function () {
        const nextTheme = root.getAttribute("data-theme") === "light" ? "dark" : "light";
        applyTheme(nextTheme);
        window.localStorage.setItem(storageKey, nextTheme);
      });
    }

    applyNavigationState();
    enhanceCodeBlocks();
  });
})();

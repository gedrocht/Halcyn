const activityMonitorState = {
  entries: [],
  sortKey: "timestamp_utc",
  sortDirection: "descending",
};

function setTheme(nextTheme) {
  document.body.setAttribute("data-theme", nextTheme);
  localStorage.setItem("halcyn-control-center-theme", nextTheme);
}

function buildActivityQueryString() {
  const sourceFilter = document.getElementById("activity-source-filter").value.trim();
  const levelFilter = document.getElementById("activity-level-filter").value;
  const searchFilter = document.getElementById("activity-search-filter").value.trim();
  const limitFilter = document.getElementById("activity-limit-filter").value || "300";

  const query = new URLSearchParams();
  query.set("limit", limitFilter);
  if (sourceFilter) {
    query.set("source", sourceFilter);
  }
  if (levelFilter) {
    query.set("level", levelFilter);
  }
  if (searchFilter) {
    query.set("search", searchFilter);
  }
  return query.toString();
}

function compareActivityValues(leftValue, rightValue) {
  return String(leftValue).localeCompare(String(rightValue), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

function sortedEntries(entries) {
  const copiedEntries = [...entries];
  copiedEntries.sort((leftEntry, rightEntry) => {
    const comparison = compareActivityValues(
      leftEntry[activityMonitorState.sortKey] ?? "",
      rightEntry[activityMonitorState.sortKey] ?? ""
    );
    return activityMonitorState.sortDirection === "ascending" ? comparison : -comparison;
  });
  return copiedEntries;
}

function renderActivityTable(entries) {
  const tableBody = document.getElementById("activity-table-body");
  tableBody.innerHTML = "";

  if (!entries.length) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="5" class="activity-empty-state">No activity entries matched the current filters.</td>
      </tr>
    `;
    document.getElementById("activity-entry-count").textContent = "0";
    return;
  }

  for (const entry of entries) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${entry.timestamp_utc ?? ""}</td>
      <td>${entry.source_app ?? ""}</td>
      <td>${entry.level ?? ""}</td>
      <td>${entry.component ?? ""}</td>
      <td>${entry.message ?? ""}</td>
    `;
    tableBody.appendChild(row);
  }

  document.getElementById("activity-entry-count").textContent = String(entries.length);
}

function updateSortLabel() {
  const readableDirection =
    activityMonitorState.sortDirection === "ascending" ? "Oldest first" : "Newest first";
  const readableKey = activityMonitorState.sortKey.replaceAll("_", " ");
  document.getElementById("activity-sort-label").textContent =
    `${readableKey} | ${readableDirection}`;
}

async function refreshActivityEntries() {
  const response = await fetch(`/api/activity-log?${buildActivityQueryString()}`);
  const payload = await response.json();
  activityMonitorState.entries = Array.isArray(payload.entries) ? payload.entries : [];
  renderActivityTable(sortedEntries(activityMonitorState.entries));
  document.getElementById("activity-last-refresh").textContent = new Date().toLocaleTimeString();
  updateSortLabel();
}

function clearFilters() {
  document.getElementById("activity-source-filter").value = "";
  document.getElementById("activity-level-filter").value = "";
  document.getElementById("activity-search-filter").value = "";
  document.getElementById("activity-limit-filter").value = "300";
}

function wireActivityMonitorEvents() {
  document.getElementById("refresh-button").addEventListener("click", () => {
    void refreshActivityEntries();
  });
  document.getElementById("activity-apply-filters").addEventListener("click", () => {
    void refreshActivityEntries();
  });
  document.getElementById("activity-clear-filters").addEventListener("click", () => {
    clearFilters();
    void refreshActivityEntries();
  });
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const nextTheme = document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  });

  document.querySelectorAll(".table-sort-button").forEach((button) => {
    button.addEventListener("click", () => {
      const nextSortKey = button.dataset.sortKey;
      if (!nextSortKey) {
        return;
      }
      if (activityMonitorState.sortKey === nextSortKey) {
        activityMonitorState.sortDirection =
          activityMonitorState.sortDirection === "ascending" ? "descending" : "ascending";
      } else {
        activityMonitorState.sortKey = nextSortKey;
        activityMonitorState.sortDirection =
          nextSortKey === "timestamp_utc" ? "descending" : "ascending";
      }
      renderActivityTable(sortedEntries(activityMonitorState.entries));
      updateSortLabel();
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const savedTheme = localStorage.getItem("halcyn-control-center-theme") || "dark";
  setTheme(savedTheme);
  wireActivityMonitorEvents();
  await refreshActivityEntries();
  setInterval(() => {
    void refreshActivityEntries();
  }, 2000);
});

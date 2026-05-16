(function () {
  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (!token || (role !== "manager" && role !== "admin")) {
    location.href = "/";
    return;
  }

  const PAGE_SIZE = 50;

  const params = new URLSearchParams(location.search);
  const filter = (params.get("filter") || "all").trim().toLowerCase();
  let page = Math.max(1, parseInt(params.get("page") || "1", 10) || 1);

  const errorBox = document.getElementById("error-box");
  const backLink = document.getElementById("back-link");
  const paginationEl = document.getElementById("workers-pagination");
  const dateInput = document.getElementById("workers-filter-date");
  const searchInput = document.getElementById("workers-search");
  const deptSelect = document.getElementById("workers-filter-department");
  const posSelect = document.getElementById("workers-filter-position");
  const testSelect = document.getElementById("workers-filter-test");
  const resetFiltersBtn = document.getElementById("workers-reset-filters");

  function todayIso() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function getShiftDate() {
    return dateInput.value || todayIso();
  }

  function updateBackLink() {
    backLink.href = `/manager?date=${encodeURIComponent(getShiftDate())}`;
  }

  const urlDate = (params.get("date") || "").trim();
  dateInput.value = urlDate || todayIso();
  updateBackLink();

  searchInput.value = params.get("q") || "";
  deptSelect.value = params.get("department") || "";
  posSelect.value = params.get("position") || "";
  testSelect.value = params.get("test") || "";

  let searchTimer = null;
  let filterOptionsLoaded = false;

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatShiftDate(isoDate) {
    if (!isoDate) return "";
    const [y, m, d] = isoDate.split("-");
    if (!y || !m || !d) return isoDate;
    return `${d}.${m}.${y}`;
  }

  function renderTestLine(test) {
    const st = attemptStatusDisplay(test);
    const score = test.score_percent != null ? ` · ${test.score_percent}%` : "";
    const ticket = test.ticket_label ? ` · билет ${escapeHtml(test.ticket_label)}` : "";
    return `<div class="worker-test-line"><span class="${st.className}">${escapeHtml(st.text)}</span> — ${escapeHtml(test.test_title)}${score}${ticket}</div>`;
  }

  function renderTests(tests) {
    if (!tests || !tests.length) {
      return '<span class="subtitle">—</span>';
    }
    return tests.map(renderTestLine).join("");
  }

  function currentFilters() {
    return {
      q: searchInput.value.trim(),
      department: deptSelect.value,
      position: posSelect.value,
      test: testSelect.value,
    };
  }

  function buildQuery() {
    const q = new URLSearchParams({ filter, page: String(page), page_size: String(PAGE_SIZE) });
    q.set("shift_date", getShiftDate());
    const f = currentFilters();
    if (f.q) q.set("q", f.q);
    if (f.department) q.set("department", f.department);
    if (f.position) q.set("position", f.position);
    if (f.test) q.set("test", f.test);
    return q;
  }

  function syncUrl() {
    const q = new URLSearchParams(location.search);
    q.set("filter", filter);
    q.set("page", String(page));
    q.set("date", getShiftDate());

    const f = currentFilters();
    if (f.q) q.set("q", f.q);
    else q.delete("q");
    if (f.department) q.set("department", f.department);
    else q.delete("department");
    if (f.position) q.set("position", f.position);
    else q.delete("position");
    if (f.test) q.set("test", f.test);
    else q.delete("test");

    const next = `${location.pathname}?${q.toString()}`;
    if (next !== `${location.pathname}${location.search}`) {
      history.replaceState(null, "", next);
    }
  }

  function goToPage(nextPage) {
    page = nextPage;
    syncUrl();
    load().catch((err) => showError(errorBox, err.message));
  }

  function fillSelect(select, items, placeholder, selected) {
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>`;
    items.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item;
      opt.textContent = item;
      select.appendChild(opt);
    });
    if (selected && ![...select.options].some((o) => o.value === selected)) {
      const opt = document.createElement("option");
      opt.value = selected;
      opt.textContent = selected;
      select.appendChild(opt);
    }
    select.value = selected || "";
  }

  function fillTestSelect(tests, selected) {
    testSelect.innerHTML = '<option value="">Все тесты</option>';
    tests.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.slug;
      opt.textContent = t.title;
      testSelect.appendChild(opt);
    });
    if (selected && ![...testSelect.options].some((o) => o.value === selected)) {
      const opt = document.createElement("option");
      opt.value = selected;
      opt.textContent = selected;
      testSelect.appendChild(opt);
    }
    testSelect.value = selected || "";
  }

  async function loadFilterOptions() {
    if (filterOptionsLoaded) return;
    const data = await API.get("/api/manager/workers/filter-options", token);
    fillSelect(deptSelect, data.departments, "Все подразделения", deptSelect.value);
    fillSelect(posSelect, data.positions, "Все должности", posSelect.value);
    fillTestSelect(data.tests, testSelect.value);
    filterOptionsLoaded = true;
  }

  function renderPagination(data) {
    const total = data.count;
    const pageSize = data.page_size || PAGE_SIZE;
    const current = data.page || page;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    if (totalPages <= 1) {
      paginationEl.classList.add("hidden");
      paginationEl.innerHTML = "";
      return;
    }

    paginationEl.classList.remove("hidden");
    const prevDisabled = current <= 1;
    const nextDisabled = current >= totalPages;

    paginationEl.innerHTML = `
      <button type="button" class="btn btn-secondary btn-sm" id="workers-prev" ${prevDisabled ? "disabled" : ""}>← Назад</button>
      <span class="workers-pagination-info">Страница ${current} из ${totalPages}</span>
      <button type="button" class="btn btn-secondary btn-sm" id="workers-next" ${nextDisabled ? "disabled" : ""}>Вперёд →</button>
    `;

    paginationEl.querySelector("#workers-prev")?.addEventListener("click", () => {
      if (current > 1) goToPage(current - 1);
    });
    paginationEl.querySelector("#workers-next")?.addEventListener("click", () => {
      if (current < totalPages) goToPage(current + 1);
    });
  }

  async function load() {
    hideError(errorBox);
    paginationEl.classList.add("hidden");
    await loadFilterOptions();

    const data = await API.get(`/api/manager/workers?${buildQuery().toString()}`, token);

    page = data.page || page;
    if (data.shift_date && dateInput.value !== data.shift_date) {
      dateInput.value = data.shift_date;
    }
    updateBackLink();
    syncUrl();

    const total = data.count;
    const pageSize = data.page_size || PAGE_SIZE;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (page > totalPages && total > 0) {
      goToPage(totalPages);
      return;
    }

    document.getElementById("page-title").textContent = data.title;
    document.getElementById("page-subtitle").textContent =
      `Смена ${formatShiftDate(data.shift_date)}`;

    const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const to = Math.min(page * pageSize, total);
    document.getElementById("workers-count").textContent =
      total === 0
        ? "Найдено: 0"
        : `Найдено: ${total} · показано ${from}–${to}`;

    const tbody = document.getElementById("workers-body");
    const emptyNote = document.getElementById("empty-note");
    tbody.innerHTML = "";

    if (!data.workers.length) {
      emptyNote.classList.remove("hidden");
      renderPagination(data);
      return;
    }
    emptyNote.classList.add("hidden");

    const frag = document.createDocumentFragment();
    data.workers.forEach((w) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(w.full_name)}</td>
        <td>${escapeHtml(w.position || "—")}</td>
        <td>${escapeHtml(w.department || "—")}</td>
        <td class="worker-tests-cell">${renderTests(w.tests)}</td>
      `;
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);

    renderPagination(data);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function applyFiltersFromPageOne() {
    page = 1;
    syncUrl();
    load().catch((err) => showError(errorBox, err.message));
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFiltersFromPageOne, 350);
  });

  dateInput.addEventListener("change", applyFiltersFromPageOne);
  deptSelect.addEventListener("change", applyFiltersFromPageOne);
  posSelect.addEventListener("change", applyFiltersFromPageOne);
  testSelect.addEventListener("change", applyFiltersFromPageOne);

  resetFiltersBtn.addEventListener("click", () => {
    dateInput.value = todayIso();
    searchInput.value = "";
    deptSelect.value = "";
    posSelect.value = "";
    testSelect.value = "";
    updateBackLink();
    applyFiltersFromPageOne();
  });

  load().catch((err) => {
    showError(errorBox, err.message);
    if (err.message.includes("401") || err.message.includes("403")) {
      location.href = "/";
    }
  });
})();

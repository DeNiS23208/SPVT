/** Блок тестов в кабинете начальника. */
const TRASH_ICON = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M9 3h6m-8 4h10M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M10 11v5M14 11v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
</svg>`;

let managerTestsDeleteBound = false;

function pluralRu(n, one, few, many) {
  const abs = Math.abs(n) % 100;
  const n1 = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

function formatTicketsBadge(n) {
  const count = Number(n) || 0;
  const word = pluralRu(count, "билет", "билета", "билетов");
  return `<span class="test-card-metric"><span class="test-card-metric-value">${count}</span><span class="test-card-metric-label">${word}</span></span>`;
}

function formatQuestionsBadge(n) {
  const count = Number(n) || 0;
  const word = pluralRu(count, "вопрос", "вопроса", "вопросов");
  return `<span class="test-card-metric"><span class="test-card-metric-value">${count}</span><span class="test-card-metric-label">${word}</span></span>`;
}

async function loadManagerTests(token, errorBox) {
  const grid = document.getElementById("manager-tests-grid");
  if (!grid) return;

  let tests = [];
  try {
    tests = await API.get("/api/manager/test-types", token);
  } catch (err) {
    if (errorBox) showError(errorBox, err.message);
  }

  grid.innerHTML = "";

  tests.forEach((test) => {
    const card = document.createElement("article");
    card.className = "test-card test-card-static";
    const activeLabel = test.is_active ? "Активен" : "Неактивен";
    const activeClass = test.is_active
      ? "test-card-status test-card-status-pass"
      : "test-card-status test-card-status-inactive";

    card.innerHTML = `
      <div class="test-card-top">
        <h2 class="test-card-title">${escapeHtml(test.title)}</h2>
        <button type="button" class="btn-icon-delete" data-slug="${escapeHtml(test.slug)}" data-title="${escapeHtml(test.title)}" title="Удалить тест" aria-label="Удалить тест">${TRASH_ICON}</button>
      </div>
      <div class="test-card-badges">
        <button type="button" class="test-card-status-toggle ${activeClass}" data-slug="${escapeHtml(test.slug)}" data-title="${escapeHtml(test.title)}" data-active="${test.is_active ? "1" : "0"}" title="${test.is_active ? "Нажмите, чтобы отключить тест" : "Нажмите, чтобы включить тест"}" aria-pressed="${test.is_active ? "true" : "false"}">${activeLabel}</button>
        ${formatTicketsBadge(test.tickets_count)}
        ${formatQuestionsBadge(test.questions_count)}
      </div>
      <p class="test-card-desc">${escapeHtml(test.description || "")}</p>
      <a class="btn btn-secondary btn-card-action" href="/manager/tests/questions?test=${encodeURIComponent(test.slug)}">Редактировать билеты</a>
    `;

    grid.appendChild(card);
  });

  renderManagerAddTestCard(grid);
  bindManagerTestActions(grid, token, errorBox);
}

function bindManagerTestActions(grid, token, errorBox) {
  if (!grid || managerTestsDeleteBound) return;
  managerTestsDeleteBound = true;

  grid.addEventListener("click", async (e) => {
    const statusBtn = e.target.closest(".test-card-status-toggle");
    if (statusBtn) {
      e.preventDefault();
      e.stopPropagation();
      const slug = statusBtn.dataset.slug;
      const title = statusBtn.dataset.title || "тест";
      const isActive = statusBtn.dataset.active === "1";
      const nextActive = !isActive;

      if (!nextActive) {
        const ok = await confirmDialog({
          title: "Отключить тест?",
          message: `Тест «${title}» станет неактивным — работники не увидят его в списке тестов.`,
          confirmText: "Отключить",
          cancelText: "Отмена",
          danger: true,
        });
        if (!ok) return;
      }

      statusBtn.disabled = true;
      try {
        hideError(errorBox);
        await API.patch(
          `/api/manager/test-types/${encodeURIComponent(slug)}`,
          token,
          { is_active: nextActive }
        );
        await loadManagerTests(token, errorBox);
      } catch (err) {
        showError(errorBox, err.message);
        statusBtn.disabled = false;
      }
      return;
    }

    const btn = e.target.closest(".btn-icon-delete");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    const slug = btn.dataset.slug;
    const title = btn.dataset.title || "тест";
    const ok = await confirmDialog({
      title: "Удалить тест?",
      message: `Тест «${title}».\n\nБудут удалены все билеты, вопросы и результаты прохождений. Это действие нельзя отменить.`,
      confirmText: "Удалить",
      cancelText: "Отмена",
      danger: true,
    });
    if (!ok) return;

    btn.disabled = true;
    try {
      hideError(errorBox);
      await API.del(`/api/manager/test-types/${encodeURIComponent(slug)}`, token);
      await loadManagerTests(token, errorBox);
    } catch (err) {
      showError(errorBox, err.message);
      btn.disabled = false;
    }
  });
}

function renderManagerAddTestCard(grid) {
  if (!grid || grid.querySelector(".test-card-add")) return;
  const addLink = document.createElement("a");
  addLink.href = "/manager/tests/new";
  addLink.className = "test-card test-card-add";
  addLink.innerHTML = `
    <span class="test-card-add-icon">+</span>
    <span class="test-card-add-text">Добавить тест</span>
  `;
  grid.appendChild(addLink);
}

function escapeHtml(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}

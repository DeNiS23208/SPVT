/** Экран выбора теста для работника. */
(function () {
  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (!token || role !== "worker") {
    location.href = "/";
    return;
  }

  document.getElementById("user-name").textContent =
    localStorage.getItem("spvt_full_name") || "Работник";
  applyWorkerBadge(document.getElementById("user-badge"));

  document.getElementById("logout-btn").addEventListener("click", () => {
    clearSession();
    location.href = "/";
  });

  const errorBox = document.getElementById("error-box");
  const loadingEl = document.getElementById("loading");
  const testsScreen = document.getElementById("tests-screen");
  const testsGrid = document.getElementById("tests-grid");

  function escapeHtml(text) {
    const el = document.createElement("span");
    el.textContent = text;
    return el.innerHTML;
  }

  function statusBadge(test) {
    if (test.has_attempt_today) {
      if (test.passed_today) {
        return { text: "Сдано", className: "test-card-status test-card-status-pass" };
      }
      return { text: "Не сдано", className: "test-card-status test-card-status-fail" };
    }
    if (test.last_finished_at != null && test.last_passed != null) {
      if (test.last_passed) {
        return { text: "Сдано ранее", className: "test-card-status test-card-status-pass-muted" };
      }
      return { text: "Не сдано ранее", className: "test-card-status test-card-status-fail-muted" };
    }
    return { text: "Ещё не проходили", className: "test-card-status test-card-status-new" };
  }

  function renderTests(tests) {
    testsGrid.innerHTML = "";
    tests.forEach((test) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "test-card";
      if (test.has_attempt_today) card.classList.add("test-card-done");

      const badge = statusBadge(test);
      const scoreBadge =
        test.last_correct_count != null && test.last_total_questions
          ? `<span class="test-card-score-badge">${test.last_correct_count}/${test.last_total_questions}</span>`
          : "";
      const lastDate = formatDateTimeIrkutsk(test.last_finished_at);
      let scoreLine = "";
      if (test.has_attempt_today && test.score_percent_today != null) {
        scoreLine = `Результат: ${test.score_percent_today}%`;
      } else if (test.last_score_percent != null) {
        scoreLine = `Последний результат: ${test.last_score_percent}%`;
      }

      card.innerHTML = `
        <div class="test-card-head">
          <h2 class="test-card-title">${escapeHtml(test.title)}</h2>
          <div class="test-card-badges">
            <span class="${badge.className}">${badge.text}</span>
            ${scoreBadge}
          </div>
        </div>
        <p class="test-card-desc">${escapeHtml(test.description || "")}</p>
        <div class="test-card-meta">
          <span>Последнее прохождение: <strong>${lastDate}</strong></span>
          ${scoreLine ? `<span>${escapeHtml(scoreLine)}</span>` : ""}
        </div>
        ${test.can_start ? '<span class="test-card-action">Начать тест →</span>' : ""}
      `;

      card.addEventListener("click", () => {
        if (!test.can_start) return;
        location.href = "/worker/test?type=" + encodeURIComponent(test.slug);
      });
      if (!test.can_start) {
        card.classList.add("test-card-locked");
      }
      testsGrid.appendChild(card);
    });
  }

  async function init() {
    try {
      const data = await API.get("/api/test/catalog", token);
      loadingEl.classList.add("hidden");
      if (!data.tests || !data.tests.length) {
        showError(errorBox, "Нет доступных тестов. Обратитесь к начальнику.");
        return;
      }
      testsScreen.classList.remove("hidden");
      renderTests(data.tests);
    } catch (err) {
      loadingEl.classList.add("hidden");
      showError(errorBox, err.message);
    }
  }

  init();
})();

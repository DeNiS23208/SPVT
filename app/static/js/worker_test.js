/** Прохождение выбранного теста. */
(function () {
  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (!token || role !== "worker") {
    location.href = "/";
    return;
  }

  const params = new URLSearchParams(location.search);
  const testType = (params.get("type") || "").trim().toLowerCase();
  if (!testType) {
    location.href = "/worker";
    return;
  }

  applyWorkerBadge(document.getElementById("user-badge"));

  function goHub() {
    location.href = "/worker";
  }

  document.getElementById("back-btn").addEventListener("click", goHub);
  document.getElementById("done-back-btn").addEventListener("click", goHub);
  document.getElementById("result-back-btn").addEventListener("click", goHub);

  const errorBox = document.getElementById("error-box");
  const loadingEl = document.getElementById("loading");
  const testScreen = document.getElementById("test-screen");
  const alreadyDone = document.getElementById("already-done");
  const resultScreen = document.getElementById("result-screen");
  const testTitleEl = document.getElementById("test-title");
  const nextBtn = document.getElementById("next-btn");

  let timerWrap = null;
  let timerValueEl = null;
  let timerLabelEl = null;

  let questions = [];
  let currentIndex = 0;
  /** @type {Map<number, string | string[]>} */
  const answers = new Map();
  /** @type {"question"|"ticket"|null} */
  let timerMode = null;
  let questionTimeLimitSeconds = null;
  let questionTimerInterval = null;
  let questionTimeLeft = 0;
  let timerForQuestionIndex = -1;
  let ticketTimerStarted = false;
  let finishingFromTimer = false;
  let endedByTimeLimit = false;

  function parseTimeLimit(raw) {
    if (raw == null || raw === "") return null;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : null;
  }

  function applyTiming(data) {
    timerMode = data.timer_mode || null;
    ticketTimerStarted = false;
    timerForQuestionIndex = -1;
    if (timerMode === "question") {
      questionTimeLimitSeconds = parseTimeLimit(data.question_time_limit_seconds);
      setTimerLabel("Время на ответ");
    } else if (timerMode === "ticket") {
      const minutes = Number(data.ticket_time_limit_minutes);
      questionTimeLimitSeconds =
        Number.isFinite(minutes) && minutes > 0 ? Math.floor(minutes * 60) : null;
      setTimerLabel("Время на билет");
    } else {
      questionTimeLimitSeconds = null;
    }
  }

  function setTimerLabel(text) {
    ensureTimerElements();
    if (timerLabelEl) timerLabelEl.textContent = text;
  }

  function ensureTimerElements() {
    timerWrap = document.getElementById("question-timer-wrap");
    timerValueEl = document.getElementById("question-timer-value");
    timerLabelEl = timerWrap?.querySelector(".question-timer__label") || null;
    if (timerWrap && timerValueEl) return;

    const card = document.querySelector("#test-screen .card");
    const counter = document.getElementById("question-counter");
    if (!card || !counter) return;

    timerWrap = document.createElement("div");
    timerWrap.id = "question-timer-wrap";
    timerWrap.className = "question-timer question-timer--card";
    timerWrap.setAttribute("aria-live", "polite");
    timerWrap.style.display = "none";
    timerWrap.innerHTML =
      '<span class="question-timer__label">Время на ответ</span>' +
      '<span id="question-timer-value" class="question-timer__value">0:00</span>';
    card.insertBefore(timerWrap, counter);
    timerValueEl = document.getElementById("question-timer-value");
    timerLabelEl = timerWrap.querySelector(".question-timer__label");
  }

  function showTimerBar() {
    ensureTimerElements();
    if (!timerWrap) return;
    timerWrap.style.display = "flex";
    timerWrap.classList.add("is-visible");
    timerWrap.removeAttribute("hidden");
  }

  function hideTimerBar() {
    if (!timerWrap) return;
    timerWrap.style.display = "none";
    timerWrap.classList.remove("is-visible");
  }

  function isMultiQuestion(q) {
    return !!q.allow_multiple_correct;
  }

  function getAnswerForQuestion(q) {
    return answers.get(q.id);
  }

  function isAnswerComplete(q) {
    const v = getAnswerForQuestion(q);
    if (isMultiQuestion(q)) {
      return Array.isArray(v) && v.length > 0;
    }
    return typeof v === "string" && v.length > 0;
  }

  function clearQuestionTimer() {
    if (questionTimerInterval) {
      clearInterval(questionTimerInterval);
      questionTimerInterval = null;
    }
  }

  function formatCountdown(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function updateTimerDisplay() {
    ensureTimerElements();
    if (!timerValueEl || !timerWrap) return;
    timerValueEl.textContent = formatCountdown(Math.max(0, questionTimeLeft));
    timerWrap.classList.remove("question-timer--warn", "question-timer--urgent");
    if (questionTimeLeft <= 10) timerWrap.classList.add("question-timer--urgent");
    else if (questionTimeLeft <= 30) timerWrap.classList.add("question-timer--warn");
  }

  function startQuestionTimer() {
    if (!questionTimeLimitSeconds || questionTimeLimitSeconds < 1) {
      hideTimerBar();
      return;
    }
    if (timerMode === "ticket" && ticketTimerStarted) {
      showTimerBar();
      updateTimerDisplay();
      return;
    }

    clearQuestionTimer();
    showTimerBar();
    questionTimeLeft = questionTimeLimitSeconds;
    if (timerMode === "ticket") {
      ticketTimerStarted = true;
      timerForQuestionIndex = 0;
    } else {
      timerForQuestionIndex = currentIndex;
    }
    updateTimerDisplay();
    questionTimerInterval = setInterval(() => {
      questionTimeLeft -= 1;
      if (questionTimeLeft <= 0) {
        clearQuestionTimer();
        questionTimeLeft = 0;
        updateTimerDisplay();
        finishTestOnTimeout();
        return;
      }
      updateTimerDisplay();
    }, 1000);
  }

  async function finishTestOnTimeout() {
    if (finishingFromTimer) return;
    finishingFromTimer = true;
    endedByTimeLimit = true;
    hideError(errorBox);
    clearQuestionTimer();
    nextBtn.disabled = true;
    try {
      await submitTest();
    } catch (err) {
      showError(errorBox, err.message);
      nextBtn.disabled = false;
      finishingFromTimer = false;
      endedByTimeLimit = false;
      if (questionTimeLimitSeconds) startQuestionTimer();
    }
  }

  function renderQuestion() {
    const q = questions[currentIndex];
    document.getElementById("question-counter").textContent =
      `Вопрос ${currentIndex + 1} из ${questions.length}`;
    document.getElementById("question-text").textContent = q.text;
    document.getElementById("progress-bar").style.width =
      `${(currentIndex / questions.length) * 100}%`;

    const optionsEl = document.getElementById("options");
    const hintWrap = document.getElementById("question-hint-wrap");
    optionsEl.innerHTML = "";
    const multi = isMultiQuestion(q);

    if (multi) {
      hintWrap.hidden = false;
      hintWrap.innerHTML =
        '<p class="question-hint question-hint--multi" role="note">' +
        "В этом вопросе может быть <strong>несколько правильных</strong> вариантов — " +
        "отметьте все подходящие в списке ниже.</p>";
      optionsEl.className = "options options--multi";
      optionsEl.setAttribute("role", "group");
      optionsEl.setAttribute("aria-label", "Варианты ответа, можно выбрать несколько");
    } else {
      hintWrap.hidden = true;
      hintWrap.innerHTML = "";
      optionsEl.className = "options";
      optionsEl.setAttribute("role", "listbox");
      optionsEl.removeAttribute("aria-label");
    }

    const stored = getAnswerForQuestion(q);
    const selectedSet = multi
      ? new Set(Array.isArray(stored) ? stored : [])
      : null;

    q.options.forEach((option) => {
      if (multi) {
        const sel = selectedSet.has(option);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "option option--multi" + (sel ? " selected" : "");
        btn.setAttribute("aria-pressed", sel ? "true" : "false");
        const mark = document.createElement("span");
        mark.className = "option-multi__mark";
        mark.setAttribute("aria-hidden", "true");
        mark.textContent = sel ? "✓" : "";
        const body = document.createElement("span");
        body.className = "option-multi__body";
        body.textContent = option;
        btn.appendChild(mark);
        btn.appendChild(body);
        btn.addEventListener("click", () => {
          const cur = new Set(Array.isArray(answers.get(q.id)) ? answers.get(q.id) : []);
          if (cur.has(option)) cur.delete(option);
          else cur.add(option);
          answers.set(q.id, [...cur]);
          renderQuestion();
        });
        optionsEl.appendChild(btn);
      } else {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "option" + (stored === option ? " selected" : "");
        btn.textContent = option;
        btn.addEventListener("click", () => {
          answers.set(q.id, option);
          [...optionsEl.children].forEach((el) => el.classList.remove("selected"));
          btn.classList.add("selected");
          nextBtn.disabled = false;
        });
        optionsEl.appendChild(btn);
      }
    });

    nextBtn.disabled = !isAnswerComplete(q);
    nextBtn.textContent =
      currentIndex === questions.length - 1 ? "Завершить тест" : "Далее";

    if (timerMode === "question") {
      if (currentIndex !== timerForQuestionIndex) startQuestionTimer();
    } else if (timerMode === "ticket" && !ticketTimerStarted) {
      startQuestionTimer();
    }
  }

  async function submitTest() {
    const payload = {
      test_type: testType,
      answers: questions.map((q) => {
        const raw = answers.get(q.id);
        if (isMultiQuestion(q)) {
          const arr = Array.isArray(raw) ? raw : [];
          const sorted = [...new Set(arr.map(String))].sort();
          return {
            question_id: q.id,
            answer: JSON.stringify(sorted),
          };
        }
        return {
          question_id: q.id,
          answer: typeof raw === "string" ? raw : "",
        };
      }),
    };
    const result = await API.post("/api/test/submit", token, payload);
    clearQuestionTimer();
    hideTimerBar();
    ticketTimerStarted = false;
    testScreen.classList.add("hidden");
    resultScreen.classList.remove("hidden");
    document.getElementById("result-title").textContent =
      result.passed ? "Допущен к работе" : "Не допущен к работе";
    let message = result.message || "";
    if (endedByTimeLimit) {
      const hint =
        timerMode === "ticket"
          ? "Время на билет истекло — тест завершён автоматически."
          : "Время на ответ истекло — тест завершён автоматически.";
      message = (message ? message + " " : "") + hint;
    }
    document.getElementById("result-message").textContent = message;
    resultScreen.classList.toggle("alert-success", result.passed);
    resultScreen.classList.toggle("alert-error", !result.passed);
  }

  async function goToNextQuestion() {
    const q = questions[currentIndex];
    if (!isAnswerComplete(q)) return;
    if (timerMode === "question") clearQuestionTimer();
    if (currentIndex < questions.length - 1) {
      currentIndex += 1;
      renderQuestion();
      return;
    }
    nextBtn.disabled = true;
    try {
      await submitTest();
    } catch (err) {
      showError(errorBox, err.message);
      nextBtn.disabled = false;
    }
  }

  nextBtn.addEventListener("click", async () => {
    hideError(errorBox);
    await goToNextQuestion();
  });

  async function init() {
    try {
      const status = await API.get(
        "/api/test/status?test_type=" + encodeURIComponent(testType),
        token
      );
      testTitleEl.textContent = status.test_title || "Тестирование";
      applyTiming(status);
      loadingEl.classList.add("hidden");

      if (status.has_attempt && status.status !== "in_progress") {
        alreadyDone.classList.remove("hidden");
        const label = statusLabel(status.status).text;
        const passed = status.passed ? "Сдано" : "Не сдано";
        document.getElementById("done-message").textContent =
          `${passed}. Статус: ${label}. Результат: ${status.score_percent}%`;
        return;
      }

      const session = await API.get(
        "/api/test/questions?test_type=" + encodeURIComponent(testType),
        token
      );
      if (Array.isArray(session)) {
        questions = session;
      } else {
        questions = session.questions || [];
        applyTiming(session);
      }
      if (!questions.length) {
        showError(errorBox, "Вопросы для этого теста не найдены.");
        return;
      }
      testScreen.classList.remove("hidden");
      ensureTimerElements();
      renderQuestion();
    } catch (err) {
      loadingEl.classList.add("hidden");
      showError(errorBox, err.message);
    }
  }

  init();
})();

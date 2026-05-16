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

  let questions = [];
  let currentIndex = 0;
  const answers = new Map();
  let selectedAnswer = null;

  function renderQuestion() {
    const q = questions[currentIndex];
    selectedAnswer = answers.get(q.id) || null;
    document.getElementById("question-counter").textContent =
      `Вопрос ${currentIndex + 1} из ${questions.length}`;
    document.getElementById("question-text").textContent = q.text;
    document.getElementById("progress-bar").style.width =
      `${(currentIndex / questions.length) * 100}%`;

    const optionsEl = document.getElementById("options");
    optionsEl.innerHTML = "";
    q.options.forEach((option) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option" + (selectedAnswer === option ? " selected" : "");
      btn.textContent = option;
      btn.addEventListener("click", () => {
        selectedAnswer = option;
        answers.set(q.id, option);
        [...optionsEl.children].forEach((el) => el.classList.remove("selected"));
        btn.classList.add("selected");
        document.getElementById("next-btn").disabled = false;
      });
      optionsEl.appendChild(btn);
    });

    document.getElementById("next-btn").disabled = !selectedAnswer;
    document.getElementById("next-btn").textContent =
      currentIndex === questions.length - 1 ? "Завершить тест" : "Далее";
  }

  async function submitTest() {
    const payload = {
      test_type: testType,
      answers: questions.map((q) => ({
        question_id: q.id,
        answer: answers.get(q.id),
      })),
    };
    const result = await API.post("/api/test/submit", token, payload);
    testScreen.classList.add("hidden");
    resultScreen.classList.remove("hidden");
    document.getElementById("result-title").textContent =
      result.passed ? "Допущен к работе" : "Не допущен к работе";
    document.getElementById("result-message").textContent = result.message;
    resultScreen.classList.toggle("alert-success", result.passed);
    resultScreen.classList.toggle("alert-error", !result.passed);
  }

  document.getElementById("next-btn").addEventListener("click", async () => {
    hideError(errorBox);
    if (!selectedAnswer) return;
    if (currentIndex < questions.length - 1) {
      currentIndex += 1;
      renderQuestion();
      return;
    }
    document.getElementById("next-btn").disabled = true;
    try {
      await submitTest();
    } catch (err) {
      showError(errorBox, err.message);
      document.getElementById("next-btn").disabled = false;
    }
  });

  async function init() {
    try {
      const status = await API.get(
        "/api/test/status?test_type=" + encodeURIComponent(testType),
        token
      );
      testTitleEl.textContent = status.test_title || "Тестирование";
      loadingEl.classList.add("hidden");

      if (status.has_attempt && status.status !== "in_progress") {
        alreadyDone.classList.remove("hidden");
        const label = statusLabel(status.status).text;
        const passed = status.passed ? "Сдано" : "Не сдано";
        document.getElementById("done-message").textContent =
          `${passed}. Статус: ${label}. Результат: ${status.score_percent}%`;
        return;
      }

      questions = await API.get(
        "/api/test/questions?test_type=" + encodeURIComponent(testType),
        token
      );
      if (!questions.length) {
        showError(errorBox, "Вопросы для этого теста не найдены.");
        return;
      }
      testScreen.classList.remove("hidden");
      renderQuestion();
    } catch (err) {
      loadingEl.classList.add("hidden");
      showError(errorBox, err.message);
    }
  }

  init();
})();

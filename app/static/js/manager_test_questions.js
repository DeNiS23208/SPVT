(function () {
  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (!token || (role !== "manager" && role !== "admin")) {
    location.href = "/";
    return;
  }

  const params = new URLSearchParams(location.search);
  const testSlug = (params.get("test") || "").trim().toLowerCase();
  if (!testSlug) {
    location.href = "/manager";
    return;
  }

  const apiBase = `/api/manager/test-types/${encodeURIComponent(testSlug)}`;
  const errorBox = document.getElementById("error-box");
  const successBox = document.getElementById("success-box");
  const ticketsList = document.getElementById("tickets-list");
  const ticketsEmpty = document.getElementById("tickets-empty");
  const addTicketBtn = document.getElementById("add-ticket-btn");
  const exportExcelBtn = document.getElementById("export-excel-btn");
  const questionTimeBtn = document.getElementById("question-time-btn");
  const questionTimeModal = document.getElementById("question-time-modal");
  const questionTimeUnlimited = document.getElementById("question-time-unlimited");
  const questionTimeField = document.getElementById("question-time-field");
  const questionTimeMinutes = document.getElementById("question-time-minutes");
  const questionTimeSave = document.getElementById("question-time-save");
  const questionTimeCancel = document.getElementById("question-time-cancel");
  const ticketTimeBtn = document.getElementById("ticket-time-btn");
  const ticketTimeModal = document.getElementById("ticket-time-modal");
  const ticketTimeUnlimited = document.getElementById("ticket-time-unlimited");
  const ticketTimeField = document.getElementById("ticket-time-field");
  const ticketTimeMinutes = document.getElementById("ticket-time-minutes");
  const ticketTimeSave = document.getElementById("ticket-time-save");
  const ticketTimeCancel = document.getElementById("ticket-time-cancel");

  const expandedTickets = new Set();
  let testInfo = null;
  /** @type {{ ticketId: number, questionId: number } | null} */
  let editingQuestion = null;
  let tickets = [];

  function escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showSuccess(message) {
    successBox.textContent = message;
    successBox.classList.remove("hidden");
    hideError(errorBox);
  }

  function pluralMinutes(n) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return "минута";
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return "минуты";
    return "минут";
  }

  function formatTicketTimeHint(minutes) {
    if (minutes == null || minutes < 1) return "без лимита на билет";
    const n = Number(minutes);
    return `${n} ${pluralMinutes(n)} на билет`;
  }

  function formatQuestionTimeHint(seconds) {
    if (seconds == null || seconds < 1) return "без лимита на вопрос";
    const n = Math.round(seconds / 60);
    if (n >= 1 && n * 60 === seconds) return `${n} ${pluralMinutes(n)} на вопрос`;
    return `${seconds} сек. на вопрос`;
  }

  function updateTestSubtitle() {
    if (!testInfo) return;
    const ticketLimit = formatTicketTimeHint(testInfo.ticket_time_limit_minutes);
    const questionLimit = formatQuestionTimeHint(testInfo.question_time_limit_seconds);
    document.getElementById("test-subtitle").textContent =
      `${testInfo.title} · всего ${testInfo.questions_count} вопр. · ${questionLimit} · ${ticketLimit}`;
  }

  async function loadTestInfo() {
    testInfo = await API.get(apiBase, token);
    updateTestSubtitle();
  }

  function syncTicketTimeForm() {
    const unlimited = ticketTimeUnlimited.checked;
    ticketTimeField.classList.toggle("is-disabled", unlimited);
    ticketTimeMinutes.disabled = unlimited;
  }

  function openTicketTimeModal() {
    const current = testInfo?.ticket_time_limit_minutes;
    if (current == null || current < 1) {
      ticketTimeUnlimited.checked = true;
      ticketTimeMinutes.value = "30";
    } else {
      ticketTimeUnlimited.checked = false;
      ticketTimeMinutes.value = String(current);
    }
    syncTicketTimeForm();
    ticketTimeModal.classList.remove("hidden");
    ticketTimeMinutes.focus();
  }

  function closeTicketTimeModal() {
    ticketTimeModal.classList.add("hidden");
  }

  function syncQuestionTimeForm() {
    const unlimited = questionTimeUnlimited.checked;
    questionTimeField.classList.toggle("is-disabled", unlimited);
    questionTimeMinutes.disabled = unlimited;
  }

  function openQuestionTimeModal() {
    const seconds = testInfo?.question_time_limit_seconds;
    if (seconds == null || seconds < 1) {
      questionTimeUnlimited.checked = true;
      questionTimeMinutes.value = "2";
    } else {
      questionTimeUnlimited.checked = false;
      const minutes = Math.max(1, Math.round(seconds / 60));
      questionTimeMinutes.value = String(minutes);
    }
    syncQuestionTimeForm();
    questionTimeModal.classList.remove("hidden");
    questionTimeMinutes.focus();
  }

  function closeQuestionTimeModal() {
    questionTimeModal.classList.add("hidden");
  }

  async function loadTickets() {
    tickets = await API.get(`${apiBase}/tickets`, token);
    renderTickets();
    await loadTestInfo();
  }

  function correctAnswersSet(question) {
    if (question.allow_multiple_correct) {
      try {
        const arr = JSON.parse(question.correct_answer || "[]");
        return Array.isArray(arr) ? new Set(arr.map(String)) : new Set();
      } catch {
        return new Set();
      }
    }
    const s = new Set();
    if (question.correct_answer) s.add(question.correct_answer);
    return s;
  }

  function syncAnswerOptionsHint(formEl) {
    const hint = formEl.querySelector(".answer-options-fieldset .form-hint");
    if (!hint) return;
    const multi = formEl.querySelector('[name="allow_multiple_correct"]')?.checked;
    hint.textContent = multi
      ? "Отметьте галочкой все правильные варианты. Минимум два варианта в списке и не менее двух правильных."
      : "Отметьте галочкой один правильный вариант. Минимум два варианта.";
  }

  function enforceSingleCorrectIfNeeded(formEl) {
    const multi = formEl.querySelector('[name="allow_multiple_correct"]')?.checked;
    if (multi) return;
    const list = formEl.querySelector("[data-options-list]");
    if (!list) return;
    const checked = list.querySelector(".answer-correct-cb:checked");
    const keep = checked || list.querySelector(".answer-correct-cb");
    list.querySelectorAll(".answer-correct-cb").forEach((cb) => {
      cb.checked = cb === keep;
    });
  }

  function questionFormMarkup(submitLabel) {
    return `
      <form class="question-form">
        <div class="form-field">
          <label>Текст вопроса <span class="field-required">*</span></label>
          <textarea name="text" rows="3" required placeholder="Введите формулировку вопроса"></textarea>
        </div>
        <div class="form-field form-field-checkbox">
          <label class="checkbox-label">
            <input type="checkbox" name="allow_multiple_correct" value="1">
            Несколько правильных ответов
          </label>
        </div>
        <fieldset class="answer-options-fieldset">
          <legend>Варианты ответа <span class="field-required">*</span></legend>
          <p class="subtitle form-hint">Отметьте галочкой один правильный вариант. Минимум два варианта.</p>
          <div class="answer-options-list" data-options-list></div>
          <button type="button" class="btn btn-secondary btn-sm btn-add-option">+ Вариант ответа</button>
        </fieldset>
        <div class="question-form-actions">
          <button type="submit" class="btn btn-primary">${escapeHtml(submitLabel)}</button>
          <button type="button" class="btn btn-secondary btn-cancel-question">Отмена</button>
        </div>
      </form>
    `;
  }

  function createOptionRow(value, checked) {
    const row = document.createElement("div");
    row.className = "answer-option-row";
    const safeVal = escapeHtml(value);
    row.innerHTML = `
      <label class="answer-option-correct" title="Правильный ответ">
        <input type="checkbox" class="answer-correct-cb" ${checked ? "checked" : ""}>
      </label>
      <input type="text" class="answer-option-text" value="${safeVal}" placeholder="Текст варианта" required>
      <button type="button" class="btn-icon-remove" title="Удалить вариант" aria-label="Удалить">×</button>
    `;
    const cb = row.querySelector(".answer-correct-cb");
    cb.addEventListener("change", () => {
      const form = row.closest(".question-form");
      const multi = form?.querySelector('[name="allow_multiple_correct"]')?.checked;
      if (!multi) {
        if (!cb.checked) {
          cb.checked = true;
          return;
        }
        row.parentElement.querySelectorAll(".answer-correct-cb").forEach((other) => {
          if (other !== cb) other.checked = false;
        });
      }
    });
    row.querySelector(".btn-icon-remove").addEventListener("click", () => {
      const list = row.parentElement;
      if (list.querySelectorAll(".answer-option-row").length <= 2) {
        showError(errorBox, "Нужно минимум два варианта ответа.");
        return;
      }
      row.remove();
    });
    return row;
  }

  function readFormPayload(formEl) {
    const text = formEl.querySelector('textarea[name="text"]').value.trim();
    const allowMultiple = !!formEl.querySelector('[name="allow_multiple_correct"]')?.checked;
    const list = formEl.querySelector("[data-options-list]");
    const rows = [...list.querySelectorAll(".answer-option-row")];
    const options = rows
      .map((row) => row.querySelector(".answer-option-text").value.trim())
      .filter(Boolean);
    const correctTexts = rows
      .filter((row) => row.querySelector(".answer-correct-cb")?.checked)
      .map((row) => row.querySelector(".answer-option-text").value.trim())
      .filter(Boolean);
    if (allowMultiple) {
      return {
        text,
        options,
        allow_multiple_correct: true,
        correct_answers: correctTexts,
        correct_answer: "",
      };
    }
    return {
      text,
      options,
      allow_multiple_correct: false,
      correct_answer: correctTexts[0] || "",
      correct_answers: null,
    };
  }

  function fillQuestionForm(wrap, question) {
    const formEl = wrap.querySelector(".question-form");
    formEl.querySelector('textarea[name="text"]').value = question.text || "";
    const allowCb = formEl.querySelector('[name="allow_multiple_correct"]');
    if (allowCb) allowCb.checked = !!question.allow_multiple_correct;
    syncAnswerOptionsHint(formEl);
    const list = formEl.querySelector("[data-options-list]");
    list.innerHTML = "";
    const correctSet = correctAnswersSet(question);
    const options = question.options && question.options.length >= 2 ? question.options : ["", ""];
    options.forEach((opt, idx) => {
      const isCorrect = correctSet.has(opt);
      list.appendChild(createOptionRow(opt, isCorrect || (idx === 0 && correctSet.size === 0)));
    });
    if (!list.querySelector(".answer-correct-cb:checked")) {
      const first = list.querySelector(".answer-correct-cb");
      if (first) first.checked = true;
    }
    enforceSingleCorrectIfNeeded(formEl);
  }

  function bindQuestionForm(wrap, ticketId, questionId) {
    const formEl = wrap.querySelector(".question-form");
    const list = formEl.querySelector("[data-options-list]");
    const isEdit = questionId != null;

    if (!isEdit) {
      list.appendChild(createOptionRow("", true));
      list.appendChild(createOptionRow("", false));
    }

    const allowMulti = formEl.querySelector('[name="allow_multiple_correct"]');
    if (allowMulti) {
      allowMulti.addEventListener("change", () => {
        syncAnswerOptionsHint(formEl);
        enforceSingleCorrectIfNeeded(formEl);
      });
    }

    formEl.querySelector(".btn-add-option").addEventListener("click", () => {
      list.appendChild(createOptionRow("", false));
    });

    formEl.querySelector(".btn-cancel-question").addEventListener("click", () => {
      if (isEdit) {
        editingQuestion = null;
        renderTickets();
        return;
      }
      wrap.classList.add("hidden");
      wrap.innerHTML = "";
    });

    formEl.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideError(errorBox);
      successBox.classList.add("hidden");

      const payload = readFormPayload(formEl);

      try {
        if (isEdit) {
          await API.put(
            `${apiBase}/tickets/${ticketId}/questions/${questionId}`,
            token,
            payload
          );
          showSuccess("Вопрос сохранён");
          editingQuestion = null;
        } else {
          await API.post(`${apiBase}/tickets/${ticketId}/questions`, token, payload);
          showSuccess("Вопрос добавлен");
          wrap.classList.add("hidden");
          wrap.innerHTML = "";
          expandedTickets.add(ticketId);
        }
        await loadTickets();
      } catch (err) {
        showError(errorBox, err.message);
      }
    });
    syncAnswerOptionsHint(formEl);
  }

  function openCreateForm(ticketId) {
    editingQuestion = null;
    expandedTickets.add(ticketId);
    renderTickets();
    const wrap = ticketsList.querySelector(`[data-form-ticket="${ticketId}"]`);
    if (!wrap) return;
    wrap.classList.remove("hidden");
    wrap.innerHTML = questionFormMarkup("Сохранить вопрос");
    bindQuestionForm(wrap, ticketId, null);
    wrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderQuestionView(q, idx, ticketId) {
    const isEditing =
      editingQuestion &&
      editingQuestion.ticketId === ticketId &&
      editingQuestion.questionId === q.id;

    if (isEditing) {
      return `
        <li class="ticket-question-item ticket-question-item-editing" data-question-id="${q.id}">
          <div class="ticket-question-head">
            <span class="ticket-question-num">${idx + 1}.</span>
            <span class="ticket-question-text">Редактирование вопроса</span>
          </div>
          <div class="question-form-wrap" data-edit-form="${q.id}"></div>
        </li>
      `;
    }

    return `
      <li class="ticket-question-item" data-question-id="${q.id}">
        <div class="ticket-question-head">
          <span class="ticket-question-num">${idx + 1}.</span>
          <span class="ticket-question-text">${escapeHtml(q.text)}</span>
          <div class="ticket-question-actions">
            <button type="button" class="btn-link-edit" data-edit-q="${q.id}" data-ticket-id="${ticketId}" title="Редактировать вопрос" aria-label="Редактировать">✎</button>
            <button type="button" class="btn-link-delete" data-delete-q="${q.id}" data-ticket-id="${ticketId}" title="Удалить вопрос" aria-label="Удалить">×</button>
          </div>
        </div>
        <ul class="ticket-question-options">
          ${(() => {
            const ok = correctAnswersSet(q);
            return q.options
              .map(
                (opt) =>
                  `<li class="${ok.has(opt) ? "ticket-option-correct" : ""}">${escapeHtml(opt)}</li>`
              )
              .join("");
          })()}
        </ul>
      </li>
    `;
  }

  function renderTickets() {
    ticketsList.innerHTML = "";
    ticketsEmpty.classList.toggle("hidden", tickets.length > 0);

    tickets.forEach((ticket) => {
      const isOpen = expandedTickets.has(ticket.id);
      const card = document.createElement("article");
      card.className = "ticket-card" + (isOpen ? " ticket-card-open" : "");
      card.dataset.ticketId = String(ticket.id);

      const questionsHtml =
        ticket.questions.length === 0
          ? '<p class="subtitle ticket-no-questions">В билете пока нет вопросов.</p>'
          : ticket.questions
              .map((q, idx) => renderQuestionView(q, idx, ticket.id))
              .join("");

      card.innerHTML = `
        <header class="ticket-head">
          <button type="button" class="ticket-toggle" aria-expanded="${isOpen}" title="${isOpen ? "Свернуть" : "Развернуть"}">
            <span class="ticket-toggle-icon">${isOpen ? "▼" : "▶"}</span>
          </button>
          <h3 class="ticket-title">${escapeHtml(ticket.title)}</h3>
          <span class="ticket-meta">${ticket.questions.length} вопр.</span>
          <button
            type="button"
            class="btn-link-delete ticket-delete-btn"
            data-delete-ticket="${ticket.id}"
            title="Удалить билет"
            aria-label="Удалить билет"
          >×</button>
        </header>
        <div class="ticket-body${isOpen ? "" : " hidden"}">
          <ul class="ticket-questions">${questionsHtml}</ul>
          <button type="button" class="btn btn-secondary btn-add-question" data-ticket-id="${ticket.id}">+ Добавить вопрос</button>
          <div class="question-form-wrap hidden" data-form-ticket="${ticket.id}"></div>
        </div>
      `;

      ticketsList.appendChild(card);
    });

    bindTicketEvents();
    mountEditForms();
  }

  function mountEditForms() {
    if (!editingQuestion) return;
    const ticket = tickets.find((t) => t.id === editingQuestion.ticketId);
    const question = ticket?.questions.find((q) => q.id === editingQuestion.questionId);
    if (!question) {
      editingQuestion = null;
      return;
    }
    const wrap = ticketsList.querySelector(`[data-edit-form="${question.id}"]`);
    if (!wrap) return;
    wrap.innerHTML = questionFormMarkup("Сохранить изменения");
    fillQuestionForm(wrap, question);
    bindQuestionForm(wrap, editingQuestion.ticketId, question.id);
  }

  function bindTicketEvents() {
    ticketsList.querySelectorAll(".ticket-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const card = btn.closest(".ticket-card");
        const id = Number(card.dataset.ticketId);
        if (expandedTickets.has(id)) expandedTickets.delete(id);
        else expandedTickets.add(id);
        renderTickets();
      });
    });

    ticketsList.querySelectorAll(".btn-add-question").forEach((btn) => {
      btn.addEventListener("click", () => openCreateForm(Number(btn.dataset.ticketId)));
    });

    ticketsList.querySelectorAll("[data-edit-q]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const ticketId = Number(btn.dataset.ticketId);
        const questionId = Number(btn.dataset.editQ);
        editingQuestion = { ticketId, questionId };
        expandedTickets.add(ticketId);
        renderTickets();
        const item = ticketsList.querySelector(`[data-edit-form="${questionId}"]`);
        item?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });

    ticketsList.querySelectorAll("[data-delete-ticket]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const ticketId = Number(btn.dataset.deleteTicket);
        const ticket = tickets.find((t) => t.id === ticketId);
        const title = ticket?.title || "билет";
        const qCount = ticket?.questions?.length || 0;
        const ok = await confirmDialog({
          title: "Удалить билет?",
          message:
            qCount > 0
              ? `«${title}» и все ${qCount} вопрос(ов) в нём будут удалены безвозвратно.`
              : `«${title}» будет удалён.`,
          confirmText: "Удалить",
          cancelText: "Отмена",
          danger: true,
        });
        if (!ok) return;
        hideError(errorBox);
        if (editingQuestion?.ticketId === ticketId) editingQuestion = null;
        expandedTickets.delete(ticketId);
        try {
          await API.del(`${apiBase}/tickets/${ticketId}`, token);
          showSuccess("Билет удалён");
          await loadTickets();
        } catch (err) {
          showError(errorBox, err.message);
        }
      });
    });

    ticketsList.querySelectorAll("[data-delete-q]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const ok = await confirmDialog({
          title: "Удалить вопрос?",
          message: "Вопрос будет удалён безвозвратно.",
          confirmText: "Удалить",
          cancelText: "Отмена",
          danger: true,
        });
        if (!ok) return;
        hideError(errorBox);
        const qid = Number(btn.dataset.deleteQ);
        if (editingQuestion?.questionId === qid) editingQuestion = null;
        try {
          await API.del(
            `${apiBase}/tickets/${btn.dataset.ticketId}/questions/${btn.dataset.deleteQ}`,
            token
          );
          await loadTickets();
        } catch (err) {
          showError(errorBox, err.message);
        }
      });
    });
  }

  addTicketBtn.addEventListener("click", async () => {
    hideError(errorBox);
    addTicketBtn.disabled = true;
    try {
      const ticket = await API.post(`${apiBase}/tickets`, token, {});
      expandedTickets.add(ticket.id);
      await loadTickets();
    } catch (err) {
      showError(errorBox, err.message);
    } finally {
      addTicketBtn.disabled = false;
    }
  });

  questionTimeBtn.addEventListener("click", () => {
    hideError(errorBox);
    openQuestionTimeModal();
  });

  questionTimeUnlimited.addEventListener("change", syncQuestionTimeForm);

  questionTimeCancel.addEventListener("click", closeQuestionTimeModal);

  questionTimeModal.addEventListener("click", (e) => {
    if (e.target === questionTimeModal) closeQuestionTimeModal();
  });

  questionTimeSave.addEventListener("click", async () => {
    hideError(errorBox);
    let payload;
    if (questionTimeUnlimited.checked) {
      payload = { question_time_limit_seconds: null };
    } else {
      const minutes = parseInt(questionTimeMinutes.value, 10);
      if (!Number.isFinite(minutes) || minutes < 1 || minutes > 60) {
        showError(errorBox, "Укажите от 1 до 60 минут или включите «Без ограничения».");
        return;
      }
      payload = { question_time_limit_seconds: minutes * 60 };
    }
    questionTimeSave.disabled = true;
    try {
      testInfo = await API.patch(apiBase, token, payload);
      updateTestSubtitle();
      closeQuestionTimeModal();
      showSuccess(
        payload.question_time_limit_seconds == null
          ? "Лимит времени на вопрос снят для этого теста."
          : `Установлено: ${formatQuestionTimeHint(payload.question_time_limit_seconds)}.`
      );
    } catch (err) {
      showError(errorBox, err.message);
    } finally {
      questionTimeSave.disabled = false;
    }
  });

  ticketTimeBtn.addEventListener("click", () => {
    hideError(errorBox);
    openTicketTimeModal();
  });

  ticketTimeUnlimited.addEventListener("change", syncTicketTimeForm);

  ticketTimeCancel.addEventListener("click", closeTicketTimeModal);

  ticketTimeModal.addEventListener("click", (e) => {
    if (e.target === ticketTimeModal) closeTicketTimeModal();
  });

  ticketTimeSave.addEventListener("click", async () => {
    hideError(errorBox);
    let payload;
    if (ticketTimeUnlimited.checked) {
      payload = { ticket_time_limit_minutes: null };
    } else {
      const minutes = parseInt(ticketTimeMinutes.value, 10);
      if (!Number.isFinite(minutes) || minutes < 1 || minutes > 480) {
        showError(errorBox, "Укажите время от 1 до 480 минут или включите «Без ограничения».");
        return;
      }
      payload = { ticket_time_limit_minutes: minutes };
    }
    ticketTimeSave.disabled = true;
    try {
      testInfo = await API.patch(apiBase, token, payload);
      updateTestSubtitle();
      closeTicketTimeModal();
      showSuccess(
        payload.ticket_time_limit_minutes == null
          ? "Ограничение по времени снято."
          : `Установлено: ${formatTicketTimeHint(payload.ticket_time_limit_minutes)}.`
      );
    } catch (err) {
      showError(errorBox, err.message);
    } finally {
      ticketTimeSave.disabled = false;
    }
  });

  exportExcelBtn.addEventListener("click", async () => {
    hideError(errorBox);
    exportExcelBtn.disabled = true;
    exportExcelBtn.classList.add("is-loading");
    try {
      const res = await fetch(`${apiBase}/questions/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Не удалось выгрузить файл");
      }
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `voprosy_${testSlug}.xlsx`;
      link.click();
      URL.revokeObjectURL(link.href);
      showSuccess("Файл Excel скачан");
    } catch (err) {
      showError(errorBox, err.message);
    } finally {
      exportExcelBtn.disabled = false;
      exportExcelBtn.classList.remove("is-loading");
    }
  });

  loadTickets().catch((err) => showError(errorBox, err.message));
})();

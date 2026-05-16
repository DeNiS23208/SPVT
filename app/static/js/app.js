const API = {
  async login(username, password, department = null) {
    const body = new URLSearchParams({ username, password });
    if (department) body.set("department", department);
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка входа");
    return data;
  },

  async getPublic(path) {
    const res = await fetch(path);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
    return data;
  },

  async get(path, token) {
    const res = await fetch(path, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
    return data;
  },

  async post(path, token, payload) {
    const res = await fetch(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
    return data;
  },

  async put(path, token, payload) {
    const res = await fetch(path, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
    return data;
  },

  async patch(path, token, payload) {
    const res = await fetch(path, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
    return data;
  },

  async del(path, token) {
    const res = await fetch(path, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || data.message || "Ошибка запроса";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  },
};

function saveSession(token, role, fullName, position) {
  localStorage.setItem("spvt_token", token);
  localStorage.setItem("spvt_role", role);
  localStorage.setItem("spvt_full_name", fullName);
  if (position && String(position).trim()) {
    localStorage.setItem("spvt_position", String(position).trim());
  } else {
    localStorage.removeItem("spvt_position");
  }
}

function applyWorkerBadge(el) {
  if (!el) return;
  const position = localStorage.getItem("spvt_position");
  el.textContent = position && position.trim() ? position.trim() : "Работник";
}

function getToken() {
  return localStorage.getItem("spvt_token");
}

function clearSession() {
  localStorage.removeItem("spvt_token");
  localStorage.removeItem("spvt_role");
  localStorage.removeItem("spvt_full_name");
  localStorage.removeItem("spvt_position");
}

function statusLabel(status) {
  if (status === "ready") return { text: "Готов", className: "status-ready" };
  if (status === "not_ready") return { text: "Не готов", className: "status-not-ready" };
  if (status === "in_progress") return { text: "В процессе", className: "status-pending" };
  if (status === "reset") return { text: "Сброшен", className: "status-reset" };
  return { text: status, className: "" };
}

function formatDateIrkutskShort(iso) {
  const d = parseServerUtc(iso);
  if (!d || Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: IRKUTSK_TIMEZONE,
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(d);
}

/** Дата и время (кратко, по Иркутску) — для статуса «Сброшен». */
function formatDateIrkutskShortWithTime(iso) {
  const d = parseServerUtc(iso);
  if (!d || Number.isNaN(d.getTime())) return "";
  const datePart = formatDateIrkutskShort(iso);
  const timePart = new Intl.DateTimeFormat("ru-RU", {
    timeZone: IRKUTSK_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
  return `${datePart}, ${timePart}`;
}

function attemptStatusDisplay(item) {
  if (item.status === "reset") {
    const when = item.reset_at ? formatDateIrkutskShortWithTime(item.reset_at) : "";
    return {
      text: when ? `Сброшен ${when}` : "Сброшен",
      className: "status-reset",
    };
  }
  return statusLabel(item.status);
}

function showError(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function hideError(el) {
  el.classList.add("hidden");
  el.textContent = "";
}

function escapeHtmlText(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Модальное подтверждение (в стиле сайта, хорошо видно на тёмном фоне).
 * @returns {Promise<boolean>}
 */
function confirmDialog(opts = {}) {
  const title = opts.title || "Подтвердите действие";
  const message = opts.message || "";
  const confirmText = opts.confirmText || "Да";
  const cancelText = opts.cancelText || "Отмена";
  const danger = opts.danger !== false;

  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "spvt-confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "spvt-confirm-title");

    const messageHtml = message
      ? `<p class="spvt-confirm-message">${escapeHtmlText(message).replace(/\n/g, "<br>")}</p>`
      : "";

    overlay.innerHTML = `
      <div class="spvt-confirm-dialog">
        <h2 class="spvt-confirm-title" id="spvt-confirm-title">${escapeHtmlText(title)}</h2>
        ${messageHtml}
        <div class="spvt-confirm-actions">
          <button type="button" class="btn btn-secondary spvt-confirm-cancel">${escapeHtmlText(cancelText)}</button>
          <button type="button" class="btn ${danger ? "btn-danger" : "btn-primary"} spvt-confirm-ok">${escapeHtmlText(confirmText)}</button>
        </div>
      </div>
    `;

    function close(result) {
      overlay.remove();
      document.removeEventListener("keydown", onKey);
      resolve(result);
    }

    function onKey(e) {
      if (e.key === "Escape") close(false);
    }

    overlay.querySelector(".spvt-confirm-cancel").addEventListener("click", () => close(false));
    overlay.querySelector(".spvt-confirm-ok").addEventListener("click", () => close(true));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(false);
    });

    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
    overlay.querySelector(".spvt-confirm-ok").focus();
  });
}

const IRKUTSK_TIMEZONE = "Asia/Irkutsk";

/** Сервер хранит UTC; без суффикса Z браузер ошибочно читает как локальное время. */
function parseServerUtc(iso) {
  if (!iso) return null;
  const s = String(iso).trim();
  if (!s) return null;
  if (s.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s);
  }
  return new Date(`${s}Z`);
}

/** Дата и время по Иркутску (UTC+8). */
function formatDateTimeIrkutsk(iso) {
  const d = parseServerUtc(iso);
  if (!d || Number.isNaN(d.getTime())) return "—";

  const parts = new Intl.DateTimeFormat("ru-RU", {
    timeZone: IRKUTSK_TIMEZONE,
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);

  const pick = (type) => parts.find((p) => p.type === type)?.value ?? "";
  const day = pick("day");
  const month = pick("month");
  const year = pick("year");
  const hour = pick("hour");
  const minute = pick("minute");

  return `${day} ${month} ${year} г. в ${hour}:${minute} (Иркутск)`;
}

const API = {
  async login(username, password) {
    const body = new URLSearchParams({ username, password });
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Ошибка входа");
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
};

function saveSession(token, role, fullName) {
  localStorage.setItem("spvt_token", token);
  localStorage.setItem("spvt_role", role);
  localStorage.setItem("spvt_full_name", fullName);
}

function getToken() {
  return localStorage.getItem("spvt_token");
}

function clearSession() {
  localStorage.removeItem("spvt_token");
  localStorage.removeItem("spvt_role");
  localStorage.removeItem("spvt_full_name");
}

function statusLabel(status) {
  if (status === "ready") return { text: "Готов", className: "status-ready" };
  if (status === "not_ready") return { text: "Не готов", className: "status-not-ready" };
  if (status === "in_progress") return { text: "В процессе", className: "status-pending" };
  return { text: status, className: "" };
}

function showError(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function hideError(el) {
  el.classList.add("hidden");
  el.textContent = "";
}

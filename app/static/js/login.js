/** Логика входа на главной странице (подразделение → сотрудник). */
(function () {
  async function fetchPublic(path) {
    if (window.API && typeof window.API.getPublic === "function") {
      return window.API.getPublic(path);
    }
    const res = await fetch(path);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || "Ошибка запроса";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (token && (role === "worker" || role === "admin")) {
    location.href = role === "worker" ? "/worker" : "/manager";
    return;
  }

  const errorEl = document.getElementById("login-error");
  const loginBtn = document.getElementById("login-btn");
  const deptSelect = document.getElementById("department");
  const employeeSelect = document.getElementById("employee");
  const usernameInput = document.getElementById("username");
  const deptHint = document.getElementById("dept-hint");

  const savedDept = localStorage.getItem("spvt_department");

  async function loadDepartments() {
    deptSelect.innerHTML = '<option value="">Выберите подразделение</option>';
    const departments = await fetchPublic("/api/public/departments");
    departments.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      deptSelect.appendChild(opt);
    });
    if (savedDept && departments.includes(savedDept)) {
      deptSelect.value = savedDept;
      await loadEmployees(savedDept);
    }
  }

  async function loadEmployees(department) {
    employeeSelect.innerHTML = '<option value="">Выберите себя в списке</option>';
    employeeSelect.disabled = true;
    usernameInput.value = "";

    if (!department) {
      deptHint.textContent = "Сначала укажите подразделение, затем выберите своё ФИО.";
      return;
    }

    const workers = await fetchPublic(
      "/api/public/department-workers?department=" + encodeURIComponent(department)
    );
    workers.forEach((w) => {
      const opt = document.createElement("option");
      opt.value = w.username;
      opt.textContent = w.full_name;
      employeeSelect.appendChild(opt);
    });
    employeeSelect.disabled = false;
    const n = workers.length;
    deptHint.textContent =
      n === 1
        ? "В подразделении один сотрудник."
        : `В подразделении ${n} сотрудников — выберите своё ФИО.`;
  }

  deptSelect.addEventListener("change", () => {
    hideError(errorEl);
    localStorage.setItem("spvt_department", deptSelect.value);
    loadEmployees(deptSelect.value).catch((err) => showError(errorEl, err.message));
  });

  employeeSelect.addEventListener("change", () => {
    hideError(errorEl);
    usernameInput.value = employeeSelect.value;
  });

  async function doLogin() {
    hideError(errorEl);
    loginBtn.disabled = true;
    loginBtn.classList.add("is-loading");
    try {
      const password = document.getElementById("password").value;
      const department = deptSelect.value.trim();
      const username = employeeSelect.value || usernameInput.value.trim();

      if (!department) {
        showError(errorEl, "Выберите подразделение.");
        return;
      }
      if (!username) {
        showError(errorEl, "Выберите себя в списке сотрудников.");
        return;
      }
      if (!password) {
        showError(errorEl, "Введите пароль.");
        return;
      }

      const data = await API.login(username, password, department);
      saveSession(data.access_token, data.role, data.full_name);
      localStorage.setItem("spvt_department", department);
      location.href = data.role === "admin" ? "/manager" : "/worker";
    } catch (err) {
      showError(errorEl, err.message);
    } finally {
      loginBtn.disabled = false;
      loginBtn.classList.remove("is-loading");
    }
  }

  loginBtn.addEventListener("click", doLogin);
  document.getElementById("password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin();
  });

  loadDepartments().catch((err) => showError(errorEl, err.message));
})();

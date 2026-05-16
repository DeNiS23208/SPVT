/** Логика входа на главной странице (подразделение → сотрудник + поиск по ФИО). */
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
  const passwordInput = document.getElementById("password");

  const standardBlock = document.getElementById("worker-login-block");
  const helpBlock = document.getElementById("login-help-block");
  const helpOpenBtn = document.getElementById("login-help-open");
  const helpCloseBtn = document.getElementById("login-help-close");
  const helpFioInput = document.getElementById("help-fio");
  const helpSearchBtn = document.getElementById("help-search-btn");
  const helpPickBlock = document.getElementById("help-pick-block");
  const helpDeptSelect = document.getElementById("help-department");
  const helpEmployeeField = document.getElementById("help-employee-field");
  const helpEmployeeSelect = document.getElementById("help-employee");
  const helpHint = document.getElementById("help-hint");

  const savedDept = localStorage.getItem("spvt_department");
  let helpMatches = [];

  function setLoginMode(help) {
    standardBlock.classList.toggle("hidden", help);
    helpBlock.classList.toggle("hidden", !help);
    helpOpenBtn.classList.toggle("hidden", help);
    helpCloseBtn.classList.toggle("hidden", !help);
    hideError(errorEl);
    if (help) {
      helpFioInput.focus();
    }
  }

  function resetHelpPick() {
    helpMatches = [];
    helpPickBlock.classList.add("hidden");
    helpDeptSelect.innerHTML = '<option value="">Выберите подразделение</option>';
    helpDeptSelect.disabled = true;
    helpEmployeeField.classList.add("hidden");
    helpEmployeeSelect.innerHTML = '<option value="">Выберите себя в списке</option>';
    helpEmployeeSelect.disabled = true;
    helpHint.textContent =
      "Введите фамилию и имя — мы покажем подразделения, где есть совпадения.";
  }

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

  async function applyMatch(match) {
    if (!deptSelect.querySelector(`option[value="${CSS.escape(match.department)}"]`)) {
      const opt = document.createElement("option");
      opt.value = match.department;
      opt.textContent = match.department;
      deptSelect.appendChild(opt);
    }
    deptSelect.value = match.department;
    localStorage.setItem("spvt_department", match.department);
    await loadEmployees(match.department);
    employeeSelect.value = match.username;
    usernameInput.value = match.username;
    deptHint.textContent = "Данные подставлены — осталось ввести пароль.";
    setLoginMode(false);
    passwordInput.focus();
  }

  function uniqueDepartments(matches) {
    const seen = new Set();
    const out = [];
    matches.forEach((m) => {
      if (!seen.has(m.department)) {
        seen.add(m.department);
        out.push(m.department);
      }
    });
    return out.sort((a, b) => a.localeCompare(b, "ru"));
  }

  function matchesInDepartment(department) {
    return helpMatches.filter((m) => m.department === department);
  }

  function fillHelpDepartments(departments) {
    helpDeptSelect.innerHTML = '<option value="">Выберите подразделение</option>';
    departments.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      const count = matchesInDepartment(name).length;
      opt.textContent = count > 1 ? `${name} (${count} совпадений)` : name;
      helpDeptSelect.appendChild(opt);
    });
    helpDeptSelect.disabled = departments.length === 0;
    helpPickBlock.classList.remove("hidden");
  }

  function fillHelpEmployees(workers) {
    helpEmployeeSelect.innerHTML = '<option value="">Выберите себя в списке</option>';
    workers.forEach((w) => {
      const opt = document.createElement("option");
      opt.value = w.username;
      opt.textContent = w.full_name;
      helpEmployeeSelect.appendChild(opt);
    });
    helpEmployeeSelect.disabled = workers.length === 0;
    helpEmployeeField.classList.toggle("hidden", workers.length <= 1);
  }

  function onHelpDepartmentChange() {
    hideError(errorEl);
    const department = helpDeptSelect.value;
    if (!department) {
      helpEmployeeField.classList.add("hidden");
      return;
    }
    const inDept = matchesInDepartment(department);
    if (inDept.length === 1) {
      applyMatch(inDept[0]).catch((err) => showError(errorEl, err.message));
      return;
    }
    fillHelpEmployees(inDept);
    helpHint.textContent =
      inDept.length > 1
        ? "В этом подразделении несколько похожих ФИО — выберите себя."
        : helpHint.textContent;
  }

  async function searchByFio() {
    hideError(errorEl);
    resetHelpPick();
    const q = helpFioInput.value.trim();
    if (q.length < 2) {
      showError(errorEl, "Введите хотя бы фамилию (2 символа и больше).");
      return;
    }

    helpSearchBtn.disabled = true;
    helpSearchBtn.classList.add("is-loading");
    try {
      helpMatches = await fetchPublic(
        "/api/public/find-workers?q=" + encodeURIComponent(q)
      );
      if (helpMatches.length === 0) {
        showError(
          errorEl,
          "Никого не нашли. Проверьте написание фамилии и имени или обратитесь к начальнику."
        );
        return;
      }
      if (helpMatches.length === 1) {
        helpHint.textContent = "Нашли одного сотрудника — подставляем данные…";
        await applyMatch(helpMatches[0]);
        return;
      }

      const departments = uniqueDepartments(helpMatches);
      if (departments.length === 1) {
        const inDept = matchesInDepartment(departments[0]);
        if (inDept.length === 1) {
          await applyMatch(inDept[0]);
          return;
        }
        helpDeptSelect.innerHTML = "";
        const opt = document.createElement("option");
        opt.value = departments[0];
        opt.textContent = departments[0];
        helpDeptSelect.appendChild(opt);
        helpDeptSelect.value = departments[0];
        helpDeptSelect.disabled = true;
        fillHelpEmployees(inDept);
        helpPickBlock.classList.remove("hidden");
        helpHint.textContent = "Выберите себя в списке — несколько похожих ФИО в подразделении.";
        return;
      }

      fillHelpDepartments(departments);
      helpHint.textContent =
        `Найдено ${helpMatches.length} совпадений в ${departments.length} подразделениях — выберите своё.`;
    } catch (err) {
      showError(errorEl, err.message);
    } finally {
      helpSearchBtn.disabled = false;
      helpSearchBtn.classList.remove("is-loading");
    }
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

  helpOpenBtn.addEventListener("click", () => {
    resetHelpPick();
    setLoginMode(true);
  });

  helpCloseBtn.addEventListener("click", () => {
    resetHelpPick();
    setLoginMode(false);
  });

  helpSearchBtn.addEventListener("click", () => {
    searchByFio().catch((err) => showError(errorEl, err.message));
  });

  helpFioInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      searchByFio().catch((err) => showError(errorEl, err.message));
    }
  });

  helpDeptSelect.addEventListener("change", onHelpDepartmentChange);

  helpEmployeeSelect.addEventListener("change", () => {
    hideError(errorEl);
    const username = helpEmployeeSelect.value;
    if (!username) return;
    const match = helpMatches.find((m) => m.username === username);
    if (match) {
      applyMatch(match).catch((err) => showError(errorEl, err.message));
    }
  });

  async function doLogin() {
    hideError(errorEl);
    loginBtn.disabled = true;
    loginBtn.classList.add("is-loading");
    try {
      const password = passwordInput.value;
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
  passwordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin();
  });

  loadDepartments().catch((err) => showError(errorEl, err.message));
})();

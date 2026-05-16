(function () {
  const token = getToken();
  const role = localStorage.getItem("spvt_role");
  if (!token || (role !== "manager" && role !== "admin")) {
    location.href = "/";
    return;
  }

  const errorBox = document.getElementById("error-box");
  const form = document.getElementById("test-form");
  const saveBtn = document.getElementById("save-btn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError(errorBox);

    const title = document.getElementById("test-title").value.trim();
    const description = document.getElementById("test-description").value.trim();

    if (title.length < 2) {
      showError(errorBox, "Название теста: минимум 2 символа.");
      return;
    }
    if (!description) {
      showError(errorBox, "Заполните описание теста.");
      return;
    }

    saveBtn.disabled = true;
    saveBtn.classList.add("is-loading");
    try {
      await API.post("/api/manager/test-types", token, { title, description });
      location.href = "/manager";
    } catch (err) {
      showError(errorBox, err.message);
      saveBtn.disabled = false;
      saveBtn.classList.remove("is-loading");
    }
  });
})();

async function loadSiteSettings() {
  try {
    const res = await fetch("/api/public/site-settings");
    if (!res.ok) return;
    const settings = await res.json();

    document.documentElement.style.setProperty("--accent", settings.accent_color || "#38bdf8");

    const titleEl = document.querySelector(".header h1, h1.page-title");
    if (titleEl && settings.site_title) titleEl.textContent = settings.site_title;

    const subtitleEl = document.querySelector(".subtitle");
    if (subtitleEl && settings.site_subtitle) subtitleEl.textContent = settings.site_subtitle;

    const logoEl = document.querySelector(".logo-shine img, img.site-logo");
    const logoWrap = document.querySelector(".logo-shine");
    if (logoEl && settings.logo_url) {
      const logoUrl = settings.logo_url.includes("?")
        ? settings.logo_url
        : `${settings.logo_url}?v=10`;
      logoEl.src = logoUrl;
      syncLogoMask(logoWrap, settings.logo_url);
    } else {
      syncLogoMask(logoWrap, logoEl?.getAttribute("src"));
    }

    if (document.body.classList.contains("page-home") && settings.hero_background_url) {
      const initial = document.body.dataset.heroUrl || "";
      const opacity = Math.min(Math.max(parseFloat(settings.hero_overlay_opacity) || 0.75, 0), 1);
      const top = opacity;
      const bottom = Math.min(opacity + 0.1, 1);
      let bgUrl = settings.hero_background_url;
      if (bgUrl !== initial) {
        bgUrl = bgUrl.includes("?") ? bgUrl : `${bgUrl}?v=${Date.now()}`;
        document.body.style.background = `linear-gradient(rgba(8, 18, 32, ${top}), rgba(8, 18, 32, ${bottom})), url("${bgUrl}") center center / cover no-repeat fixed`;
        document.body.style.backgroundColor = "#0b1220";
        document.body.dataset.heroUrl = settings.hero_background_url;
      }
    }
  } catch (_err) {
    /* настройки необязательны для работы страницы */
  }
}

function syncLogoMask(logoWrap, url) {
  if (!logoWrap || !url) return;
  let pathOnly = url;
  try {
    const base = url.startsWith("http") ? undefined : window.location.origin;
    pathOnly = new URL(url, base).pathname;
  } catch {
    pathOnly = url.split("?")[0].split("#")[0];
  }
  if (!pathOnly.startsWith("/")) pathOnly = "/" + pathOnly;
  logoWrap.style.setProperty("--logo-mask", `url("${pathOnly}")`);
}

document.addEventListener("DOMContentLoaded", () => {
  const logoWrap = document.querySelector(".logo-shine");
  const logoEl = document.querySelector(".logo-shine img");
  syncLogoMask(logoWrap, logoEl?.getAttribute("src"));
  loadSiteSettings();
});

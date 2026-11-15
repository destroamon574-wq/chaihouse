/* ЧайHouse — переключение тёмной темы.
   Подключается в <head> БЕЗ defer: применяет класс `dark` до первой отрисовки,
   чтобы не было мигания светлой темы. Работает в паре с Tailwind darkMode: 'class'.
   Также определяет Alpine-состояние шапки (window.headerState). */
(function () {
  "use strict";

  var stored = null;
  try {
    stored = window.localStorage.getItem("theme");
  } catch (error) {
    stored = null;
  }

  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (stored === "dark" || (stored === null && prefersDark)) {
    document.documentElement.classList.add("dark");
  }
  document.documentElement.style.colorScheme = document.documentElement.classList.contains("dark") ? "dark" : "light";

  window.headerState = function () {
    return {
      mobileOpen: false,
      dark: document.documentElement.classList.contains("dark"),
      scrolled: false,
      init: function () {
        var self = this;
        this.scrolled = window.scrollY > 8;
        window.addEventListener("scroll", function () {
          self.scrolled = window.scrollY > 8;
        }, { passive: true });
      },
      toggleTheme: function () {
        this.dark = !this.dark;
        document.documentElement.classList.toggle("dark", this.dark);
        document.documentElement.style.colorScheme = this.dark ? "dark" : "light";
        try {
          window.localStorage.setItem("theme", this.dark ? "dark" : "light");
        } catch (error) { /* приватный режим — просто не сохраняем */ }
      },
    };
  };
})();


/* ЧайHouse — UI-инициализация (подключается с defer после CDN-скриптов).
   1) Lucide: заменяет <i data-lucide="name"> на SVG-иконки.
   2) Toastify: Flask flash-сообщения → красивые тосты (без alert()).
      Серверный блок .flash-stack остаётся fallback-ом без JS: скрываем его
      только после успешной конвертации.
   3) Кнопки [data-loading-btn]: показывают спиннер на время отправки формы. */
(function () {
  "use strict";

  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }

  /* --- Flash → Toastify --- */
  var TOAST_STYLES = {
    success: { background: "linear-gradient(135deg, #217f74, #2a9d8f)", color: "#fff" },
    danger: { background: "linear-gradient(135deg, #a8462e, #c4573a)", color: "#fff" },
    warning: { background: "linear-gradient(135deg, #a37422, #c08b2d)", color: "#fff" },
    info: { background: "linear-gradient(135deg, #2b251d, #3a3228)", color: "#fff" },
  };

  function showToast(message, category) {
    if (!window.Toastify) return false;
    window.Toastify({
      text: message,
      duration: 4500,
      close: true,
      gravity: "top",
      position: "right",
      stopOnFocus: true,
      style: TOAST_STYLES[category] || TOAST_STYLES.info,
    }).showToast();
    return true;
  }

  var stack = document.querySelector(".flash-stack");
  if (stack) {
    var converted = 0;
    stack.querySelectorAll(".flash").forEach(function (flash) {
      var text = flash.querySelector(".flash__text");
      var match = /flash--(success|danger|warning|info)/.exec(flash.className);
      var category = match ? match[1] : "info";
      if (text && showToast(text.textContent.trim(), category)) converted += 1;
    });
    if (converted > 0) stack.remove();
  }

  /* --- Состояние загрузки кнопок --- */
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("[data-loading-btn]");
      if (!button || button.disabled) return;
      button.disabled = true;
      var spinner = button.querySelector("[data-loading-spinner]");
      var label = button.querySelector("[data-loading-label]");
      if (spinner) spinner.classList.remove("hidden");
      if (label) label.textContent = "Отправляем…";
    });
  });
})();

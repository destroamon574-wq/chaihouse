/* ЧайHouse — интерактив без inline-скриптов (совместим со строгим CSP). */
(function () {
  "use strict";

  var header = document.getElementById("site-header");
  var navToggle = document.querySelector(".nav-toggle");
  var mobileNav = document.getElementById("mobile-nav");
  var prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setNav(open) {
    if (!navToggle || !mobileNav) return;
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    navToggle.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
    mobileNav.classList.toggle("is-open", open);
  }

  if (navToggle && mobileNav) {
    navToggle.addEventListener("click", function () {
      setNav(navToggle.getAttribute("aria-expanded") !== "true");
    });
    mobileNav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setNav(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setNav(false);
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 1024) setNav(false);
    });
  }

  if (header) {
    var onScroll = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  document.querySelectorAll("[data-dismiss-flash]").forEach(function (button) {
    button.addEventListener("click", function () {
      var flash = button.closest(".flash");
      if (!flash) return;
      flash.style.opacity = "0";
      if (prefersReducedMotion) {
        flash.remove();
      } else {
        flash.addEventListener("transitionend", function () { flash.remove(); }, { once: true });
        window.setTimeout(function () { flash.remove(); }, 240);
      }
    });
  });

  document.querySelectorAll("[data-back]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      var sameOrigin = false;
      try {
        sameOrigin = document.referrer && new URL(document.referrer).origin === window.location.origin;
      } catch (error) {
        sameOrigin = false;
      }
      if (sameOrigin && window.history.length > 1) {
        event.preventDefault();
        window.history.back();
      }
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var message = form.getAttribute("data-confirm") || "Подтвердить действие?";
      if (!window.confirm(message)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () { window.print(); });
  });

  document.querySelectorAll("[data-width]").forEach(function (bar) {
    var raw = parseFloat(bar.getAttribute("data-width"));
    if (!isNaN(raw)) {
      bar.style.width = Math.max(0, Math.min(100, raw)) + "%";
    }
  });

  var lightbox = document.getElementById("lightbox");
  if (lightbox) {
    var lightboxImage = lightbox.querySelector("img");
    var lightboxCaption = lightbox.querySelector(".lightbox__caption");
    var closeLightbox = function () {
      if (lightbox.open) lightbox.close();
      if (lightboxImage) {
        lightboxImage.src = lightboxImage.getAttribute("data-placeholder") || lightboxImage.src;
        lightboxImage.alt = "";
      }
      if (lightboxCaption) lightboxCaption.textContent = "";
    };

    document.querySelectorAll("[data-lightbox]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var source = trigger.getAttribute("data-src");
        var caption = trigger.getAttribute("data-caption") || "";
        if (!source || !lightboxImage) return;
        lightboxImage.src = source;
        lightboxImage.alt = caption;
        if (lightboxCaption) lightboxCaption.textContent = caption;
        if (typeof lightbox.showModal === "function") {
          lightbox.showModal();
        }
      });
    });

    lightbox.addEventListener("click", function (event) {
      if (event.target === lightbox) closeLightbox();
    });
    var lightboxClose = lightbox.querySelector("[data-lightbox-close]");
    if (lightboxClose) lightboxClose.addEventListener("click", closeLightbox);
    lightbox.addEventListener("close", closeLightbox);
  }

  document.querySelectorAll("form.js-favorite").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.fetch) return;
      event.preventDefault();
      var button = form.querySelector("button[type=submit]");
      if (!button) return;
      button.disabled = true;
      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
        credentials: "same-origin"
      }).then(function (response) {
        if (!response.ok) throw new Error("request failed");
        return response.json();
      }).then(function (data) {
        if (!data || !data.ok) throw new Error("bad payload");
        button.classList.toggle("is-active", !!data.active);
        button.setAttribute("aria-pressed", data.active ? "true" : "false");
        button.setAttribute("aria-label", data.active ? "Убрать из избранного" : "Добавить в избранное");
      }).catch(function () {
        HTMLFormElement.prototype.submit.call(form);
      }).finally(function () {
        button.disabled = false;
      });
    });
  });

  var geoPanel = document.querySelector("[data-geo]");
  if (geoPanel) {
    var geoButton = geoPanel.querySelector("[data-geo-button]");
    var geoOutput = geoPanel.querySelector("[data-geo-output]");
    var lat = parseFloat(geoPanel.getAttribute("data-lat"));
    var lng = parseFloat(geoPanel.getAttribute("data-lng"));
    var placeName = geoPanel.getAttribute("data-name") || "ЧайHouse";

    var distanceKm = function (lat1, lon1, lat2, lon2) {
      var toRad = function (value) { return value * Math.PI / 180; };
      var earth = 6371;
      var dLat = toRad(lat2 - lat1);
      var dLon = toRad(lon2 - lon1);
      var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
      return earth * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    };

    if (geoButton && geoOutput && !isNaN(lat) && !isNaN(lng)) {
      geoButton.addEventListener("click", function () {
        if (!navigator.geolocation) {
          geoOutput.textContent = "Браузер не поддерживает геолокацию. Постройте маршрут в Яндекс Картах.";
          return;
        }
        geoButton.disabled = true;
        geoOutput.textContent = "Определяем местоположение…";
        navigator.geolocation.getCurrentPosition(function (position) {
          var km = distanceKm(position.coords.latitude, position.coords.longitude, lat, lng);
          var rounded = km < 1 ? Math.round(km * 1000) + " м" : km.toFixed(1).replace(".", ",") + " км";
          geoOutput.textContent = "До " + placeName + " — примерно " + rounded + " по прямой. Маршрут удобнее строить в Яндекс Картах.";
          geoButton.disabled = false;
        }, function (error) {
          geoOutput.textContent = error && error.code === 1
            ? "Доступ к геолокации запрещён. Разрешите его в настройках браузера или постройте маршрут в Яндекс Картах."
            : "Не удалось определить местоположение. Попробуйте ещё раз или постройте маршрут в Яндекс Картах.";
          geoButton.disabled = false;
        }, { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 });
      });
    }
  }

  var bookingForm = document.querySelector("[data-booking-form]");
  if (bookingForm) {
    var summary = document.querySelector("[data-booking-summary]");
    var summaryTime = summary ? summary.querySelector("[data-summary-time]") : null;
    var summaryTable = summary ? summary.querySelector("[data-summary-table]") : null;
    var summaryGuests = summary ? summary.querySelector("[data-summary-guests]") : null;
    var guestsSelect = bookingForm.querySelector("[data-guests]");

    var updateSlots = function () {
      var selected = bookingForm.querySelector("input[name=slot]:checked");
      if (!selected) return;
      var time = selected.getAttribute("data-slot-time") || "";
      var end = selected.getAttribute("data-slot-end") || "";
      var table = selected.getAttribute("data-slot-table") || "";
      if (summaryTime) summaryTime.textContent = end ? time + "–" + end : time;
      if (summaryTable) summaryTable.textContent = table || "любой свободный";
    };

    bookingForm.querySelectorAll("input[name=slot]").forEach(function (input) {
      input.addEventListener("change", updateSlots);
    });
    if (guestsSelect && summaryGuests) {
      guestsSelect.addEventListener("change", function () {
        summaryGuests.textContent = guestsSelect.value;
      });
    }
    updateSlots();
  }
})();

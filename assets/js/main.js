/* ==========================================================================
   The Denture Clinic — progressive enhancement
   Vanilla JS, no dependencies. Every feature degrades gracefully:
   the site is fully usable with JavaScript disabled.
   ========================================================================== */
(function () {
  "use strict";

  /* ------------------------------------------------------------------------
     Mobile navigation
     The nav is visible by default in the markup so it still works without JS;
     we only hide it once we know the toggle is running.
     ---------------------------------------------------------------------- */
  function initNav() {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("primary-nav");
    if (!toggle || !nav) return;

    var mq = window.matchMedia("(max-width: 900px)");

    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      nav.hidden = !open;
    }

    function sync() {
      if (mq.matches) {
        setOpen(false);
      } else {
        // Desktop: always visible, toggle state is irrelevant.
        nav.hidden = false;
        toggle.setAttribute("aria-expanded", "false");
      }
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    // Close on Escape, returning focus to the toggle.
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      if (mq.matches && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });

    // Close when a link inside the menu is followed (same-page anchors).
    nav.addEventListener("click", function (event) {
      if (mq.matches && event.target.closest("a")) setOpen(false);
    });

    if (mq.addEventListener) {
      mq.addEventListener("change", sync);
    } else if (mq.addListener) {
      mq.addListener(sync); // Safari < 14
    }

    sync();
  }

  /* ------------------------------------------------------------------------
     Header shadow once the page has scrolled
     ---------------------------------------------------------------------- */
  function initStickyHeader() {
    var header = document.querySelector(".site-header");
    if (!header) return;

    var ticking = false;
    function update() {
      header.classList.toggle("is-stuck", window.scrollY > 8);
      ticking = false;
    }

    window.addEventListener(
      "scroll",
      function () {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(update);
      },
      { passive: true }
    );

    update();
  }

  /* ------------------------------------------------------------------------
     Footer copyright year
     ---------------------------------------------------------------------- */
  function initYear() {
    var nodes = document.querySelectorAll("[data-year]");
    var year = String(new Date().getFullYear());
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = year;
  }

  /* ------------------------------------------------------------------------
     Enquiry form
     ------------------------------------------------------------------------
     Validation runs client-side; submission behaviour depends on config:

       - data-endpoint set  -> POST as JSON (Formspree, Netlify Forms, Basin,
                               your own handler — anything that accepts JSON).
       - data-endpoint empty -> fall back to opening the visitor's mail client
                               with the message pre-filled. No backend needed,
                               but the visitor has to press send themselves.

     See PLACEHOLDERS.md for how to wire a real endpoint.
     ---------------------------------------------------------------------- */
  function initForm() {
    var form = document.querySelector("[data-enquiry-form]");
    if (!form) return;

    var status = form.querySelector(".form-status");
    var submitBtn = form.querySelector("[type='submit']");

    function fieldError(input) {
      var wrapper = input.closest(".field");
      return wrapper ? wrapper.querySelector(".error") : null;
    }

    function showError(input, message) {
      input.setAttribute("aria-invalid", "true");
      var slot = fieldError(input);
      if (slot) slot.textContent = message;
    }

    function clearError(input) {
      input.removeAttribute("aria-invalid");
      var slot = fieldError(input);
      if (slot) slot.textContent = "";
    }

    function validate() {
      var invalid = [];
      var controls = form.querySelectorAll("input, select, textarea");

      for (var i = 0; i < controls.length; i++) {
        var input = controls[i];
        if (input.type === "hidden" || input.name === "website") continue;

        clearError(input);

        if (input.hasAttribute("required") && !input.value.trim()) {
          showError(input, "Please fill this in.");
          invalid.push(input);
          continue;
        }
        if (input.type === "email" && input.value && !input.checkValidity()) {
          showError(input, "Please enter a valid email address.");
          invalid.push(input);
        }
      }

      return invalid;
    }

    function setStatus(message, kind) {
      if (!status) return;
      status.textContent = message;
      status.className = "form-status form-status--" + kind;
      status.hidden = false;
    }

    // Clear a field's error as soon as the visitor starts fixing it.
    form.addEventListener("input", function (event) {
      if (event.target.getAttribute("aria-invalid") === "true") {
        clearError(event.target);
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();

      // Honeypot: real people never see this field, so a value means a bot.
      // Pretend it worked rather than telling the bot it was caught.
      if (form.elements.website && form.elements.website.value) {
        setStatus("Thank you — your enquiry has been sent.", "ok");
        form.reset();
        return;
      }

      var invalid = validate();
      if (invalid.length) {
        setStatus(
          "Please check the highlighted " +
            (invalid.length === 1 ? "field" : "fields") +
            " and try again.",
          "error"
        );
        invalid[0].focus();
        return;
      }

      var data = {};
      new FormData(form).forEach(function (value, key) {
        if (key !== "website") data[key] = value;
      });

      var endpoint = form.getAttribute("data-endpoint");

      if (!endpoint) {
        sendByMail(form, data);
        return;
      }

      if (submitBtn) submitBtn.disabled = true;
      setStatus("Sending your enquiry…", "ok");

      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(data)
      })
        .then(function (response) {
          if (!response.ok) throw new Error("Request failed: " + response.status);
          form.reset();
          setStatus(
            "Thank you — your enquiry has been sent. We aim to reply within one working day.",
            "ok"
          );
        })
        .catch(function () {
          setStatus(
            "Sorry, we could not send that. Please call the practice instead, or email us directly.",
            "error"
          );
        })
        .then(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });

    function sendByMail(formEl, data) {
      var address = formEl.getAttribute("data-mailto");
      if (!address) {
        setStatus(
          "This form is not connected yet. Please call the practice to get in touch.",
          "error"
        );
        return;
      }

      var lines = Object.keys(data).map(function (key) {
        return labelFor(formEl, key) + ": " + data[key];
      });

      var href =
        "mailto:" +
        address +
        "?subject=" +
        encodeURIComponent("Website enquiry") +
        "&body=" +
        encodeURIComponent(lines.join("\n"));

      window.location.href = href;
      setStatus(
        "Your email app should now be open with the enquiry ready to send. " +
          "If nothing happened, please call the practice instead.",
        "ok"
      );
    }

    function labelFor(formEl, name) {
      var control = formEl.elements[name];
      if (control && control.id) {
        var label = formEl.querySelector("label[for='" + control.id + "']");
        if (label) return label.textContent.replace(/\s*\*\s*$/, "").trim();
      }
      return name;
    }
  }

  /* ------------------------------------------------------------------------
     Boot
     ---------------------------------------------------------------------- */
  function init() {
    initNav();
    initStickyHeader();
    initYear();
    initForm();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

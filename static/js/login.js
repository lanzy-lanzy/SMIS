/* Login page behaviours: password reveal + submit loading state. */
(function () {
    "use strict";

    var form = document.querySelector("[data-login-form]");
    var username = document.getElementById("id_username");
    var password = document.getElementById("id_password");
    var toggle = document.querySelector("[data-password-toggle]");
    var submit = document.querySelector("[data-login-submit]");

    /* Focus the username on desktop only, so phones do not pop a keyboard
       over the card as soon as the page opens. */
    if (username && window.matchMedia("(min-width: 1024px)").matches) {
        username.focus({ preventScroll: true });
    }

    if (toggle && password) {
        var eyeOpen = toggle.querySelector("[data-eye-open]");
        var eyeClosed = toggle.querySelector("[data-eye-closed]");

        toggle.addEventListener("click", function () {
            var reveal = password.type === "password";

            password.type = reveal ? "text" : "password";
            toggle.setAttribute("aria-pressed", String(reveal));
            toggle.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
            toggle.setAttribute("title", reveal ? "Hide password" : "Show password");

            if (eyeOpen) eyeOpen.classList.toggle("hidden", reveal);
            if (eyeClosed) eyeClosed.classList.toggle("hidden", !reveal);

            /* Keep typing where the user left off. */
            password.focus({ preventScroll: true });
            var end = password.value.length;
            try {
                password.setSelectionRange(end, end);
            } catch (error) {
                /* Not selectable for this input type; nothing to restore. */
            }
        });
    }

    if (!form || !submit) {
        return;
    }

    var label = submit.querySelector("[data-submit-label]");
    var spinner = submit.querySelector("[data-spinner]");
    var arrow = submit.querySelector("[data-submit-arrow]");
    var restingLabel = label ? label.textContent : "";

    function setBusy(busy) {
        submit.dataset.busy = busy ? "1" : "";
        submit.disabled = busy;
        submit.setAttribute("aria-busy", busy ? "true" : "false");

        if (spinner) spinner.classList.toggle("hidden", !busy);
        if (arrow) arrow.classList.toggle("hidden", busy);
        if (label) label.textContent = busy ? "Signing in\u2026" : restingLabel;
    }

    form.addEventListener("submit", function (event) {
        if (submit.dataset.busy === "1") {
            event.preventDefault();
            return;
        }
        setBusy(true);
    });

    /* Returning through back/forward cache must not leave a stuck spinner. */
    window.addEventListener("pageshow", function () {
        if (submit.dataset.busy === "1") {
            setBusy(false);
        }
    });
})();

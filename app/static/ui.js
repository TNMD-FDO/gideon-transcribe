// The small shared pieces every page uses: in-app dialogs in place of the
// browser's own pop-ups, a toast for the quiet confirmations, forms and buttons
// that ask before they act, and first-time hints a person can dismiss. Loaded
// on every page before the page's own script, so window.UI is always there.

(function () {
  "use strict";

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function icon(name) {
    return "<svg class='i' aria-hidden='true' focusable='false'><use href='#i-" + name + "'></use></svg>";
  }

  // Dialogs -----------------------------------------------------------------------
  //
  // One <dialog>, made on first use and reused. A confirm has a plain title,
  // one sentence of consequence, the safe choice first and the action last;
  // a destructive action is red. A prompt adds a field. Each returns a
  // promise: true or false for confirm, the text or null for prompt.

  var dialog = null;
  var settle = null;

  function theDialog() {
    if (dialog) { return dialog; }
    dialog = el("dialog", "ui-dialog");
    dialog.innerHTML =
      "<form method='dialog' class='ui-dialog-form'>" +
        "<h2 class='ui-dialog-title'></h2>" +
        "<div class='ui-dialog-body'></div>" +
        "<div class='ui-dialog-field' hidden><input type='text' class='ui-dialog-input' maxlength='200' autocomplete='off'></div>" +
        "<div class='ui-dialog-buttons'>" +
          "<button type='button' class='ui-cancel'>Cancel</button>" +
          "<button type='submit' class='primary ui-ok'>OK</button>" +
        "</div>" +
      "</form>";
    document.body.appendChild(dialog);
    var form = dialog.querySelector("form");
    dialog.querySelector(".ui-cancel").addEventListener("click", function () { dialog.close("cancel"); });
    form.addEventListener("submit", function (event) { event.preventDefault(); dialog.close("ok"); });
    dialog.addEventListener("cancel", function (event) { event.preventDefault(); dialog.close("cancel"); });
    dialog.addEventListener("close", function () {
      var done = settle;
      settle = null;
      if (done) { done(dialog.returnValue === "ok"); }
    });
    return dialog;
  }

  function open(options, withField) {
    var box = theDialog();
    box.querySelector(".ui-dialog-title").textContent = options.title || "";
    var body = box.querySelector(".ui-dialog-body");
    body.textContent = "";
    var lines = Array.isArray(options.body) ? options.body : (options.body ? [options.body] : []);
    lines.forEach(function (line) { body.appendChild(el("p", null, line)); });
    body.hidden = !lines.length;
    var field = box.querySelector(".ui-dialog-field");
    var input = box.querySelector(".ui-dialog-input");
    field.hidden = !withField;
    if (withField) {
      input.value = options.value || "";
      input.placeholder = options.placeholder || "";
      if (options.list) { input.setAttribute("list", options.list); } else { input.removeAttribute("list"); }
    }
    var ok = box.querySelector(".ui-ok");
    var cancel = box.querySelector(".ui-cancel");
    ok.textContent = options.ok || "OK";
    cancel.textContent = options.cancel || "Cancel";
    cancel.hidden = options.cancel === false;
    ok.className = "ui-ok " + (options.danger ? "danger primary" : "primary");
    box.classList.toggle("danger", !!options.danger);
    return new Promise(function (resolve) {
      settle = resolve;
      box.showModal();
      // The safe choice has the focus for a destructive question; the field
      // for a prompt; the action otherwise.
      if (withField) { input.focus(); input.select(); }
      else if (options.danger && !cancel.hidden) { cancel.focus(); }
      else { ok.focus(); }
    });
  }

  function confirm(options) {
    if (typeof options === "string") { options = { body: options }; }
    return open(options, false);
  }

  function prompt(options) {
    return open(options, true).then(function (yes) {
      if (!yes) { return null; }
      return theDialog().querySelector(".ui-dialog-input").value.trim();
    });
  }

  function alert(options) {
    if (typeof options === "string") { options = { body: options }; }
    options.cancel = false;
    options.ok = options.ok || "OK";
    return open(options, false).then(function () { return undefined; });
  }

  // Toast -------------------------------------------------------------------------

  var toast = null;
  var toastTimer = null;

  function showToast(text, options) {
    options = options || {};
    if (!toast) {
      toast = el("div", "ui-toast");
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.innerHTML = icon(options.icon || "done") + "<span></span>";
    toast.querySelector("span").textContent = text;
    toast.classList.toggle("problem", !!options.problem);
    toast.classList.add("on");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.classList.remove("on"); }, options.for || 2200);
  }

  // Forms and buttons that ask first ---------------------------------------------------
  //
  // <form data-confirm="Delete this?" data-confirm-title="..." data-confirm-ok="Delete"
  //       data-danger> asks in the dialog and submits only on yes; a <button> with
  // the same attributes asks before its form is submitted with that button.

  function asks(node) {
    return {
      title: node.dataset.confirmTitle || "",
      body: node.dataset.confirm,
      ok: node.dataset.confirmOk || "OK",
      cancel: node.dataset.confirmCancel || "Cancel",
      danger: node.hasAttribute("data-danger")
    };
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirm || form.dataset.confirmed) { return; }
    event.preventDefault();
    var submitter = event.submitter;
    confirm(asks(form)).then(function (yes) {
      if (!yes) { return; }
      form.dataset.confirmed = "yes";
      if (submitter && form.requestSubmit) { form.requestSubmit(submitter); }
      else if (form.requestSubmit) { form.requestSubmit(); }
      else { form.submit(); }
    });
  }, true);

  document.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-confirm], a[data-confirm]");
    if (!button || button.dataset.confirmed) { return; }
    event.preventDefault();
    confirm(asks(button)).then(function (yes) {
      if (!yes) { return; }
      button.dataset.confirmed = "yes";
      if (button.tagName === "A") { window.location.href = button.href; return; }
      var form = button.form;
      if (form && form.requestSubmit) { form.requestSubmit(button); }
      else if (form) { form.submit(); }
      else { button.click(); }
      delete button.dataset.confirmed;
    });
  }, true);

  // First-time hints --------------------------------------------------------------------
  //
  // <div class="hint" data-hint="speakers">... <button class="dismiss">Got it</button></div>
  // stays until dismissed, and the choice is remembered in this browser.

  function hintKey(name) { return "hint-" + name; }

  function showHints() {
    Array.prototype.forEach.call(document.querySelectorAll(".hint[data-hint]"), function (hint) {
      var seen = false;
      try { seen = window.localStorage.getItem(hintKey(hint.dataset.hint)) === "seen"; } catch (ignored) { /* shown every time */ }
      hint.hidden = seen;
    });
  }

  document.addEventListener("click", function (event) {
    var dismiss = event.target.closest(".hint .dismiss");
    if (!dismiss) { return; }
    var hint = dismiss.closest(".hint");
    hint.hidden = true;
    try { window.localStorage.setItem(hintKey(hint.dataset.hint), "seen"); } catch (ignored) { /* forgotten on reload */ }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showHints);
  } else {
    showHints();
  }

  window.UI = { confirm: confirm, prompt: prompt, alert: alert, toast: showToast, icon: icon, showHints: showHints };
})();

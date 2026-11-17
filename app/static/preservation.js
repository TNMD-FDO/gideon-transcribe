// The Preservation copy's part of the case's Details tab (Phase 14 chapter 1,
// v1.244.0). The part is drawn by the app (preservation-part.html); this
// sends Make and Stop, and while a copy is being made asks every few seconds
// how far it has got and swaps the part for the app's new drawing of it.
(function () {
  "use strict";
  var part = document.getElementById("preservation");
  if (!part) { return; }
  var asking = null;

  function cookie(name) {
    var found = document.cookie.split("; ").filter(function (one) { return one.indexOf(name + "=") === 0; })[0];
    return found ? decodeURIComponent(found.split("=")[1]) : "";
  }

  function show(told) {
    part.innerHTML = told.html;
    watch(told.making);
  }

  function ask() {
    fetch(part.dataset.status, { headers: { "Accept": "application/json" } })
      .then(function (answer) { return answer.ok ? answer.json() : null; })
      .then(function (told) { if (told) { show(told); } })
      .catch(function () { /* the next asking tries again */ });
  }

  // Asked again only while one is being made; a finished part asks nothing.
  function watch(making) {
    if (making && !asking) { asking = window.setInterval(ask, 3000); }
    if (!making && asking) { window.clearInterval(asking); asking = null; }
  }

  function send(url, button, sorry) {
    button.disabled = true;
    fetch(url, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken"), "Accept": "application/json" } })
      .then(function (answer) { return answer.json().then(function (told) { return { ok: answer.ok, told: told }; }); })
      .then(function (got) {
        if (!got.ok) {
          button.disabled = false;
          window.UI.toast(got.told.error || sorry, { problem: true, icon: "warning" });
          return;
        }
        show(got.told);
      })
      .catch(function () {
        button.disabled = false;
        window.UI.toast(sorry, { problem: true, icon: "warning" });
      });
  }

  part.addEventListener("click", function (ev) {
    var button = ev.target.closest("button[data-act]");
    if (!button) { return; }
    if (button.dataset.act === "make") { send(part.dataset.make, button, "The Preservation copy could not be started."); }
    if (button.dataset.act === "stop") { send(part.dataset.stop, button, "It could not be stopped."); }
  });

  watch(part.dataset.making === "1");
})();

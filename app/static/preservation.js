// The Preservation copy's part of the case's Details tab (Phase 14 chapter 1,
// v1.244.0). The part is drawn by the app (preservation-part.html); this
// sends Make and Stop, and while a copy is being made asks every few seconds
// how far it has got and swaps the part for the app's new drawing of it.
// From v1.245.0 (chapter 2) the part also says a Delete's wait: the case is
// deleted when its copy is ready, and this page then leaves for the Cases
// page; and a Delete that stopped, with Try again and Delete without a copy.
(function () {
  "use strict";
  var part = document.getElementById("preservation");
  if (!part) { return; }
  var asking = null;

  function cookie(name) {
    var found = document.cookie.split("; ").filter(function (one) { return one.indexOf(name + "=") === 0; })[0];
    return found ? decodeURIComponent(found.split("=")[1]) : "";
  }

  // Where the Cases page is told what went and where its copy is.
  function gone(name, days) {
    window.location = "/cases?gone=" + encodeURIComponent(name) + "&days=" + encodeURIComponent(days || 0);
  }

  function show(told) {
    if (told.gone) { gone(told.name, told.days); return; }
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

  function send(url, button, sorry, fields) {
    var body = new URLSearchParams();
    Object.keys(fields || {}).forEach(function (key) { body.append(key, fields[key]); });
    button.disabled = true;
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken"), "Accept": "application/json" }, body: body })
      .then(function (answer) { return answer.json().then(function (told) { return { ok: answer.ok, told: told }; }); })
      .then(function (got) {
        if (!got.ok) {
          button.disabled = false;
          window.UI.toast(got.told.error || sorry, { problem: true, icon: "warning" });
          return null;
        }
        return got.told;
      })
      .catch(function () {
        button.disabled = false;
        window.UI.toast(sorry, { problem: true, icon: "warning" });
        return null;
      });
  }

  // What Delete answers: gone already, with where; or its copy being made.
  function afterDelete(told) {
    if (!told) { return; }
    if (told.making) { ask(); watch(true); return; }
    if (told.kept_days) { gone(told.name, told.kept_days); return; }
    window.location = told.where || "/cases";
  }

  part.addEventListener("click", function (ev) {
    var button = ev.target.closest("button[data-act]");
    if (!button) { return; }
    var act = button.dataset.act;
    if (act === "make") { send(part.dataset.make, button, "The Preservation copy could not be started.").then(function (told) { if (told) { show(told); } }); }
    if (act === "stop") { send(part.dataset.stop, button, "It could not be stopped.").then(function (told) { if (told) { show(told); } }); }
    if (act === "delete-again") { send(part.dataset.delete, button, "That case could not be deleted.").then(afterDelete); }
    if (act === "delete-without") {
      window.UI.confirm({
        title: "Delete " + part.dataset.name + " without a Preservation copy?",
        body: ["Nothing of this case will be kept: no copy goes to Archived.", "This is final. There is no way to get the case or its work back."],
        ok: "Delete without a copy",
        cancel: "Keep it",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        send(part.dataset.delete, button, "That case could not be deleted.", { without_copy: "1" }).then(afterDelete);
      });
    }
  });

  // Delete case (cases.js) says its copy is being made: watch it here.
  part.addEventListener("preservation:watch", function () {
    ask();
    watch(true);
    part.scrollIntoView({ block: "center" });
  });

  watch(part.dataset.making === "1");
})();

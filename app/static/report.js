// Report a problem (Phase 8 chapter 3).
//
// One link on every page opens the same box: a problem or an idea, what
// happened and what was expected in the person's own words, and a tick that
// adds where they were. The line the app will add is drawn before Send, so
// nobody sends what they have not seen. The app's own dialog, never the
// browser's; a box that has been typed in asks before it closes.

(function () {
  "use strict";

  var dialog = document.getElementById("report-dialog");
  var opener = document.getElementById("report-open");
  if (!dialog || !opener) { return; }

  var form = document.getElementById("report-form");
  var happened = form.querySelector("[name=happened]");
  var expected = form.querySelector("[name=expected]");
  var expectedField = document.getElementById("report-expected-field");
  var happenedLabel = document.getElementById("report-happened-label");
  var include = document.getElementById("report-include");
  var where = document.getElementById("report-where");
  var send = document.getElementById("report-send");
  var cancel = document.getElementById("report-cancel");

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function kind() {
    var picked = form.querySelector("[name=report_kind]:checked");
    return picked ? picked.value : "problem";
  }

  // The browser, short, as the app works it out from the same header; the
  // app's own reading is what is kept.
  function browserName() {
    var agent = navigator.userAgent || "";
    var names = [["Edg/", "Edge"], ["OPR/", "Opera"], ["Firefox/", "Firefox"], ["Chrome/", "Chrome"], ["Safari/", "Safari"]];
    var systems = [["Windows", "Windows"], ["Mac OS", "macOS"], ["CrOS", "ChromeOS"], ["Android", "Android"], ["iPhone", "iOS"], ["iPad", "iPadOS"], ["Linux", "Linux"]];
    var name = "";
    for (var n = 0; n < names.length; n += 1) {
      var found = agent.match(new RegExp(names[n][0].replace("/", "\\/") + "(\\d+)"));
      if (found) {
        var version = found[1];
        if (names[n][1] === "Safari") {
          var real = agent.match(/Version\/(\d+)/);
          if (real) { version = real[1]; }
        }
        name = names[n][1] + " " + version;
        break;
      }
    }
    var system = "";
    for (var s = 0; s < systems.length; s += 1) {
      if (agent.indexOf(systems[s][0]) !== -1) { system = systems[s][1]; break; }
    }
    if (!name) { name = "a browser"; }
    return name + (system ? " on " + system : "");
  }

  function windowSize() {
    return window.innerWidth + " by " + window.innerHeight;
  }

  function drawWhere() {
    var name = dialog.dataset.name || "you";
    if (!include.checked) {
      where.textContent = "The report will carry your name (" + name + ") and the Release (" + (dialog.dataset.release || "not tagged") + "), nothing else about where you were.";
      return;
    }
    where.textContent = "This will be added: this page (" + window.location.pathname + "), Release " +
      (dialog.dataset.release || "not tagged") + ", " + browserName() + ", a window of " + windowSize() +
      ", sent by " + name + ".";
  }

  function drawKind() {
    var idea = kind() === "idea";
    happenedLabel.textContent = idea ? "What would help" : "What happened";
    expectedField.hidden = idea;
    dialog.querySelector(".ui-dialog-title").textContent = idea ? "An idea" : "Report a problem";
  }

  function typed() {
    return !!(happened.value.trim() || expected.value.trim());
  }

  function reset() {
    form.reset();
    drawKind();
    drawWhere();
    send.disabled = false;
  }

  function open() {
    reset();
    dialog.showModal();
    happened.focus();
  }

  function close() {
    dialog.close();
  }

  // A box that has been typed in asks before closing; the ask is the app's
  // own dialog, opened over this one.
  function askThenClose() {
    if (!typed()) { close(); return; }
    UI.confirm({
      title: "Close without sending?",
      body: "What you typed will be lost.",
      ok: "Close"
    }).then(function (yes) {
      if (yes) { close(); } else { happened.focus(); }
    });
  }

  opener.addEventListener("click", function (event) {
    event.preventDefault();
    open();
  });
  cancel.addEventListener("click", askThenClose);
  dialog.addEventListener("cancel", function (event) {
    event.preventDefault();
    askThenClose();
  });
  include.addEventListener("change", drawWhere);
  Array.prototype.forEach.call(form.querySelectorAll("[name=report_kind]"), function (one) {
    one.addEventListener("change", drawKind);
  });
  window.addEventListener("resize", function () { if (dialog.open) { drawWhere(); } });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var words = happened.value.trim();
    if (!words) { happened.focus(); return; }
    send.disabled = true;
    fetch("/report", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify({
        kind: kind(),
        happened: words,
        expected: expectedField.hidden ? "" : expected.value.trim(),
        include: include.checked,
        page: window.location.pathname,
        window: windowSize()
      })
    }).then(function (answer) {
      if (!answer.ok) { return Promise.reject(answer.status); }
      return answer.json();
    }).then(function (told) {
      if (!told.sent) { return Promise.reject("refused"); }
      close();
      UI.toast("Thank you. Your report went to the Admins.");
    }).catch(function () {
      send.disabled = false;
      UI.alert({
        title: "That report was not sent",
        body: "You may have been signed out, or reports may be off. Open the page again and try once more."
      });
    });
  });
})();

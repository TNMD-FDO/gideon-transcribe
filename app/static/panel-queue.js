// The Queue page: every job, and a cancel on the ones still running. Read
// again every five seconds while someone is looking (v1.134.0).

(function () {
  "use strict";

  var EVERY = 5000;
  var rows = document.getElementById("jobs");

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function draw(state) {
    rows.innerHTML = state.jobs.map(function (one) {
      var step = one.step || "";
      if (one.position) { step += " (" + one.position + " ahead)"; }
      return "<tr><td>" + escape(one.user) + "</td><td>" + escape(one.title) +
        "</td><td>" + escape(one.batch) + "</td><td>" + one.minutes +
        " min</td><td>" + escape(one.state) + "</td><td>" + escape(step) +
        "</td><td>" + (one.live
          ? "<button type='button' class='small ghost danger cancel' data-job='" + one.id +
            "' data-title='" + escape(one.title) + "'>Cancel</button>"
          : "") + "</td></tr>";
    }).join("");
  }

  rows.addEventListener("click", function (event) {
    var button = event.target.closest(".cancel");
    if (!button) { return; }
    UI.confirm({
      title: "Cancel the job for " + button.dataset.title + "?",
      body: "The recording stays; the transcription stops.",
      ok: "Cancel the job",
      cancel: "Let it run",
      danger: true
    }).then(function (yes) {
      if (!yes) { return; }
      fetch("/panel/queue/" + button.dataset.job + "/cancel", {
        method: "POST",
        headers: { "X-CSRFToken": cookie("csrftoken") }
      }).then(function () { polling.now(); });
    });
  });

  function ask() {
    return fetch("/panel/queue/state")
      .then(function (answer) { return answer.json(); })
      .then(function (state) { draw(state); });
  }

  // The reading is UI.poll's (v1.134.0): nothing while the tab is hidden,
  // at once when it comes back, slower as the page is left alone, and after
  // an hour it stops and the line under the lead says so until a click.
  var pausedLine = document.getElementById("poll-paused");
  var polling = window.UI.poll(ask, EVERY, {
    paused: function (isPaused) { if (pausedLine) { pausedLine.hidden = !isPaused; } }
  });
})();

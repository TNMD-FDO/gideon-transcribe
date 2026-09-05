// The Queue page: every job, and a cancel on the ones still running.

(function () {
  "use strict";

  var EVERY = 5000;
  var rows = document.getElementById("jobs");

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
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
      }).then(ask);
    });
  });

  function ask() {
    fetch("/panel/queue/state")
      .then(function (answer) { return answer.json(); })
      .then(function (state) { draw(state); })
      .catch(function () { /* the next ask will find it */ })
      .then(function () { window.setTimeout(ask, EVERY); });
  }

  ask();
})();

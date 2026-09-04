// The Batch page: what every recording in the batch is doing, refreshed every
// five seconds until nothing in it is still on its way.
//
// One request for the whole batch rather than one per recording, because a
// batch of twenty-five would otherwise be twenty-five requests every five
// seconds for as long as it ran.

(function () {
  "use strict";

  var EVERY = 5000;

  var rows = document.getElementById("rows");
  var counts = document.getElementById("counts");
  var after = document.getElementById("after");
  var cancel = document.getElementById("cancel");
  var downloadLine = document.getElementById("download-line");
  var download = document.getElementById("download");

  var STATES = {
    uploading: "Waiting to upload",
    checking: "Checking the file",
    preparing: "Preparing the audio",
    ready: "In line",
    rejected: "Refused",
    failed: "Failed"
  };

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function line(one) {
    if (one.state === "rejected") { return "Refused: " + escape(one.message); }
    if (one.state === "failed") { return "Failed: " + escape(one.message); }

    var job = one.job;
    if (!job) { return escape(STATES[one.state] || one.state); }

    if (job.state === "done") { return "Done"; }
    if (job.state === "failed") { return "Failed: " + escape(job.message); }
    if (job.state === "cancelled") { return "Cancelled"; }
    if (job.step) { return escape(job.step); }

    if (job.position) {
      var place = job.position === 1
        ? "Next in line"
        : ordinal(job.position) + " in line";
      return escape(place) + (job.wait ? ", " + escape(job.wait) : "");
    }
    return "In line";
  }

  function ordinal(number) {
    // 1st, 2nd, 3rd, 4th. The teens are the exception every time.
    var tens = number % 100;
    if (tens >= 11 && tens <= 13) { return number + "th"; }
    var suffix = ["th", "st", "nd", "rd"][number % 10];
    return number + (suffix || "th");
  }

  function draw(state) {
    rows.innerHTML = "";
    var tally = { waiting: 0, inLine: 0, running: 0, done: 0, failed: 0, refused: 0 };

    state.recordings.forEach(function (one) {
      var card = document.createElement("li");

      var about = [];
      if (one.minutes) { about.push(one.minutes + " minutes"); }
      if (one.two_channel_call) {
        about.push("Two-channel call: " + one.sides + " sides, each transcribed on its own");
      }

      var tools = "";
      if (one.can_retry) {
        tools = " <button type='button' class='small retry' data-recording='" +
          one.id + "'>Retry</button>";
      } else if (one.can_process_again) {
        tools = " <button type='button' class='small process-again' " +
          "data-recording='" + one.id + "' data-title='" + escape(one.title) +
          "'>Process again</button>";
      }
      if (one.has_transcript) {
        tools = "<a href='/recording/" + one.id +
          "' class='btn primary small'>Open</a>" + tools;
      }

      card.innerHTML =
        "<div class='row'><b class='grow'>" + escape(one.title) + "</b>" +
        "<span>" + line(one) + "</span>" + tools + "</div>" +
        "<p class='muted small' style='margin:4px 0 0'>" + about.join(" &middot; ") +
        (one.playback_ready ? "" : " &middot; preparing audio") + "</p>";
      rows.appendChild(card);

      if (one.state === "rejected") { tally.refused += 1; }
      else if (one.state === "failed") { tally.failed += 1; }
      else if (!one.job) { tally.waiting += 1; }
      else if (one.job.state === "done") { tally.done += 1; }
      else if (one.job.state === "failed") { tally.failed += 1; }
      else if (one.job.state === "running") { tally.running += 1; }
      else { tally.inLine += 1; }
    });

    counts.textContent =
      tally.waiting + " uploading or preparing · " +
      tally.inLine + " in line · " +
      tally.running + " transcribing · " +
      tally.done + " done · " +
      tally.failed + " failed · " +
      tally.refused + " refused";

    // The download is a zip of the transcripts that are done. Recordings
    // still on their way are simply left out, so the button says how many.
    var waiting = tally.waiting + tally.inLine + tally.running;
    downloadLine.hidden = tally.done === 0;
    download.querySelector("button").textContent =
      "Download " + tally.done +
      (tally.done === 1 ? " transcript" : " transcripts") +
      (waiting ? " (" + waiting + " not ready)" : "");

    // The one overall line, while anything is still on its way.
    var done = document.getElementById("when-done");
    done.textContent = state.finished ? "" : (state.everything_done_by || "");

    if (state.reprocessing) {
      document.getElementById("heading").textContent = "Processing again";
    }

    after.hidden = !state.finished;
    cancel.hidden = state.finished;
  }

  function ask() {
    fetch("/batch/" + window.BATCH + "/state")
      .then(function (answer) { return answer.json(); })
      .then(function (state) {
        draw(state);
        if (!state.finished) { window.setTimeout(ask, EVERY); }
      })
      .catch(function () {
        // A moment's trouble reaching the app is not worth saying anything
        // about; the next ask will find it.
        window.setTimeout(ask, EVERY);
      });
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  cancel.addEventListener("click", function () {
    if (!window.confirm(
      "Cancel this batch? Each recording is removed from your recordings and " +
      "would have to be uploaded again."
    )) { return; }
    fetch("/batch/" + window.BATCH + "/cancel", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function () { window.location = "/"; });
  });

  ask();
})();

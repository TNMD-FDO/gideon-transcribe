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
  var cancel = document.getElementById("cancel");
  var downloadLine = document.getElementById("download-line");
  var download = document.getElementById("download");
  // The Ready now pane: the transcripts already finished, each with Open.
  var ready = document.getElementById("ready");
  var readyNone = document.getElementById("ready-none");

  // The finished state: the download becomes the page and everything about
  // waiting goes away, because a batch that is done is about getting the
  // transcripts out and nothing else.
  var finished = document.getElementById("finished");
  var finishedHeading = document.getElementById("finished-heading");
  var finishedWhen = document.getElementById("finished-when");
  var downloadDone = document.getElementById("download-done");
  var whileRunning = document.getElementById("while-running");
  var heading = document.getElementById("heading");
  var lead = document.getElementById("lead");

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

    // The whole sentence is built by the app, so that the wording lives in
    // one place rather than half here and half there.
    if (job.line) { return escape(job.line); }
    return "In line";
  }

  function draw(state) {
    rows.innerHTML = "";
    var tally = { waiting: 0, inLine: 0, running: 0, done: 0, failed: 0, refused: 0 };

    state.recordings.forEach(function (one) {
      var card = document.createElement("li");

      var about = [];
      if (one.minutes) { about.push(one.minutes + " minutes"); }
      // A recording kept in a case that is out of reach says where it went
      // and offers no way in, because a hidden case is hidden from everyone.
      if (one.out_of_reach) { about.push("in a case (cases are off)"); }
      else if (one.in_a_case) { about.push("in a case"); }
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

      var bar = "";
      if (one.job && one.job.percent) {
        bar = "<div class='bar' style='margin:6px 0 0'><i style='width:" +
          Math.max(2, Math.min(100, one.job.percent)) + "%'></i></div>";
      }

      card.innerHTML =
        "<div class='row'><b class='grow'>" + escape(one.title) + "</b>" +
        "<span>" + line(one) + "</span>" + tools + "</div>" + bar +
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
    var words =
      "Download " + tally.done +
      (tally.done === 1 ? " transcript" : " transcripts") +
      (waiting ? " (" + waiting + " not ready)" : "");
    downloadLine.hidden = tally.done === 0;
    download.querySelector("button").textContent = words;
    downloadDone.querySelector("button").textContent =
      "Download all " + tally.done +
      (tally.done === 1 ? " transcript" : " transcripts");

    // Ready now: whatever can already be opened, in the order of the batch.
    var finishedOnes = state.recordings.filter(function (one) { return one.has_transcript; });
    ready.innerHTML = finishedOnes.map(function (one) {
      return "<li><span class='grow'>" + escape(one.title) + "</span>" +
        "<a href='/recording/" + one.id + "' class='btn small'>Open</a></li>";
    }).join("");
    readyNone.hidden = finishedOnes.length > 0;

    // Still to come: how many, and the estimate, while anything is on its way.
    var done = document.getElementById("when-done");
    done.textContent = state.finished ? "" :
      (waiting ? waiting + (waiting === 1 ? " recording" : " recordings") + " still to come" : "Nothing still to come") +
      (state.everything_done_by ? ". " + state.everything_done_by : ".");

    if (state.reprocessing) {
      document.getElementById("heading").textContent = "Processing again";
    }

    cancel.hidden = state.finished;

    // Done: the summary takes over, and the row of controls that was about
    // waiting goes. A batch where nothing came out has nothing to download,
    // so it says so rather than offering an empty zip.
    finished.hidden = !state.finished;
    whileRunning.hidden = state.finished;
    heading.hidden = state.finished;
    if (lead) { lead.hidden = state.finished; }

    if (state.finished) {
      finishedHeading.textContent = tally.done
        ? (tally.done === 1
            ? "The transcript is ready"
            : "All " + tally.done + " transcripts are ready")
        : "This batch produced no transcripts";
      finishedWhen.textContent = tally.failed || tally.refused
        ? tally.failed + " failed, " + tally.refused + " refused."
        : "";
      downloadDone.hidden = tally.done === 0;
    }
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
    UI.confirm({
      title: "Cancel this batch?",
      body: "Each recording is removed from your recordings and would have to be uploaded again.",
      ok: "Cancel the batch",
      cancel: "Keep going",
      danger: true
    }).then(function (yes) {
      if (!yes) { return; }
      fetch("/batch/" + window.BATCH + "/cancel", {
        method: "POST",
        headers: { "X-CSRFToken": cookie("csrftoken") }
      }).then(function () { window.location = "/"; });
    });
  });

  ask();
})();

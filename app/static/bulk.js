// Bulk transcription (v1.173.0, the settings card v1.174.0): the drop, the
// files with their titles and chips, the settings card folded under them,
// Start, the batch where it stands, the download. The same endpoints as the
// Upload page and the batch page (/upload/submit, the sidecar,
// /batch/<id>/state, /batch/<id>/cancel and the batch's download), on one
// page that never leaves. The card is read and written by upload-settings.js,
// shared with the Upload page; the upload part follows upload.js, three
// files at a time; the batch part draws the batch page's state feed in one
// list rather than two panes.

(function () {
  "use strict";

  var AT_ONCE = 3;
  var EVERY = 4000;

  var section = document.getElementById("bulk-batch");
  var dropBox = document.getElementById("bulk-drop");
  var picker = document.getElementById("picker");
  if (!section || !picker || !window.UploadSettings) { return; }
  var Card = window.UploadSettings;

  var chosen = [];
  var list = document.getElementById("chosen");
  var start = document.getElementById("start");
  var hint = document.getElementById("start-hint");
  var problem = document.getElementById("submit-problem");
  var progress = document.getElementById("progress");
  var drop = document.getElementById("drop");
  var fold = document.getElementById("bulk-settings");
  var line = document.getElementById("bulk-settings-line");

  function by(id) { return document.getElementById(id); }
  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function bytes(size) {
    if (size >= 1073741824) { return (size / 1073741824).toFixed(1) + " GB"; }
    if (size >= 1048576) { return (size / 1048576).toFixed(0) + " MB"; }
    return (size / 1024).toFixed(0) + " KB";
  }
  function withoutExtension(name) {
    var dot = name.lastIndexOf(".");
    return dot > 0 ? name.slice(0, dot) : name;
  }
  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  // The settings: the batch's, or one file's own ---------------------------------
  //
  // As on the Upload page: a file's own start as null, meaning "same as the
  // batch", and a copy is taken only when somebody unticks the box, so a
  // file that follows the batch keeps following it when the batch changes.
  var batchSettings = null;
  var railFor = null;

  function settings() {
    if (railFor === null) { batchSettings = Card.read(); }
    return batchSettings || Card.read();
  }
  function settingsFor(one) { return one.own || settings(); }

  function showBatch() {
    railFor = null;
    by("rail-heading").textContent = "Batch settings";
    by("back-to-batch").hidden = true;
    by("use-batch-line").hidden = true;
    by("file-title-line").hidden = true;
    Card.enable(true);
    Card.write(batchSettings || Card.read());
    draw();
  }

  function showFile(index) {
    railFor = index;
    var one = chosen[index];
    by("rail-heading").textContent = one.title;
    by("back-to-batch").hidden = false;
    by("use-batch-line").hidden = false;
    by("file-title-line").hidden = false;
    by("file-title").value = one.title;
    by("use-batch").checked = !one.own;
    Card.enable(!!one.own);
    Card.write(one.own || settings());
    fold.open = true;
    draw();
    fold.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // Whatever the card is showing, keep it in the right place.
  function remember() {
    if (railFor === null) { batchSettings = Card.read(); }
    else if (chosen[railFor] && chosen[railFor].own) { chosen[railFor].own = Card.read(); }
    sayLine();
  }
  Card.onChange(remember);

  by("back-to-batch").addEventListener("click", showBatch);
  by("use-batch").addEventListener("change", function () {
    var one = chosen[railFor];
    if (!one) { return; }
    one.own = this.checked ? null : Card.copyOf(settings());
    Card.enable(!this.checked);
    Card.write(one.own || settings());
    draw();
  });
  by("file-title").addEventListener("input", function () {
    var one = chosen[railFor];
    if (!one) { return; }
    one.title = this.value;
    by("rail-heading").textContent = this.value;
    var card = list.querySelector("li[data-index='" + railFor + "'] input");
    if (card && card.value !== this.value) { card.value = this.value; }
  });

  // The one line under Settings: what is set for the batch, and how many
  // files have their own.
  function speakersInWords(values) {
    var speakers = values.speakers;
    if (!values.diarize) { return "speakers not told apart"; }
    if (speakers && speakers.exactly) { return "exactly " + speakers.exactly + " speakers"; }
    if (speakers && speakers.between) { return "between " + speakers.between[0] + " and " + speakers.between[1] + " speakers"; }
    return "speakers told apart";
  }
  function sayLine() {
    var values = settings();
    var parts = [
      speakersInWords(values),
      values.translate ? "to English" : "not translated",
      values.language ? "language " + values.language : "language detected"
    ];
    if (values.vocabulary && values.vocabulary.join("").trim()) { parts.push("vocabulary"); }
    if (values.context && values.context.trim()) { parts.push("context"); }
    if (values.enrich) { parts.push("vision"); }
    if (values.email_when_done) { parts.push("email when done"); }
    var own = chosen.filter(function (one) { return one.own && !one.refused; }).length;
    if (own) { parts.push(plural(own, "file") + " with " + (own === 1 ? "its" : "their") + " own"); }
    line.textContent = parts.join(" · ");
  }

  // The files -------------------------------------------------------------------------

  function add(files) {
    Array.prototype.forEach.call(files, function (file) {
      var refused = null;
      if (/\.(zip|rar|7z|tar|gz)$/i.test(file.name)) {
        refused = "Zip files are not accepted. Choose the recordings inside it instead.";
      } else if (file.size === 0) {
        refused = "The file is empty";
      }
      chosen.push({ own: null, file: file, title: withoutExtension(file.name), refused: refused });
    });
    draw();
  }

  function usable() { return chosen.filter(function (one) { return !one.refused; }); }

  function draw() {
    list.innerHTML = "";
    chosen.forEach(function (one, index) {
      var card = document.createElement("li");
      card.className = one.refused ? "card refused" : "card";
      card.dataset.index = String(index);

      var title = document.createElement("input");
      title.type = "text";
      title.value = one.title;
      title.setAttribute("aria-label", "Title");
      title.addEventListener("input", function () {
        one.title = title.value;
        if (railFor === index) { by("rail-heading").textContent = title.value; by("file-title").value = title.value; }
      });
      card.appendChild(title);

      var about = document.createElement("p");
      about.className = "quiet";
      about.textContent = one.file.name + " · " + bytes(one.file.size);
      card.appendChild(about);

      if (one.refused) {
        var why = document.createElement("p");
        why.className = "problem";
        why.textContent = one.refused;
        card.appendChild(why);
      } else {
        // The chip says whether the file follows the batch, and opens the
        // settings card for that file.
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "pill chip-for" + (railFor === index ? " on" : "");
        chip.textContent = one.own ? "Own settings" : "Same as batch";
        chip.title = "Give this file its own settings";
        chip.addEventListener("click", function () { showFile(index); });
        card.appendChild(chip);
      }

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "plain";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () {
        chosen.splice(index, 1);
        if (railFor === index) { showBatch(); return; }
        if (railFor !== null && railFor > index) { railFor -= 1; }
        draw();
      });
      card.appendChild(remove);
      list.appendChild(card);
    });
    var count = usable().length;
    start.disabled = !count;
    start.textContent = count ? "Start: transcribe " + plural(count, "file") : "Start";
    hint.hidden = !!count;
    sayLine();
  }

  picker.addEventListener("change", function () { add(picker.files); picker.value = ""; });
  drop.addEventListener("dragover", function (event) { event.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", function () { drop.classList.remove("over"); });
  drop.addEventListener("drop", function (event) {
    event.preventDefault();
    drop.classList.remove("over");
    add(event.dataTransfer.files);
  });

  // Start: the batch is made with the card's settings; a file with its own
  // sends them, as on the Upload page. Never a case: the card has no box
  // for one here.
  start.addEventListener("click", function () {
    var files = usable();
    start.disabled = true;
    problem.hidden = true;
    var batch = Card.copyOf(settings());
    batch.case = "";
    batch.recording_type = "";
    batch.summaries = false;
    fetch("/upload/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify({
        batch: batch,
        files: files.map(function (one) {
          var sent = { name: one.file.name, title: one.title, size: one.file.size };
          if (one.own) {
            sent.settings = Card.copyOf(one.own);
            sent.settings.case = "";
            sent.settings.recording_type = "";
          }
          return sent;
        })
      })
    }).then(function (answer) {
      return answer.json().then(function (body) {
        if (!answer.ok) { throw new Error(body.error || "That did not work."); }
        return body;
      });
    }).then(function (body) {
      startUploads(files, body.recordings, body.batch);
    }).catch(function (trouble) {
      problem.textContent = trouble.message;
      problem.hidden = false;
      start.disabled = false;
    });
  });

  // The upload, as upload.js does it: three at a time, each with its line,
  // a failed one with its own Try again. When the last file is up the page
  // becomes the batch.
  function startUploads(files, recordings, batch) {
    var byKey = {};
    recordings.forEach(function (one, index) { byKey[index] = one.id; });
    files.forEach(function (one, index) { one.key = index; });
    start.hidden = true;
    hint.hidden = true;
    list.hidden = true;
    fold.hidden = true;
    progress.hidden = false;
    progress.innerHTML = "";
    var lines = {};
    files.forEach(function (one) {
      var row = document.createElement("li");
      row.className = "card";
      row.innerHTML = "<strong>" + escape(one.title) + "</strong><p class='state quiet'>Waiting</p>";
      progress.appendChild(row);
      lines[one.key] = row;
    });
    function say(one, words, isProblem) {
      var state = lines[one.key].querySelector(".state");
      state.textContent = words;
      state.className = isProblem ? "state problem" : "state quiet";
    }
    function why(error) {
      var answer = error && error.originalResponse;
      if (answer) {
        try {
          var body = JSON.parse(answer.getBody());
          if (body && body.error) { return body.error; }
        } catch (ignored) { /* not the app's own answer */ }
      }
      return "The upload did not finish. Check the connection and try again.";
    }
    function offerRetry(one) {
      var row = lines[one.key];
      if (row.querySelector("button")) { return; }
      var again = document.createElement("button");
      again.type = "button";
      again.className = "plain";
      again.textContent = "Try again";
      again.addEventListener("click", function () { again.remove(); waiting.push(one); next(); });
      row.appendChild(again);
    }
    var waiting = files.slice();
    var running = 0;
    var done = 0;
    function finishedIfDone() {
      if (waiting.length || running || done !== files.length) { return; }
      // Every file is up: the drop goes and the batch takes the page.
      dropBox.hidden = true;
      showBatch_(batch);
    }
    function next() {
      if (!waiting.length || running >= AT_ONCE) { finishedIfDone(); return; }
      var one = waiting.shift();
      running += 1;
      say(one, "Uploading");
      var upload = new tus.Upload(one.file, {
        endpoint: "/files/",
        retryDelays: [0, 1000, 3000, 5000, 10000, 30000, 60000],
        chunkSize: 50 * 1024 * 1024,
        removeFingerprintOnSuccess: true,
        metadata: { recording: byKey[one.key], filename: one.file.name },
        onProgress: function (sent, total) { say(one, "Uploading " + Math.floor((sent / total) * 100) + "%"); },
        onError: function (error) { running -= 1; say(one, why(error), true); offerRetry(one); next(); },
        onSuccess: function () { running -= 1; done += 1; say(one, "Uploaded"); next(); }
      });
      upload.findPreviousUploads().then(function (previous) {
        if (previous && previous.length) { upload.resumeFromPreviousUpload(previous[0]); }
        upload.start();
      }).catch(function () { upload.start(); });
      next();
    }
    window.addEventListener("beforeunload", function (event) {
      if (done < files.length) { event.preventDefault(); event.returnValue = ""; }
    });
    next();
  }

  // The batch -------------------------------------------------------------------------

  var batchId = section.dataset.batch || "";
  var rows = document.getElementById("bulk-rows");
  var lead = document.getElementById("bulk-lead");
  var downloadLine = document.getElementById("bulk-download");
  var cancel = document.getElementById("bulk-cancel");
  var doneBox = document.getElementById("bulk-done");
  var runningBox = document.getElementById("bulk-running");
  var asking = false;

  var STATES = {
    uploading: "Uploading", checking: "Checking the file", preparing: "Preparing the audio",
    ready: "In line", rejected: "Refused", failed: "Failed"
  };
  function words(row) {
    if (row.state === "rejected") { return ["Refused: " + (row.message || "the app would not take this file"), "warn"]; }
    if (row.state === "failed") { return ["Failed: " + (row.message || ""), "warn"]; }
    var job = row.job;
    if (!job) { return [STATES[row.state] || row.state, ""]; }
    if (job.state === "done") { return ["Ready", "ok"]; }
    if (job.state === "failed") { return ["Failed: " + (job.message || ""), "warn"]; }
    if (job.state === "cancelled") { return ["Cancelled", ""]; }
    if (job.state === "running") { return [(job.step || "Transcribing") + (job.percent ? ", " + job.percent + "%" : ""), "acc"]; }
    return [job.line || "In line", ""];
  }
  function minutes(row) {
    var m = row.minutes || 0;
    if (!m) { return ""; }
    var whole = Math.floor(m);
    var h = Math.floor(whole / 60);
    return (h ? h + " h " : "") + (whole % 60) + " min";
  }

  function drawBatch(state) {
    var tally = { done: 0, failed: 0, waiting: 0 };
    rows.innerHTML = "";
    state.recordings.forEach(function (row) {
      var said = words(row);
      if (row.job && row.job.state === "done") { tally.done += 1; }
      else if (row.state === "rejected" || row.state === "failed" || (row.job && row.job.state === "failed")) { tally.failed += 1; }
      else if (!(row.job && row.job.state === "cancelled")) { tally.waiting += 1; }
      var card = document.createElement("li");
      card.className = "card";
      card.innerHTML =
        "<div class='row'><b class='grow'>" + escape(row.title) + "</b>" +
        "<span class='muted small mono'>" + escape(minutes(row)) + "</span>" +
        "<span class='pill small " + said[1] + "'>" + escape(said[0]) + "</span>" +
        (row.has_transcript ? " <a href='/recording/" + row.id + "' class='btn small'>Open</a>" : "") +
        "</div>";
      rows.appendChild(card);
    });
    var total = state.recordings.length;
    var download = "/batch/" + batchId + "/download";
    if (state.finished) {
      runningBox.hidden = true;
      doneBox.hidden = false;
      by("bulk-done-heading").textContent = tally.done
        ? (tally.done === 1 ? "The transcript is ready" : "The " + tally.done + " transcripts are ready")
        : "This batch produced no transcripts";
      by("bulk-done-when").textContent =
        (tally.failed ? plural(tally.failed, "file") + " could not be transcribed; each row says why. " : "") +
        "Yours until you sign out or press Done with these.";
      var doneLink = by("bulk-download-done");
      doneLink.hidden = tally.done === 0;
      doneLink.href = download;
      by("bulk-clear").dataset.batch = batchId;
      return;
    }
    doneBox.hidden = true;
    runningBox.hidden = false;
    lead.textContent =
      tally.done + " of " + total + " transcribed" +
      (state.everything_done_by ? ". " + state.everything_done_by : "") +
      ". The page carries on without you, and the download stays on Home until you press Done with these.";
    downloadLine.hidden = tally.done === 0;
    downloadLine.href = download;
    downloadLine.querySelector("button").textContent = "Download the " + plural(tally.done, "transcript") + " ready";
  }

  function ask() {
    if (!batchId) { return; }
    window.UI.whenVisible().then(function () { return fetch("/batch/" + batchId + "/state", { credentials: "same-origin" }); })
      .then(function (answer) { return answer.json(); })
      .then(function (state) {
        drawBatch(state);
        if (!state.finished) { window.setTimeout(ask, EVERY); } else { asking = false; }
      })
      .catch(function () { window.setTimeout(ask, EVERY); });
  }

  function showBatch_(id) {
    batchId = id;
    section.dataset.batch = id;
    section.hidden = false;
    if (!asking) { asking = true; ask(); }
  }

  cancel.addEventListener("click", function () {
    UI.confirm({
      title: "Cancel the rest?",
      body: "What has not started is removed from your recordings and would have to be uploaded again. Transcripts already made stay.",
      ok: "Cancel the rest",
      cancel: "Keep going",
      danger: true
    }).then(function (yes) {
      if (!yes) { return; }
      fetch("/batch/" + batchId + "/cancel", { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") } })
        .then(function (answer) {
          if (answer.ok) { window.location.reload(); return; }
          UI.toast("The batch could not be cancelled.", { problem: true, icon: "warning" });
        })
        .catch(function () { UI.toast("The app did not answer. Try again.", { problem: true, icon: "warning" }); });
    });
  });

  // Transcribe more: the drop again, the finished batch kept under it.
  by("bulk-more").addEventListener("click", function () {
    dropBox.hidden = false;
    start.hidden = false;
    list.hidden = false;
    fold.hidden = false;
    progress.hidden = true;
    chosen = [];
    showBatch();
    dropBox.scrollIntoView({ block: "start", behavior: "smooth" });
  });

  // The card starts on the batch's settings.
  batchSettings = Card.read();
  showBatch();
  if (batchId) { showBatch_(batchId); }
})();

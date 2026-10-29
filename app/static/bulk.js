// Bulk transcription (v1.173.0): the drop, Start, the batch where it stands,
// the download. The same endpoints as the Upload page and the batch page
// (/upload/submit, the sidecar, /batch/<id>/state, /batch/<id>/cancel and the
// batch's download), on one page that never leaves. The upload part follows
// upload.js, three files at a time; the batch part draws the batch page's
// state feed in one list rather than two panes.

(function () {
  "use strict";

  var AT_ONCE = 3;
  var EVERY = 4000;

  var section = document.getElementById("bulk-batch");
  var dropBox = document.getElementById("bulk-drop");
  var picker = document.getElementById("picker");
  if (!section || !picker) { return; }

  var chosen = [];
  var list = document.getElementById("chosen");
  var start = document.getElementById("start");
  var hint = document.getElementById("start-hint");
  var problem = document.getElementById("submit-problem");
  var progress = document.getElementById("progress");
  var drop = document.getElementById("drop");

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

  // The files -------------------------------------------------------------------------

  function add(files) {
    Array.prototype.forEach.call(files, function (file) {
      var refused = null;
      if (/\.(zip|rar|7z|tar|gz)$/i.test(file.name)) {
        refused = "Zip files are not accepted. Choose the recordings inside it instead.";
      } else if (file.size === 0) {
        refused = "The file is empty";
      }
      chosen.push({ file: file, title: withoutExtension(file.name), refused: refused });
    });
    draw();
  }

  function usable() { return chosen.filter(function (one) { return !one.refused; }); }

  function draw() {
    list.innerHTML = "";
    chosen.forEach(function (one, index) {
      var card = document.createElement("li");
      card.className = one.refused ? "card refused" : "card";
      card.innerHTML =
        "<strong>" + escape(one.title) + "</strong>" +
        "<p class='quiet'>" + escape(one.file.name) + " · " + bytes(one.file.size) + "</p>" +
        (one.refused ? "<p class='problem'>" + escape(one.refused) + "</p>" : "");
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "plain";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () { chosen.splice(index, 1); draw(); });
      card.appendChild(remove);
      list.appendChild(card);
    });
    var count = usable().length;
    start.disabled = !count;
    start.textContent = count ? "Start: transcribe " + plural(count, "file") : "Start";
    hint.hidden = !!count;
  }

  picker.addEventListener("change", function () { add(picker.files); picker.value = ""; });
  drop.addEventListener("dragover", function (event) { event.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", function () { drop.classList.remove("over"); });
  drop.addEventListener("drop", function (event) {
    event.preventDefault();
    drop.classList.remove("over");
    add(event.dataTransfer.files);
  });

  // Start: the batch is made with the two options and nothing else chosen;
  // speakers off, no vocabulary, no context, no case, as the page says.
  start.addEventListener("click", function () {
    var files = usable();
    start.disabled = true;
    problem.hidden = true;
    var translate = document.getElementById("translate");
    fetch("/upload/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify({
        batch: {
          diarize: false,
          translate: !!(translate && translate.checked && !translate.disabled),
          language: document.getElementById("language").value,
          vocabulary: [],
          context: ""
        },
        files: files.map(function (one) { return { name: one.file.name, title: one.title, size: one.file.size }; })
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
    progress.hidden = false;
    progress.innerHTML = "";
    var lines = {};
    files.forEach(function (one) {
      var line = document.createElement("li");
      line.className = "card";
      line.innerHTML = "<strong>" + escape(one.title) + "</strong><p class='state quiet'>Waiting</p>";
      progress.appendChild(line);
      lines[one.key] = line;
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
      var line = lines[one.key];
      if (line.querySelector("button")) { return; }
      var again = document.createElement("button");
      again.type = "button";
      again.className = "plain";
      again.textContent = "Try again";
      again.addEventListener("click", function () { again.remove(); waiting.push(one); next(); });
      line.appendChild(again);
    }
    var waiting = files.slice();
    var running = 0;
    var done = 0;
    function finishedIfDone() {
      if (waiting.length || running || done !== files.length) { return; }
      // Every file is up: the drop goes and the batch takes the page.
      dropBox.hidden = true;
      showBatch(batch);
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

  function draw(state) {
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
      document.getElementById("bulk-done-heading").textContent = tally.done
        ? (tally.done === 1 ? "The transcript is ready" : "The " + tally.done + " transcripts are ready")
        : "This batch produced no transcripts";
      document.getElementById("bulk-done-when").textContent =
        (tally.failed ? plural(tally.failed, "file") + " could not be transcribed; each row says why. " : "") +
        "Yours until you sign out or press Done with these.";
      var doneLink = document.getElementById("bulk-download-done");
      doneLink.hidden = tally.done === 0;
      doneLink.href = download;
      document.getElementById("bulk-clear").dataset.batch = batchId;
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
        draw(state);
        if (!state.finished) { window.setTimeout(ask, EVERY); } else { asking = false; }
      })
      .catch(function () { window.setTimeout(ask, EVERY); });
  }

  function showBatch(id) {
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
  document.getElementById("bulk-more").addEventListener("click", function () {
    dropBox.hidden = false;
    start.hidden = false;
    list.hidden = false;
    progress.hidden = true;
    chosen = [];
    draw();
    dropBox.scrollIntoView({ block: "start", behavior: "smooth" });
  });

  if (batchId) { showBatch(batchId); }
})();

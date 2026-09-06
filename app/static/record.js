// The Record page: record from the microphone, send the sound to the server
// as it goes, and wait for the finished transcript.
//
// The browser encodes the sound (Opus in WebM) and hands it to the upload
// sidecar as an upload of unknown length: each piece is appended as the
// recorder produces it, so a page that dies loses at most the last few
// seconds. Nothing rougher than the finished transcript is ever shown: the
// page records, then says where the recording stands until the viewer opens.

(function () {
  "use strict";

  var page = document.getElementById("record");
  if (!page || !window.tus) { return; }

  var csrf = page.dataset.csrf;
  var LONGEST = parseInt(page.dataset.longest, 10) || 10800;
  // How much is gathered before a piece goes to the server: about ten
  // seconds of speech at the rate below.
  var PIECE = 64 * 1024;
  var BITS_PER_SECOND = 48000;

  var before = document.getElementById("before");
  var during = document.getElementById("during");
  var after = document.getElementById("after");

  function show(section) {
    [before, during, after].forEach(function (one) { one.hidden = one !== section; });
  }

  function problem(where, text) {
    var box = document.getElementById(where);
    box.textContent = text || "";
    box.hidden = !text;
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  function clock(seconds) {
    var s = Math.floor(seconds);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
    var mm = (h ? String(m).padStart(2, "0") : String(m));
    return (h ? h + ":" : "") + mm + ":" + String(r).padStart(2, "0");
  }

  // A source the tus client reads from: pieces arrive from the recorder and
  // are handed out in order; when the recorder stops, the source ends.
  function pieceSource() {
    var pieces = [];
    var waiting = null;
    var ended = false;
    return {
      push: function (bytes) {
        pieces.push(bytes);
        if (waiting) { var w = waiting; waiting = null; w(); }
      },
      end: function () {
        ended = true;
        if (waiting) { var w = waiting; waiting = null; w(); }
      },
      read: function () {
        if (pieces.length) { return Promise.resolve({ done: false, value: pieces.shift() }); }
        if (ended) { return Promise.resolve({ done: true, value: undefined }); }
        return new Promise(function (resolve) { waiting = resolve; }).then(function () {
          if (pieces.length) { return { done: false, value: pieces.shift() }; }
          return { done: true, value: undefined };
        });
      }
    };
  }

  var recording = null;   // { id, title, caseUrl }
  var recorder = null;
  var stream = null;
  var audio = null;       // AudioContext
  var upload = null;
  var source = null;
  var startedAt = 0;      // performance.now() when recording (re)started
  var recordedBefore = 0; // seconds recorded before the current stretch
  var paused = false;
  var pauseBegan = 0;
  var pauses = [];
  var ended = false;
  var ticker = null;
  var uploadDone = false;

  function elapsed() {
    if (!recorder) { return 0; }
    if (paused) { return recordedBefore; }
    return recordedBefore + (performance.now() - startedAt) / 1000;
  }

  // Before: Record -------------------------------------------------------------

  document.getElementById("start").addEventListener("click", function () {
    var caseId = document.getElementById("record-case").value;
    if (!caseId) { problem("before-problem", "Choose a case to record into."); return; }
    problem("before-problem", "");
    var button = this;
    button.disabled = true;

    // The microphone first, so that a refused microphone makes no recording.
    navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } })
      .then(function (got) {
        stream = got;
        return post("/record/start", {
          case: caseId,
          recording_type: document.getElementById("record-type").value,
          title: document.getElementById("record-title").value,
          language: document.getElementById("record-language").value,
          translate: document.getElementById("record-translate").checked
        });
      })
      .then(function (answer) {
        if (!answer.ok) {
          stopStream();
          throw new Error(answer.said.why || "The recording could not start.");
        }
        recording = { id: answer.said.id, title: answer.said.title, filename: answer.said.filename, caseUrl: answer.said.case };
        LONGEST = answer.said.longest_seconds || LONGEST;
        begin();
      })
      .catch(function (error) {
        button.disabled = false;
        var why = error && error.name === "NotAllowedError"
          ? "The browser did not allow the microphone. Allow it for this site and try again."
          : (error && error.name === "NotFoundError")
            ? "No microphone was found on this computer."
            : (error && error.message) || "The recording could not start.";
        problem("before-problem", why);
      });
  });

  function stopStream() {
    if (stream) { stream.getTracks().forEach(function (track) { track.stop(); }); stream = null; }
    if (audio) { audio.close().catch(function () {}); audio = null; }
  }

  // During: the recorder, the upload, the clock and the meter -------------------

  function begin() {
    source = pieceSource();
    var mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
    recorder = new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: BITS_PER_SECOND });
    recorder.addEventListener("dataavailable", function (event) {
      if (event.data && event.data.size) {
        event.data.arrayBuffer().then(function (buffer) { source.push(new Uint8Array(buffer)); });
      }
    });
    recorder.addEventListener("stop", function () {
      // The last piece follows the stop event; the source ends after it.
      window.setTimeout(source.end, 300);
    });

    upload = new tus.Upload(source, {
      endpoint: "/files/",
      uploadLengthDeferred: true,
      chunkSize: PIECE,
      retryDelays: [0, 1000, 3000, 5000, 10000],
      metadata: { recording: recording.id, filename: recording.filename, live: "1" },
      onError: function (error) {
        problem("during-problem", "The server stopped taking the recording: " + (error && error.message ? error.message : error) + ". What was sent is kept.");
        endNow("disk");
      },
      onSuccess: function () {
        uploadDone = true;
        if (ended) { watch(); }
      }
    });
    upload.start();
    // The sidecar's id for this upload, so an early end can take the pieces.
    window.setTimeout(function () {
      if (upload && upload.url) {
        post("/record/" + recording.id + "/upload", { tus: upload.url.split("/").pop() });
      }
    }, 1500);

    recorder.start(5000);
    startedAt = performance.now();
    document.getElementById("during-title").textContent = recording.title;
    show(during);
    meter();
    ticker = window.setInterval(tick, 500);
  }

  function tick() {
    var seconds = elapsed();
    document.getElementById("clock").textContent = clock(seconds);
    if (seconds >= LONGEST) { endNow("limit"); }
  }

  function meter() {
    try {
      audio = new (window.AudioContext || window.webkitAudioContext)();
      var analyser = audio.createAnalyser();
      analyser.fftSize = 512;
      audio.createMediaStreamSource(stream).connect(analyser);
      var data = new Uint8Array(analyser.frequencyBinCount);
      var bar = document.getElementById("meter");
      (function draw() {
        if (!recorder) { return; }
        analyser.getByteTimeDomainData(data);
        var peak = 0;
        for (var i = 0; i < data.length; i += 1) { peak = Math.max(peak, Math.abs(data[i] - 128)); }
        bar.style.width = Math.min(100, Math.round((peak / 128) * 140)) + "%";
        window.requestAnimationFrame(draw);
      })();
    } catch (error) { /* no meter, no harm */ }
  }

  document.getElementById("pause").addEventListener("click", function () {
    if (!recorder) { return; }
    if (!paused) {
      recordedBefore = elapsed();
      recorder.pause();
      paused = true;
      pauseBegan = performance.now();
      this.textContent = "Resume";
      document.getElementById("rec-pill").textContent = "Paused";
      document.getElementById("rec-pill").className = "pill warn";
    } else {
      pauses.push({ at: Math.round(recordedBefore * 10) / 10, seconds: Math.round((performance.now() - pauseBegan) / 100) / 10 });
      recorder.resume();
      paused = false;
      startedAt = performance.now();
      this.textContent = "Pause";
      document.getElementById("rec-pill").textContent = "Recording";
      document.getElementById("rec-pill").className = "pill danger";
    }
  });

  document.getElementById("stop").addEventListener("click", function () { endNow("stop"); });

  function endNow(how) {
    if (ended || !recorder) { return; }
    ended = true;
    var seconds = elapsed();
    window.clearInterval(ticker);
    if (paused) { pauses.push({ at: recordedBefore, seconds: Math.round((performance.now() - pauseBegan) / 100) / 10 }); }
    try { recorder.stop(); } catch (error) { source.end(); }
    stopStream();
    recorder = null;
    document.getElementById("after-title").textContent = recording.title;
    document.getElementById("open-case").href = recording.caseUrl;
    show(after);
    post("/record/" + recording.id + "/ended", { how: how, pauses: pauses, seconds: Math.round(seconds * 10) / 10 })
      .then(function () { if (uploadDone || how !== "stop") { watch(); } });
  }

  // Leaving the page ends the recording with what has been sent. A beacon
  // carries the token in its body, since it can carry no headers.
  window.addEventListener("pagehide", function () {
    if (!recorder || ended) { return; }
    var form = new FormData();
    form.append("csrfmiddlewaretoken", csrf);
    form.append("how", "closed");
    form.append("pauses", JSON.stringify(pauses));
    form.append("seconds", String(Math.round(elapsed() * 10) / 10));
    navigator.sendBeacon("/record/" + recording.id + "/ended", form);
  });
  window.addEventListener("beforeunload", function (event) {
    if (recorder && !ended) { event.preventDefault(); event.returnValue = ""; }
  });

  // After: the queue line, until the transcript opens ----------------------------

  var watching = null;
  function watch() {
    if (watching) { return; }
    var line = document.getElementById("after-line");
    var pill = document.getElementById("after-pill");
    function ask() {
      fetch("/record/" + recording.id + "/state", { cache: "no-store" })
        .then(function (answer) { return answer.json(); })
        .then(function (said) {
          line.textContent = said.says;
          if (said.state === "ready") {
            pill.textContent = "Ready";
            pill.className = "pill ok";
            var open = document.getElementById("open-viewer");
            open.href = said.viewer;
            open.hidden = false;
            window.clearInterval(watching);
            window.location = said.viewer;
          } else if (said.state === "failed") {
            pill.textContent = "Failed";
            pill.className = "pill danger";
            window.clearInterval(watching);
          } else {
            pill.textContent = said.state === "queued" ? "In the queue" : "Transcribing";
          }
        })
        .catch(function () {});
    }
    ask();
    watching = window.setInterval(ask, 4000);
  }
})();

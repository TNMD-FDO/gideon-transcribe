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
  var CASE = page.dataset.case || "";
  var LONGEST = parseInt(page.dataset.longest, 10) || 10800;

  // The style chosen: a dictation, a meeting in the room, a call on this
  // computer. Each shows what it needs and no more.
  function style() {
    var chosen = document.querySelector("input[name='style']:checked");
    return chosen ? chosen.value : "dictation";
  }
  function applyStyle() {
    var which = style();
    document.querySelectorAll(".styles .style").forEach(function (card) {
      card.classList.toggle("on", card.querySelector("input").checked);
    });
    document.getElementById("people-field").hidden = which === "dictation";
    document.getElementById("computer-help").hidden = which !== "call";
    var tick = document.getElementById("record-computer");
    if (which === "call") { tick.checked = true; tick.disabled = true; }
    else { tick.disabled = false; if (tick.dataset.forced) { tick.checked = false; } }
    tick.dataset.forced = which === "call" ? "1" : "";
  }
  document.querySelectorAll("input[name='style']").forEach(function (radio) {
    radio.addEventListener("change", applyStyle);
  });
  applyStyle();
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
  var stream = null;      // the microphone
  var computer = null;    // what the computer plays, when asked for
  var computerEndedAt = null;
  var mixed = null;       // the two together, one channel each
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
  var people = [];        // the names expected, buttons while recording
  var taps = [];          // { at, name }
  var marks = [];         // { at, word }

  function elapsed() {
    if (!recorder) { return 0; }
    if (paused) { return recordedBefore; }
    return recordedBefore + (performance.now() - startedAt) / 1000;
  }

  // Before: the people expected -----------------------------------------------

  var expected = document.getElementById("people-expected");

  function drawPeople() {
    expected.innerHTML = people.map(function (name) {
      return "<span class='btn small' data-name='" + name.replace(/'/g, "&#39;") + "'>" + name.replace(/</g, "&lt;") +
        " <button type='button' class='ghost tiny drop' aria-label='Remove'>&times;</button></span>";
    }).join("") || "<span class='muted small'>Nobody yet.</span>";
  }

  function loadPeople() {
    if (!CASE) { people = []; drawPeople(); return; }
    fetch("/record/people?case=" + encodeURIComponent(CASE))
      .then(function (answer) { return answer.json(); })
      .then(function (said) { people = said.people || []; drawPeople(); })
      .catch(function () { people = []; drawPeople(); });
  }
  loadPeople();

  function addPerson() {
    var box = document.getElementById("record-person");
    var name = box.value.trim().slice(0, 60);
    if (name && people.indexOf(name) < 0) { people.push(name); drawPeople(); }
    box.value = "";
  }
  document.getElementById("add-person").addEventListener("click", addPerson);
  document.getElementById("record-person").addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); addPerson(); }
  });
  expected.addEventListener("click", function (event) {
    var drop = event.target.closest(".drop");
    if (!drop) { return; }
    var name = drop.parentNode.dataset.name;
    people = people.filter(function (one) { return one !== name; });
    drawPeople();
  });

  // Before: Record -------------------------------------------------------------

  document.getElementById("start").addEventListener("click", function () {
    var caseId = CASE;
    problem("before-problem", "");
    var button = this;
    button.disabled = true;

    var withComputer = document.getElementById("record-computer").checked || style() === "call";

    // The microphone first, so that a refused microphone makes no recording;
    // then the computer's sound, when asked for, which the browser offers
    // only as part of sharing a screen: the picture is dropped at once.
    navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } })
      .then(function (got) {
        stream = got;
        if (!withComputer) { return null; }
        return navigator.mediaDevices.getDisplayMedia({ video: true, audio: true }).then(function (shared) {
          shared.getVideoTracks().forEach(function (track) { track.stop(); });
          if (!shared.getAudioTracks().length) {
            shared.getTracks().forEach(function (track) { track.stop(); });
            throw new Error("The sound was not shared. Choose the whole screen and tick Share system audio (Edge) or Share audio (Chrome), then try again.");
          }
          computer = new MediaStream(shared.getAudioTracks());
          return null;
        });
      })
      .then(function () {
        return post("/record/start", {
          case: caseId,
          dictation: !caseId,
          style: style(),
          recording_type: document.getElementById("record-type").value,
          title: document.getElementById("record-title").value,
          language: document.getElementById("record-language").value,
          translate: document.getElementById("record-translate").checked,
          with_computer: !!computer
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
    if (computer) { computer.getTracks().forEach(function (track) { track.stop(); }); computer = null; }
    if (audio) { audio.close().catch(function () {}); audio = null; }
  }

  // The two sources as one stream of two channels: the microphone on the
  // first, the computer on the second, each mixed down to one channel. The
  // pipeline reads them as the two sides of a call.
  function mix() {
    audio = new (window.AudioContext || window.webkitAudioContext)();
    var merger = audio.createChannelMerger(2);
    var out = audio.createMediaStreamDestination();
    out.channelCount = 2;
    audio.createMediaStreamSource(stream).connect(merger, 0, 0);
    if (computer) {
      audio.createMediaStreamSource(computer).connect(merger, 0, 1);
      computer.getAudioTracks()[0].addEventListener("ended", function () {
        // Sharing stopped from the browser's own bar: the microphone goes on
        // alone, and the transcript's provenance says from when.
        if (computerEndedAt === null && recorder) {
          computerEndedAt = Math.round(elapsed() * 10) / 10;
          document.getElementById("during-line").textContent = "The computer's sound stopped at " + clock(computerEndedAt) + "; the microphone is still recording.";
          document.getElementById("computer-row").hidden = true;
        }
      });
    }
    merger.connect(out);
    return out.stream;
  }

  // During: the recorder, the upload, the clock and the meter -------------------

  function begin() {
    source = pieceSource();
    var mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
    mixed = computer ? mix() : stream;
    recorder = new MediaRecorder(mixed, { mimeType: mime, audioBitsPerSecond: computer ? BITS_PER_SECOND * 2 : BITS_PER_SECOND });
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
    document.getElementById("computer-row").hidden = !computer;
    drawTapButtons();
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
      if (!audio) { audio = new (window.AudioContext || window.webkitAudioContext)(); }
      var meters = [[stream, document.getElementById("meter")]];
      if (computer) { meters.push([computer, document.getElementById("meter-computer")]); }
      var live = meters.map(function (pair) {
        var analyser = audio.createAnalyser();
        analyser.fftSize = 512;
        audio.createMediaStreamSource(pair[0]).connect(analyser);
        return { analyser: analyser, bar: pair[1], data: new Uint8Array(analyser.frequencyBinCount) };
      });
      (function draw() {
        if (!recorder) { return; }
        live.forEach(function (one) {
          one.analyser.getByteTimeDomainData(one.data);
          var peak = 0;
          for (var i = 0; i < one.data.length; i += 1) { peak = Math.max(peak, Math.abs(one.data[i] - 128)); }
          one.bar.style.width = Math.min(100, Math.round((peak / 128) * 140)) + "%";
        });
        window.requestAnimationFrame(draw);
      })();
    } catch (error) { /* no meter, no harm */ }
  }

  // During: who is talking, and the moments that matter -------------------------

  var tapButtons = document.getElementById("people-during");

  function drawTapButtons() {
    tapButtons.innerHTML = people.map(function (name) {
      return "<button type='button' class='btn small tap' data-name='" + name.replace(/'/g, "&#39;") + "'>" + name.replace(/</g, "&lt;") + "</button>";
    }).join("");
    tapButtons.hidden = !people.length;
  }

  tapButtons.addEventListener("click", function (event) {
    var button = event.target.closest(".tap");
    if (!button || !recorder || paused) { return; }
    taps.push({ at: Math.round(elapsed() * 10) / 10, name: button.dataset.name });
    tapButtons.querySelectorAll(".tap").forEach(function (one) { one.classList.toggle("on", one === button); });
  });

  var markBox = document.getElementById("mark-box");
  var markWord = document.getElementById("mark-word");
  var pendingMark = null;

  function dropMark() {
    if (!recorder || paused) { return; }
    finishMark();
    pendingMark = { at: Math.round(elapsed() * 10) / 10, word: "" };
    marks.push(pendingMark);
    document.getElementById("marks-count").textContent = marks.length + (marks.length === 1 ? " mark" : " marks");
    markWord.value = "";
    markBox.hidden = false;
    markWord.focus();
  }
  function finishMark() {
    if (pendingMark) { pendingMark.word = markWord.value.trim().slice(0, 80); pendingMark = null; }
    markBox.hidden = true;
  }
  document.getElementById("mark").addEventListener("click", dropMark);
  document.getElementById("mark-done").addEventListener("click", finishMark);
  markWord.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === "Escape") { event.preventDefault(); finishMark(); }
  });
  document.addEventListener("keydown", function (event) {
    if (during.hidden || !recorder) { return; }
    var typing = event.target && (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA");
    if ((event.key === "m" || event.key === "M") && !typing) { event.preventDefault(); dropMark(); }
  });

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
    finishMark();
    post("/record/" + recording.id + "/ended", { how: how, pauses: pauses, seconds: Math.round(seconds * 10) / 10, computer_ended_at: computerEndedAt, taps: taps, marks: marks })
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
    if (computerEndedAt !== null) { form.append("computer_ended_at", String(computerEndedAt)); }
    form.append("taps", JSON.stringify(taps));
    form.append("marks", JSON.stringify(marks));
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
            // A recording kept on its own lands on the Record tab, on top,
            // with Play to check it and Send to beside it; a case's opens in
            // the viewer with the case at its side.
            window.location = CASE ? said.viewer : "/record?new=" + recording.id;
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

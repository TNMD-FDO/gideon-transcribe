// The Interpreter's Session page (Phase 3, chapter 3), text only.
//
// The microphone is recorded twice at once: one recorder streams the whole
// session to the sidecar as the Live recording (as record.js does), and a
// second is started and stopped per Turn, so each Turn's audio reaches the
// server the moment the person stops talking and comes back heard and
// translated a second or two later. Turns end automatically at a pause (the
// level meter falls quiet for three quarters of a second), or by hand with
// the two hold-to-talk buttons. Nothing rougher than the Turn as heard is
// ever shown, and the notice at the top says what the machine is.

(function () {
  "use strict";

  var page = document.getElementById("interpret");
  if (!page || !window.tus) { return; }

  var csrf = page.dataset.csrf;
  var CASE = page.dataset.case || "";
  var LONGEST = parseInt(page.dataset.longest, 10) || 3 * 3600;
  var AUTOMATIC = page.dataset.turnTaking !== "hold";
  var READBACK = page.dataset.readback === "1";

  var PIECE = 64 * 1024;
  // A Turn ends after this much quiet, and is sent only if it lasted this long.
  var PAUSE_MS = 750;
  var SHORTEST_TURN_MS = 500;
  // The meter's level above which somebody is talking (0 to 1). Tuned in the
  // room; the meter bar shows the level, so a room's floor is visible.
  var TALK_LEVEL = 0.06;

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  function problem(id, text) {
    var box = document.getElementById(id);
    box.textContent = text || "";
    box.hidden = !text;
  }

  function clock(seconds) {
    var s = Math.floor(seconds);
    var m = Math.floor(s / 60);
    return (m < 10 ? "0" : "") + m + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
  }

  // The stream source the tus client reads pieces from.
  function pieceSource() {
    var pieces = [];
    var waiting = null;
    var ended = false;
    return {
      push: function (bytes) { pieces.push(bytes); if (waiting) { var w = waiting; waiting = null; w(); } },
      end: function () { ended = true; if (waiting) { var w = waiting; waiting = null; w(); } },
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

  var before = document.getElementById("before");
  var during = document.getElementById("during");
  var after = document.getElementById("after");
  function show(section) {
    [before, during, after].forEach(function (one) { one.hidden = one !== section; });
  }

  var session = null;     // { id, title, after }
  var stream = null;
  var recorder = null;    // the whole session, streamed
  var source = null;
  var upload = null;
  var turnRecorder = null; // the Turn in progress
  var turnStartedAt = 0;   // recorded seconds
  var turnSide = "";       // "visitor" or "staff" while a button is held
  var turnPieces = [];
  var startedAt = 0;
  var recordedBefore = 0;
  var paused = false;
  var pauseBegan = 0;
  var pauses = [];
  var ended = false;
  var ticker = null;
  var uploadDone = false;
  var audio = null;
  var lastNumber = 0;
  var known = {};          // number -> turn as last drawn

  function elapsed() {
    if (!recorder) { return 0; }
    if (paused) { return recordedBefore; }
    return recordedBefore + (performance.now() - startedAt) / 1000;
  }

  // Before -------------------------------------------------------------------------

  document.getElementById("start").addEventListener("click", function () {
    problem("before-problem", "");
    var language = document.getElementById("visitor-language").value;
    var title = document.getElementById("session-title").value;
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      .then(function (mic) {
        stream = mic;
        return post("/record/interpret/start", { case: CASE, language: language, title: title });
      })
      .then(function (answer) {
        if (!answer.ok) { throw new Error(answer.said.why || "The session could not start."); }
        session = answer.said;
        LONGEST = session.longest_seconds || LONGEST;
        begin();
      })
      .catch(function (error) {
        if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
        problem("before-problem", error && error.message ? error.message : "The microphone could not be opened.");
      });
  });

  function begin() {
    source = pieceSource();
    recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 32000 });
    recorder.addEventListener("dataavailable", function (event) {
      if (event.data && event.data.size) {
        event.data.arrayBuffer().then(function (buffer) { source.push(new Uint8Array(buffer)); });
      }
    });
    recorder.addEventListener("stop", function () { window.setTimeout(source.end, 300); });
    upload = new tus.Upload(source, {
      endpoint: "/files/",
      uploadLengthDeferred: true,
      chunkSize: PIECE,
      retryDelays: [0, 1000, 3000, 5000, 10000],
      metadata: { recording: session.id, filename: session.filename, live: "1" },
      onError: function (error) {
        problem("during-problem", "The server stopped taking the recording: " + (error && error.message ? error.message : error) + ". What was sent is kept.");
        endNow("disk");
      },
      onSuccess: function () { uploadDone = true; if (ended) { finishPage(); } }
    });
    upload.start();
    window.setTimeout(function () {
      if (upload && upload.url) { post("/record/" + session.id + "/upload", { tus: upload.url.split("/").pop() }); }
    }, 1500);
    recorder.start(5000);
    startedAt = performance.now();

    drawNotice(session.notice);
    languageLine(session.language_name);
    document.getElementById("talk-help").textContent = AUTOMATIC
      ? "Just talk: a turn ends at a pause. Hold a button instead when the room is loud."
      : "Hold a button while speaking, release when done.";
    show(during);
    listen();
    ticker = window.setInterval(tick, 500);
    poll();
  }

  function drawNotice(lines) {
    var box = document.getElementById("notice-during");
    box.innerHTML = "";
    (lines || []).forEach(function (line, index) {
      if (index) { box.appendChild(document.createElement("br")); }
      var span = document.createElement("span");
      span.className = "notice-line";
      span.textContent = line;
      box.appendChild(span);
    });
  }

  function languageLine(name) {
    document.getElementById("language-line").textContent = name
      ? "Visitor: " + name : "Visitor: language not heard yet";
    document.getElementById("visitor-heading").textContent = name ? "Visitor (" + name + ")" : "Visitor";
  }

  function tick() {
    var seconds = elapsed();
    document.getElementById("clock").textContent = clock(seconds);
    if (seconds >= LONGEST) { endNow("limit"); }
  }

  // Turns --------------------------------------------------------------------------------
  //
  // The level meter decides when a Turn starts and ends in automatic mode; a
  // held button decides in both modes and names the side.

  var analyser = null;
  var data = null;
  var talking = false;
  var quietSince = 0;
  var talkingSince = 0;

  function listen() {
    try {
      if (!audio) { audio = new (window.AudioContext || window.webkitAudioContext)(); }
      analyser = audio.createAnalyser();
      analyser.fftSize = 1024;
      audio.createMediaStreamSource(stream).connect(analyser);
      data = new Uint8Array(analyser.fftSize);
    } catch (error) { analyser = null; }
    (function frame() {
      if (!recorder) { return; }
      var level = 0;
      if (analyser) {
        analyser.getByteTimeDomainData(data);
        var sum = 0;
        for (var i = 0; i < data.length; i++) { var v = (data[i] - 128) / 128; sum += v * v; }
        level = Math.sqrt(sum / data.length);
      }
      document.getElementById("meter").style.width = Math.min(100, level * 300) + "%";
      if (AUTOMATIC && !paused && !turnSide) { automatic(level); }
      window.requestAnimationFrame(frame);
    })();
  }

  function automatic(level) {
    var now = performance.now();
    if (level >= TALK_LEVEL) {
      quietSince = 0;
      if (!talking) { talking = true; talkingSince = now; beginTurn(""); }
      return;
    }
    if (!talking) { return; }
    if (!quietSince) { quietSince = now; return; }
    if (now - quietSince >= PAUSE_MS) {
      talking = false;
      quietSince = 0;
      endTurn(now - talkingSince >= SHORTEST_TURN_MS + PAUSE_MS);
    }
  }

  function beginTurn(side) {
    if (turnRecorder || !stream) { return; }
    turnPieces = [];
    turnStartedAt = Math.max(0, elapsed() - 0.3);
    turnRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus", audioBitsPerSecond: 32000 });
    turnRecorder.addEventListener("dataavailable", function (event) {
      if (event.data && event.data.size) { turnPieces.push(event.data); }
    });
    turnRecorder.start();
    if (side) { document.getElementById("hold-" + side).classList.add("on"); }
  }

  function endTurn(worthSending) {
    if (!turnRecorder) { return; }
    var side = turnSide;
    var endedAt = Math.round(elapsed() * 10) / 10;
    var startAt = Math.round(turnStartedAt * 10) / 10;
    var finishing = turnRecorder;
    turnRecorder = null;
    finishing.addEventListener("stop", function () {
      document.querySelectorAll(".hold.on").forEach(function (b) { b.classList.remove("on"); });
      if (!worthSending || !turnPieces.length) { return; }
      var blob = new Blob(turnPieces, { type: "audio/webm" });
      var form = new FormData();
      form.append("audio", blob, "turn.webm");
      form.append("start", String(startAt));
      form.append("end", String(endedAt));
      form.append("side", side);
      fetch("/record/" + session.id + "/turn", { method: "POST", headers: { "X-CSRFToken": csrf }, body: form })
        .then(function (answer) { if (!answer.ok) { problem("during-problem", "A turn could not be sent."); } })
        .catch(function () { problem("during-problem", "A turn could not be sent."); });
    });
    try { finishing.stop(); } catch (error) { /* already stopped */ }
  }

  // Hold to talk: the button names the side and brackets the Turn.
  document.querySelectorAll(".hold").forEach(function (button) {
    function down(event) {
      event.preventDefault();
      if (paused || turnSide) { return; }
      if (talking) { talking = false; quietSince = 0; endTurn(true); }
      turnSide = button.dataset.side;
      beginTurn(turnSide);
    }
    function up() {
      if (!turnSide) { return; }
      var held = performance.now() - turnStartedAtMs;
      endTurn(held >= SHORTEST_TURN_MS);
      turnSide = "";
    }
    var turnStartedAtMs = 0;
    button.addEventListener("pointerdown", function (event) { turnStartedAtMs = performance.now(); down(event); });
    button.addEventListener("pointerup", up);
    button.addEventListener("pointerleave", up);
    button.addEventListener("pointercancel", up);
  });

  // Typed Turns and the quick phrases: words instead of sound, same path after.
  function sendTyped(side, text) {
    if (!text.trim()) { return; }
    var at = Math.round(elapsed() * 10) / 10;
    post("/record/" + session.id + "/turn", { typed: text.trim(), side: side, start: at, end: at })
      .then(function (answer) { if (!answer.ok) { problem("during-problem", answer.said.why || "That could not be sent."); } });
  }
  document.getElementById("type-send").addEventListener("click", function () {
    var box = document.getElementById("type-text");
    sendTyped(document.getElementById("type-side").value, box.value);
    box.value = "";
  });
  document.getElementById("type-text").addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); document.getElementById("type-send").click(); }
  });
  document.getElementById("phrases").addEventListener("click", function (event) {
    var button = event.target.closest(".phrase");
    if (button) { sendTyped("staff", button.dataset.phrase); }
  });

  // The rows -----------------------------------------------------------------------------

  function poll() {
    if (!session) { return; }
    fetch("/record/" + session.id + "/turns?since=" + lastNumber, { cache: "no-store" })
      .then(function (answer) { return answer.json(); })
      .then(function (said) {
        (said.turns || []).forEach(draw);
        if (said.language_name) { languageLine(said.language_name); }
        if (said.notice) { drawNotice(said.notice); }
      })
      .catch(function () {})
      .then(function () { if (recorder || document.querySelector(".turn.waiting")) { window.setTimeout(poll, 1000); } });
  }

  function rowFor(number, side) {
    var list = document.getElementById(side === "staff" ? "turns-staff" : "turns-visitor");
    var row = document.getElementById("turn-" + number);
    if (!row) {
      row = document.createElement("li");
      row.id = "turn-" + number;
      row.className = "turn";
      row.innerHTML = "<div class='heard'></div><div class='said muted'></div><div class='state small muted'></div>";
      list.appendChild(row);
    } else if (row.parentNode !== list) {
      list.appendChild(row);
    }
    return row;
  }

  // Each Turn is drawn once per state, in its own column: what the person
  // said as heard (the Readback, in their own language), and under it the
  // translation for the other side. A Turn whose side is not yet known waits
  // in the Visitor's column until the language says.
  function draw(turn) {
    var was = known[turn.number];
    if (was && was.state === turn.state && was.translation === turn.translation && was.side === turn.side) { return; }
    known[turn.number] = turn;
    lastNumber = Math.max(lastNumber, turn.state === "done" || turn.state === "failed" ? turn.number : lastNumber);
    var row = rowFor(turn.number, turn.side || "visitor");
    row.classList.toggle("waiting", turn.state !== "done" && turn.state !== "failed");
    row.classList.toggle("typed", !!turn.typed);
    var heard = row.querySelector(".heard");
    var said = row.querySelector(".said");
    var state = row.querySelector(".state");
    heard.textContent = READBACK || turn.side === "staff" ? (turn.heard || "") : "";
    said.textContent = turn.translation || "";
    said.classList.toggle("big", !!turn.translation);
    if (turn.state === "hearing") { state.textContent = "hearing"; }
    else if (turn.state === "translating") { state.textContent = "translating"; }
    else if (turn.state === "failed") { state.textContent = "could not be " + (turn.heard ? "translated" : "heard") + (turn.failure ? " (" + turn.failure + ")" : "") + ". Say it again."; }
    else if (!turn.heard && !turn.typed) { state.textContent = "nothing heard"; }
    else { state.textContent = clock(turn.start); }
    var column = document.getElementById(turn.side === "staff" ? "turns-staff" : "turns-visitor");
    column.parentNode.scrollTop = column.parentNode.scrollHeight;
  }

  document.getElementById("swap-columns").addEventListener("click", function () {
    document.getElementById("columns").classList.toggle("swapped");
  });

  // Pause, Stop, leaving ------------------------------------------------------------------

  document.getElementById("pause").addEventListener("click", function () {
    if (!recorder) { return; }
    if (!paused) {
      if (talking) { talking = false; endTurn(true); }
      recordedBefore = elapsed();
      recorder.pause();
      paused = true;
      pauseBegan = performance.now();
      this.textContent = "Resume";
      document.getElementById("rec-pill").textContent = "Paused";
    } else {
      pauses.push({ at: Math.round(recordedBefore * 10) / 10, seconds: Math.round((performance.now() - pauseBegan) / 100) / 10 });
      recorder.resume();
      paused = false;
      startedAt = performance.now();
      this.textContent = "Pause";
      document.getElementById("rec-pill").textContent = "Recording";
    }
  });

  document.getElementById("stop").addEventListener("click", function () { endNow("stop"); });

  function endNow(how) {
    if (ended || !recorder) { return; }
    ended = true;
    if (talking || turnRecorder) { talking = false; endTurn(true); }
    var seconds = elapsed();
    window.clearInterval(ticker);
    if (paused) { pauses.push({ at: recordedBefore, seconds: Math.round((performance.now() - pauseBegan) / 100) / 10 }); }
    try { recorder.stop(); } catch (error) { source.end(); }
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); }
    recorder = null;
    post("/record/" + session.id + "/ended", { how: how, pauses: pauses, seconds: Math.round(seconds * 10) / 10, taps: [], marks: [] })
      .then(function () { if (uploadDone || how !== "stop") { finishPage(); } });
  }

  function finishPage() {
    document.getElementById("after-title").textContent = session.title;
    document.getElementById("open-after").href = session.after;
    show(after);
  }

  window.addEventListener("pagehide", function () {
    if (!recorder || ended) { return; }
    var form = new FormData();
    form.append("csrfmiddlewaretoken", csrf);
    form.append("how", "closed");
    form.append("pauses", JSON.stringify(pauses));
    form.append("seconds", String(Math.round(elapsed() * 10) / 10));
    navigator.sendBeacon("/record/" + session.id + "/ended", form);
  });
  window.addEventListener("beforeunload", function (event) {
    if (recorder && !ended) { event.preventDefault(); event.returnValue = ""; }
  });
})();

// The Interpreter's Session page (Phase 3, chapter 3), text only.
//
// Two things happen to the microphone at once. One MediaRecorder streams the
// whole session to the sidecar as the Live recording, as record.js does. And
// the raw samples are read continuously into a rolling buffer, so that each
// Turn is cut from it the moment the person stops talking, with half a second
// of lead-in so the first syllable is never lost, and sent as a small WAV the
// server can hear at once.
//
// Whose Turn it is is never guessed. One of the two big buttons is always lit,
// Visitor or Staff; tap yours and speak. The lit side's column says "Speak
// now" in its own language, a Turn ends at a pause, and the side tells the
// server which language to listen for. Hold to talk is the other mode: hold
// a button while speaking.

(function () {
  "use strict";

  var page = document.getElementById("interpret");
  if (!page || !window.tus) { return; }

  var csrf = page.dataset.csrf;
  var CASE = page.dataset.case || "";
  var LONGEST = parseInt(page.dataset.longest, 10) || 3 * 3600;
  var HOLD_MODE = page.dataset.turnTaking === "hold";
  var READBACK = page.dataset.readback === "1";

  var PIECE = 64 * 1024;
  // The sound: 16 kHz mono, which is what the service expects, cut from a
  // rolling buffer that keeps a little of the past.
  var RATE = 16000;
  var LEAD_IN_MS = 500;
  var TAIL_MS = 300;
  // A Turn ends after this much quiet, and is sent only if it held this much
  // speech. The level is the frame's RMS against a floor learnt from the room.
  var PAUSE_MS = 700;
  var SHORTEST_SPEECH_MS = 700;
  var START_FRAMES = 3;          // frames of speech before a Turn begins
  var FRAME_MS = 50;
  var FLOOR_GAIN = 3.0;          // speech is this many times the room's floor
  var LEVEL_MIN = 0.012;         // and at least this loud
  var LONGEST_TURN_MS = 60000;   // a Turn that runs on is cut here

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

  var session = null;
  var stream = null;
  var recorder = null;
  var source = null;
  var upload = null;
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
  var known = {};
  var side = "staff";        // whose Turn it is: the lit button
  var holding = "";          // the button held, in hold mode
  var visitorName = "";      // the Visitor's language, once known

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
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
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
    document.getElementById("talk-help").textContent = HOLD_MODE
      ? "Hold your button while speaking; let go when done."
      : "Tap your button, then speak. A turn ends when you pause.";
    document.querySelectorAll(".hold").forEach(function (b) { b.classList.toggle("tap", !HOLD_MODE); });
    setSide("staff");
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
    visitorName = name || "";
    document.getElementById("language-line").textContent = name
      ? "Visitor: " + name : "Visitor: language not heard yet";
    document.getElementById("visitor-heading").textContent = name ? "Visitor (" + name + ")" : "Visitor";
    speakNowLines();
  }

  // Whose Turn it is. In tap mode the lit button stays lit until the other is
  // tapped; a Turn in progress is cut at the switch, so nothing is lost.
  function setSide(which) {
    if (speaking) { endTurn(true); }
    side = which;
    document.querySelectorAll(".hold").forEach(function (b) {
      b.classList.toggle("on", !HOLD_MODE && b.dataset.side === which);
    });
    document.getElementById("col-visitor").classList.toggle("live", which === "visitor");
    document.getElementById("col-staff").classList.toggle("live", which === "staff");
    speakNowLines();
  }

  var SPEAK_NOW = { es: "Hable ahora", pt: "Fale agora", fr: "Parlez maintenant", vi: "Xin hãy nói", ar: "تكلم الآن", ru: "Говорите", uk: "Говоріть", zh: "请说话", ko: "말씀하세요", hi: "अब बोलें", ht: "Pale kounye a", so: "Hadal hadda", sw: "Sema sasa", de: "Sprechen Sie jetzt", it: "Parli ora", tl: "Magsalita na", pl: "Proszę mówić", tr: "Konuşun", fa: "صحبت کنید", ja: "話してください", am: "አሁን ይናገሩ", pa: "ਹੁਣ ਬੋਲੋ" };
  function speakNowLines() {
    var code = session && session.language ? session.language : (known.__language || "");
    var own = SPEAK_NOW[code] || "";
    document.getElementById("speak-visitor").textContent = side === "visitor"
      ? "Speak now" + (own ? " · " + own : "") : "";
    document.getElementById("speak-staff").textContent = side === "staff" ? "Speak now" : "";
  }

  function tick() {
    var seconds = elapsed();
    document.getElementById("clock").textContent = clock(seconds);
    if (seconds >= LONGEST) { endNow("limit"); }
  }

  // The sound ---------------------------------------------------------------------------
  //
  // Raw samples from the microphone, resampled to 16 kHz, kept in a rolling
  // buffer. The level of each frame is measured against the room's floor;
  // speech begins after a few loud frames and ends after a pause, and the
  // Turn is cut from a little before the first loud frame to a little after
  // the last, as one WAV.

  var ring = [];               // Float32Array frames, oldest first
  var ringMs = 0;
  var RING_MAX_MS = LONGEST_TURN_MS + LEAD_IN_MS + 1000;
  var speaking = false;
  var speechFrames = [];       // frames of the Turn in progress
  var loudRun = 0;
  var quietMs = 0;
  var speechMs = 0;
  var turnStartedAt = 0;
  var floor = 0.004;           // the room's quiet, learnt as it goes
  var processor = null;

  function listen() {
    try {
      if (!audio) { audio = new (window.AudioContext || window.webkitAudioContext)(); }
      var input = audio.createMediaStreamSource(stream);
      processor = audio.createScriptProcessor(4096, 1, 1);
      var ratio = audio.sampleRate / RATE;
      var carry = [];
      processor.onaudioprocess = function (event) {
        var data = event.inputBuffer.getChannelData(0);
        // Resample by picking every ratio-th sample (the microphone's own
        // noise suppression has already low-passed it; speech survives).
        var out = new Float32Array(Math.floor(data.length / ratio));
        for (var i = 0; i < out.length; i++) { out[i] = data[Math.floor(i * ratio)]; }
        carry = carry.concat(Array.prototype.slice.call(out));
        var frameSize = RATE * FRAME_MS / 1000;
        while (carry.length >= frameSize) {
          var frame = new Float32Array(carry.splice(0, frameSize));
          frameArrived(frame);
        }
      };
      input.connect(processor);
      processor.connect(audio.destination);
    } catch (error) {
      problem("during-problem", "The microphone could not be read for turns: " + (error && error.message ? error.message : error));
    }
  }

  function frameArrived(frame) {
    var sum = 0;
    for (var i = 0; i < frame.length; i++) { sum += frame[i] * frame[i]; }
    var level = Math.sqrt(sum / frame.length);
    document.getElementById("meter").style.width = Math.min(100, level * 400) + "%";

    ring.push(frame);
    ringMs += FRAME_MS;
    while (ringMs > RING_MAX_MS) { ring.shift(); ringMs -= FRAME_MS; }

    if (paused) { return; }
    // The floor follows the quiet; speech is well above it.
    if (!speaking) { floor = Math.min(0.05, floor * 0.97 + level * 0.03); }
    var threshold = Math.max(LEVEL_MIN, floor * FLOOR_GAIN);
    var loud = level >= threshold;

    if (HOLD_MODE && !holding) { return; }

    if (!speaking) {
      loudRun = loud ? loudRun + 1 : 0;
      if (loudRun >= START_FRAMES) { beginTurn(); }
      return;
    }
    speechFrames.push(frame);
    speechMs += FRAME_MS;
    if (loud) { quietMs = 0; } else { quietMs += FRAME_MS; }
    if (quietMs >= PAUSE_MS || speechMs >= LONGEST_TURN_MS) { endTurn(speechMs - quietMs >= SHORTEST_SPEECH_MS); }
  }

  function beginTurn() {
    speaking = true;
    quietMs = 0;
    speechMs = 0;
    loudRun = 0;
    // The lead-in: the last half second of the ring, which holds the frames
    // that were loud before the Turn was declared, and the breath before them.
    var lead = Math.floor(LEAD_IN_MS / FRAME_MS);
    speechFrames = ring.slice(Math.max(0, ring.length - lead));
    turnStartedAt = Math.max(0, elapsed() - LEAD_IN_MS / 1000);
    document.getElementById("col-" + side).classList.add("hearing");
  }

  function endTurn(worthSending) {
    if (!speaking) { return; }
    speaking = false;
    document.querySelectorAll(".side-column.hearing").forEach(function (c) { c.classList.remove("hearing"); });
    var frames = speechFrames;
    speechFrames = [];
    if (!worthSending) { return; }
    // Trim the pause off the end, keeping a short tail.
    var drop = Math.max(0, Math.floor((quietMs - TAIL_MS) / FRAME_MS));
    if (drop) { frames = frames.slice(0, frames.length - drop); }
    var endedAt = Math.round(elapsed() * 10) / 10;
    var startAt = Math.round(turnStartedAt * 10) / 10;
    var blob = wavOf(frames);
    var form = new FormData();
    form.append("audio", blob, "turn.wav");
    form.append("start", String(startAt));
    form.append("end", String(endedAt));
    form.append("side", holding || side);
    fetch("/record/" + session.id + "/turn", { method: "POST", headers: { "X-CSRFToken": csrf }, body: form })
      .then(function (answer) { if (!answer.ok) { problem("during-problem", "A turn could not be sent."); } })
      .catch(function () { problem("during-problem", "A turn could not be sent."); });
  }

  function wavOf(frames) {
    var length = frames.reduce(function (n, f) { return n + f.length; }, 0);
    var buffer = new ArrayBuffer(44 + length * 2);
    var view = new DataView(buffer);
    function ascii(offset, text) { for (var i = 0; i < text.length; i++) { view.setUint8(offset + i, text.charCodeAt(i)); } }
    ascii(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); ascii(8, "WAVE");
    ascii(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, RATE, true); view.setUint32(28, RATE * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    ascii(36, "data"); view.setUint32(40, length * 2, true);
    var offset = 44;
    frames.forEach(function (frame) {
      for (var i = 0; i < frame.length; i++) {
        var s = Math.max(-1, Math.min(1, frame[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        offset += 2;
      }
    });
    return new Blob([buffer], { type: "audio/wav" });
  }

  // The buttons: tap to make a side live, or hold to talk.
  document.querySelectorAll(".hold").forEach(function (button) {
    var which = button.dataset.side;
    if (!HOLD_MODE) {
      button.addEventListener("click", function () { setSide(which); });
      return;
    }
    button.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      if (paused || holding) { return; }
      holding = which;
      side = which;
      button.classList.add("on");
      document.getElementById("col-" + which).classList.add("live");
      speakNowLines();
      beginTurn();
    });
    function release() {
      if (holding !== which) { return; }
      endTurn(speechMs >= SHORTEST_SPEECH_MS);
      holding = "";
      button.classList.remove("on");
      document.getElementById("col-" + which).classList.remove("live");
      speakNowLines();
    }
    button.addEventListener("pointerup", release);
    button.addEventListener("pointerleave", release);
    button.addEventListener("pointercancel", release);
  });

  // Typed Turns and the quick phrases: words instead of sound, same path after.
  function sendTyped(which, text) {
    if (!text.trim()) { return; }
    var at = Math.round(elapsed() * 10) / 10;
    post("/record/" + session.id + "/turn", { typed: text.trim(), side: which, start: at, end: at })
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
        if (said.language && !session.language) { session.language = said.language; }
        if (said.language_name) { languageLine(said.language_name); }
        if (said.notice) { drawNotice(said.notice); }
      })
      .catch(function () {})
      .then(function () { if (recorder || document.querySelector(".turn.waiting")) { window.setTimeout(poll, 1000); } });
  }

  function rowFor(number, which) {
    var list = document.getElementById(which === "staff" ? "turns-staff" : "turns-visitor");
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

  function draw(turn) {
    var was = known[turn.number];
    if (was && was.state === turn.state && was.translation === turn.translation && was.side === turn.side) { return; }
    known[turn.number] = turn;
    if (turn.state === "done" || turn.state === "failed") { lastNumber = Math.max(lastNumber, turn.number); }
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
    else if (turn.state === "failed") { state.textContent = "could not be " + (turn.heard ? "translated" : "heard") + ". Please say it again."; }
    else if (!turn.heard && !turn.typed) { state.textContent = "nothing heard; please say it again"; }
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
      if (speaking) { endTurn(true); }
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
    if (speaking) { endTurn(true); }
    var seconds = elapsed();
    window.clearInterval(ticker);
    if (paused) { pauses.push({ at: recordedBefore, seconds: Math.round((performance.now() - pauseBegan) / 100) / 10 }); }
    try { recorder.stop(); } catch (error) { source.end(); }
    if (processor) { try { processor.disconnect(); } catch (error) { /* gone */ } }
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

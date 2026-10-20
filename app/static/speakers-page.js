// The Speakers page (Phase 5, chapter 1): one recording's speakers, each a
// card, while the recording plays.
//
// Everything here reads the transcript once and works from it: the Ledger's
// rows, the lanes' blocks, the counts on the cards. Every change goes through
// the viewer's own routes (rename and merge, one line given to a speaker,
// Undo), and a rename or a merge loads the page again at the same moment,
// since the colours, the cards and the lanes all change together. In a
// window of its own the page also follows, and is followed by, the
// recording's page through the browser's channel, as the Speakers window did.

(function () {
  "use strict";

  var V = window.VIEWER;
  if (!V) { return; }

  var player = document.getElementById("player");
  var column = document.getElementById("transcript");
  var reading = document.getElementById("reading");
  var lanesBox = document.getElementById("lanes");
  var cardsBox = document.getElementById("cards");
  var pill = document.getElementById("follow-pill");
  var state = document.getElementById("win-state");
  var channel = (V.inWindow && "BroadcastChannel" in window)
    ? new BroadcastChannel("transcribe-" + V.recording)
    : null;

  var segments = [];
  var duration = 0;
  var time = 0;
  var here = -1;
  var picked = "";
  var following = true;
  var paused = false;
  var stopAt = null;        // a sample plays to the end of its line and stops
  var zoom = 0;             // seconds in view, 0 for the whole recording
  var windowFrom = 0;       // the lanes' first second when zoomed
  var colours = {};
  // The proposed changes by segment id and the Hand-overs waiting (ADR
  // 0021, v1.139.0): drawn in the transcript where each line is, and on
  // the cards and the lanes.
  var changes = {};
  var handovers = [];
  var viewMode = "changes";   // "changes" collapses the quiet stretches
  var showQuiet = false;      // the proposals the voice could not judge, folded
  var stored = document.getElementById("speaker-colours");
  if (stored) {
    JSON.parse(stored.textContent).forEach(function (one) { colours[one.name] = one.colour; });
  }

  // Bearings --------------------------------------------------------------------

  function tell(message) { if (channel) { channel.postMessage(message); } }

  function clock(seconds) {
    var whole = Math.max(0, Math.floor(seconds || 0));
    var minutes = Math.floor(whole / 60);
    var rest = whole % 60;
    if (minutes >= 60) {
      return Math.floor(minutes / 60) + ":" +
        String(minutes % 60).padStart(2, "0") + ":" + String(rest).padStart(2, "0");
    }
    return minutes + ":" + String(rest).padStart(2, "0");
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function send(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    }).catch(function () {
      // The app did not answer, or answered with a page (v1.132.0): the
      // caller gets a plain "not ok" rather than a dead button.
      if (window.UI && window.UI.toast) { window.UI.toast("The app did not answer. Try again.", { problem: true }); }
      return { ok: false, said: {} };
    });
  }

  function cards() { return cardsBox ? Array.prototype.slice.call(cardsBox.querySelectorAll(".sp-card")) : []; }
  function names() { return cards().map(function (card) { return card.dataset.name; }); }
  function cardOf(name) { return cardsBox ? cardsBox.querySelector('.sp-card[data-name="' + CSS.escape(name) + '"]') : null; }

  // The last segment that has started at a time.
  function at(when) {
    var low = 0;
    var high = segments.length - 1;
    var found = -1;
    while (low <= high) {
      var middle = (low + high) >> 1;
      if (segments[middle].start <= when) { found = middle; low = middle + 1; } else { high = middle - 1; }
    }
    return found;
  }

  function now() { return player ? player.currentTime : time; }

  // Loading the page again at the same moment, with the same card picked,
  // after a change that recolours everything.
  function reloadHere(pick) {
    var url = window.location.pathname + "?t=" + Math.floor(now());
    if (pick) { url += "&pick=" + encodeURIComponent(pick); }
    window.location.replace(url);
  }

  // The player ------------------------------------------------------------------

  function seek(seconds) {
    stopAt = null;
    if (!player) { tell({ kind: "seek", at: seconds }); return; }
    player.currentTime = Math.max(0, Math.min(seconds, duration || seconds));
    resumeFollowing();
  }
  function play() { if (player) { player.play(); } else { tell({ kind: "play" }); } }
  function pause() { if (player) { player.pause(); } else { tell({ kind: "pause" }); } }

  if (player) {
    var lastTold = -1;
    function tellTime() {
      if (!channel) { return; }
      var tick = Math.floor(player.currentTime * 4);
      if (tick === lastTold) { return; }
      lastTold = tick;
      tell({ kind: "window-time", at: player.currentTime, playing: !player.paused });
    }
    player.addEventListener("timeupdate", function () {
      time = player.currentTime;
      if (stopAt !== null && time >= stopAt) { stopAt = null; player.pause(); }
      followAt(time);
      tellTime();
      keepDone();
    });
    player.addEventListener("loadedmetadata", function () {
      if (isFinite(player.duration) && player.duration > 0) { duration = player.duration; }
      drawLanes();
      drawWave();
      followAt(player.currentTime);
    });
    player.addEventListener("play", function () {
      document.getElementById("play").textContent = "Pause";
      lastTold = -1;
      tellTime();
    });
    player.addEventListener("pause", function () {
      document.getElementById("play").textContent = "Play";
      tell({ kind: "window-time", at: player.currentTime, playing: false });
    });
    player.addEventListener("error", function () {
      if (state) { state.textContent = "This page cannot play the recording here; the recording's page still can."; }
    });
    document.getElementById("play").addEventListener("click", function () {
      stopAt = null;
      if (player.paused) { player.play(); } else { player.pause(); }
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-seek]"), function (button) {
      button.addEventListener("click", function () {
        seek(player.currentTime + parseFloat(button.dataset.seek));
        if (button.dataset.seek === "-3") { player.play(); }
      });
    });
    document.getElementById("speed").addEventListener("change", function () {
      player.playbackRate = parseFloat(this.value);
    });
  }

  // Done goes back to the recording at this moment.
  var done = document.getElementById("done");
  var lastDone = -1;
  function keepDone() {
    if (!done) { return; }
    var second = Math.floor(now());
    if (second === lastDone) { return; }
    lastDone = second;
    done.href = V.backUrl + (second ? "?t=" + second : "");
  }

  var openInWindow = document.getElementById("open-in-window");
  if (openInWindow) {
    openInWindow.addEventListener("click", function () {
      var opened = window.open(V.windowUrl + "?t=" + Math.floor(now()), "transcribe-" + V.recording + "-speakers", "popup,width=1100,height=800");
      if (!opened) {
        UI.toast("The browser blocked the window. Allow pop-ups for this site and try again.", { problem: true, icon: "warning" });
        return;
      }
      if (player) { player.pause(); }
    });
  }

  // The waveform, on a sound recording: the strip where the picture would be.
  var wave = document.getElementById("wave");
  var peaks = null;
  function drawWave() {
    if (!wave || !peaks || !peaks.data) { return; }
    var width = wave.clientWidth;
    var height = 48;
    if (!width) { return; }
    var ratio = window.devicePixelRatio || 1;
    wave.width = Math.floor(width * ratio);
    wave.height = Math.floor(height * ratio);
    wave.style.height = height + "px";
    var pen = wave.getContext("2d");
    pen.setTransform(ratio, 0, 0, ratio, 0, 0);
    var style = window.getComputedStyle(document.documentElement);
    pen.fillStyle = style.getPropertyValue("--surface-2").trim();
    pen.fillRect(0, 0, width, height);
    pen.fillStyle = style.getPropertyValue("--muted").trim();
    var channels = peaks.channels || 1;
    var pairs = Math.floor(peaks.data.length / (2 * channels));
    var scale = Math.pow(2, (peaks.bits || 8) - 1);
    for (var x = 0; x < width; x += 1) {
      var first = Math.floor((x / width) * pairs);
      var last = Math.max(first + 1, Math.floor(((x + 1) / width) * pairs));
      var low = 0;
      var high = 0;
      for (var index = first; index < last && index < pairs; index += 1) {
        var here = index * channels * 2;
        if (peaks.data[here] < low) { low = peaks.data[here]; }
        if (peaks.data[here + 1] > high) { high = peaks.data[here + 1]; }
      }
      var top = height / 2 - Math.max(1, (high / scale) * (height / 2 - 1));
      pen.fillRect(x, top, 1, Math.max(1, ((high - low) / scale) * (height / 2 - 1)));
    }
  }
  if (wave && V.waveform) {
    fetch(V.waveform).then(function (answer) { return answer.json(); })
      .then(function (body) { peaks = body; drawWave(); })
      .catch(function () { /* the lanes are the timeline anyway */ });
  }

  // The Ledger ------------------------------------------------------------------
  //
  // The viewer's rows: the time, the name in its colour, the words, and on the
  // line being spoken the buttons. Filtered to the picked speaker's lines with
  // the line before and after each dimmed for context, or everyone.

  var showAll = false;

  function draw() {
    if (!column) { return; }
    column.innerHTML = "";
    // Runs of changes between the same two speakers, close together, get
    // one head with Accept all (the block of the chosen mock-up).
    var runStart = {};
    var runIds = {};
    var previous = null;
    segments.forEach(function (segment, index) {
      var change = drawnChange(segment);
      if (change && previous && previous.change.from === change.from && previous.change.to === change.to && segment.start - previous.end <= 20) {
        runIds[previous.head].push(change.id);
        previous = { change: change, end: segment.end, head: previous.head };
      } else if (change) {
        runStart[index] = true;
        runIds[index] = [change.id];
        previous = { change: change, end: segment.end, head: index };
      } else {
        previous = null;
      }
    });
    segments.forEach(function (segment, index) {
      var change = drawnChange(segment);
      if (change && runStart[index] && runIds[index].length > 1) {
        var head = document.createElement("li");
        head.className = "block-head";
        head.dataset.index = index;
        head.dataset.ids = runIds[index].join(",");
        head.innerHTML = "<b>" + runIds[index].length + " lines</b> <span class='muted'>shown as " + escape(change.from) + ", read as " + escape(change.to) + "'s</span> " + changePill(change) +
          "<span class='grow'></span>" + hearThree(change) +
          "<button type='button' class='tiny" + (change.voice === "agrees" ? " primary" : "") + " block-accept'>Accept all " + runIds[index].length + "</button>" +
          "<button type='button' class='ghost tiny block-leave'>Leave</button>";
        column.appendChild(head);
      }
      var row = document.createElement("li");
      row.className = "seg";
      row.dataset.index = index;
      if (segment.speaker) {
        row.style.setProperty("--speaker", colours[segment.speaker] || "");
        row.style.borderLeftColor = colours[segment.speaker] || "transparent";
      }
      if (index > 0 && segments[index - 1].speaker === segment.speaker && !change) { row.classList.add("cont"); }
      if (change) {
        row.classList.add("change", change.voice || "quiet");
        row.dataset.correction = change.id;
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'><s>" + escape(change.from) + "</s> <span class='to' style='--speaker: " + (colours[change.to] || "") + "'>" + escape(change.to) + "</span></span><span class='tags'></span></div>" +
          "<div class='words'><p class='txt'>" + escape(segment.text) + "</p></div>" +
          "<span class='actions change-acts'>" + changePill(change) + hearThree(change) +
          "<button type='button' class='tiny" + (change.voice === "agrees" ? " primary" : "") + " accept-change' title='Move this line to " + escape(change.to) + "'>Accept</button>" +
          "<button type='button' class='ghost tiny leave-change' title='Leave the line as it is and put the proposal away'>Leave</button>" +
          "</span>";
      } else {
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'>" + escape(segment.speaker) + "</span><span class='tags'></span></div>" +
          "<div class='words'><p class='txt'>" + escape(segment.text) + "</p></div>" +
          "<span class='actions'>" +
          "<button type='button' class='ghost tiny play-row' title='Play this line'>play</button>" +
          "<button type='button' class='ghost tiny give-row' title='Give this line to another speaker'>not this speaker</button>" +
          "</span>";
      }
      column.appendChild(row);
    });
    filter();
    here = -1;
    followAt(now());
    document.dispatchEvent(new CustomEvent("transcript-drawn"));
  }

  function anyChangesDrawn() {
    return segments.some(function (segment) { return !!drawnChange(segment); });
  }

  function filter() {
    if (!column) { return; }
    var rows = Array.prototype.filter.call(column.children, function (row) { return row.classList.contains("seg"); });
    var heads = Array.prototype.filter.call(column.children, function (row) { return row.classList.contains("block-head"); });
    var count = 0;
    var keep = null;
    var changesOn = anyChangesDrawn();
    var views = document.getElementById("views");
    if (views) { views.hidden = !changesOn; }
    if (changesOn && viewMode === "changes") {
      // Changes only: a marked line and its neighbours; the quiet stretches
      // between them collapse to one line saying so.
      keep = {};
      segments.forEach(function (segment, index) {
        if (drawnChange(segment)) {
          keep[index - 1] = keep[index - 1] || "near";
          keep[index] = "mine";
          keep[index + 1] = keep[index + 1] || "near";
        }
      });
    } else if (!showAll && picked) {
      keep = {};
      segments.forEach(function (segment, index) {
        if (segment.speaker === picked) {
          keep[index - 1] = keep[index - 1] || "dim";
          keep[index] = "mine";
          keep[index + 1] = keep[index + 1] || "dim";
        }
      });
    }
    var hiddenFrom = -1;
    for (var i = 0; i < rows.length; i += 1) {
      var how = keep ? keep[i] : "all";
      rows[i].hidden = !how;
      rows[i].classList.toggle("dim", how === "dim");
      rows[i].classList.toggle("mine", how === "mine");
      rows[i].classList.remove("gapped");
      rows[i].removeAttribute("data-gap");
      if (!how) { if (hiddenFrom < 0) { hiddenFrom = i; } }
      else {
        if (hiddenFrom >= 0 && changesOn && viewMode === "changes") {
          rows[i].classList.add("gapped");
          rows[i].dataset.gap = clock(segments[hiddenFrom].start) + " to " + clock(segments[i - 1].end) + ", no changes";
        }
        hiddenFrom = -1;
      }
      if (how === "mine" || (!keep && segments[i].speaker === picked)) { count += 1; }
    }
    heads.forEach(function (head) {
      var first = rows[parseInt(head.dataset.index, 10)];
      head.hidden = !first || first.hidden;
    });
    var viewChanges = document.getElementById("view-changes");
    var viewWhole = document.getElementById("view-whole");
    if (viewChanges) { viewChanges.classList.toggle("on", viewMode === "changes"); }
    if (viewWhole) { viewWhole.classList.toggle("on", viewMode !== "changes"); }
    var one = document.getElementById("filter-one");
    var all = document.getElementById("filter-all");
    if (one) {
      one.textContent = (picked || "This speaker") + " only";
      one.classList.toggle("on", !showAll);
      one.hidden = !picked;
    }
    if (all) { all.classList.toggle("on", showAll); }
    var said = document.getElementById("filter-count");
    if (said) { said.textContent = picked ? count + (count === 1 ? " line" : " lines") : ""; }
  }

  document.getElementById("filter-one") && document.getElementById("filter-one").addEventListener("click", function () { showAll = false; viewMode = "whole"; filter(); });
  document.getElementById("filter-all") && document.getElementById("filter-all").addEventListener("click", function () { showAll = true; viewMode = "whole"; filter(); });
  document.getElementById("view-changes") && document.getElementById("view-changes").addEventListener("click", function () { viewMode = "changes"; filter(); });
  document.getElementById("view-whole") && document.getElementById("view-whole").addEventListener("click", function () { viewMode = "whole"; showAll = true; filter(); });
  document.getElementById("show-quiet") && document.getElementById("show-quiet").addEventListener("click", function () {
    showQuiet = !showQuiet;
    var quietCount = Object.keys(changes).filter(function (id) { return !changes[id].voice; }).length;
    this.textContent = showQuiet ? "Hide the " + quietCount + " the voice could not judge" : quietCount + " more the voice could not judge: show them in place";
    draw();
  });

  if (column) {
    column.addEventListener("click", function (event) {
      var row = event.target.closest(".seg");
      if (!row) { return; }
      var segment = segments[parseInt(row.dataset.index, 10)];
      if (!segment) { return; }
      if (event.target.closest(".give-row")) { giveLine(segment); return; }
      if (event.target.closest(".play-row")) { playLine(segment); return; }
      var voice = event.target.closest(".hear-voice");
      if (voice) { playSample(voice.dataset.voice); return; }
      if (event.target.closest(".accept-change")) { decideChange(row.dataset.correction, true, segment); return; }
      if (event.target.closest(".leave-change")) { decideChange(row.dataset.correction, false, segment); return; }
      seek(segment.start);
      play();
    });
    column.addEventListener("click", function (event) {
      var head = event.target.closest(".block-head");
      if (!head) { return; }
      var change = changes[String(segments[parseInt(head.dataset.index, 10)].id)];
      var voice = event.target.closest(".hear-voice");
      if (voice) { playSample(voice.dataset.voice); return; }
      if (event.target.closest(".play-row") && change) { playLine(segments[parseInt(head.dataset.index, 10)]); return; }
      var accept = event.target.closest(".block-accept");
      var leave = event.target.closest(".block-leave");
      if (!accept && !leave) { return; }
      send("/recording/" + V.recording + "/corrections/" + (accept ? "accept" : "dismiss") + "-many", { ids: head.dataset.ids }).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
        if (accept && answer.said.undo) { sayUndo(answer.said.undo); }
        load().then(refreshSuggestions);
      });
    });
  }

  // One change accepted or left (ADR 0021): the line moves here as a
  // correction's Accept always has, with the same Undo; Leave puts the
  // proposal away and the line stays.
  function decideChange(correctionId, accept, segment) {
    if (!correctionId) { return; }
    var change = changes[String(segment.id)];
    send("/correction/" + correctionId + "/" + (accept ? "accept" : "dismiss")).then(function (answer) {
      if (!answer.ok) { UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
      if (accept) {
        if (answer.said.stale) { UI.toast("This line changed since the check, so it was left as it is.", { icon: "info" }); }
        else { sayUndo(answer.said.undo); if (change) { moved(segment.id, change.to); } }
      }
      refreshSuggestions();
    });
  }

  // Following: the line being spoken lights and stays in view, scrolled only
  // once it has left the middle of the column, as on the recording page.
  // The row of a line, by the number the row carries (v1.140.0): since
  // v1.139.0 the column holds a head above each run of changes too, so
  // counting the column's children from the top lit the line above.
  function rowAt(index) {
    if (!column || index < 0) { return null; }
    return column.querySelector(".seg[data-index='" + index + "']");
  }

  function outOfTheMiddle(row) {
    if (!reading) { return true; }
    var box = reading.getBoundingClientRect();
    var seen = row.getBoundingClientRect();
    if (!box.height) { return false; }
    return seen.top < box.top + box.height * 0.18 || seen.bottom > box.top + box.height * 0.74;
  }

  function followAt(when) {
    time = when;
    movePlayheads(when);
    var index = at(when);
    if (index !== here) {
      var was = column ? column.querySelector(".seg.here") : null;
      if (was) { was.classList.remove("here"); }
      var row = rowAt(index);
      if (row) {
        row.classList.add("here");
        if (following && !paused && !row.hidden && outOfTheMiddle(row)) {
          row.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      here = index;
      sayNow(index >= 0 ? segments[index] : null);
    }
    var clockBox = document.getElementById("clock");
    if (clockBox) { clockBox.textContent = clock(when) + " / " + clock(duration); }
  }

  function sayNow(segment) {
    var who = document.getElementById("now-who");
    var text = document.getElementById("now-text");
    if (!who || !text) { return; }
    who.textContent = segment ? (segment.speaker || "") : "";
    who.style.setProperty("--speaker", segment && segment.speaker ? (colours[segment.speaker] || "") : "");
    text.textContent = segment ? segment.text : "";
  }

  function pauseFollowing() {
    if (!following || paused) { return; }
    paused = true;
    if (pill) { pill.hidden = false; }
  }
  function resumeFollowing() {
    if (!paused) { return; }
    paused = false;
    if (pill) { pill.hidden = true; }
    var row = rowAt(here);
    if (row && !row.hidden) { row.scrollIntoView({ block: "center", behavior: "smooth" }); }
  }
  if (reading) {
    window.addEventListener("wheel", function (event) {
      if (!event.target.closest || !event.target.closest(".sp-read")) { return; }
      if (!paused) { pauseFollowing(); }
    }, { passive: true });
  }
  if (pill) { document.getElementById("resume-follow").addEventListener("click", resumeFollowing); }

  // Playing one line and stopping at its end: a sample, or play on a row.
  function playLine(segment) {
    seek(segment.start);
    stopAt = segment.end;
    play();
  }

  function playRange(start, end) {
    seek(Math.max(0, start));
    stopAt = end;
    play();
  }

  // A speaker's sample: the first on its card (its surest line).
  function sampleOf(name) {
    var card = cardOf(name);
    var button = card ? card.querySelector(".sample") : null;
    if (!button) { return null; }
    return { start: parseFloat(button.dataset.start), end: parseFloat(button.dataset.end) };
  }

  function playSample(name) {
    var sample = sampleOf(name);
    if (sample) { playRange(sample.start, sample.end); }
  }

  // A change's voice word as a pill, in the pills' colours.
  function changePill(change) {
    if (change.voice === "agrees") { return "<span class='pill small ok' title='The voice on this line sounds like " + escape(change.to) + ".'>the voice agrees</span>"; }
    if (change.voice === "against") { return "<span class='pill small danger' title='The voice on this line sounds like " + escape(change.from) + ", not " + escape(change.to) + ". Listen before you accept.'>the voice disagrees, listen first</span>"; }
    return "<span class='pill small' title='The line is short, or the two speakers sound alike on it; the words alone propose this.'>the voice could not judge</span>";
  }

  function drawnChange(segment) {
    var change = changes[String(segment.id)];
    if (!change) { return null; }
    if (!change.voice && !showQuiet) { return null; }
    return change;
  }

  // The three sounds: the line, the voice it has, the voice proposed.
  function hearThree(change) {
    var k1 = names().indexOf(change.from) + 1;
    var k2 = names().indexOf(change.to) + 1;
    return "<span class='hear3'><span class='k'>hear</span>" +
      "<button type='button' class='play-row' title='Play this line'>" + UI.icon("play") + "</button>" +
      "<button type='button' class='hear-voice' data-voice='" + escape(change.from) + "' style='--speaker: " + (colours[change.from] || "") + "' title='Play " + escape(change.from) + " as a whole'>" + (k1 || "?") + "</button>" +
      "<button type='button' class='hear-voice' data-voice='" + escape(change.to) + "' style='--speaker: " + (colours[change.to] || "") + "' title='Play " + escape(change.to) + " as a whole'>" + (k2 || "?") + "</button></span>";
  }

  // The lanes -------------------------------------------------------------------
  //
  // A block for every stretch a speaker talks, lines of one speaker less than
  // a second apart drawn as one. The lanes are the scrub bar: a press seeks.

  var blocks = {};

  function buildBlocks() {
    blocks = {};
    segments.forEach(function (segment) {
      if (!segment.speaker) { return; }
      var mine = blocks[segment.speaker] || (blocks[segment.speaker] = []);
      var last = mine[mine.length - 1];
      if (last && segment.start - last.end < 1) { last.end = Math.max(last.end, segment.end); }
      else { mine.push({ start: segment.start, end: segment.end }); }
    });
  }

  function view() {
    var length = duration || (segments.length ? segments[segments.length - 1].end : 0);
    if (!zoom || zoom >= length) { return { from: 0, to: length || 1 }; }
    var from = Math.max(0, Math.min(windowFrom, length - zoom));
    return { from: from, to: from + zoom };
  }

  function percent(seconds, span) {
    return ((seconds - span.from) / (span.to - span.from)) * 100;
  }

  function drawLanes() {
    if (!lanesBox) { return; }
    var span = view();
    Array.prototype.forEach.call(lanesBox.querySelectorAll(".lane[data-name]"), function (lane) {
      var track = lane.querySelector(".track");
      var mine = blocks[lane.dataset.name] || [];
      var drawn = ["<span class='playhead'></span>"];
      mine.forEach(function (block) {
        if (block.end < span.from || block.start > span.to) { return; }
        var left = Math.max(0, percent(block.start, span));
        var right = Math.min(100, percent(block.end, span));
        drawn.push("<i style='left:" + left.toFixed(3) + "%;width:" + Math.max(0.15, right - left).toFixed(3) + "%' data-start='" + block.start + "' title='" + clock(block.start) + " to " + clock(block.end) + "'></i>");
      });
      // A Hand-over waiting (ADR 0021): the time another voice takes over
      // under this label, as a marker on its lane.
      handovers.forEach(function (one) {
        if (one.speaker !== lane.dataset.name || one.at < span.from || one.at > span.to) { return; }
        drawn.push("<b class='hmark' style='left:" + percent(one.at, span).toFixed(3) + "%' title='Another voice from " + clock(one.at) + "'></b>");
      });
      // The picked speaker's samples, as ticks on its lane.
      if (lane.dataset.name === picked) {
        var card = cardOf(picked);
        Array.prototype.forEach.call(card ? card.querySelectorAll(".sample") : [], function (button) {
          var start = parseFloat(button.dataset.start);
          if (start < span.from || start > span.to) { return; }
          drawn.push("<b class='tick' style='left:" + percent(start, span).toFixed(3) + "%' title='Sample at " + clock(start) + "'></b>");
        });
      }
      track.innerHTML = drawn.join("");
    });
    var ticks = document.getElementById("ticks");
    if (ticks) {
      var labels = [];
      for (var n = 0; n <= 4; n += 1) {
        labels.push("<span>" + clock(span.from + ((span.to - span.from) * n) / 4) + "</span>");
      }
      ticks.innerHTML = labels.join("");
    }
    foldSmall();
    movePlayheads(now());
  }

  // With many speakers, the ones under a minute fold into one lane.
  var smallOpen = false;
  function foldSmall() {
    var fold = document.getElementById("small-lane");
    if (!fold) { return; }
    var small = lanesBox.querySelectorAll(".lane.small[data-name]");
    fold.hidden = !small.length;
    Array.prototype.forEach.call(small, function (lane) { lane.hidden = !smallOpen; });
    var toggle = document.getElementById("small-toggle");
    toggle.textContent = (smallOpen ? "fold " : "") + small.length + " small speaker" + (small.length === 1 ? "" : "s");
    var track = fold.querySelector(".track");
    var span = view();
    var drawn = ["<span class='playhead'></span>"];
    Array.prototype.forEach.call(small, function (lane) {
      (blocks[lane.dataset.name] || []).forEach(function (block) {
        if (block.end < span.from || block.start > span.to) { return; }
        var left = Math.max(0, percent(block.start, span));
        var right = Math.min(100, percent(block.end, span));
        drawn.push("<i style='left:" + left.toFixed(3) + "%;width:" + Math.max(0.15, right - left).toFixed(3) + "%;background:" + (colours[lane.dataset.name] || "") + "' data-start='" + block.start + "'></i>");
      });
    });
    track.innerHTML = drawn.join("");
  }
  var smallToggle = document.getElementById("small-toggle");
  if (smallToggle) {
    smallToggle.addEventListener("click", function () { smallOpen = !smallOpen; foldSmall(); });
  }

  function movePlayheads(when) {
    if (!lanesBox) { return; }
    var span = view();
    if (zoom && (when < span.from || when > span.to)) {
      // Zoomed in and the playhead has left the view: the view follows it.
      windowFrom = Math.max(0, when - zoom / 4);
      drawLanes();
      return;
    }
    var left = Math.max(0, Math.min(100, percent(when, span))).toFixed(3) + "%";
    Array.prototype.forEach.call(lanesBox.querySelectorAll(".playhead"), function (head) { head.style.left = left; });
  }

  if (lanesBox) {
    lanesBox.addEventListener("click", function (event) {
      var zoomButton = event.target.closest("[data-zoom]");
      if (zoomButton) {
        zoom = parseInt(zoomButton.dataset.zoom, 10) || 0;
        windowFrom = Math.max(0, now() - zoom / 4);
        Array.prototype.forEach.call(lanesBox.querySelectorAll("[data-zoom]"), function (one) { one.classList.toggle("on", one === zoomButton); });
        try { window.localStorage.setItem("lanes-zoom", String(zoom)); } catch (ignored) { /* this page only */ }
        drawLanes();
        return;
      }
      var head = event.target.closest(".lane[data-name] .head");
      if (head) { pick(head.parentNode.dataset.name); return; }
      var block = event.target.closest(".track i");
      if (block) { seek(parseFloat(block.dataset.start)); play(); return; }
      var track = event.target.closest(".track");
      if (track) {
        var box = track.getBoundingClientRect();
        var span = view();
        seek(span.from + ((event.clientX - box.left) / box.width) * (span.to - span.from));
      }
    });

    // Drag a lane's head onto another to merge the two speakers.
    var dragged = null;
    lanesBox.addEventListener("dragstart", function (event) {
      var head = event.target.closest(".lane[data-name] .head");
      dragged = head ? head.parentNode.dataset.name : null;
    });
    lanesBox.addEventListener("dragover", function (event) {
      var lane = event.target.closest(".lane[data-name]");
      if (!lane || !dragged) { return; }
      event.preventDefault();
      lane.classList.add("over");
    });
    lanesBox.addEventListener("dragleave", function (event) {
      var lane = event.target.closest(".lane[data-name]");
      if (lane) { lane.classList.remove("over"); }
    });
    lanesBox.addEventListener("drop", function (event) {
      event.preventDefault();
      var lane = event.target.closest(".lane[data-name]");
      Array.prototype.forEach.call(lanesBox.querySelectorAll(".lane.over"), function (one) { one.classList.remove("over"); });
      if (!lane || !dragged || dragged === lane.dataset.name) { return; }
      merge(dragged, lane.dataset.name);
      dragged = null;
    });
    try {
      var kept = parseInt(window.localStorage.getItem("lanes-zoom") || "0", 10) || 0;
      if (kept) {
        zoom = kept;
        Array.prototype.forEach.call(lanesBox.querySelectorAll("[data-zoom]"), function (one) { one.classList.toggle("on", parseInt(one.dataset.zoom, 10) === kept); });
      }
    } catch (ignored) { /* the whole recording then */ }
  }

  // The cards -------------------------------------------------------------------

  function pick(name) {
    picked = name;
    cards().forEach(function (card) { card.classList.toggle("on", card.dataset.name === name); });
    Array.prototype.forEach.call(lanesBox ? lanesBox.querySelectorAll(".lane[data-name]") : [], function (lane) {
      lane.classList.toggle("on", lane.dataset.name === name);
    });
    showAll = false;
    filter();
    drawLanes();
    var row = column ? column.querySelector(".seg.mine") : null;
    if (row && following && !paused) { row.scrollIntoView({ block: "center" }); }
  }

  function fillCounts() {
    cards().forEach(function (card) {
      var mine = segments.filter(function (one) { return one.speaker === card.dataset.name; });
      var count = card.querySelector(".count");
      if (count) { count.textContent = mine.length + (mine.length === 1 ? " line" : " lines"); }
    });
  }

  function sayProgress() {
    var all = cards();
    var named = all.filter(function (card) { return !card.classList.contains("unnamed"); }).length;
    var text = document.getElementById("sp-progress-text");
    var bar = document.getElementById("sp-progress-bar");
    if (text) { text.textContent = named + " of " + all.length + " speaker" + (all.length === 1 ? "" : "s") + " named"; }
    if (bar) { bar.style.width = (all.length ? (named / all.length) * 100 : 0) + "%"; }
  }

  function sayUndo(words) {
    var line = document.getElementById("speakers-undo-line");
    var what = document.getElementById("speakers-undo-what");
    if (!line) { return; }
    line.hidden = !words;
    what.textContent = words || "";
  }

  // Naming: the viewer's rename, with the Role of a new person inside a case.
  function rename(was, to, role) {
    if (!to || to === was) { return; }
    var ontoAnother = names().some(function (one) { return one !== was && one.toLowerCase() === to.toLowerCase(); });
    var go = ontoAnother
      ? UI.confirm({ title: "Merge " + was + " into " + to + "?", body: "Every line of " + was + " becomes " + to + ". Undo puts them back.", ok: "Merge" })
      : Promise.resolve(true);
    go.then(function (yes) {
      if (!yes) { return; }
      send("/recording/" + V.recording + "/speakers", { from: was, to: to, role: role || "" }).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "Not renamed.", { problem: true, icon: "warning" }); return; }
        tell({ kind: "speakers-changed" });
        reloadHere(to);
      });
    });
  }

  function merge(was, onto) {
    UI.confirm({
      title: "Merge " + was + " into " + onto + "?",
      body: "Every line of " + was + " becomes " + onto + "'s. Undo puts them back.",
      ok: "Merge"
    }).then(function (yes) {
      if (!yes) { return; }
      send("/recording/" + V.recording + "/speakers", { from: was, to: onto }).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "Not merged.", { problem: true, icon: "warning" }); return; }
        tell({ kind: "speakers-changed" });
        reloadHere(onto);
      });
    });
  }

  function askWhich(title, body, except) {
    var choices = names().filter(function (one) { return one !== except; });
    if (!choices.length) { return Promise.resolve(null); }
    var listed = choices.map(function (one) { return (names().indexOf(one) + 1) + " " + one; }).join(", ");
    return UI.prompt({ title: title, body: body + " Type the number of the speaker: " + listed + ".", value: "", ok: "Choose" })
      .then(function (typed) {
        var chosen = names()[parseInt(String(typed || "").trim(), 10) - 1];
        return chosen && chosen !== except ? chosen : null;
      });
  }

  // One line given to another speaker: the number keys, or the row's button.
  function give(segment, name) {
    if (!segment || !name || segment.speaker === name) { return; }
    send("/recording/" + V.recording + "/segment/" + segment.id + "/speaker", { speaker: name })
      .then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "That line was not changed.", { problem: true, icon: "warning" }); return; }
        segment.speaker = name;
        sayUndo(answer.said.undo);
        buildBlocks();
        fillCounts();
        var keep = here;
        draw();
        here = keep;
        var row = rowAt(keep);
        if (row) { row.classList.add("here"); }
        drawLanes();
        tell({ kind: "segments-changed" });
      });
  }

  function giveLine(segment) {
    askWhich("Whose line is this?", "“" + segment.text.slice(0, 80) + "”", segment.speaker)
      .then(function (name) { if (name) { give(segment, name); } });
  }

  function currentSegment() { return here >= 0 ? segments[here] : null; }

  if (cardsBox) {
    cardsBox.addEventListener("click", function (event) {
      var card = event.target.closest(".sp-card");
      if (!card) { return; }
      var name = card.dataset.name;
      var sample = event.target.closest(".sample");
      if (sample) {
        pick(name);
        playLine({ start: parseFloat(sample.dataset.start), end: parseFloat(sample.dataset.end) });
        return;
      }
      if (event.target.closest(".name-speaker")) {
        var box = card.querySelector(".namebox");
        box.hidden = false;
        var input = box.querySelector(".name-input");
        input.focus();
        input.select();
        showPeople(card);
        return;
      }
      if (event.target.closest(".name-cancel")) {
        card.querySelector(".namebox").hidden = true;
        return;
      }
      if (event.target.closest(".name-save")) {
        var typed = card.querySelector(".name-input").value.trim();
        var role = card.querySelector(".role-pick");
        rename(name, typed, role ? role.value : "");
        return;
      }
      var pickButton = event.target.closest(".pick");
      if (pickButton) { rename(name, pickButton.dataset.name, ""); return; }
      if (event.target.closest(".same-as")) {
        askWhich(name + " is the same person as...", "Every line of " + name + " takes that speaker's name.", name)
          .then(function (onto) { if (onto) { merge(name, onto); } });
        return;
      }
      var mergeInto = event.target.closest(".merge-into");
      if (mergeInto) { merge(name, mergeInto.dataset.onto); return; }
      var accept = event.target.closest(".accept");
      var reject = event.target.closest(".reject");
      if (accept || reject) {
        var button = accept || reject;
        button.disabled = true;
        send("/suggestion/" + button.dataset.suggestion + "/" + (accept ? "accept" : "reject")).then(function (got) {
          if (!got.ok) { button.disabled = false; return; }
          tell({ kind: "speakers-changed" });
          if (accept) { reloadHere(button.dataset.name); } else { refreshSuggestions(); }
        });
        return;
      }
      if (event.target.closest("input, select, button, a")) { return; }
      pick(name);
    });

    cardsBox.addEventListener("keydown", function (event) {
      if (!event.target.classList.contains("name-input")) { return; }
      event.stopPropagation();
      var card = event.target.closest(".sp-card");
      if (event.key === "Enter") { event.preventDefault(); card.querySelector(".name-save").click(); }
      if (event.key === "Escape" && !card.classList.contains("unnamed")) { card.querySelector(".namebox").hidden = true; }
    });
    cardsBox.addEventListener("input", function (event) {
      if (event.target.classList.contains("name-input")) { showPeople(event.target.closest(".sp-card")); }
    });
  }

  // The case's people under the box: all of them until something is typed,
  // then those that contain what was typed.
  function showPeople(card) {
    var list = card.querySelector(".people-pick");
    if (!list) { return; }
    var typed = card.querySelector(".name-input").value.trim().toLowerCase();
    var narrowing = typed && typed !== card.dataset.name.toLowerCase();
    var shown = 0;
    Array.prototype.forEach.call(list.querySelectorAll("li"), function (row) {
      var on = !narrowing || row.querySelector(".pick").dataset.name.toLowerCase().indexOf(typed) !== -1;
      row.hidden = !on;
      if (on) { shown += 1; }
    });
    var none = card.querySelector(".people-none");
    if (none) { none.hidden = shown > 0; }
  }

  // Suggest names: the AI assistant's feature, from the words, on request.
  // A suggestion lands on its speaker's card with Accept and Reject.
  var suggestLine = document.getElementById("suggest-line");
  var suggestTimer = null;
  var checkLine = document.getElementById("check-line");
  var correctionsBox = document.getElementById("corrections");

  function drawNameSuggestions(body) {
    if (!suggestLine || !V.assistant.suggestions) { return false; }
    var unnamed = body.unnamed || [];
    // The one run (v1.140.0): where the check is offered it suggests the
    // names too, so the button of its own is kept for a transcript the
    // check cannot read (fewer than two speakers told apart).
    var oneRun = !!(V.assistant.speakerCheck && (body.speaker_check || {}).offered);
    suggestLine.hidden = unnamed.length < 2 || oneRun;
    var button = document.getElementById("suggest-names");
    var said = document.getElementById("suggest-said");
    var run = body.suggestion_run;
    var busy = run && (run.state === "queued" || run.state === "running");
    button.disabled = !body.reachable || !!busy;
    button.title = body.reachable ? "" : (body.unavailable_line || "");
    if (busy) { said.textContent = "Reading the transcript..."; }
    else if (run && run.state === "failed") { said.textContent = run.said || ""; }
    else if (run && run.state === "done" && !(body.pending || []).length) { said.textContent = "Nothing in the transcript shows who these speakers are."; }
    else { said.textContent = ""; }
    // The best-practice line (v1.127.1): advice, never a bar; the button
    // stays live whatever the check has done.
    if (!said.textContent && V.assistant.speakerCheck) {
      var check = body.speaker_check || {};
      var waiting = (check.pending || []).length;
      var checkRun = check.run;
      if (waiting) { said.textContent = "For the best names, answer the " + waiting + " proposal" + (waiting === 1 ? "" : "s") + " below first. Suggest names works either way."; }
      else if (check.offered && (!checkRun || checkRun.state !== "done")) { said.textContent = "For the best names, run Check the speakers first. Suggest names works either way."; }
    }
    cards().forEach(function (card) {
      var box = card.querySelector(".suggested");
      box.hidden = true;
      box.innerHTML = "";
    });
    (body.pending || []).forEach(function (one) {
      var card = cardOf(one.speaker);
      if (!card) { return; }
      var box = card.querySelector(".suggested");
      box.hidden = false;
      // Which way the line points (v1.105.0): the app says whether the
      // speaker gave the name themselves or was called by it.
      var basis = one.basis === "introduces" ? ", who says so themselves at " : (one.basis === "addressed" ? ", called that by another speaker at " : ", from ");
      // A name reached through an Also called form (v1.140.0): the form is
      // the reason, said before the line.
      var through = one.form ? ", known here as \u201c" + escape(one.form) + "\u201d" : "";
      box.innerHTML = "Probably <b>" + escape(one.name) + "</b>" + (one.role ? " (" + escape(one.role) + ")" : "") + through +
        basis + "<a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a>: “" + escape(one.quote) + "” " +
        "<button type='button' class='tiny accept' data-suggestion='" + one.id + "' data-name='" + escape(one.name) + "'>Accept</button> " +
        "<button type='button' class='ghost tiny reject' data-suggestion='" + one.id + "'>Reject</button>";
    });
    return !!busy;
  }

  // What the check found (v1.129.0): one list of proposals, each a question
  // with a yes and a no, the biggest first. A proposal about a whole
  // speaker ("the same voice?") settles dozens of lines and sits at the
  // top; one about a few lines follows, the voice-backed first; the single
  // lines the voice could not judge and the proposals a speaker question
  // would settle fold under their counts. A count at the top goes down.
  function voicePill(voice, count) {
    if (voice === "agrees") { return "<span class='pill small ok' title='Word by word, the voice step heard the other speaker inside " + (count ? "these lines" : "this line") + ".'>two voices heard" + (count ? " on " + count + " line" + (count === 1 ? "" : "s") : "") + "</span>"; }
    if (voice === "against") { return "<span class='pill small warn' title='The voice step gave every word of " + (count ? "these long lines" : "this long line") + " to the speaker " + (count ? "they are" : "it is") + " labelled with.'>one voice heard, the labelled one" + (count ? ", on " + count + " line" + (count === 1 ? "" : "s") : "") + "</span>"; }
    if (voice === "mixed") { return "<span class='pill small' title='The voice step heard two voices on some of these lines and one on others.'>the voice is split</span>"; }
    return "<span class='pill small' title='" + (count ? "These lines are" : "This line is") + " short, or the words were not timed, so the voice step has nothing to add; the words alone decide.'>the voice is silent</span>";
  }

  // The share in three sizes and nothing else.
  function howMany(share) {
    if (share >= 0.67) { return "Most of"; }
    if (share >= 0.42) { return "Half of"; }
    if (share >= 0.25) { return "About a third of"; }
    return "A few of";
  }

  function cite(one) { return "<a href='#' class='cite mono' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a>"; }

  function speakerCard(card) {
    var figures = card.count + " of " + card.lines + " line" + (card.lines === 1 ? "" : "s") + " read as " + card.to + "'s" +
      card.others.map(function (one) { return ", " + one.count + " as " + one.to + "'s"; }).join("");
    var hear = card.hear.map(cite).join(" ");
    var own = card.own ? " <span class='muted'>&middot; " + escape(card.from) + " as itself:</span> " + cite(card.own) : "";
    var yes = card.voice === "against" ? ""
      : "<button type='button' class='tiny merge-card" + (card.clears ? " primary" : "") + "' data-from='" + escape(card.from) + "' data-to='" + escape(card.to) + "'>Yes, the same voice</button> ";
    return "<div class='found-card speaker" + (card.clears ? " clears" : "") + "' data-ids='" + card.ids.join(",") + "'>" +
      "<div class='title'><b>Is " + escape(card.from) + " the same voice as " + escape(card.to) + "?</b> " + voicePill(card.voice, card.voice === "agrees" ? card.voice_both : (card.voice === "against" ? card.voice_against : 0)) + "</div>" +
      "<div class='bar' title='" + escape(figures) + "'><i style='width: " + Math.round(card.share * 100) + "%'></i></div>" +
      "<p class='why small muted'>" + howMany(card.share) + " " + escape(card.from) + "'s lines read like " + escape(card.to) + ". Yes settles " + card.count + " line" + (card.count === 1 ? "" : "s") + ".</p>" +
      "<div class='hear small muted'>" + hear + own + "</div>" +
      "<div class='row acts'>" + yes + "<button type='button' class='ghost tiny not-same'>No</button></div></div>";
  }

  function plural(count, word) { return count + " " + word + (count === 1 ? "" : "s"); }

  // A Hand-over on its speaker's card (ADR 0021): another voice from a
  // time, Play before and after, Split here or not a different person.
  function drawHandovers() {
    cards().forEach(function (card) {
      var box = card.querySelector(".handover-box");
      if (!box) { return; }
      var mine = handovers.filter(function (one) { return one.speaker === card.dataset.name; });
      box.hidden = !mine.length;
      box.innerHTML = mine.map(function (one) {
        return "<div class='handover' data-handover='" + one.id + "' data-at='" + one.at + "'>" +
          "<b>Another voice from " + escape(one.clock) + "</b> under this label, " + plural(one.lines_after, "line") + (one.voices === 3 ? ", a third voice later" : "") + ". " +
          "<span class='hear3'><button type='button' class='hear-before' title='Play the six seconds before'>" + UI.icon("play") + " before</button><button type='button' class='hear-after' title='Play the six seconds after'>" + UI.icon("play") + " after</button></span> " +
          "<button type='button' class='tiny split-handover'>Split here</button> " +
          "<button type='button' class='ghost tiny dismiss-handover'>Not a different person</button></div>";
      }).join("");
    });
  }

  function drawCorrections(body) {
    if (!checkLine || !correctionsBox || !V.assistant.speakerCheck) { return false; }
    var check = body.speaker_check || {};
    var run = check.run;
    var cards = (check.speakers || []).slice().sort(function (a, b) { return b.count - a.count; });
    var all = check.stretches || [];
    var open = all.filter(function (one) { return !one.covered; });
    var backed = open.filter(function (one) { return one.voice === "agrees"; });
    var quiet = open.filter(function (one) { return one.voice !== "agrees"; });
    var covered = all.filter(function (one) { return one.covered; });
    var busy = run && (run.state === "queued" || run.state === "running");
    checkLine.hidden = !check.offered;
    var button = document.getElementById("check-speakers");
    var said = document.getElementById("check-said");
    button.disabled = !body.reachable || !!busy;
    button.title = body.reachable ? "" : (body.unavailable_line || "");
    // How it was read (v1.100.0): whole, or in windows.
    var how = run && run.state === "done" ? (run.whole ? ", read whole" : (run.windows ? ", read in " + plural(run.windows, "window") : "")) : "";
    if (busy) { said.textContent = run.sketch ? "Reading the transcript, " + (run.windows ? run.windows + " windows so far..." : "window by window...") : "Reading the whole transcript for who is who..."; }
    else if (run && run.state === "failed") { said.textContent = run.said || ""; }
    else if (run && run.state === "done" && !cards.length && !all.length) { said.textContent = "Checked " + run.when + how + "; nothing to move."; }
    else if (run && run.state === "done") { said.textContent = "Checked " + run.when + how + "."; }
    else { said.textContent = ""; }
    // The names the same run suggested (v1.140.0, the one run).
    if (run && run.state === "done" && V.assistant.suggestions) {
      if (typeof run.names === "number") { said.textContent += run.names ? " It also suggested " + plural(run.names, "name") + ", on the cards." : " Nothing in the transcript shows who the speakers are."; }
      else if (run.names_state === "failed") { said.textContent += " The names could not be suggested this time."; }
    }
    if (run && run.cut_short) {
      // A window's list ran past the answer cap (v1.56.0): the run did not
      // see everything, and the page says so rather than looking finished.
      said.textContent += " " + run.cut_short + (run.cut_short === 1 ? " window's list was" : " windows' lists were") +
        (document.body.dataset.admin === "1"
          ? " cut short at the answer cap; raise the cap on the Panel's Speakers page or shorten the window, then check again."
          : " cut short at the answer cap; ask your Admin to raise it, then check again.");
    }
    // The one explanation on the page, and the count that goes down. Once
    // everything is settled the count stays, so the page says it is done.
    var found = run && run.found ? run.found : (check.pending || []).length;
    var pending = check.pending || [];
    var left = pending.length;
    var settled = Math.max(0, found - left);
    var waitingHandovers = check.handovers || [];
    var backedLines = pending.filter(function (one) { return one.voice === "agrees"; }).length;
    var quietLines = pending.filter(function (one) { return !one.voice; }).length;
    var byVoice = pending.filter(function (one) { return one.source === "voice"; }).length;
    correctionsBox.hidden = !cards.length && !pending.length && !settled && !waitingHandovers.length;
    var how2 = check.voice === "titanet" ? " The voice listened to every line." : (check.voice === "unavailable" ? " The voice could not listen this time; the words alone proposed these." : "");
    document.getElementById("corrections-state").textContent = !left && settled
      ? "The check found " + plural(found, "change") + "; every one is settled."
      : "The check found " + plural(found, "change") + (backedLines ? ", " + backedLines + " backed by the voice" : "") + (byVoice ? ", " + byVoice + " the voice found on its own" : "") +
        (waitingHandovers.length ? "; " + plural(waitingHandovers.length, "hand-over") : "") + "." + how2 + " Read down; accept or leave each as you go.";
    var progress = document.getElementById("corrections-progress");
    progress.hidden = !found;
    progress.querySelector(".track i").style.width = (found ? Math.round((settled / found) * 100) : 0) + "%";
    document.getElementById("corrections-found").textContent = plural(found, "change") + " found";
    document.getElementById("corrections-left").textContent = settled ? settled + " settled, " + left + " left" : "0 settled";
    document.getElementById("speaker-cards").innerHTML = cards.map(speakerCard).join("");
    // The changes live in the transcript now (ADR 0021): by segment id.
    changes = {};
    pending.forEach(function (one) { changes[String(one.segment)] = one; });
    handovers = waitingHandovers;
    var acceptBacked = document.getElementById("accept-corrections");
    acceptBacked.hidden = backedLines < 1;
    acceptBacked.textContent = "Accept the " + backedLines + " change" + (backedLines === 1 ? "" : "s") + " the voice backs";
    document.getElementById("corrections-where").hidden = !pending.length;
    var quietButton = document.getElementById("show-quiet");
    if (quietButton) {
      quietButton.hidden = !quietLines;
      quietButton.textContent = showQuiet ? "Hide the " + quietLines + " the voice could not judge" : quietLines + " more the voice could not judge: show them in place";
    }
    document.getElementById("stretches-quiet").hidden = true;
    document.getElementById("stretches-covered").hidden = true;
    document.getElementById("corrections-actions").hidden = backedLines < 1;
    drawHandovers();
    if (segments.length) { draw(); drawLanes(); }
    var again = document.getElementById("check-again-why");
    if (again) { again.hidden = !settled; }
    // The bar at the foot on a phone (v1.140.0): what is left, and Run again.
    var foot = document.getElementById("sp-foot");
    if (foot) {
      foot.hidden = !run;
      document.getElementById("foot-left").textContent = busy ? "reading..." : (left ? left + " left" : (settled ? "all settled" : ""));
      document.getElementById("foot-run-again").disabled = !body.reachable || !!busy;
    }
    // The finding on the speaker's own card, where the person already looks.
    Array.prototype.forEach.call(document.querySelectorAll(".sp-card .check-hint"), function (pill) { pill.remove(); });
    cards.forEach(function (card) {
      var owner = cardOf(card.from);
      var head = owner && owner.querySelector(".h");
      if (!head) { return; }
      var pill = document.createElement("span");
      pill.className = "pill small warn check-hint";
      pill.textContent = "reads like " + card.to + "?";
      head.appendChild(pill);
    });
    var scoreLine = document.getElementById("corrections-score");
    if (scoreLine) {
      var score = check.score || {};
      var decided = (score.accepted || 0) + (score.dismissed || 0);
      scoreLine.hidden = !decided;
      scoreLine.textContent = decided ? "Decided so far: " + (score.accepted || 0) + " yes, " + (score.dismissed || 0) + " no." : "";
    }
    return !!busy;
  }

  function swap(a, b, start, end) {
    return UI.confirm({
      title: "Swap " + a + " and " + b + " between " + clock(start) + " and " + clock(end) + "?",
      body: "Every line of " + a + " in that stretch becomes " + b + "'s, and the other way round. Undo puts them all back.",
      ok: "Swap"
    }).then(function (yes) {
      if (!yes) { return; }
      return send("/recording/" + V.recording + "/speakers/swap", { a: a, b: b, start: start, end: end }).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "Nothing was swapped.", { problem: true, icon: "warning" }); return; }
        sayUndo(answer.said.undo);
        tell({ kind: "segments-changed" });
        load().then(refreshSuggestions);
      });
    });
  }

  // "mm:ss", "h:mm:ss" or plain seconds, as a person types a time.
  function secondsOf(text) {
    var parts = String(text || "").trim().split(":").map(function (one) { return parseFloat(one); });
    if (!parts.length || parts.some(isNaN)) { return NaN; }
    return parts.reduce(function (total, one) { return total * 60 + one; }, 0);
  }

  var swapForm = document.getElementById("swap-form");
  if (swapForm) {
    document.getElementById("swap-open").addEventListener("click", function () {
      swapForm.hidden = !swapForm.hidden;
      if (!swapForm.hidden) {
        document.getElementById("swap-from").value = clock(now());
        document.getElementById("swap-to").value = clock(duration);
        var a = document.getElementById("swap-a");
        if (picked && names().indexOf(picked) !== -1) { a.value = picked; }
      }
    });
    document.getElementById("swap-cancel").addEventListener("click", function () { swapForm.hidden = true; });
    document.getElementById("swap-go").addEventListener("click", function () {
      var a = document.getElementById("swap-a").value;
      var b = document.getElementById("swap-b").value;
      var start = secondsOf(document.getElementById("swap-from").value);
      var end = secondsOf(document.getElementById("swap-to").value);
      if (a === b) { UI.toast("Choose two different speakers.", { problem: true, icon: "warning" }); return; }
      if (isNaN(start) || isNaN(end) || start >= end) { UI.toast("The times must run forward, as mm:ss.", { problem: true, icon: "warning" }); return; }
      swap(a, b, start, end).then(function () { swapForm.hidden = true; });
    });
  }

  function refreshSuggestions() {
    if (!V.assistant || (!V.assistant.suggestions && !V.assistant.speakerCheck)) { return; }
    // Not while the tab is hidden (v1.134.0): the ask waits for it to come back.
    window.UI.whenVisible().then(function () { return fetch("/recording/" + V.recording + "/assistant"); })
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        var busy = drawNameSuggestions(body);
        busy = drawCorrections(body) || busy;
        if (suggestTimer) { window.clearTimeout(suggestTimer); suggestTimer = null; }
        if (busy) { suggestTimer = window.setTimeout(refreshSuggestions, 2000); }
      })
      .catch(function () {
        // One failed answer (an upgrade's restart, a network blink) used to
        // end the polling for good and leave the buttons dead (v1.132.0).
        if (said) { said.textContent = "The app did not answer; trying again."; }
        if (suggestTimer) { window.clearTimeout(suggestTimer); }
        suggestTimer = window.setTimeout(refreshSuggestions, 6000);
      });
  }

  // A correction accepted moves the line here as give() does, so the lanes,
  // the counts and the reading pane change at once; Accept all reloads the
  // lines instead, since many may have moved.
  function moved(segmentId, name) {
    var segment = segments.filter(function (one) { return String(one.id) === String(segmentId); })[0];
    if (!segment) { return; }
    segment.speaker = name;
    buildBlocks();
    fillCounts();
    var keep = here;
    draw();
    here = keep;
    var row = rowAt(keep);
    if (row) { row.classList.add("here"); }
    drawLanes();
    tell({ kind: "segments-changed" });
  }
  var footRun = document.getElementById("foot-run-again");
  if (footRun) { footRun.addEventListener("click", function () { var button = document.getElementById("check-speakers"); if (button) { button.click(); } }); }
  if (checkLine) {
    document.getElementById("check-speakers").addEventListener("click", function () {
      var button = this;
      button.disabled = true;
      send("/recording/" + V.recording + "/speaker-check").then(function (got) {
        if (!got.ok) { button.disabled = false; return; }
        refreshSuggestions();
      });
    });
  }
  if (correctionsBox) {
    correctionsBox.addEventListener("click", function (event) {
      var cite = event.target.closest(".cite");
      if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.seconds)); play(); return; }
      if (event.target.closest("#check-again")) { document.getElementById("check-speakers").click(); return; }
      if (event.target.closest("#accept-corrections")) {
        send("/recording/" + V.recording + "/corrections/accept-all").then(function (answer) {
          if (!answer.ok) { UI.toast(answer.said.error || "Nothing was moved.", { problem: true, icon: "warning" }); return; }
          sayUndo(answer.said.undo);
          load().then(refreshSuggestions);
        });
        return;
      }
      // Yes on a speaker question is the page's own merge, with its Undo;
      // the corrections follow it (v1.129.0).
      var mergeCard = event.target.closest(".merge-card");
      if (mergeCard) { merge(mergeCard.dataset.from, mergeCard.dataset.to); return; }
      var card = event.target.closest(".found-card");
      if (!card) { return; }
      var ids = (card.dataset.ids || "").split(",").filter(Boolean);
      var accept = event.target.closest(".accept-stretch");
      var dismiss = event.target.closest(".dismiss-stretch, .not-same");
      if (!accept && !dismiss) { return; }
      send("/recording/" + V.recording + "/corrections/" + (accept ? "accept" : "dismiss") + "-many", { ids: ids.join(",") }).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
        if (accept) {
          if (!answer.said.changed) { UI.toast("Those lines changed since the check, so they were left as they are.", { icon: "info" }); }
          else { sayUndo(answer.said.undo); }
          load().then(refreshSuggestions);
          return;
        }
        refreshSuggestions();
      });
    });
  }
  if (suggestLine) {
    document.getElementById("suggest-names").addEventListener("click", function () {
      var button = this;
      button.disabled = true;
      send("/recording/" + V.recording + "/suggest").then(function (got) {
        if (!got.ok) { button.disabled = false; return; }
        refreshSuggestions();
      });
    });
    cardsBox.addEventListener("click", function (event) {
      var cite = event.target.closest(".cite");
      if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.seconds)); play(); }
    });
  }
  if (cardsBox) {
    cardsBox.addEventListener("click", function (event) {
      var box = event.target.closest(".handover");
      if (!box) { return; }
      var at = parseFloat(box.dataset.at);
      if (event.target.closest(".hear-before")) { playRange(at - 6, at); return; }
      if (event.target.closest(".hear-after")) { playRange(at, at + 6); return; }
      var split = event.target.closest(".split-handover");
      var dismiss = event.target.closest(".dismiss-handover");
      if (!split && !dismiss) { return; }
      send("/handover/" + box.dataset.handover + "/" + (split ? "accept" : "dismiss")).then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
        if (split) {
          if (answer.said.stale) { UI.toast("No line of that speaker lies after the time any more.", { icon: "info" }); refreshSuggestions(); return; }
          tell({ kind: "speakers-changed" });
          reloadHere(answer.said.made || picked);
          return;
        }
        refreshSuggestions();
      });
    });
  }

  // Undo: the viewer's own, then the page loads again at this moment.
  var undoButton = document.getElementById("speakers-undo");
  if (undoButton) {
    undoButton.addEventListener("click", function () {
      var what = document.getElementById("speakers-undo-what").textContent;
      UI.confirm({ title: "Undo " + what + "?", body: "The lines that were moved take their old name back. Nothing else changes.", ok: "Undo" })
        .then(function (yes) {
          if (!yes) { return; }
          send("/recording/" + V.recording + "/speakers/undo").then(function (answer) {
            if (!answer.ok) { return; }
            tell({ kind: "speakers-changed" });
            reloadHere(picked);
          });
        });
    });
  }

  // The keys --------------------------------------------------------------------

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }
    if (/^[1-9]$/.test(event.key)) {
      var name = names()[parseInt(event.key, 10) - 1];
      if (name) { event.preventDefault(); give(currentSegment(), name); }
    } else if (event.key === " ") {
      event.preventDefault();
      stopAt = null;
      if (player ? !player.paused : false) { pause(); } else { play(); }
    } else if (event.key === "b" || event.key === "B") {
      seek(now() - 3);
      play();
    } else if (event.key === "f" || event.key === "F") {
      resumeFollowing();
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      var by = event.shiftKey ? 1 : (event.ctrlKey || event.metaKey ? 30 : 5);
      seek(now() + (event.key === "ArrowLeft" ? -by : by));
    }
  });

  // The channel, in a window: the page's time when it plays, and word of
  // changes made here.
  if (channel) {
    channel.onmessage = function (event) {
      var said = event.data || {};
      if (said.kind === "time") {
        if (player) {
          if (said.playing && !player.paused) { player.pause(); }
          if (player.paused && Math.abs(player.currentTime - (said.at || 0)) > 1) { player.currentTime = said.at || 0; }
        }
        if (state) { state.textContent = said.playing ? "The recording's page is playing, " + clock(said.at || 0) : ""; }
        if (!player || player.paused) { followAt(said.at || 0); }
      } else if (said.kind === "page-closed") {
        if (state) { state.textContent = "The recording's page has closed."; }
      }
    };
    tell({ kind: "window-open", panel: "speakers" });
    window.addEventListener("beforeunload", function () { tell({ kind: "window-closed", panel: "speakers" }); });
  }

  // Off we go ------------------------------------------------------------------

  function load() {
    if (!V.hasTranscript) { return Promise.resolve(); }
    // Without the words (v1.134.0): this page reads lines, speakers and
    // times and never a word's timing, and the words were most of the answer.
    return fetch("/recording/" + V.recording + "/segments?words=0")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        segments = body.segments || [];
        if (!duration && segments.length) { duration = segments[segments.length - 1].end; }
        buildBlocks();
        fillCounts();
        draw();
        drawLanes();
      })
      .catch(function () { if (state) { state.textContent = "The transcript could not be read; try the page again."; } });
  }

  load().then(function () {
    var asked = new URLSearchParams(window.location.search);
    var when = parseFloat(asked.get("t"));
    if (!isNaN(when) && when >= 0 && player) { player.currentTime = when; followAt(when); }
    var wanted = asked.get("pick");
    var first = cards().filter(function (card) { return card.classList.contains("unnamed"); })[0] || cards()[0];
    var card = wanted ? cardOf(wanted) : null;
    pick((card || first) ? (card || first).dataset.name : "");
    sayProgress();
    keepDone();
    refreshSuggestions();
  });
})();

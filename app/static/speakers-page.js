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
  // Hold still while a speaker picker is open (v1.142.1): a sample played
  // from the picker seeks the player, and following had scrolled the page to
  // that line, taking the row being judged and the picker with it. The
  // picker says when it opens and closes; while it is open nothing scrolls,
  // and when it closes the page returns to the line in hand.
  var holding = false;
  var holdRow = null;
  document.addEventListener("picker-open", function (event) {
    holding = true;
    holdRow = event.detail && event.detail.anchor ? event.detail.anchor : null;
  });
  document.addEventListener("picker-close", function () {
    holding = false;
    if (holdRow && holdRow.isConnected) { holdRow.scrollIntoView({ block: "center", behavior: "smooth" }); }
    holdRow = null;
  });
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
  // The Preview pauses this page's player before it plays (v1.142.2).
  V.pause = pause;

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
  var wordTiming = false;

  // The words, each with its time, when the Transcript has them (v1.141.0).
  function wordsOf(segment) {
    if (!wordTiming || !segment.words || !segment.words.length) { return escape(segment.text); }
    return segment.words.map(function (word) {
      var start = word.start === undefined ? "" : word.start;
      var end = word.end === undefined ? "" : word.end;
      return "<span class='word' data-start='" + start + "' data-end='" + end + "'>" + escape(word.word) + "</span>";
    }).join(" ");
  }

  // The pill on a line whose timing is a guess (v1.141.0): a phrase the
  // recogniser repeated, or words spread far thinner than the recording's
  // pace; such a line is never a sample, and its clock is not to be argued with.
  function guessPill(segment) {
    if (!segment.guess) { return ""; }
    return "<span class='pill small guess' title='The recogniser repeated a phrase here, or spread the words far thinner than usual: it was guessing, and the times of these words may be off by a few seconds.'>the timing of these words is a guess</span>";
  }

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
      if (change && change.settled) { previous = null; return; }
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
      if (change && !change.settled && runStart[index] && runIds[index].length > 1) {
        var head = document.createElement("li");
        head.className = "block-head";
        head.dataset.index = index;
        head.dataset.ids = runIds[index].join(",");
        head.innerHTML = "<b>" + runIds[index].length + " lines</b> <span class='muted'>shown as " + escape(change.from) + ", read as " + escape(change.to) + "'s</span> " + changePill(change) + rereadPill(change) +
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
      if (change && change.split_at !== null && change.split_at !== undefined && !change.settled) {
        // A mixed line (v1.145.0): the part the voice hears as another's is
        // marked; Accept splits the line at that word.
        row.classList.add("change", "mixed");
        row.dataset.correction = change.id;
        var ws = (segment.words || []).map(function (w) { return escape(String(w.word || w.text || "")); });
        var marked = change.split_part === "first"
          ? "<mark>" + ws.slice(0, change.split_at).join(" ") + "</mark> " + ws.slice(change.split_at).join(" ")
          : ws.slice(0, change.split_at).join(" ") + " <mark>" + ws.slice(change.split_at).join(" ") + "</mark>";
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'>" + escape(segment.speaker) + " <span class='pill small warn'>two voices</span></span></div>" +
          "<div class='words'><p class='txt'>" + (ws.length ? marked : wordsOf(segment)) + "</p></div>" +
          "<div class='why small muted'>" + escape(change.reason) + (change.words_why ? "; " + escape(change.words_why) : "") + "</div>" +
          "<span class='actions change-acts'>" + hearThree(change) +
          "<button type='button' class='tiny accept-change' title='Split the line at the marked word and give that part to " + escape(change.to) + "'>Split at the word, " + escape(change.split_part || "second") + " part to " + escape(change.to) + "</button>" +
          "<button type='button' class='ghost tiny leave-change' title='Leave the line as it is and put the proposal away'>Leave</button>" +
          "</span>";
      } else if (change && change.settled) {
        // A proposal the name settled (v1.144.1): in place, tinted, with
        // what settled it and the viewer's Undo of the name.
        row.classList.add("change", "settled");
        row.dataset.correction = change.id;
        var by = change.settled_by || {};
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'><s>" + escape(change.from) + "</s> <span class='to' style='--speaker: " + (colours[change.to] || "") + "'>" + escape(change.to) + "</span></span><span class='tags'>" + guessPill(segment) + "</span></div>" +
          "<div class='words'><p class='txt'>" + wordsOf(segment) + "</p></div>" +
          "<span class='actions change-acts'><span class='pill small ok'>settled: this line is " + escape(change.to) + "'s now</span>" +
          (by.was ? "<span class='muted tiny'>by naming " + escape(by.was) + " as " + escape(by.now) + "</span>" : "") +
          "<button type='button' class='ghost tiny undo-name' title='Undo the name; the proposal comes back as it was'>Undo</button></span>";
      } else if (change) {
        row.classList.add("change", change.voice || "quiet");
        row.dataset.correction = change.id;
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'><s>" + escape(change.from) + "</s> <span class='to' style='--speaker: " + (colours[change.to] || "") + "'>" + escape(change.to) + "</span></span><span class='tags'>" + guessPill(segment) + "</span></div>" +
          "<div class='words'><p class='txt'>" + wordsOf(segment) + "</p></div>" +
          "<span class='actions change-acts'>" + changePill(change) + rereadPill(change) + hearThree(change) +
          "<button type='button' class='tiny" + (change.voice === "agrees" ? " primary" : "") + " accept-change' title='Move this line to " + escape(change.to) + "'>Accept</button>" +
          "<button type='button' class='ghost tiny leave-change' title='Leave the line as it is and put the proposal away'>Leave</button>" +
          "</span>";
      } else {
        row.innerHTML =
          "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
          "<div class='who'><span class='name'>" + escape(segment.speaker) + "</span><span class='tags'>" + guessPill(segment) + "</span></div>" +
          "<div class='words'><p class='txt'>" + wordsOf(segment) + "</p></div>" +
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
        else if (change && change.split_at !== null && change.split_at !== undefined) {
          // A line split at the word (v1.145.0): a new line exists, so the
          // page loads again at this moment rather than moving a row.
          tell({ kind: "segments-changed" });
          reloadHere(picked);
          return;
        }
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
      if (was) {
        was.classList.remove("here");
        Array.prototype.forEach.call(was.querySelectorAll(".word.now"), function (word) { word.classList.remove("now"); });
      }
      var row = rowAt(index);
      if (row) {
        row.classList.add("here");
        if (following && !paused && !holding && !row.hidden && outOfTheMiddle(row)) {
          row.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      here = index;
      sayNow(index >= 0 ? segments[index] : null);
    }
    // The word being said, underlined (v1.141.0), as on the recording page.
    var lit = wordTiming ? rowAt(here) : null;
    if (lit) {
      Array.prototype.forEach.call(lit.querySelectorAll(".word"), function (word) {
        var start = parseFloat(word.dataset.start);
        var end = parseFloat(word.dataset.end);
        word.classList.toggle("now", !isNaN(start) && when >= start && when <= end);
      });
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
    if (row && !row.hidden && !holding) { row.scrollIntoView({ block: "center", behavior: "smooth" }); }
  }
  if (reading) {
    window.addEventListener("wheel", function (event) {
      if (!event.target.closest || !event.target.closest(".sp-read")) { return; }
      if (!paused) { pauseFollowing(); }
    }, { passive: true });
  }
  if (pill) { document.getElementById("resume-follow").addEventListener("click", resumeFollowing); }

  // Playing one line and stopping at its end: a sample, or play on a row.
  // With half a second either side (v1.141.0), so a line whose clock is a
  // word off is still heard whole, in its sentence.
  var MARGIN = 0.5;
  function playLine(segment) {
    seek(Math.max(0, segment.start - MARGIN));
    stopAt = segment.end + MARGIN;
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
    // Voices first (v1.145.0): on a line in doubt the words' second reading
    // sits beside the voice's word.
    if (stageNow && change.source === "voice" && !change.settled) {
      if (change.words === "agrees") { return "<span class='pill small ok' title='The voice and the words both read this line as " + escape(change.to) + "\'s.'>voice and words agree</span>"; }
      if (change.words === "against") { return "<span class='pill small warn' title='" + escape(change.words_why || "The words read this line as it is labelled.") + "'>the words read it the other way; listen first</span>"; }
      if (!change.voice) { return "<span class='pill small' title='" + escape(change.reason) + "'>the voice cannot tell</span>"; }
      return "<span class='pill small acc' title='" + escape(change.reason) + (change.words_why ? "; " + escape(change.words_why) : "") + "'>the voice alone</span>";
    }
    if (change.voice === "agrees") { return "<span class='pill small ok' title='The voice on this line sounds like " + escape(change.to) + ".'>the voice agrees</span>"; }
    if (change.voice === "against") { return "<span class='pill small danger' title='The voice on this line sounds like " + escape(change.from) + ", not " + escape(change.to) + ". Listen before you accept.'>the voice disagrees, listen first</span>"; }
    return "<span class='pill small' title='The line is short, or the two speakers sound alike on it; the words alone propose this.'>the voice could not judge</span>";
  }

  function drawnChange(segment) {
    var change = changes[String(segment.id)];
    if (!change) { return null; }
    if (change.settled) { return change; }
    if (!change.voice && !showQuiet) { return null; }
    return change;
  }

  // The re-read after a name (v1.144.1): the pill on a block or a row the
  // re-read touched, and the line under the check's state.
  function rereadPill(change) {
    if (!rereadNote || !change || (rereadNote.touched || []).indexOf(change.id) < 0) { return ""; }
    return " <span class='pill small acc reread-pill' title='This proposal was rewritten for the new name'>re-read for " + escape(rereadNote["for"]) + "</span>";
  }
  function agoText(iso) {
    var then = Date.parse(iso || "");
    if (!then) { return ""; }
    var minutes = (Date.now() - then) / 60000;
    if (minutes < 2) { return "a moment ago"; }
    var d = new Date(then);
    return "at " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }
  function drawRereadLine(check) {
    var line = document.getElementById("reread-line");
    if (!line) { return; }
    var note = rereadNote;
    var dismissed = false;
    try { dismissed = !!note && window.sessionStorage.getItem("reread-dismissed") === note.at; } catch (e) { dismissed = false; }
    if (!note || !note["for"] || dismissed) { line.hidden = true; line.innerHTML = ""; return; }
    var parts = [];
    var settled = (note.settled || []).length;
    var touched = (note.touched || []).length;
    var closed = (note.closed || []).length;
    var fresh = (note.new_matches || []).length;
    if (settled) { parts.push(plural(settled, "proposal") + (settled === 1 ? " was" : " were") + " settled by the name"); }
    if (touched) { parts.push(touched + " now read" + (touched === 1 ? "s" : "") + " against " + escape(note["for"])); }
    if (closed) { parts.push(plural(closed, "name suggestion") + " closed"); }
    if (fresh) { parts.push(fresh + " more voice" + (fresh === 1 ? "" : "s") + " on this call sound" + (fresh === 1 ? "s" : "") + " like " + escape(note["for"])); }
    var said = parts.length
      ? "<b>Re-read for " + escape(note["for"]) + "</b> " + agoText(note.at) + ": " + parts.join(", ") + "."
      : "<b>Re-read for " + escape(note["for"]) + "</b> " + agoText(note.at) + ": the proposals already read against the new name; nothing changed.";
    line.className = "reread small" + (parts.length ? "" : " quiet");
    line.innerHTML = "<span class='tick'>\u2713</span> <span class='said'>" + said +
      " The words were read before the name; <button type='button' class='linklike reread-run'>Run again</button> re-reads them too.</span>" +
      "<button type='button' class='ghost tiny reread-dismiss' title='Hide this line'>dismiss</button>";
    line.hidden = false;
  }
  document.addEventListener("click", function (event) {
    if (event.target.closest(".reread-run")) { var run = document.getElementById("check-speakers"); if (run) { run.click(); } return; }
    if (event.target.closest(".reread-dismiss")) {
      try { if (rereadNote) { window.sessionStorage.setItem("reread-dismissed", rereadNote.at); } } catch (e) { /* no storage */ }
      var line = document.getElementById("reread-line");
      if (line) { line.hidden = true; }
      return;
    }
    if (event.target.closest(".undo-name")) { var undo = document.getElementById("speakers-undo"); if (undo) { undo.click(); } }
  });
  function pendingNow() { return Object.keys(changes).filter(function (id) { return !changes[id].settled; }).length; }
  function sayRereading(was, to) {
    var n = pendingNow();
    if (!n) { return; }
    UI.toast(escape(was) + " is now " + escape(to) + ". Re-reading " + plural(n, "proposal") + " for the new name\u2026", { icon: "info" });
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
    if (row && following && !paused && !holding) { row.scrollIntoView({ block: "center" }); }
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
      sayRereading(was, to);
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
      sayRereading(was, onto);
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
  function give(segment, name, role) {
    if (!segment || !name || segment.speaker === name) { return; }
    var known = names().indexOf(name) >= 0;
    return send("/recording/" + V.recording + "/segment/" + segment.id + "/speaker", { speaker: name, role: role || "" })
      .then(function (answer) {
        if (!answer.ok) { UI.toast(answer.said.error || "That line was not changed.", { problem: true, icon: "warning" }); return; }
        // A person from the case, or someone new (v1.142.0): a speaker this
        // page has no card for yet, so the page loads again at this moment.
        if (!known) { tell({ kind: "speakers-changed" }); reloadHere(name); return; }
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

  // The speaker picker (v1.142.0): never a typed number. Opened under the
  // line's row, or under the card a sample sits on.
  function giveLine(segment, anchor, beside) {
    if (!window.Picker) {
      askWhich("Whose line is this?", "“" + segment.text.slice(0, 80) + "”", segment.speaker)
        .then(function (name) { if (name) { give(segment, name); } });
      return;
    }
    var index = segments.indexOf(segment);
    window.Picker.open({
      recording: V.recording,
      anchor: anchor || rowAt(index) || null,
      beside: beside || null,
      question: "Whose line is this?",
      quote: "“" + segment.text.slice(0, 80) + "”",
      current: segment.speaker,
      play: playRange,
      onPick: function (name, role) { return give(segment, name, role); }
    });
  }

  // Name or merge (v1.143.0, the drawing phase-5-speakers-page-breathes.html):
  // the picker beside the card asks "<speaker> is". Another speaker on the
  // call is the same person (the merge, confirmed as before); a person of
  // the case, or someone new with a role, names every line (the rename).
  function nameOrMerge(card) {
    var name = card.dataset.name;
    if (!window.Picker) {
      askWhich(name + " is the same person as...", "Every line of " + name + " takes that speaker's name.", name)
        .then(function (onto) { if (onto) { merge(name, onto); } });
      return;
    }
    var first = card.querySelector(".sample");
    var quote = first && first.dataset.quote ? first.dataset.quote.slice(0, 60) : "";
    window.Picker.open({
      recording: V.recording,
      anchor: card,
      beside: card,
      question: name + " is",
      quote: quote ? "\u201c" + quote + "\u201d" : "",
      current: name,
      currentPill: "this one",
      merging: true,
      prefill: stageNow ? (((card.querySelector(".suggested.hint b") || {}).textContent) || suggestedFor[name] || "") : "",
      suggested: suggestedFor[name] || "",
      newGo: "Name",
      newHint: "Names every line of " + name + "; inside a case it also makes the person, and a name already in the case joins that person.",
      play: playRange,
      onPick: function (picked, role) {
        if (!picked) { return; }
        if (names().indexOf(picked) >= 0) { return merge(name, picked); }
        return rename(name, picked, role);
      }
    });
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
      // Not this voice (v1.142.0): a sample that is not this speaker is a
      // line like any other, moved by the picker, from the card it sits on.
      var wrong = event.target.closest(".not-voice");
      if (wrong) {
        var line = segments.filter(function (one) { return String(one.id) === String(wrong.dataset.segment); })[0];
        if (line) { giveLine(line, card, card); }
        else { UI.toast("That line is not in the transcript any more; the page loads again.", { icon: "info" }); reloadHere(name); }
        return;
      }
      // Name or merge (v1.143.0): the one picker, beside the card, asks
      // "<speaker> is"; rename, same person as and the name box folded into it.
      if (event.target.closest(".name-or-merge")) { nameOrMerge(card); return; }
      // Voices first (v1.145.0): a named card is folded to a line; its
      // stats line opens it again.
      if (stageNow && event.target.closest(".stats") && !card.classList.contains("unnamed")) { card.classList.toggle("open"); return; }
      if (event.target.closest(".closed-dismiss")) {
        try { if (rereadNote) { window.sessionStorage.setItem("reread-closed-dismissed", rereadNote.at); } } catch (e) { /* no storage */ }
        var closedBox = card.querySelector(".suggested");
        if (closedBox) { closedBox.hidden = true; closedBox.innerHTML = ""; }
        return;
      }
      // Sounds like (v1.144.0): Accept names the label as the Person on every
      // line and teaches the print; Not them sets the match aside; Neither
      // sets a conflict's rows aside; the Side alarm's "Not X on this call"
      // opens the picker for the whole side.
      var matchAccept = event.target.closest(".match-accept");
      if (matchAccept) {
        matchAccept.disabled = true;
        if (pendingNow()) { UI.toast("Re-reading " + plural(pendingNow(), "proposal") + " for the new name\u2026", { icon: "info" }); }
        send("/voice-match/" + matchAccept.dataset.match + "/accept").then(function (answer) {
          if (!answer.ok) { matchAccept.disabled = false; UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
          tell({ kind: "speakers-changed" });
          if (answer.said.changed) { reloadHere(answer.said.made || name); } else { refreshSuggestions(); }
        });
        return;
      }
      // The unit's voice book (v1.146.0): Check compares by a press; Accept
      // names the label as the book's Person; Not them counts against it.
      var bookCheck = event.target.closest(".book-check, .book-check-again");
      if (bookCheck) {
        bookCheck.disabled = true;
        UI.toast("Comparing " + name + " with the unit's voices\u2026", { icon: "info" });
        send("/recording/" + V.recording + "/book-check", { speaker: name }).then(function (answer) {
          bookCheck.disabled = false;
          if (!answer.ok) { UI.toast(answer.said.error || "The book could not be checked.", { problem: true, icon: "warning" }); return; }
          refreshSuggestions();
        });
        return;
      }
      var bookAccept = event.target.closest(".book-accept");
      if (bookAccept) {
        bookAccept.disabled = true;
        send("/book-check/" + bookAccept.dataset.check + "/accept").then(function (answer) {
          if (!answer.ok) { bookAccept.disabled = false; UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
          tell({ kind: "speakers-changed" });
          reloadHere(answer.said.made || name);
        });
        return;
      }
      var bookDismiss = event.target.closest(".book-dismiss");
      if (bookDismiss) {
        var checkIds = (bookDismiss.dataset.checks || bookDismiss.dataset.check || "").split(",").filter(Boolean);
        Promise.all(checkIds.map(function (id) { return send("/book-check/" + id + "/dismiss"); })).then(function () { refreshSuggestions(); });
        return;
      }
      var matchDismiss = event.target.closest(".match-dismiss");
      if (matchDismiss) {
        var ids = (matchDismiss.dataset.matches || matchDismiss.dataset.match || "").split(",").filter(Boolean);
        Promise.all(ids.map(function (id) { return send("/voice-match/" + id + "/dismiss"); })).then(function () { refreshSuggestions(); });
        return;
      }
      if (event.target.closest(".side-not")) {
        var sideBox = event.target.closest(".sounds");
        var who = sideBox ? sideBox.dataset.person : name;
        window.Picker.open({
          recording: V.recording,
          anchor: card,
          beside: card,
          question: who + " on this call is",
          current: who,
          currentPill: "the case rule's name",
          newSpeaker: true,
          newGo: "Name",
          play: playRange,
          onPick: function (picked, role) { if (picked) { return rename(who, picked, role); } }
        });
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

  }

  // A speaker split off a moment ago (v1.143.0): its card says where it
  // came from, once, after the page has loaded again.
  (function () {
    var note = null;
    try {
      note = JSON.parse(window.sessionStorage.getItem("sp-split") || "null");
      window.sessionStorage.removeItem("sp-split");
    } catch (e) { note = null; }
    if (!note || !note.name) { return; }
    var card = cardOf(note.name);
    var head = card ? card.querySelector(".h") : null;
    if (!head) { return; }
    var pill = document.createElement("span");
    pill.className = "pill split-from";
    pill.textContent = "split from " + note.from + " at " + note.at;
    head.insertBefore(pill, head.querySelector(".label"));
  })();

  // Suggest names: the AI assistant's feature, from the words, on request.
  // A suggestion lands on its speaker's card with Accept and Reject.
  var suggestLine = document.getElementById("suggest-line");
  var suggestTimer = null;
  var suggestedFor = {};  // speaker -> the name the check suggested (v1.143.0: lit in the picker)
  var rereadNote = null;  // the last re-read after a name (v1.144.1), from the run
  var stageNow = null;    // voices first (v1.145.0): 1, 2, 3, or null where the words ran first
  var lastCheck = null;
  function sendForm(url, fields) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": cookie("csrftoken") },
      body: new URLSearchParams(fields || {}).toString()
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    }).catch(function () { return { ok: false, said: {} }; });
  }
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
      if (!box) { return; }
      box.hidden = true;
      box.innerHTML = "";
    });
    suggestedFor = {};
    (body.pending || []).forEach(function (one) {
      var card = cardOf(one.speaker);
      if (!card) { return; }
      var box = card.querySelector(".suggested");
      if (!box) { return; }
      suggestedFor[one.speaker] = one.name;
      box.hidden = false;
      if ((body.speaker_check || {}).stage) {
        // Voices first (v1.145.0): the words' name is evidence on the card,
        // never an Accept of its own; Name or merge... starts with it typed.
        var basis2 = one.basis === "introduces" ? "said by this voice" : (one.basis === "addressed" ? "said to this voice" : "heard here");
        box.className = "suggested hint";
        box.innerHTML = "<span class='who'>The words point at a name: <b>" + escape(one.name) + "</b>" + (one.role ? " (" + escape(one.role) + ")" : "") + "</span>" +
          "<span class='q'>\u201c" + escape(one.quote) + "\u201d <a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a>, " + basis2 + "</span>" +
          "<span class='tiny muted'>Evidence, not an answer: Name or merge... starts with it typed.</span>";
        return;
      }
      box.className = "suggested";
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
    // A suggestion the name closed (v1.144.1): struck through on the named
    // card, with why, once, until dismissed or the next run.
    var closedShown = false;
    try { closedShown = !!rereadNote && window.sessionStorage.getItem("reread-closed-dismissed") === rereadNote.at; } catch (e) { closedShown = false; }
    if (rereadNote && (rereadNote.closed || []).length && !closedShown) {
      var named = cardOf(rereadNote["for"]);
      var closedBox = named ? named.querySelector(".suggested") : null;
      if (closedBox) {
        closedBox.hidden = false;
        closedBox.innerHTML = rereadNote.closed.map(function (one) {
          return "<s>Probably " + escape(one.name) + ", from " + escape(one.clock) + "</s> \u00b7 closed: this speaker is " + escape(rereadNote["for"]) + " now";
        }).join("<br>") + " <button type='button' class='ghost tiny closed-dismiss'>dismiss</button>";
      }
    }
    return !!busy;
  }

  // Sounds like (Phase 5 chapter 2, v1.144.0; the drawing
  // phase-5-voice-prints.html): on an unnamed card, the Person the voice
  // matched with their voice to play beside this one; two People over one
  // voice as a conflict; on a Side named by the case rule, the alarm that it
  // does not sound like its Person. Accepted or declined here and nowhere
  // else; the Case tab only points back.
  function previewButtons(person) {
    return (person.heard || []).slice(0, 2).map(function (one) {
      var where = one.here ? "this call" : (one.title.length > 28 ? one.title.slice(0, 26) + "\u2026" : one.title);
      return "<button type='button' class='tiny ghost hear-else' data-preview-recording='" + escape(one.recording) + "' data-preview-at='" + one.start + "' title='Hear " + escape(person.name) + " on " + escape(one.title) + "'>" + UI.icon("play") + " " + escape(person.name.split(" ")[0]) + " on " + escape(where) + ", " + escape(one.clock) + "</button>";
    }).join("");
  }
  function ratingPill(person) {
    var word = person.rating === "high" ? "high" : "medium";
    var more = person.rating !== "high" && person.recordings === 1 ? ", from one recording" : "";
    // A match the last re-read made (v1.144.1): born of the print just taught.
    var fresh = person["new"] ? " <span class='pill small acc' title='This match appeared when the print was taught a moment ago'>new: their print was just taught from this call</span>" : "";
    return "<span class='pill small " + (word === "high" ? "ok" : "") + "'>" + word + more + "</span>" + fresh;
  }
  function drawVoiceMatches(body) {
    var state = (body.speaker_check || {}).voice_matches || {};
    var groups = state.matches || [];
    cards().forEach(function (card) {
      var box = card.querySelector(".sounds-box");
      if (box) { box.hidden = true; box.innerHTML = ""; }
      var old = card.querySelector(".pill.was-voice");
      if (old) { old.remove(); }
    });
    (state.unlearnt || []).forEach(function (one) {
      var card = cardOf(one.speaker);
      var head = card ? card.querySelector(".h") : null;
      if (!head || head.querySelector(".pill.was-voice")) { return; }
      var pill = document.createElement("span");
      pill.className = "pill small was-voice";
      pill.title = "Unlearnt on the case's Speakers tab; name this voice again by ear.";
      pill.textContent = "was " + one.person + ", by voice";
      head.insertBefore(pill, head.querySelector(".label"));
    });
    groups.forEach(function (group) {
      var card = cardOf(group.speaker);
      var box = card ? card.querySelector(".sounds-box") : null;
      if (!box) { return; }
      var html = "";
      if (group.kind === "match") {
        var person = group.people[0];
        suggestedFor[group.speaker] = person.name;
        html = "<div class='sounds'>" +
          "<div><b>Sounds like " + escape(person.name) + "</b>" + (person.role ? " <span class='pill small role'>" + escape(person.role) + "</span>" : "") + " " + ratingPill(person) +
          " <span class='muted'>\u00b7 their voice is on " + person.recordings + (person.recordings === 1 ? " recording" : " recordings") + " of this case</span></div>" +
          "<div class='hear'>" + previewButtons(person) + "<span class='muted tiny'>the samples above are this voice</span></div>" +
          "<div class='acts'><button type='button' class='tiny primary match-accept' data-match='" + person.id + "'>Accept: " + escape(group.speaker) + " is " + escape(person.name) + "</button>" +
          "<button type='button' class='ghost tiny match-dismiss' data-match='" + person.id + "'>Not them</button></div>" +
          "<div class='ask muted tiny'>Accept names every line of " + escape(group.speaker) + " on this call and teaches the print from it. Undo takes the name back and the print forgets this call.</div></div>";
      } else if (group.kind === "conflict") {
        var names = group.people.map(function (one) { return escape(one.name); });
        html = "<div class='sounds'>" +
          "<div><b>Sounds like two people</b> <span class='pill small warn'>" + names.join(" and ") + "</span></div>" +
          "<div class='ask muted tiny'>Two voice prints both claim this voice: brothers, or one print taught from the wrong call. Nothing is proposed until you have heard them all.</div>" +
          "<div class='hear'>" + group.people.map(previewButtons).join("") + "</div>" +
          "<div class='acts'>" + group.people.map(function (one) { return "<button type='button' class='tiny match-accept' data-match='" + one.id + "'>" + escape(one.name) + "</button>"; }).join("") +
          "<button type='button' class='ghost tiny match-dismiss' data-matches='" + group.people.map(function (one) { return one.id; }).join(",") + "'>Neither</button></div></div>";
      } else if (group.kind === "side") {
        var who = group.people[0];
        html = "<div class='sounds alarm' data-person='" + escape(who.name) + "'>" +
          "<div><b>Does not sound like " + escape(who.name) + "</b> <span class='pill small danger'>the voice disagrees</span></div>" +
          "<div class='ask muted tiny'>The case rule names this side " + escape(who.name) + " on every call. On this call the voice is someone else's. Nothing is renamed until you say.</div>" +
          "<div class='hear'>" + previewButtons(who) + "<span class='muted tiny'>the samples above are this call's side</span></div>" +
          "<div class='acts'><button type='button' class='tiny side-not'>Not " + escape(who.name.split(" ")[0]) + " on this call...</button>" +
          "<button type='button' class='ghost tiny match-accept' data-match='" + who.id + "'>It is " + escape(who.name.split(" ")[0]) + "</button></div></div>";
      }
      if (!html) { return; }
      box.innerHTML = html;
      box.hidden = false;
    });
  }

  // The unit's voice book (v1.146.0; the drawing phase-5-voice-book.html,
  // figure 4): Check against the unit's voices on every unnamed card,
  // pressed and never automatic, greyed with the reason; the answer
  // (Sounds like with the pill "the unit's voices", a conflict, or no
  // match) drawn under the case's own Sounds like, with Accept, Not them,
  // Neither and Check again.
  function drawBookChecks(body) {
    var book = (body.speaker_check || {}).voice_book || {};
    cards().forEach(function (card) {
      var button = card.querySelector(".book-check");
      var why = card.querySelector(".book-why");
      if (!button) { return; }
      var name = card.dataset.name;
      var can = (book.can || {})[name];
      if (!book.on || !can) { button.hidden = true; if (why) { why.hidden = true; } return; }
      button.hidden = false;
      button.textContent = "Check against the " + book.unit + " unit's voices";
      button.disabled = !can.ok;
      button.title = can.ok ? "Compares this voice with the voices kept for the " + book.unit + " unit. A few seconds; the answer lands here." : can.why;
      if (why) {
        why.textContent = can.ok ? "Compares this voice with the " + book.unit + " unit's known voices. A few seconds; the answer lands here." : can.why;
        why.hidden = false;
      }
    });
    (book.checks || []).forEach(function (group) {
      var card = cardOf(group.speaker);
      var box = card ? card.querySelector(".sounds-box") : null;
      if (!box) { return; }
      var html = "";
      var unitPill = " <span class='pill small acc'>the unit's voices</span>";
      if (group.kind === "match") {
        var voice = group.voices[0];
        html = "<div class='sounds book'>" +
          "<div><b>Sounds like " + escape(voice.name) + "</b>" + (voice.role ? " <span class='pill small role'>" + escape(voice.role) + "</span>" : "") + unitPill + " " + ratingPill({ rating: voice.rating, recordings: voice.cases }) +
          " <span class='muted'>\u00b7 kept from " + voice.cases + (voice.cases === 1 ? " case" : " cases") + "</span></div>" +
          "<div class='hear'>" + (voice.heard.length ? previewButtons(voice) : (voice.openable ? "" : "<span class='pill small' title='The voice is heard only from a recording you may open'>heard on a case you may not open</span>")) + "<span class='muted tiny'>the samples above are this voice</span></div>" +
          "<div class='acts'><button type='button' class='tiny primary book-accept' data-check='" + voice.id + "'>Accept: " + escape(group.speaker) + " is " + escape(voice.name) + "</button>" +
          "<button type='button' class='ghost tiny book-dismiss' data-check='" + voice.id + "'>Not them</button></div>" +
          "<div class='ask muted tiny'>Accept adds " + escape(voice.name) + " to this case" + (voice.role ? " as " + escape(voice.role) : "") + ", names every line of " + escape(group.speaker) + " here, and teaches both this case's print and the book. Undo takes it all back.</div></div>";
      } else if (group.kind === "conflict") {
        html = "<div class='sounds book'>" +
          "<div><b>Sounds like two of the unit's voices</b> <span class='pill small warn'>" + group.voices.map(function (one) { return escape(one.name); }).join(" and ") + "</span>" + unitPill + "</div>" +
          "<div class='ask muted tiny'>Both prints claim this voice. Nothing is proposed until you have heard all three.</div>" +
          "<div class='hear'>" + group.voices.map(function (one) { return one.heard.length ? previewButtons(one) : (one.openable ? "" : "<span class='pill small'>" + escape(one.name.split(" ")[0]) + ": heard on a case you may not open</span>"); }).join("") + "</div>" +
          "<div class='acts'>" + group.voices.map(function (one) { return "<button type='button' class='tiny book-accept' data-check='" + one.id + "'>" + escape(one.name) + "</button>"; }).join("") +
          "<button type='button' class='ghost tiny book-dismiss' data-checks='" + group.voices.map(function (one) { return one.id; }).join(",") + "'>Neither</button></div></div>";
      } else {
        html = "<div class='sounds book none'>" +
          "<div><b>No voice in the " + escape(group.unit) + " unit's book sounds like " + escape(group.speaker) + "</b> <span class='muted'>\u00b7 " + group.compared + " compared, " + escape(group.at) + "</span></div>" +
          "<div class='acts'><button type='button' class='quiet tiny book-check-again'>Check again</button></div></div>";
      }
      box.innerHTML += html;
      box.hidden = false;
    });
  }

  // Voices first (v1.145.0; the drawing phase-5-voices-first.html): the
  // stages strip, the head's sentence per stage, the next button, the
  // named cards folded, the strip's count. The stage lives on the run.
  function drawStages(check, run, cards) {
    var strip = document.getElementById("stages");
    var next = document.getElementById("stage-next");
    var note = document.getElementById("stage-note");
    var said = document.getElementById("corrections-state");
    if (!strip) { return; }
    var stage = check.stage || null;
    strip.hidden = !stage;
    document.body.classList.toggle("voices-first", !!stage);
    if (!stage) { if (next) { next.hidden = true; } if (note) { note.hidden = true; } return; }
    var cast = check.cast || { total: 0, named: 0 };
    var doubt = check.doubt || { near: 0, unsure: 0, mixed: 0, agree: 0, words_against: 0 };
    var inDoubt = doubt.near + doubt.unsure + doubt.mixed;
    var reading = check.reading || null;
    var hints = (lastBody && lastBody.pending ? lastBody.pending.length : 0);
    Array.prototype.forEach.call(strip.querySelectorAll(".stage"), function (one) {
      var n = parseInt(one.dataset.stage, 10);
      one.classList.toggle("on", n === stage);
      one.classList.toggle("done", n < stage);
      var sub = one.querySelector(".sub");
      if (n === 1) { sub.textContent = plural(cast.total, "voice") + ", " + cast.named + " named"; }
      if (n === 2) { sub.textContent = stage < 2 ? (inDoubt ? inDoubt + " so far" : "after the names") : plural(inDoubt, "line") + (reading && reading.state === "done" && reading.against ? ", " + reading.against + " the words read the other way" : ""); }
      if (n === 3) { sub.textContent = stage < 3 ? "the words, once more" : "checked against the names"; }
    });
    if (stage === 1) {
      said.textContent = "The voice heard " + plural(cast.total, "voice") + " on this call" + (hints ? " and the words suggest " + plural(hints, "name") : "") + ". Name each voice from its samples; the lines in doubt come after" + (inDoubt ? " (" + inDoubt + " so far)" : "") + ".";
      next.textContent = "Next: lines in doubt" + (inDoubt ? " (" + inDoubt + ")" : "");
      next.hidden = false;
      next.classList.toggle("primary", cast.named >= cast.total && cast.total > 0);
      note.textContent = cast.named < cast.total ? "You can go on with the unnamed as labels; they can be named later from their cards." : "Every voice is named.";
      note.hidden = false;
    } else if (stage === 2) {
      var parts = [];
      if (doubt.near) { parts.push(doubt.near + " sound" + (doubt.near === 1 ? "s" : "") + " more like another speaker"); }
      if (doubt.unsure) { parts.push(doubt.unsure + " the voice cannot tell"); }
      if (doubt.mixed) { parts.push(doubt.mixed + " carr" + (doubt.mixed === 1 ? "ies" : "y") + " two voices"); }
      var words = "";
      if (!reading || reading.state === "queued" || reading.state === "running") { words = " The words are reading them against the names\u2026"; }
      else if (reading.state === "done") { words = reading.rows ? " The words read " + (reading.against || 0) + " of them the other way" + (reading.agree ? " and agree on " + reading.agree : "") + "." : ""; }
      else if (reading.state === "failed") { words = " The words could not read them this time" + (reading.said ? ": " + reading.said : "") + "."; }
      said.textContent = inDoubt
        ? plural(inDoubt, "line") + " the voice puts in doubt" + (parts.length ? ": " + parts.join(", ") : "") + "." + words + " Read down; accept or leave each as you go."
        : "Nothing in doubt: the voice is sure of every line it could judge.";
      next.textContent = "Next: done";
      next.hidden = false;
      next.classList.remove("primary");
      note.textContent = "Done runs the words once over the whole call, against the names as they stand.";
      note.hidden = false;
    } else {
      next.hidden = true;
      note.hidden = true;
      if (run && run.state === "done" && check.mode === "words") {
        var leftover = (check.pending || []).length;
        said.textContent = "Checked against the names, " + run.when + ". " + (leftover ? "The words found " + leftover + " more line" + (leftover === 1 ? "" : "s") + " worth a look, below." : "The words found nothing more to move.") + " The names stand; the voice has heard every line.";
      }
    }
  }
  var lastBody = null;

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
        // Two lines (v1.143.0): the words, then the sounds and the buttons.
        return "<div class='handover' data-handover='" + one.id + "' data-at='" + one.at + "'>" +
          "<div class='said'><b>Another voice from " + escape(one.clock) + "</b> under this label, " + plural(one.lines_after, "line") + " after it" + (one.voices === 3 ? ", a third voice later" : "") + ".</div>" +
          "<div class='acts'><span class='hear3'><button type='button' class='hear-before' title='Play the six seconds before'>" + UI.icon("play") + " before</button><button type='button' class='hear-after' title='Play the six seconds after'>" + UI.icon("play") + " after</button></span>" +
          "<button type='button' class='tiny split-handover'>Split here...</button>" +
          "<button type='button' class='ghost tiny dismiss-handover'>Not a different person</button></div></div>";
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
      else if (run.names_state === "too_few") { said.textContent += " No names were suggested: fewer than two speakers are still unnamed, and the names need two or more to tell apart."; }
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
    lastCheck = check;
    stageNow = check.stage || null;
    // Voices first (v1.145.0): at stage 1 the transcript reads plain; the
    // lines in doubt come at stage 2, the words' leftovers at stage 3.
    if (stageNow !== 1) { pending.forEach(function (one) { changes[String(one.segment)] = one; }); }
    (check.settled || []).forEach(function (one) { one.settled = true; changes[String(one.segment)] = one; });
    drawStages(check, run, cards);
    handovers = waitingHandovers;
    var acceptBacked = document.getElementById("accept-corrections");
    acceptBacked.hidden = backedLines < 1;
    if (stageNow === 2) {
      var agreeing = pending.filter(function (one) { return one.source === "voice" && one.words === "agrees" && (one.split_at === null || one.split_at === undefined); });
      acceptBacked.hidden = agreeing.length < 1;
      acceptBacked.textContent = "Accept the " + agreeing.length + " the voice and the words agree on";
      acceptBacked.dataset.ids = agreeing.map(function (one) { return one.id; }).join(",");
    } else if (stageNow === 1) {
      acceptBacked.hidden = true;
    } else { acceptBacked.textContent = "Accept the changes the voice backs"; acceptBacked.dataset.ids = ""; }
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
        var sc = body.speaker_check || {};
        lastBody = body;
        rereadNote = (sc.run && sc.run.voice_notes && sc.run.voice_notes.reread) || null;
        var busy = drawNameSuggestions(body);
        busy = drawCorrections(body) || busy;
        drawVoiceMatches(body);
        drawBookChecks(body);
        drawRereadLine(sc);
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

  // Voices first (v1.145.0): the stage lives on the run; 2 asks the words
  // for their second reading, 3 queues the words' run over the whole call.
  function moveToStage(stage) {
    if (!stage || stage > 3 || stage < 1) { return; }
    var next = document.getElementById("stage-next");
    if (next) { next.disabled = true; }
    send("/recording/" + V.recording + "/stage/" + stage).then(function (answer) {
      if (next) { next.disabled = false; }
      if (!answer.ok) { UI.toast(answer.said.error || "That stage could not be opened.", { problem: true, icon: "warning" }); return; }
      if (stage === 2 && answer.said.queued === "reading") { UI.toast("The words are reading the lines in doubt against the names\u2026", { icon: "info" }); }
      if (stage === 3 && answer.said.queued === "words") { UI.toast("Checking the whole call against the names\u2026", { icon: "info" }); }
      refreshSuggestions();
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
      var stageButton = event.target.closest(".stage[data-stage]");
      if (stageButton) { moveToStage(parseInt(stageButton.dataset.stage, 10)); return; }
      if (event.target.closest("#stage-next")) { moveToStage((stageNow || 1) + 1); return; }
      if (event.target.closest("#accept-corrections") && event.target.closest("#accept-corrections").dataset.ids) {
        var acceptIds = event.target.closest("#accept-corrections").dataset.ids;
        var acceptButton = event.target.closest("#accept-corrections");
        acceptButton.disabled = true;
        sendForm("/recording/" + V.recording + "/corrections/accept-many", { ids: acceptIds }).then(function (answer) {
          acceptButton.disabled = false;
          if (!answer.ok) { UI.toast(answer.said.error || "Not changed.", { problem: true, icon: "warning" }); return; }
          tell({ kind: "speakers-changed" });
          reloadHere(picked);
        });
        return;
      }
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
      function decide(into) {
        return send("/handover/" + box.dataset.handover + "/" + (split ? "accept" : "dismiss"), split ? { into: into || "" } : {}).then(function (answer) {
          if (!answer.ok) { UI.toast(answer.said.error || "That was not changed.", { problem: true, icon: "warning" }); return; }
          if (split) {
            if (answer.said.stale) { UI.toast("No line of that speaker lies after the time any more.", { icon: "info" }); refreshSuggestions(); return; }
            // The new speaker's card says where it came from, once (v1.143.0).
            try { window.sessionStorage.setItem("sp-split", JSON.stringify({ name: answer.said.made || "", from: card ? card.dataset.name : "", at: clock(at) })); } catch (e) { /* no storage */ }
            tell({ kind: "speakers-changed" });
            reloadHere(answer.said.made || picked);
            return;
          }
          refreshSuggestions();
        });
      }
      if (!split || !window.Picker) { decide(""); return; }
      // Split, into whom (v1.142.0): a known speaker or person, or a new
      // speaker as before, which stays the lit default.
      var card = box.closest(".sp-card");
      window.Picker.open({
        recording: V.recording,
        anchor: card || box,
        beside: card || null,
        question: "From " + clock(at) + " the voice is",
        current: card ? card.dataset.name : "",
        newSpeaker: true,
        play: playRange,
        onPick: function (name) { return decide(name); }
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
    // With the words (v1.141.0; v1.134.0 had left them out): the line in
    // hand lights each word as the voice reaches it, so a line whose clock
    // is a guess gives itself away and the words proposed are the ones under
    // the mark.
    return fetch("/recording/" + V.recording + "/segments")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        wordTiming = !!body.word_timestamps;
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

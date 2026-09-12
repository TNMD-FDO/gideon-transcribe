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
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function send(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  function cards() { return cardsBox ? Array.prototype.slice.call(cardsBox.querySelectorAll(".sp-card")) : []; }
  function names() { return cards().map(function (card) { return card.dataset.name; }); }
  function cardOf(name) { return cardsBox ? cardsBox.querySelector('.sp-card[data-name="' + CSS.escape(name) + '"]') : null; }
  function laneOf(name) { return lanesBox ? lanesBox.querySelector('.lane[data-name="' + CSS.escape(name) + '"]') : null; }

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
    segments.forEach(function (segment, index) {
      var row = document.createElement("li");
      row.className = "seg";
      row.dataset.index = index;
      if (segment.speaker) {
        row.style.setProperty("--speaker", colours[segment.speaker] || "");
        row.style.borderLeftColor = colours[segment.speaker] || "transparent";
      }
      if (index > 0 && segments[index - 1].speaker === segment.speaker) { row.classList.add("cont"); }
      row.innerHTML =
        "<button type='button' class='t' title='Play from here'>" + clock(segment.start) + "</button>" +
        "<div class='who'><span class='name'>" + escape(segment.speaker) + "</span><span class='tags'></span></div>" +
        "<div class='words'><p class='txt'>" + escape(segment.text) + "</p></div>" +
        "<span class='actions'>" +
        "<button type='button' class='ghost tiny play-row' title='Play this line'>play</button>" +
        "<button type='button' class='ghost tiny give-row' title='Give this line to another speaker'>not this speaker</button>" +
        "</span>";
      column.appendChild(row);
    });
    filter();
    here = -1;
    followAt(now());
    document.dispatchEvent(new CustomEvent("transcript-drawn"));
  }

  function filter() {
    if (!column) { return; }
    var rows = column.children;
    var count = 0;
    var keep = null;
    if (!showAll && picked) {
      keep = {};
      segments.forEach(function (segment, index) {
        if (segment.speaker === picked) {
          keep[index - 1] = keep[index - 1] || "dim";
          keep[index] = "mine";
          keep[index + 1] = keep[index + 1] || "dim";
        }
      });
    }
    for (var i = 0; i < rows.length; i += 1) {
      var how = keep ? keep[i] : "all";
      rows[i].hidden = !how;
      rows[i].classList.toggle("dim", how === "dim");
      rows[i].classList.toggle("mine", how === "mine");
      if (how === "mine" || (!keep && segments[i].speaker === picked)) { count += 1; }
    }
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

  document.getElementById("filter-one") && document.getElementById("filter-one").addEventListener("click", function () { showAll = false; filter(); });
  document.getElementById("filter-all") && document.getElementById("filter-all").addEventListener("click", function () { showAll = true; filter(); });

  if (column) {
    column.addEventListener("click", function (event) {
      var row = event.target.closest(".seg");
      if (!row) { return; }
      var segment = segments[parseInt(row.dataset.index, 10)];
      if (!segment) { return; }
      if (event.target.closest(".give-row")) { giveLine(segment); return; }
      if (event.target.closest(".play-row")) { playLine(segment); return; }
      seek(segment.start);
      play();
    });
  }

  // Following: the line being spoken lights and stays in view, scrolled only
  // once it has left the middle of the column, as on the recording page.
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
      var row = column ? column.children[index] : null;
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
    var row = column ? column.children[here] : null;
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
      body: "Every line of " + was + " becomes " + onto + ". Undo puts them back.",
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
        var row = column ? column.children[keep] : null;
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
        send("/suggestion/" + button.dataset.suggestion + "/" + (accept ? "accept" : "reject")).then(function () {
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
  function refreshSuggestions() {
    if (!suggestLine || !V.assistant || !V.assistant.suggestions) { return; }
    fetch("/recording/" + V.recording + "/assistant")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        var unnamed = body.unnamed || [];
        suggestLine.hidden = unnamed.length < 2;
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
          box.innerHTML = "Probably <b>" + escape(one.name) + "</b>" + (one.role ? " (" + escape(one.role) + ")" : "") +
            ", from <a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a>: “" + escape(one.quote) + "” " +
            "<button type='button' class='tiny accept' data-suggestion='" + one.id + "' data-name='" + escape(one.name) + "'>Accept</button> " +
            "<button type='button' class='ghost tiny reject' data-suggestion='" + one.id + "'>Reject</button>";
        });
        if (suggestTimer) { window.clearTimeout(suggestTimer); suggestTimer = null; }
        if (busy) { suggestTimer = window.setTimeout(refreshSuggestions, 2000); }
      })
      .catch(function () { /* the button waits for the next look */ });
  }
  if (suggestLine) {
    document.getElementById("suggest-names").addEventListener("click", function () {
      this.disabled = true;
      send("/recording/" + V.recording + "/suggest").then(refreshSuggestions);
    });
    cardsBox.addEventListener("click", function (event) {
      var cite = event.target.closest(".cite");
      if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.seconds)); play(); }
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
    return fetch("/recording/" + V.recording + "/segments")
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

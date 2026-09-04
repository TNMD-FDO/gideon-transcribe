// The viewer: play one recording and read, search, correct, and mark its
// transcript.
//
// The transcript is the page. Everything else is here to serve reading it, so
// the transcript is the only thing that scrolls in Follow mode, and every
// control is reachable from the keyboard without leaving it.
//
// This file owns the player, the timeline, the transcript, the speakers, the
// search, and the keyboard. The clip tool lives in clip-tool.js and talks to
// this one through window.CLIPS.

(function () {
  "use strict";

  var player = document.getElementById("player");
  var column = document.getElementById("transcript");
  var waveCanvas = document.getElementById("waveform");
  var laneCanvas = document.getElementById("lanes");
  var timeline = document.getElementById("timeline");

  var segments = [];
  var wordTiming = false;
  var here = -1;
  var colours = {};
  var peaks = null;
  var duration = 0;
  var following = true;
  var paused = false;
  var matches = [];
  var atMatch = -1;

  var stored = document.getElementById("speaker-colours");
  if (stored) {
    JSON.parse(stored.textContent).forEach(function (one) {
      colours[one.name] = one.colour;
    });
  }

  function clock(seconds) {
    var whole = Math.max(0, Math.floor(seconds || 0));
    var minutes = Math.floor(whole / 60);
    var rest = whole % 60;
    if (minutes >= 60) {
      return Math.floor(minutes / 60) + ":" +
        String(minutes % 60).padStart(2, "0") + ":" +
        String(rest).padStart(2, "0");
    }
    return minutes + ":" + String(rest).padStart(2, "0");
  }

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  // What the rest of the page may ask this one for.
  window.VIEWER.clock = clock;
  window.VIEWER.at = function () { return player ? player.currentTime : 0; };
  window.VIEWER.currentSegment = function () {
    return here >= 0 ? segments[here] : null;
  };
  window.VIEWER.seek = function (seconds) {
    if (player) { player.currentTime = Math.max(0, seconds); }
  };
  window.VIEWER.play = function () { if (player) { player.play(); } };
  window.VIEWER.pause = function () { if (player) { player.pause(); } };
  window.VIEWER.segments = function () { return segments; };
  window.VIEWER.length = function () { return duration; };

  // The transcript ------------------------------------------------------------

  function draw() {
    if (!column) { return; }
    column.innerHTML = "";
    segments.forEach(function (segment, index) {
      var row = document.createElement("li");
      row.className = "segment";
      row.dataset.index = index;
      if (segment.speaker) {
        row.style.setProperty("--speaker", colours[segment.speaker] || "");
      }

      var at = document.createElement("button");
      at.type = "button";
      at.className = "at plain";
      at.textContent = clock(segment.start);
      at.title = "Play from here";

      var body = document.createElement("div");
      var line = document.createElement("div");
      line.className = "who";
      if (segment.speaker) {
        line.textContent = segment.speaker + (segment.corrected ? " ✎" : "");
      } else if (segment.corrected) {
        line.textContent = "✎";
      }

      var tools = document.createElement("span");
      tools.className = "row-tools";
      var editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "plain tiny edit-row";
      editButton.title = "Correct this segment (E)";
      editButton.textContent = "✎ edit";
      tools.appendChild(editButton);

      if (window.VIEWER.clips) {
        var clipButton = document.createElement("button");
        clipButton.type = "button";
        clipButton.className = "plain tiny clip-row";
        clipButton.title = "Add this segment to the clip";
        clipButton.textContent = "+ clip";
        tools.appendChild(clipButton);
      }
      line.appendChild(tools);
      body.appendChild(line);

      var said = document.createElement("p");
      said.className = "said";
      said.innerHTML = wordsOf(segment);
      body.appendChild(said);

      row.appendChild(at);
      row.appendChild(body);
      column.appendChild(row);
    });
    tintRange();
  }

  function wordsOf(segment) {
    // With word timing the text is drawn word by word, so the one being said
    // can be underlined. Without it the segment is one piece: a translated
    // transcript has segment timing only, and pretending otherwise would
    // underline the wrong words.
    if (!wordTiming || !segment.words || !segment.words.length) {
      return escape(segment.text);
    }
    return segment.words.map(function (word, index) {
      var start = word.start === undefined ? "" : word.start;
      var end = word.end === undefined ? "" : word.end;
      return "<span class='word' data-start='" + start + "' data-end='" + end +
        "' data-index='" + index + "'>" + escape(word.word) + "</span>";
    }).join(" ");
  }

  // Following -----------------------------------------------------------------

  function at(time) {
    // The last segment that has started. A binary search, because a two-hour
    // recording is thousands of segments and this runs on every timeupdate.
    var low = 0;
    var high = segments.length - 1;
    var found = -1;
    while (low <= high) {
      var middle = (low + high) >> 1;
      if (segments[middle].start <= time) { found = middle; low = middle + 1; }
      else { high = middle - 1; }
    }
    return found;
  }

  var pill = document.getElementById("follow-pill");
  var followBox = document.getElementById("follow");

  function follow() {
    if (!player) { return; }
    var time = player.currentTime;
    movePlayhead(time);

    var index = at(time);
    if (index !== here) {
      var was = column ? column.querySelector(".segment.here") : null;
      if (was) { was.classList.remove("here"); }
      var now = column ? column.children[index] : null;
      if (now) {
        now.classList.add("here");
        if (following && !paused && !now.querySelector("textarea")) {
          now.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      here = index;
    }

    var row = column ? column.children[here] : null;
    if (row && wordTiming) {
      var words = row.querySelectorAll(".word");
      Array.prototype.forEach.call(words, function (word) {
        var start = parseFloat(word.dataset.start);
        var end = parseFloat(word.dataset.end);
        word.classList.toggle("now", !isNaN(start) && time >= start && time <= end);
      });
    }

    document.getElementById("clock").textContent =
      clock(time) + " / " + clock(player.duration || duration);
  }

  function label(text) {
    if (followBox && followBox.parentNode) {
      followBox.parentNode.lastChild.textContent = text;
    }
  }

  function pauseFollowing() {
    if (!following || paused) { return; }
    paused = true;
    if (pill) { pill.hidden = false; }
    label(" Follow (paused)");
  }

  function resumeFollowing() {
    paused = false;
    following = true;
    if (followBox) { followBox.checked = true; }
    label(" Follow");
    if (pill) { pill.hidden = true; }
    var row = column ? column.children[here] : null;
    if (row) { row.scrollIntoView({ block: "center", behavior: "smooth" }); }
  }

  if (column) {
    window.addEventListener("wheel", function (event) {
      if (event.target.closest && event.target.closest(".transcript")) {
        pauseFollowing();
      }
    }, { passive: true });
  }
  if (pill) {
    document.getElementById("resume-follow").addEventListener("click", resumeFollowing);
  }
  if (followBox) {
    followBox.addEventListener("change", function () {
      following = this.checked;
      paused = false;
      if (pill) { pill.hidden = true; }
      label(" Follow");
    });
  }

  // The timeline --------------------------------------------------------------

  function sizeCanvases() {
    if (!waveCanvas || !timeline) { return; }
    var width = timeline.clientWidth;
    if (!width) { return; }
    [waveCanvas, laneCanvas].forEach(function (canvas) {
      canvas.width = width;
      canvas.style.width = width + "px";
    });
    drawWave();
    drawLanes();
  }

  function drawWave() {
    if (!waveCanvas || !peaks || !peaks.data) { return; }
    var pen = waveCanvas.getContext("2d");
    var width = waveCanvas.width;
    var height = waveCanvas.height;
    pen.clearRect(0, 0, width, height);

    var style = window.getComputedStyle(document.body);
    pen.fillStyle = (style.getPropertyValue("--quiet") || "#777").trim();

    var data = peaks.data;
    var pairs = Math.floor(data.length / 2);
    var scale = Math.pow(2, (peaks.bits || 8) - 1);
    var middle = height / 2;

    for (var x = 0; x < width; x += 1) {
      var fromPair = Math.floor((x / width) * pairs);
      var toPair = Math.max(fromPair + 1, Math.floor(((x + 1) / width) * pairs));
      var low = 0;
      var high = 0;
      for (var i = fromPair; i < toPair && i < pairs; i += 1) {
        low = Math.min(low, data[i * 2]);
        high = Math.max(high, data[i * 2 + 1]);
      }
      var top = middle - (high / scale) * middle;
      var bottom = middle - (low / scale) * middle;
      pen.fillRect(x, top, 1, Math.max(1, bottom - top));
    }
  }

  function drawLanes() {
    if (!laneCanvas) { return; }
    var pen = laneCanvas.getContext("2d");
    var width = laneCanvas.width;
    pen.clearRect(0, 0, width, laneCanvas.height);
    if (!segments.length || !duration) { return; }

    var names = Object.keys(colours);
    if (!names.length) { return; }

    var lane = laneCanvas.height / names.length;
    segments.forEach(function (segment) {
      var which = names.indexOf(segment.speaker);
      if (which < 0) { return; }
      pen.fillStyle = colours[segment.speaker];
      var from = (segment.start / duration) * width;
      var to = (segment.end / duration) * width;
      pen.fillRect(from, which * lane, Math.max(1, to - from), Math.max(1, lane - 1));
    });
  }

  function movePlayhead(time) {
    var head = document.getElementById("playhead");
    if (!head || !duration) { return; }
    head.style.left = ((time / duration) * 100) + "%";
  }

  function timeAt(event) {
    var box = timeline.getBoundingClientRect();
    var along = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    return along * duration;
  }

  function showRange(from, to) {
    var box = document.getElementById("range");
    if (!box) { return; }
    if (from === null || from === undefined || !duration) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    box.style.left = ((from / duration) * 100) + "%";
    box.style.width = (((to - from) / duration) * 100) + "%";
  }
  window.VIEWER.showRange = showRange;

  function tintRange() {
    if (!window.CLIPS || !column) { return; }
    var range = window.CLIPS.range();
    Array.prototype.forEach.call(column.children, function (row, index) {
      var segment = segments[index];
      var inside = range && segment.start < range.to && segment.end > range.from;
      row.classList.toggle("in-range", !!inside);
    });
  }
  window.VIEWER.tintRange = tintRange;

  if (timeline) {
    var dragging = false;
    var dragFrom = 0;

    timeline.addEventListener("mousedown", function (event) {
      if (!duration) { return; }
      dragging = true;
      dragFrom = timeAt(event);
      event.preventDefault();
    });

    window.addEventListener("mousemove", function (event) {
      if (!dragging) { return; }
      var now = timeAt(event);
      showRange(Math.min(dragFrom, now), Math.max(dragFrom, now));
    });

    window.addEventListener("mouseup", function (event) {
      if (!dragging) { return; }
      dragging = false;
      var now = timeAt(event);
      if (Math.abs(now - dragFrom) < 0.4) {
        // A click, not a drag: seek there.
        window.VIEWER.seek(now);
        showRange(null, null);
        return;
      }
      if (window.CLIPS) {
        window.CLIPS.mark(Math.min(dragFrom, now), Math.max(dragFrom, now));
      }
    });

    window.addEventListener("resize", sizeCanvases);
  }

  // The transport -------------------------------------------------------------

  function step(seconds) {
    if (!player) { return; }
    player.currentTime = Math.max(0, player.currentTime + seconds);
  }

  function frameStep(forward) {
    // The frame rate comes from the provenance; an audio-only recording has
    // none and steps a tenth of a second instead.
    var one = window.VIEWER.frameRate > 0 ? 1 / window.VIEWER.frameRate : 0.1;
    step(forward ? one : -one);
  }

  if (player) {
    player.addEventListener("timeupdate", follow);
    player.addEventListener("loadedmetadata", function () {
      duration = player.duration || duration;
      sizeCanvases();
    });

    document.getElementById("play").addEventListener("click", function () {
      if (player.paused) { player.play(); } else { player.pause(); }
    });
    player.addEventListener("play", function () {
      document.getElementById("play").textContent = "Pause";
    });
    player.addEventListener("pause", function () {
      document.getElementById("play").textContent = "Play";
    });

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-seek]"),
      function (button) {
        button.addEventListener("click", function () {
          step(parseFloat(button.dataset.seek));
          if (button.dataset.seek === "-3") { player.play(); }
        });
      }
    );
    document.getElementById("frame-back").addEventListener("click", function () {
      frameStep(false);
    });
    document.getElementById("frame-on").addEventListener("click", function () {
      frameStep(true);
    });

    document.getElementById("speed").addEventListener("change", function () {
      player.playbackRate = parseFloat(this.value);
    });

    // Boost exists because browsers cap volume at 100% and quiet recordings
    // are common: a jail call at arm's length from the handset is not made
    // louder by turning the speakers up if the file itself is quiet. Balance
    // shares the same audio graph, because a media element can be handed to
    // Web Audio only once.
    var sound = null;
    var gain = null;
    var panner = null;

    function buildAudio() {
      if (sound) { return; }
      sound = new (window.AudioContext || window.webkitAudioContext)();
      gain = sound.createGain();
      panner = sound.createStereoPanner ? sound.createStereoPanner() : null;
      var source = sound.createMediaElementSource(player);
      if (panner) {
        source.connect(panner);
        panner.connect(gain);
      } else {
        source.connect(gain);
      }
      gain.connect(sound.destination);
    }

    document.getElementById("boost").addEventListener("input", function () {
      var per = parseInt(this.value, 10);
      document.getElementById("boost-figure").textContent = per + "%";
      if (per > 100) { buildAudio(); }
      if (gain) { gain.gain.value = per / 100; }
    });

    var balance = document.getElementById("balance");
    if (balance) {
      balance.addEventListener("input", function () {
        buildAudio();
        if (panner) { panner.pan.value = parseInt(this.value, 10) / 100; }
      });
    }
  } else {
    // No playback copy yet: the transport does nothing until there is one.
    Array.prototype.forEach.call(
      document.querySelectorAll(
        ".transport button, .transport select, .transport input[type=range]"
      ),
      function (control) {
        if (control.id !== "new-clip") { control.disabled = true; }
      }
    );
  }

  // Rows ----------------------------------------------------------------------

  if (column) {
    column.addEventListener("click", function (event) {
      var row = event.target.closest(".segment");
      if (!row) { return; }
      var index = parseInt(row.dataset.index, 10);

      if (event.target.closest(".edit-row")) { edit(index); return; }
      if (event.target.closest(".clip-row")) {
        if (window.CLIPS) { window.CLIPS.addSegment(segments[index]); }
        return;
      }
      if (row.querySelector("textarea")) { return; }
      window.VIEWER.seek(segments[index].start);
    });

    column.addEventListener("dblclick", function (event) {
      var row = event.target.closest(".segment");
      if (row) { edit(parseInt(row.dataset.index, 10)); }
    });
  }

  // Correcting ----------------------------------------------------------------

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }
  window.VIEWER.cookie = cookie;

  function edit(index) {
    var segment = segments[index];
    var row = column ? column.children[index] : null;
    if (!segment || !row || row.querySelector("textarea")) { return; }

    var box = document.createElement("textarea");
    box.rows = 3;
    box.value = segment.text;
    var said = row.querySelector(".said");
    said.replaceWith(box);
    box.focus();

    function stop() {
      var back = document.createElement("p");
      back.className = "said";
      back.innerHTML = wordsOf(segment);
      box.replaceWith(back);
    }

    box.addEventListener("keydown", function (event) {
      event.stopPropagation();
      if (event.key === "Escape") { stop(); }
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        var text = box.value.trim();
        fetch("/recording/" + window.VIEWER.recording + "/segment/" + segment.id, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": cookie("csrftoken")
          },
          body: JSON.stringify({ text: text })
        }).then(function () {
          segment.text = text;
          segment.corrected = true;
          // The words are the machine's; once a person has changed the text,
          // the old word timings no longer describe it.
          segment.words = [];
          draw();
          follow();
          if (window.CLIPS) { window.CLIPS.load(); }
        });
      }
    });
  }

  // Speakers ------------------------------------------------------------------

  var chips = document.getElementById("speakers");
  if (chips) {
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest(".chip");
      if (!chip) { return; }
      var now = window.prompt("Rename " + chip.dataset.name + " to:", chip.dataset.name);
      if (!now || now === chip.dataset.name) { return; }
      rename(chip.dataset.name, now);
    });

    var dragged = null;
    chips.addEventListener("dragstart", function (event) {
      dragged = event.target.dataset.name;
    });
    chips.addEventListener("dragover", function (event) {
      event.preventDefault();
      var chip = event.target.closest(".chip");
      if (chip) { chip.classList.add("over"); }
    });
    chips.addEventListener("dragleave", function (event) {
      var chip = event.target.closest(".chip");
      if (chip) { chip.classList.remove("over"); }
    });
    chips.addEventListener("drop", function (event) {
      event.preventDefault();
      var onto = event.target.closest(".chip");
      if (!onto) { return; }
      onto.classList.remove("over");
      if (!dragged || dragged === onto.dataset.name) { return; }
      if (!window.confirm(
        "Merge " + dragged + " into " + onto.dataset.name +
        "? Every segment of " + dragged + " becomes " + onto.dataset.name + "."
      )) { return; }
      rename(dragged, onto.dataset.name);
    });
  }

  var speakersToggle = document.getElementById("speakers-toggle");
  if (speakersToggle) {
    speakersToggle.addEventListener("click", function () {
      var hidden = document.body.classList.toggle("no-speakers");
      this.textContent = hidden ? "show" : "hide";
    });
  }

  function rename(from, to) {
    fetch("/recording/" + window.VIEWER.recording + "/speakers", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: JSON.stringify({ from: from, to: to })
    }).then(function () { window.location.reload(); });
  }

  // Searching -----------------------------------------------------------------

  var search = document.getElementById("search");

  function look() {
    var wanted = search.value.trim().toLowerCase();
    matches = [];
    atMatch = -1;

    Array.prototype.forEach.call(column ? column.children : [], function (row, index) {
      var segment = segments[index];
      var text = segment.text.toLowerCase();
      var hit = wanted && text.indexOf(wanted) !== -1;
      row.hidden = wanted !== "" && !hit;
      row.classList.remove("match-here");

      var said = row.querySelector(".said");
      if (!said) { return; }
      if (hit) {
        matches.push(index);
        var pattern = new RegExp(
          wanted.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"
        );
        said.innerHTML = escape(segment.text).replace(pattern, function (found) {
          return "<mark>" + found + "</mark>";
        });
      } else if (!wanted) {
        said.innerHTML = wordsOf(segment);
      }
    });

    document.getElementById("matches").textContent = wanted === ""
      ? ""
      : matches.length + (matches.length === 1 ? " match" : " matches");
  }

  if (search) {
    search.addEventListener("input", look);
    search.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") { return; }
      event.preventDefault();
      if (!matches.length) { return; }
      atMatch = event.shiftKey
        ? (atMatch <= 0 ? matches.length - 1 : atMatch - 1)
        : (atMatch + 1) % matches.length;
      var row = column.children[matches[atMatch]];
      Array.prototype.forEach.call(column.children, function (one) {
        one.classList.remove("match-here");
      });
      row.classList.add("match-here");
      row.scrollIntoView({ block: "center", behavior: "smooth" });
      window.VIEWER.seek(segments[matches[atMatch]].start);
    });
  }

  // The sheet, the overlay, the theme, the pop-out -----------------------------

  var sheet = document.getElementById("sheet");
  var detailsLoaded = false;

  function loadDetails() {
    if (detailsLoaded) { return; }
    detailsLoaded = true;
    fetch("/recording/" + window.VIEWER.recording + "/details")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        document.getElementById("details").innerHTML = (body.rows || []).map(
          function (row) {
            return "<dt>" + escape(row[0]) + "</dt><dd>" + escape(row[1]) + "</dd>";
          }
        ).join("");
      });
  }

  function openSheet(which) {
    sheet.hidden = false;
    Array.prototype.forEach.call(
      sheet.querySelectorAll(".sheet-panel"),
      function (panel) { panel.hidden = panel.dataset.panel !== which; }
    );
    Array.prototype.forEach.call(
      sheet.querySelectorAll(".sheet-tab"),
      function (tab) { tab.classList.toggle("here", tab.dataset.panel === which); }
    );
    if (which === "details") { loadDetails(); }
  }
  window.VIEWER.openSheet = openSheet;

  Array.prototype.forEach.call(
    sheet.querySelectorAll(".sheet-tab"),
    function (tab) {
      tab.addEventListener("click", function () { openSheet(tab.dataset.panel); });
    }
  );
  document.getElementById("close-sheet").addEventListener("click", function () {
    sheet.hidden = true;
  });
  document.getElementById("open-details").addEventListener("click", function () {
    openSheet("details");
  });

  var overlay = document.getElementById("shortcuts");
  function shortcuts(show) { overlay.hidden = !show; }
  document.getElementById("open-shortcuts").addEventListener("click", function () {
    shortcuts(true);
  });
  document.getElementById("close-shortcuts").addEventListener("click", function () {
    shortcuts(false);
  });

  document.getElementById("theme").addEventListener("click", function () {
    var root = document.documentElement;
    var now = root.getAttribute("data-theme");
    var next = now === "dark" ? "light" : (now === "light" ? "" : "dark");
    if (next) { root.setAttribute("data-theme", next); }
    else { root.removeAttribute("data-theme"); }
    try { window.localStorage.setItem("theme", next); } catch (ignored) { /* fine */ }
    drawWave();
  });

  var popOut = document.getElementById("pop-out");
  if (popOut && player && player.requestPictureInPicture) {
    popOut.addEventListener("click", function () {
      if (document.pictureInPictureElement) {
        document.exitPictureInPicture();
      } else {
        player.requestPictureInPicture().catch(function () {
          window.alert("This browser would not pop the video out.");
        });
      }
    });
    player.addEventListener("enterpictureinpicture", function () {
      popOut.textContent = "Dock video";
      document.getElementById("popped").hidden = false;
    });
    player.addEventListener("leavepictureinpicture", function () {
      popOut.textContent = "Pop out video";
      document.getElementById("popped").hidden = true;
    });
  } else if (popOut) {
    popOut.hidden = true;
  }

  // The keyboard --------------------------------------------------------------

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }

    var speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5];
    var speed = document.getElementById("speed");

    if (event.key === "/") { event.preventDefault(); search.focus(); return; }
    if (event.key === "?") { shortcuts(overlay.hidden); return; }
    if (event.key === "Escape") {
      if (!overlay.hidden) { shortcuts(false); return; }
      if (!sheet.hidden) { sheet.hidden = true; }
      return;
    }
    if (event.key === "d" || event.key === "D") { openSheet("details"); return; }

    if (event.key === "f" || event.key === "F") {
      if (paused) { resumeFollowing(); }
      else if (followBox) {
        followBox.checked = !followBox.checked;
        followBox.dispatchEvent(new Event("change"));
      }
      return;
    }

    if (event.key === "e" || event.key === "E") {
      if (here >= 0) { event.preventDefault(); edit(here); }
      return;
    }

    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      var to = here + (event.key === "ArrowDown" ? 1 : -1);
      if (segments[to]) { window.VIEWER.seek(segments[to].start); }
      return;
    }

    if (!player) { return; }

    if (event.key === " ") {
      event.preventDefault();
      if (player.paused) { player.play(); } else { player.pause(); }
    } else if (event.key === "b" || event.key === "B") {
      // The foot-pedal substitute: back three seconds and keep playing.
      step(-3);
      player.play();
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      var by = event.shiftKey ? 1 : (event.ctrlKey || event.metaKey ? 30 : 5);
      step(event.key === "ArrowLeft" ? -by : by);
    } else if (event.key === ",") {
      frameStep(false);
    } else if (event.key === ".") {
      frameStep(true);
    } else if (event.key === "[" || event.key === "]") {
      var where = speeds.indexOf(parseFloat(speed.value)) + (event.key === "]" ? 1 : -1);
      where = Math.max(0, Math.min(speeds.length - 1, where));
      speed.value = String(speeds[where]);
      player.playbackRate = speeds[where];
    } else if (event.key === "0") {
      speed.value = "1";
      player.playbackRate = 1;
    }
  });

  // Waiting for the transcript -------------------------------------------------

  function watchTheQueue() {
    if (!window.VIEWER.batch) { return; }
    window.setInterval(function () {
      fetch("/batch/" + window.VIEWER.batch + "/state")
        .then(function (answer) { return answer.json(); })
        .then(function (state) {
          var mine = (state.recordings || []).filter(function (one) {
            return one.id === window.VIEWER.recording;
          })[0];
          if (!mine) { return; }
          if (mine.has_transcript) { window.location.reload(); return; }

          var what = document.getElementById("waiting-what");
          var where = document.getElementById("waiting-where");
          if (!what || !mine.job) { return; }
          if (mine.job.state === "running") {
            what.textContent = mine.job.step || "Transcribing";
            where.textContent = "Diarization follows. You can leave this page.";
          } else if (mine.job.position) {
            what.textContent = "Position " + mine.job.position + " in the line";
            where.textContent = "You can leave this page.";
          }
        })
        .catch(function () { /* the next look will find it */ });
    }, 5000);
  }

  var cancel = document.getElementById("cancel-job");
  if (cancel) {
    cancel.addEventListener("click", function () {
      if (!window.confirm(
        "Cancel this recording? It is removed from your recordings as if it " +
        "had never been uploaded, and would have to be uploaded again."
      )) { return; }
      fetch("/recording/" + window.VIEWER.recording + "/delete", {
        method: "POST",
        headers: { "X-CSRFToken": cookie("csrftoken") }
      }).then(function () { window.location = "/"; });
    });
  }

  // Loading -------------------------------------------------------------------

  if (window.VIEWER.waveform) {
    fetch(window.VIEWER.waveform)
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        peaks = body;
        if (!duration && body.length && body.samples_per_pixel && body.sample_rate) {
          duration = (body.length * body.samples_per_pixel) / body.sample_rate;
        }
        sizeCanvases();
      })
      .catch(function () { /* no waveform is not a failure of the page */ });
  }

  if (window.VIEWER.hasTranscript) {
    fetch("/recording/" + window.VIEWER.recording + "/segments")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        segments = body.segments || [];
        wordTiming = body.word_timestamps;
        if (!duration && segments.length) {
          duration = segments[segments.length - 1].end;
        }
        draw();
        drawLanes();
        if (player) { follow(); }
      });
  } else {
    watchTheQueue();
  }

  sizeCanvases();
})();

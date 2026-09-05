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
  var canvas = document.getElementById("waveform");
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

  function ink(name) {
    // A token, or a "var(--token)" as the page writes a speaker's colour.
    var token = String(name).replace("var(", "").replace(")", "").trim();
    return window.getComputedStyle(document.documentElement)
      .getPropertyValue(token).trim();
  }

  // What the rest of the page may ask this one for.
  window.VIEWER.clock = clock;
  window.VIEWER.at = function () { return player ? player.currentTime : 0; };
  window.VIEWER.currentSegment = function () {
    return here >= 0 ? segments[here] : null;
  };
  // A media element that will not jump about says nothing about it: the
  // assignment to currentTime is accepted and ignored, and a person clicking
  // the timeline is left to guess. Every seek is watched, and one that does
  // not take is reported in the same line the player's other troubles use.
  var seekWatch = null;

  function withinSeekable(seconds) {
    // A media element that cannot be jumped about in does not report no
    // ranges: it reports one range of nothing, from zero to zero. Asking
    // whether the wanted moment is inside a range covers both, and covers a
    // file only partly answered for as well.
    var ranges = player ? player.seekable : null;
    if (!ranges || !ranges.length) { return false; }
    for (var n = 0; n < ranges.length; n += 1) {
      if (seconds >= ranges.start(n) && seconds <= ranges.end(n)) { return true; }
    }
    return false;
  }

  window.VIEWER.seek = function (seconds) {
    if (!player) { return; }
    var wanted = Math.max(0, seconds);

    if (seekWatch) { window.clearTimeout(seekWatch); }
    player.currentTime = wanted;
    seekWatch = window.setTimeout(function () {
      seekWatch = null;
      if (Math.abs(player.currentTime - wanted) < 1.5) { return; }

      if (!withinSeekable(wanted)) {
        window.VIEWER.sayTrouble(
          "This recording cannot be jumped about in: the browser cannot " +
          "reach that part of the file. It still plays from where it is."
        );
        return;
      }

      // The one bit that says where to look. Still seeking after five
      // seconds means the browser asked and is waiting, so the file or the
      // server is not answering for that part. Not seeking means it decided
      // straight away that it could not, which is the file's own shape.
      if (player.seeking) {
        window.VIEWER.sayTrouble(
          "This recording is taking a long time to jump to that point: the " +
          "server has not answered for that part of the file. It still " +
          "plays from where it is."
        );
        return;
      }
      window.VIEWER.sayTrouble(
        "This recording will not jump to that point: the browser gave up at " +
        "once, which means the file itself cannot be jumped about in. It " +
        "still plays from where it is. Process again remakes the playback " +
        "copy."
      );
    }, 5000);

    // Going somewhere on purpose is asking to watch from there, so a follow
    // that was paused for reading comes back rather than leaving the
    // transcript behind at the place that was just left.
    if (window.VIEWER.resumeFollowing) { window.VIEWER.resumeFollowing(); }
  };
  window.VIEWER.play = function () { if (player) { player.play(); } };
  window.VIEWER.pause = function () { if (player) { player.pause(); } };
  window.VIEWER.segments = function () { return segments; };
  window.VIEWER.length = function () { return duration; };
  window.VIEWER.redraw = function () { drawTimeline(); };

  // The transcript ------------------------------------------------------------

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

      var when = document.createElement("button");
      when.type = "button";
      when.className = "t";
      when.textContent = clock(segment.start);
      when.title = "Play from here";

      var body = document.createElement("div");

      var who = document.createElement("div");
      who.className = "who";
      var actions = document.createElement("span");
      actions.className = "actions";

      var editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "ghost tiny edit-row";
      editButton.title = "Correct this segment (E)";
      editButton.textContent = "✎ edit";
      actions.appendChild(editButton);

      if (window.VIEWER.clips) {
        var clipButton = document.createElement("button");
        clipButton.type = "button";
        clipButton.className = "ghost tiny clip-row";
        clipButton.title = "Mark where a clip starts, then where it ends";
        var first = document.createElement("span");
        first.className = "step-start";
        first.textContent = "clip start";
        var second = document.createElement("span");
        second.className = "step-end";
        second.textContent = "clip end";
        clipButton.appendChild(first);
        clipButton.appendChild(second);
        actions.appendChild(clipButton);
      }

      // The name line is always there, because it carries the row's own
      // controls even when there is no speaker to name.
      var name = document.createElement("span");
      name.className = "name";
      name.textContent = (segment.speaker || "") + (segment.corrected ? " ✎" : "");
      who.appendChild(name);
      who.appendChild(actions);
      body.appendChild(who);

      var said = document.createElement("p");
      said.className = "txt";
      said.innerHTML = wordsOf(segment);
      body.appendChild(said);

      row.appendChild(when);
      row.appendChild(body);
      column.appendChild(row);
    });
    tintRange();
    // A redraw builds every row again, so a start marked before it has to be
    // put back on the row it belongs to.
    if (clipStartsAt !== null) { showsStart(clipStartsAt); }
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
  var reading = document.querySelector(".read");

  function follow() {
    if (!player) { return; }
    var time = player.currentTime;
    movePlayhead(time);

    var index = at(time);
    if (index !== here) {
      var was = column ? column.querySelector(".seg.here") : null;
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

  function pauseFollowing() {
    if (!following || paused) { return; }
    paused = true;
    if (pill) { pill.hidden = false; }
  }

  function lineIsInView() {
    // Whether the line being spoken is on the screen. Asked after a scroll,
    // not before: a wheel event is delivered before the scroll it causes.
    var row = column ? column.children[here] : null;
    if (!row || !reading) { return false; }
    var seen = row.getBoundingClientRect();
    var box = reading.getBoundingClientRect();
    return seen.top >= box.top - 1 && seen.bottom <= box.bottom + 1;
  }

  function resumeFollowing() {
    if (!paused) { return; }
    paused = false;
    following = true;
    if (followBox) { followBox.checked = true; }
    if (pill) { pill.hidden = true; }
    var row = column ? column.children[here] : null;
    if (row) { row.scrollIntoView({ block: "center", behavior: "smooth" }); }
  }

  if (reading) {
    // Scrolling the transcript means "let me read", and the app stops pulling
    // the page back. It cannot wait to see whether the line went off the
    // screen first, because while it is still following it would have put the
    // line straight back, and the reader would never get anywhere.
    //
    // The way back is scrolling to the line being spoken: bring it into view
    // and the follow picks up again. That is also what undoes a nudge of the
    // wheel nobody meant, without the app having to guess which nudges were
    // meant.
    window.addEventListener("wheel", function (event) {
      if (!event.target.closest || !event.target.closest(".read")) { return; }
      if (!paused) { pauseFollowing(); return; }
      window.setTimeout(function () {
        if (paused && lineIsInView()) { resumeFollowing(); }
      }, 120);
    }, { passive: true });
  }
  window.VIEWER.resumeFollowing = resumeFollowing;

  if (pill) {
    document.getElementById("resume-follow").addEventListener("click", resumeFollowing);
  }
  if (followBox) {
    followBox.addEventListener("change", function () {
      following = this.checked;
      paused = false;
      if (pill) { pill.hidden = true; }
    });
  }

  // The timeline --------------------------------------------------------------
  //
  // One canvas, drawn in two layers: the surface, then the peaks, with the
  // part already played in the accent colour and the rest in the muted one.
  // The speaker lanes the prototype drew behind the peaks are gone: one band
  // per segment on every redraw, on a transcript of thousands of rows, for a
  // stripe of colour the rows already carry.

  function drawTimeline() {
    if (!canvas || !timeline) { return; }
    var width = timeline.clientWidth;
    if (!width) { return; }

    var height = 56;
    var ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.floor(width * ratio)) {
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      canvas.style.height = height + "px";
    }

    var pen = canvas.getContext("2d");
    pen.setTransform(ratio, 0, 0, ratio, 0, 0);
    pen.clearRect(0, 0, width, height);

    // Read the theme's colours once. Asking for a computed style forces the
    // browser to work out the styles of the whole page, and the loop below
    // runs once per pixel across the width: on a transcript of nine hundred
    // rows that was over a thousand full style passes every redraw.
    var surface = ink("--surface-2");
    var played = ink("--accent");
    var unplayed = ink("--muted");

    pen.fillStyle = surface;
    pen.fillRect(0, 0, width, height);

    var time = player ? player.currentTime : 0;

    var strip = peaksForWidth(width);
    if (strip) {
      var lane = strip.channels === 2 ? height / 2 : height;
      for (var x = 0; x < width; x += 1) {
        pen.fillStyle = duration && (x / width) * duration <= time
          ? played
          : unplayed;
        for (var channel = 0; channel < strip.channels; channel += 1) {
          var at = x * strip.channels + channel;
          var low = strip.lows[at];
          var high = strip.highs[at];
          var middle = strip.channels === 2 ? lane * channel + lane / 2 : height / 2;
          var top = middle - Math.max(1, high * (lane / 2 - 1));
          pen.fillRect(x, top, 1, Math.max(1, (high - low) * (lane / 2 - 1)));
        }
      }
    }
  }

  // The peaks file holds a few pairs per pixel for a recording made since
  // v1.3.0, and hundreds for one made before. Either way the strip is worked
  // out once per width, every pair taken in (the lowest low and the highest
  // high of the pairs a pixel covers, so a shout or a slammed door does not
  // vanish between samples), and the redraw once a second only paints it.
  var reduced = null;

  function peaksForWidth(width) {
    if (!peaks || !peaks.data) { return null; }
    if (reduced && reduced.width === width && reduced.from === peaks) {
      return reduced;
    }
    var channels = peaks.channels || 1;
    var pairs = Math.floor(peaks.data.length / (2 * channels));
    var scale = Math.pow(2, (peaks.bits || 8) - 1);
    var lows = new Float32Array(width * channels);
    var highs = new Float32Array(width * channels);
    for (var x = 0; x < width; x += 1) {
      var first = Math.floor((x / width) * pairs);
      var last = Math.max(first + 1, Math.floor(((x + 1) / width) * pairs));
      for (var channel = 0; channel < channels; channel += 1) {
        var low = 0;
        var high = 0;
        for (var index = first; index < last && index < pairs; index += 1) {
          var here = (index * channels + channel) * 2;
          if (peaks.data[here] < low) { low = peaks.data[here]; }
          if (peaks.data[here + 1] > high) { high = peaks.data[here + 1]; }
        }
        lows[x * channels + channel] = low / scale;
        highs[x * channels + channel] = high / scale;
      }
    }
    reduced = { width: width, from: peaks, channels: channels, lows: lows, highs: highs };
    return reduced;
  }

  function movePlayhead(time) {
    var head = document.getElementById("playhead");
    if (!head || !duration) { return; }
    head.style.left = ((time / duration) * 100) + "%";
    // The played part of the waveform is drawn in the accent colour, so the
    // canvas follows the playhead. Once a second is enough for that.
    var second = Math.floor(time);
    if (second !== movePlayhead.last) {
      movePlayhead.last = second;
      drawTimeline();
    }
  }

  function timeAt(event) {
    var box = timeline.getBoundingClientRect();
    var along = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    return along * duration;
  }

  function showRange(from, to) {
    var box = document.getElementById("range");
    var said = document.getElementById("clip-said");
    var drop = document.getElementById("drop-clip");
    if (!box) { return; }
    if (from === null || from === undefined || !duration) {
      box.hidden = true;
      if (said) { said.textContent = ""; }
      if (drop) { drop.hidden = true; }
      return;
    }
    box.hidden = false;
    box.style.left = ((from / duration) * 100) + "%";
    box.style.width = (((to - from) / duration) * 100) + "%";
    if (said) {
      said.textContent = "Clip " + clock(from) + " to " + clock(to);
      said.style.color = ink("--clip");
    }
    // The selection is shown here, so the way to be rid of it is here.
    if (drop) { drop.hidden = false; }
  }

  var dropClip = document.getElementById("drop-clip");
  if (dropClip) {
    dropClip.addEventListener("click", function () {
      if (window.CLIPS) { window.CLIPS.clear(); }
    });
  }
  window.VIEWER.showRange = showRange;

  function tintRange() {
    if (!window.CLIPS || !column) { return; }
    var range = window.CLIPS.range();
    Array.prototype.forEach.call(column.children, function (row, index) {
      var segment = segments[index];
      var inside = range && segment.start < range.to && segment.end > range.from;
      row.classList.toggle("inclip", !!inside);
    });
  }
  window.VIEWER.tintRange = tintRange;

  if (timeline) {
    var dragging = false;
    var dragFrom = 0;
    var dragFromX = 0;

    // A click and a drag are told apart by how far the mouse moved on the
    // screen, not by how much time that is. Time was the old rule and it does
    // not work: on a twenty-five minute recording one pixel of timeline is
    // over a second, so every click, which always jitters a pixel or two,
    // counted as a drag and marked a clip instead of seeking. How far a hand
    // moves is the same however long the recording is.
    var A_CLICK = 6;

    timeline.addEventListener("mousedown", function (event) {
      if (!duration) {
        // Nothing can be worked out from an x position without a length, and
        // doing nothing at all leaves a person clicking and wondering.
        window.VIEWER.sayTrouble(
          "The player does not know how long this recording is yet, so the " +
          "timeline cannot be used. Press Play once, or reload the page."
        );
        return;
      }
      dragging = true;
      dragFrom = timeAt(event);
      dragFromX = event.clientX;
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
      if (Math.abs(event.clientX - dragFromX) < A_CLICK) {
        // A click, not a drag: seek there, and put back whatever range the
        // clip tool still holds rather than wiping it off the timeline.
        window.VIEWER.seek(now);
        var held = window.CLIPS ? window.CLIPS.range() : null;
        showRange(held ? held.from : null, held ? held.to : null);
        return;
      }
      if (window.CLIPS) {
        window.CLIPS.mark(Math.min(dragFrom, now), Math.max(dragFrom, now));
      }
    });

    window.addEventListener("resize", drawTimeline);
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

  var trouble = document.getElementById("player-trouble");

  function sayTrouble(words) {
    if (!trouble) { return; }
    trouble.textContent = words;
    trouble.hidden = false;
  }
  window.VIEWER.sayTrouble = sayTrouble;

  if (player) {
    // A media element that fails does it silently: no message, no exception,
    // the Play button simply does nothing. Whatever went wrong is worth
    // saying, because the person watching cannot see the network.
    var WHY = {
      1: "the download was stopped",
      2: "the download failed part way through",
      3: "this browser could not decode the file",
      4: "this browser will not play this file, or it could not be fetched"
    };
    player.addEventListener("error", function () {
      var code = player.error ? player.error.code : 0;
      sayTrouble(
        "This recording will not play: " + (WHY[code] || "an unknown fault") +
        " (error " + code + "). The transcript below still works."
      );
      if (window.console) {
        window.console.error("playback failed", code,
          player.error && player.error.message, player.currentSrc);
      }
    });
    player.addEventListener("playing", function () {
      if (trouble) { trouble.hidden = true; }
    });

    player.addEventListener("seeked", function () {
      if (seekWatch) {
        window.clearTimeout(seekWatch);
        seekWatch = null;
      }
      // A jump that landed takes any complaint about jumping with it.
      if (trouble && !trouble.hidden) { trouble.hidden = true; }
    });

    player.addEventListener("timeupdate", follow);
    player.addEventListener("loadedmetadata", function () {
      // Only a real number. Some files report their length as Infinity or
      // as nothing at all, and either would make every position on the
      // timeline meaningless while looking like a length.
      if (isFinite(player.duration) && player.duration > 0) {
        duration = player.duration;
      }
      drawTimeline();
    });

    document.getElementById("play").addEventListener("click", function () {
      if (!player.paused) { player.pause(); return; }
      var started = player.play();
      if (started && started.catch) {
        started.catch(function (problem) {
          sayTrouble(
            "This recording did not start: " + problem.name + ". " +
            (problem.name === "NotAllowedError"
              ? "The browser blocked it; click the picture itself."
              : "The transcript below still works.")
          );
          if (window.console) { window.console.error("play() refused", problem); }
        });
      }
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
      document.querySelectorAll(".transport button, .transport select, .transport input"),
      function (control) { control.disabled = true; }
    );
  }

  // Rows ----------------------------------------------------------------------

  if (column) {
    column.addEventListener("click", function (event) {
      var row = event.target.closest(".seg");
      if (!row) { return; }
      var index = parseInt(row.dataset.index, 10);

      if (event.target.closest(".edit-row")) { edit(index); return; }
      if (event.target.closest(".clip-row")) { markFrom(index); return; }
      if (row.querySelector("textarea")) { return; }
      window.VIEWER.seek(segments[index].start);
    });

    column.addEventListener("dblclick", function (event) {
      var row = event.target.closest(".seg");
      if (row) { edit(parseInt(row.dataset.index, 10)); }
    });
  }

  // Marking a clip from the transcript -----------------------------------------
  //
  // Two steps, because one is not enough to say what is wanted and the button
  // has to say which step it is on. The first click marks where the clip
  // starts; the second marks where it ends and brings the panel up to name it
  // and save it. The panel stays out of the way until there is something in
  // it worth saving.

  var clipStartsAt = null;

  function markFrom(index) {
    if (!window.CLIPS || !segments[index]) { return; }
    var segment = segments[index];

    if (clipStartsAt === null) {
      clipStartsAt = index;
      if (column) { column.classList.add("marking"); }
      showsStart(index);
      // No panel yet: nothing is finished, and flinging it open over the
      // transcript at this point is in the way rather than helpful.
      window.CLIPS.mark(segment.start, segment.end, false);
      return;
    }

    // The earlier of the two is the start, whichever was clicked first, so
    // marking upwards through the transcript works as well as downwards.
    var other = segments[clipStartsAt];
    var start = Math.min(other.start, segment.start);
    var end = Math.max(other.end, segment.end);
    stopMarking();
    window.CLIPS.mark(start, end, true);
  }

  function showsStart(index) {
    if (!column) { return; }
    Array.prototype.forEach.call(
      column.querySelectorAll(".seg.clipstart"),
      function (row) { row.classList.remove("clipstart"); }
    );
    var row = column.children[index];
    if (row) { row.classList.add("clipstart"); }
  }

  function stopMarking() {
    clipStartsAt = null;
    if (!column) { return; }
    column.classList.remove("marking");
    Array.prototype.forEach.call(
      column.querySelectorAll(".seg.clipstart"),
      function (row) { row.classList.remove("clipstart"); }
    );
  }
  window.VIEWER.stopMarking = stopMarking;

  // Correcting ----------------------------------------------------------------

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }
  window.VIEWER.cookie = cookie;

  // One correction box at a time. Two would be a way to lose work: saving
  // one draws the transcript again, and the other would go with it.
  var editing = null;

  function tidyUp() {
    // Clicking away from an untouched box closes it: there is nothing to
    // lose and leaving it open is only clutter. A box that has been typed in
    // is left alone and says so, because this is a transcript: saving what
    // somebody was still thinking about would be as wrong as throwing it
    // away.
    if (!editing) { return; }
    if (editing.box.value === editing.was) {
      editing.stop();
      return;
    }
    editing.row.classList.add("unfinished");
  }

  document.addEventListener("mousedown", function (event) {
    if (!editing) { return; }
    if (event.target.closest(".seg.editing")) { return; }
    tidyUp();
  });

  function edit(index) {
    var segment = segments[index];
    var row = column ? column.children[index] : null;
    if (!segment || !row || row.querySelector("textarea")) { return; }

    // Opening another one closes this one first, under the same rule. If it
    // will not close, because it has been typed in, this one does not open:
    // saving a correction draws the transcript again, which would take an
    // unfinished box down with it and lose what was in it. One box, always.
    tidyUp();
    if (editing) {
      editing.row.scrollIntoView({ block: "center" });
      editing.box.focus();
      return;
    }

    var said = row.querySelector(".txt");
    if (!said) { return; }

    var holder = document.createElement("div");
    holder.className = "correcting";

    var box = document.createElement("textarea");
    box.rows = 3;
    box.value = segment.text;
    holder.appendChild(box);

    var tools = document.createElement("div");
    tools.className = "row small";

    var save = document.createElement("button");
    save.type = "button";
    save.className = "primary small";
    save.textContent = "Save correction";

    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost small";
    cancel.textContent = "Cancel";

    var hint = document.createElement("span");
    hint.className = "muted";
    hint.textContent = "Ctrl + Enter saves, Esc cancels";

    tools.appendChild(save);
    tools.appendChild(cancel);
    tools.appendChild(hint);
    holder.appendChild(tools);

    said.replaceWith(holder);
    row.classList.add("editing");
    box.focus();

    function stop() {
      var back = document.createElement("p");
      back.className = "txt";
      back.innerHTML = wordsOf(segment);
      holder.replaceWith(back);
      row.classList.remove("editing", "unfinished");
      if (editing && editing.box === box) { editing = null; }
    }

    editing = { row: row, box: box, was: segment.text, stop: stop };

    function keep() {
      var text = box.value.trim();
      if (text === segment.text) { stop(); return; }
      box.disabled = true;
      save.disabled = true;
      fetch("/recording/" + window.VIEWER.recording + "/segment/" + segment.id, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken")
        },
        body: JSON.stringify({ text: text })
      }).then(function (answer) {
        // A correction is only saved when the app says so. A session that
        // ended while this page sat open is turned away here, and showing
        // the new words as though they were kept would be a lie about a
        // transcript.
        if (!answer.ok) { return Promise.reject(answer.status); }
        return answer.json();
      }).then(function (told) {
        if (!told.corrected) { return Promise.reject("refused"); }
        segment.text = text;
        segment.corrected = true;
        // The words are the machine's; once a person has changed the text,
        // the old word timings no longer describe it.
        segment.words = [];
        editing = null;
        draw();
        // draw() built the rows again, so the highlight and any search
        // have to be put back.
        here = -1;
        follow();
        if (search && search.value.trim()) { look(); }
        if (window.CLIPS) { window.CLIPS.load(); }
      }).catch(function () {
        box.disabled = false;
        save.disabled = false;
        window.alert(
          "That correction was not saved. You may have been signed out; " +
          "open the page again and check before retyping it."
        );
      });
    }

    save.addEventListener("click", keep);
    cancel.addEventListener("click", stop);

    box.addEventListener("input", function () {
      row.classList.toggle("unfinished", false);
    });

    box.addEventListener("keydown", function (event) {
      event.stopPropagation();
      if (event.key === "Escape") { stop(); return; }
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { keep(); }
    });
  }

  // Speakers ------------------------------------------------------------------

  var chips = document.getElementById("speakers");
  if (chips) {
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest(".speakerchip");
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
      var chip = event.target.closest(".speakerchip");
      if (chip) { chip.classList.add("over"); }
    });
    chips.addEventListener("dragleave", function (event) {
      var chip = event.target.closest(".speakerchip");
      if (chip) { chip.classList.remove("over"); }
    });
    chips.addEventListener("drop", function (event) {
      event.preventDefault();
      var onto = event.target.closest(".speakerchip");
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
      var hit = wanted && segment.text.toLowerCase().indexOf(wanted) !== -1;
      row.hidden = wanted !== "" && !hit;
      row.classList.remove("match-here");

      var said = row.querySelector(".txt");
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

  // The sheet and the overlay --------------------------------------------------

  var sheet = document.getElementById("sheet");
  var closeSheet = document.getElementById("close-sheet");
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

  // The sheet stays where it was put. Somebody working through a case moves
  // from one recording to the next all day, and a panel that closed itself
  // every time would have to be reopened every time.
  var sheetGrip = document.getElementById("sheet-grip");

  function rememberSheet(what) {
    try {
      window.localStorage.setItem("sheet", what);
    } catch (ignored) { /* a browser that forbids storage forgets it */ }
  }

  function openSheet(which, keep) {
    sheet.hidden = false;
    closeSheet.hidden = false;
    if (sheetGrip) { sheetGrip.hidden = false; }
    Array.prototype.forEach.call(
      sheet.querySelectorAll(".panel"),
      function (panel) { panel.hidden = panel.dataset.panel !== which; }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll(".sheet-tab"),
      function (tab) { tab.classList.toggle("on", tab.dataset.panel === which); }
    );
    if (which === "details") { loadDetails(); }
    // `keep` is for restoring what was already chosen, which is not itself a
    // choice and must not overwrite one.
    if (!keep) { rememberSheet(which); }
  }
  window.VIEWER.openSheet = openSheet;

  Array.prototype.forEach.call(
    document.querySelectorAll(".sheet-tab"),
    function (tab) {
      tab.addEventListener("click", function () {
        if (!sheet.hidden && tab.classList.contains("on")) {
          hideSheet();
        } else {
          openSheet(tab.dataset.panel);
        }
      });
    }
  );

  function hideSheet(keep) {
    sheet.hidden = true;
    closeSheet.hidden = true;
    if (sheetGrip) { sheetGrip.hidden = true; }
    Array.prototype.forEach.call(
      document.querySelectorAll(".sheet-tab"),
      function (tab) { tab.classList.remove("on"); }
    );
    if (!keep) { rememberSheet("closed"); }
  }
  closeSheet.addEventListener("click", function () { hideSheet(); });

  // Resizing it ----------------------------------------------------------------

  var SHORTEST = 120;
  // What the transcript and the panels beside it must keep, whatever the
  // sheet is dragged to. A fraction of the window is not enough of a rule:
  // the dock above is as tall as the picture, which is itself resizable, so
  // the room left over has to be measured rather than assumed.
  //
  // A floor rather than a comfortable minimum, on purpose. This figure also
  // trims a remembered height on load, and a comfortable one would snap the
  // sheet smaller every time the page opened, which is the jerkiness this is
  // meant to be rid of. It only has to stop the transcript disappearing.
  var LEAST_ROOM_ABOVE = 160;

  function tallest() {
    var above = document.querySelector(".body");
    // Measured only when the sheet is actually in the layout. Asked while it
    // is hidden, the body has the room the sheet would take, and the answer
    // would be far too small: that is what shrank a remembered height every
    // time the page loaded.
    if (!above || sheet.hidden) {
      return Math.max(SHORTEST, Math.round(window.innerHeight * 0.7));
    }
    // The sheet and the part above it share what is left of the window, so
    // the most the sheet can take is the pair of them less that minimum.
    var shared = sheet.getBoundingClientRect().height
      + above.getBoundingClientRect().height;
    return Math.max(SHORTEST, Math.round(shared - LEAST_ROOM_ABOVE));
  }

  function setSheetHeight(pixels) {
    var wanted = Math.round(Math.min(tallest(), Math.max(SHORTEST, pixels)));
    document.documentElement.style.setProperty("--sheet-height", wanted + "px");
    return wanted;
  }

  function trimToFit() {
    // Once the sheet is really there, a remembered height that no longer fits
    // is brought down to one that does. The stored figure is left alone, so a
    // bigger window gets it back.
    if (sheet.hidden) { return; }
    if (sheet.getBoundingClientRect().height > tallest()) {
      setSheetHeight(tallest());
    }
  }

  function rememberHeight(pixels) {
    try {
      window.localStorage.setItem("sheet-height", String(pixels));
    } catch (ignored) { /* the size then lasts this page only */ }
  }

  var storedHeight = null;
  try {
    storedHeight = window.localStorage.getItem("sheet-height");
  } catch (ignored) { /* the sheet keeps the usual height */ }
  if (storedHeight) { setSheetHeight(parseInt(storedHeight, 10)); }

  if (sheetGrip) {
    var sizing = false;
    var startedY = 0;
    var wasTall = 0;

    sheetGrip.addEventListener("pointerdown", function (event) {
      sizing = true;
      startedY = event.clientY;
      wasTall = sheet.getBoundingClientRect().height;
      sheetGrip.setPointerCapture(event.pointerId);
      document.querySelector(".desk").classList.add("sizing");
      event.preventDefault();
    });

    sheetGrip.addEventListener("pointermove", function (event) {
      if (!sizing) { return; }
      // Dragging the strip upwards makes the sheet taller, so the sign is
      // the other way round from the pointer's own movement.
      setSheetHeight(wasTall - (event.clientY - startedY));
    });

    function doneSizing() {
      if (!sizing) { return; }
      sizing = false;
      document.querySelector(".desk").classList.remove("sizing");
      rememberHeight(Math.round(sheet.getBoundingClientRect().height));
      drawTimeline();
    }
    sheetGrip.addEventListener("pointerup", doneSizing);
    sheetGrip.addEventListener("pointercancel", doneSizing);
    // Backstops. A pointer capture is not always given back to the element
    // that took it, and when the up is missed the drag never ends: the size
    // is not remembered and the resize cursor stays on the whole page.
    sheetGrip.addEventListener("lostpointercapture", doneSizing);
    window.addEventListener("pointerup", doneSizing);
    window.addEventListener("blur", doneSizing);

    sheetGrip.addEventListener("dblclick", function () {
      rememberHeight(setSheetHeight(Math.round(window.innerHeight * 0.4)));
      drawTimeline();
    });

    // A window that shrinks takes the sheet with it rather than leaving the
    // transcript with nothing. The choice is left alone, so the sheet comes
    // back at its full height on a taller window.
    window.addEventListener("resize", trimToFit);

    sheetGrip.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 60 : 20;
      if (event.key === "ArrowDown") { step = -step; }
      else if (event.key !== "ArrowUp") { return; }
      event.preventDefault();
      rememberHeight(setSheetHeight(sheet.getBoundingClientRect().height + step));
      drawTimeline();
    });
  }

  // The sheet comes back as it was left, now rather than when the transcript
  // arrives, so the page settles once instead of jumping. A link that names a
  // panel wins, and openWhereAsked() opens that one when it runs. Restoring is
  // not a choice, so it does not overwrite the one that was made.
  (function () {
    var asked = new URLSearchParams(window.location.search);
    if (asked.get("clip") || asked.get("panel")) { return; }
    var was = null;
    try {
      was = window.localStorage.getItem("sheet");
    } catch (ignored) { /* the sheet then starts closed, as it always did */ }
    if (was === "clips" && window.VIEWER.clips) { openSheet("clips", true); }
    else if (was === "details") { openSheet("details", true); }
    window.requestAnimationFrame(trimToFit);
  }());

  var overlay = document.getElementById("shortcuts");
  function shortcuts(show) { overlay.hidden = !show; }
  document.getElementById("open-shortcuts").addEventListener("click", function () {
    shortcuts(true);
  });
  document.getElementById("close-shortcuts").addEventListener("click", function () {
    shortcuts(false);
  });
  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) { shortcuts(false); }
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
      if (clipStartsAt !== null) { stopMarking(); return; }
      if (window.CLIPS && window.CLIPS.range()) { window.CLIPS.clear(); return; }
      if (!sheet.hidden) { hideSheet(); }
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

  // Waiting for the playback copy ---------------------------------------------
  //
  // Recognition finishes before the playback copy of a long video does, so a
  // person who opens the recording the moment the transcript lands sees
  // "Preparing video" on the thumbnail. The chapter says that overlay lifts
  // by itself, so the page asks every five seconds whether the copy is ready
  // and loads itself again the moment it is. Reading, search and correction
  // work meanwhile, and nothing here writes an audit row.
  function watchThePlayer() {
    if (window.VIEWER.canPlay) { return; }
    window.setInterval(function () {
      fetch("/recording/" + window.VIEWER.recording + "/media")
        .then(function (answer) { return answer.json(); })
        .then(function (state) { if (state.ready) { window.location.reload(); } })
        .catch(function () { /* the next look will find it */ });
    }, 5000);
  }
  watchThePlayer();

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

  // Opening at a place ---------------------------------------------------------

  function openWhereAsked() {
    // A link can name a time and a panel: the Clips page opens a recording at
    // its clip's start with the clips sheet open, and a citation will reach a
    // segment the same way.
    var asked = new URLSearchParams(window.location.search);

    // Not named "at": that is the binary search over the segments, which is
    // exactly what finds the row to bring into view.
    var when = parseFloat(asked.get("t"));
    if (!isNaN(when) && when >= 0) {
      window.VIEWER.seek(when);
      var index = at(when);
      var row = index >= 0 && column ? column.children[index] : null;
      if (row) {
        row.classList.add("here");
        row.scrollIntoView({ block: "center" });
      }
    }

    if (asked.get("clip") || asked.get("panel") === "clips") {
      if (window.VIEWER.clips) { openSheet("clips"); }
      return;
    }
    if (asked.get("panel") === "details") {
      openSheet("details");
      return;
    }

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
        drawTimeline();
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
        drawTimeline();
        if (player) { follow(); }
        openWhereAsked();
      });
  } else {
    watchTheQueue();
    openWhereAsked();
  }

  // Resizing the picture ------------------------------------------------------
  //
  // The width is the only thing chosen; the height follows it, so the picture
  // keeps its shape and the transport beside it does not jump about. The
  // choice is remembered, because somebody who wants a big picture wants it
  // on the next recording too.

  var SMALLEST = 160;
  var USUAL = 220;

  function widest() {
    // Never more than half the window: the transcript is the point of the
    // page, and a picture that pushed it off the screen would be a worse
    // page, not a bigger picture.
    return Math.max(SMALLEST, Math.round(window.innerWidth * 0.5));
  }

  function setWidth(pixels) {
    var wanted = Math.round(Math.min(widest(), Math.max(SMALLEST, pixels)));
    document.documentElement.style.setProperty("--thumb-width", wanted + "px");
    return wanted;
  }

  var grip = document.getElementById("thumb-grip");
  var thumb = document.getElementById("thumb");

  var remembered = null;
  try {
    remembered = window.localStorage.getItem("thumb-width");
  } catch (ignored) { /* a browser that forbids storage keeps the usual size */ }
  if (remembered) { setWidth(parseInt(remembered, 10) || USUAL); }

  function remember(pixels) {
    try {
      window.localStorage.setItem("thumb-width", String(pixels));
    } catch (ignored) { /* the same, and the size lasts this page only */ }
  }

  if (grip && thumb) {
    // Named for the picture, and not `dragging`, which is the timeline's.
    // This whole file is one function, so a second `var dragging` here was
    // not a second variable: it was the same one. This block listens for
    // pointerup on the window, and a browser sends pointerup before
    // mouseup, so every click on the timeline of a video had its drag
    // cancelled here before the timeline could act on it, and the video
    // never moved. A recording with no picture has no grip and none of
    // this exists for it, which is why audio scrubbed and video did not.
    var sizingPicture = false;
    var pictureFromX = 0;
    var pictureWas = 0;

    grip.addEventListener("pointerdown", function (event) {
      sizingPicture = true;
      pictureFromX = event.clientX;
      pictureWas = thumb.getBoundingClientRect().width;
      grip.setPointerCapture(event.pointerId);
      document.querySelector(".dock").classList.add("resizing");
      event.preventDefault();
    });

    grip.addEventListener("pointermove", function (event) {
      if (!sizingPicture) { return; }
      setWidth(pictureWas + (event.clientX - pictureFromX));
    });

    function letGo() {
      if (!sizingPicture) { return; }
      sizingPicture = false;
      document.querySelector(".dock").classList.remove("resizing");
      remember(Math.round(thumb.getBoundingClientRect().width));
      trimToFit();
      drawTimeline();
    }
    grip.addEventListener("pointerup", letGo);
    grip.addEventListener("pointercancel", letGo);
    grip.addEventListener("lostpointercapture", letGo);
    window.addEventListener("pointerup", letGo);
    window.addEventListener("blur", letGo);

    grip.addEventListener("dblclick", function () {
      remember(setWidth(USUAL));
      drawTimeline();
    });

    // The keyboard reaches it too: the handle takes focus, and the arrows
    // move it in steps a person can predict.
    grip.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 60 : 20;
      if (event.key === "ArrowLeft") { step = -step; }
      else if (event.key !== "ArrowRight") { return; }
      event.preventDefault();
      remember(setWidth(thumb.getBoundingClientRect().width + step));
      drawTimeline();
    });

    // A window that shrinks below what was chosen takes the picture with it,
    // and the choice is left alone so it comes back on a wider window.
    window.addEventListener("resize", function () {
      var now = thumb.getBoundingClientRect().width;
      if (now > widest()) { setWidth(widest()); }
      drawTimeline();
    });
  }

  drawTimeline();
})();

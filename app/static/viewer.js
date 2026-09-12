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
  // A sprite icon from a script, the same one the {% icon %} tag draws.
  function icon(name) {
    return "<svg class='i' aria-hidden='true' focusable='false'><use href='#i-" + name + "'></use></svg>";
  }
  window.VIEWER.icon = icon;
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
  // A citation clicked: the transcript scrolls to the line that starts in
  // that second and lights it for a moment, so the eye lands where the ear does.
  window.VIEWER.showSegment = function (seconds) {
    if (!column) { return; }
    if (window.VIEWER.openTab) { window.VIEWER.openTab("transcript"); }
    var index = -1;
    segments.some(function (segment, n) {
      if (Math.floor(segment.start) === Math.floor(seconds)) { index = n; return true; }
      return false;
    });
    if (index < 0) { return; }
    var row = column.children[index];
    if (!row) { return; }
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    row.classList.add("lit");
    window.setTimeout(function () { row.classList.remove("lit"); }, 2400);
  };
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
      body.className = "words";

      var who = document.createElement("div");
      who.className = "who";
      // A speaker's second line in a row leaves the name column blank.
      if (index > 0 && segments[index - 1].speaker === segment.speaker) {
        row.classList.add("cont");
      }
      var actions = document.createElement("span");
      actions.className = "actions";

      var editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "ghost tiny edit-row";
      editButton.title = "Correct this segment (E)";
      editButton.innerHTML = icon("correct") + " edit";
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
      name.textContent = segment.speaker || "";
      if (segment.corrected) {
        var mark = document.createElement("span");
        mark.className = "corrected-mark";
        mark.title = "Corrected by staff";
        mark.innerHTML = icon("corrected");
        name.appendChild(mark);
      }
      who.appendChild(name);
      // The pills (a suggested name, a Camera? cue) go over the words, in
      // the words' column, where there is room for them.
      var tags = document.createElement("span");
      tags.className = "tags";
      body.appendChild(tags);

      var said = document.createElement("p");
      said.className = "txt";
      said.innerHTML = wordsOf(segment);
      body.appendChild(said);

      row.appendChild(when);
      row.appendChild(who);
      row.appendChild(body);
      // Its own column, so the buttons never sit over the words.
      row.appendChild(actions);
      column.appendChild(row);
    });
    tintRange();
    // A redraw builds every row again, so a start marked before it has to be
    // put back on the row it belongs to.
    if (clipStartsAt !== null) { showsStart(clipStartsAt); }
    // The AI assistant puts its suggestion pills on the rows after they exist.
    document.dispatchEvent(new Event("transcript-drawn"));
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
    followAt(player.currentTime);
  }

  // The rows, the playhead and the clock at a time: the player's own, or the
  // Speakers window's while that window has the sound.
  function followAt(time) {
    movePlayhead(time);

    var index = at(time);
    if (index !== here) {
      var was = column ? column.querySelector(".seg.here") : null;
      if (was) { was.classList.remove("here"); }
      var now = column ? column.children[index] : null;
      if (now) {
        now.classList.add("here");
        // Scrolled to the centre only once it has left the middle of the
        // column. Centring every new line made a column of short lines
        // creep and bounce, a glide every second or two.
        if (following && !paused && !now.querySelector("textarea") && outOfTheMiddle(now)) {
          now.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      here = index;
      sayNow(segments[index]);
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
      clock(time) + " / " + clock((player && player.duration) || duration);
  }

  // The line being spoken, on the stage, so a person watching the picture
  // or tagging voices sees who is speaking without looking down.
  var nowLine = document.getElementById("now");
  function sayNow(segment) {
    if (!nowLine) { return; }
    var who = document.getElementById("now-who");
    var text = document.getElementById("now-text");
    var when = document.getElementById("now-clock");
    nowLine.classList.toggle("empty", !segment);
    who.textContent = segment ? (segment.speaker || "") : "";
    who.style.setProperty("--speaker", segment && segment.speaker ? (colours[segment.speaker] || "") : "");
    text.textContent = segment ? segment.text : "";
    when.textContent = segment ? clock(segment.start) : "";
  }

  function pauseFollowing() {
    if (!following || paused) { return; }
    paused = true;
    if (pill) { pill.hidden = false; }
  }

  // Whether a row sits outside the middle band of the column, from about a
  // fifth of the way down to about three quarters: inside it, reading is
  // comfortable and nothing moves.
  function outOfTheMiddle(row) {
    if (!reading) { return true; }
    var box = reading.getBoundingClientRect();
    var seen = row.getBoundingClientRect();
    if (!box.height) { return false; }
    return seen.top < box.top + box.height * 0.18 || seen.bottom > box.top + box.height * 0.74;
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
    var strip = document.getElementById("caption");
    var said = document.getElementById("clip-said");
    var drop = document.getElementById("drop-clip");
    var preview = document.getElementById("clip-preview-strip");
    var save = document.getElementById("clip-save-go");
    if (!box) { return; }
    var marked = !(from === null || from === undefined || !duration);
    if (strip) { strip.classList.toggle("marking", marked); }
    [drop, preview, save].forEach(function (one) { if (one) { one.hidden = !marked; } });
    if (!marked) {
      box.hidden = true;
      if (said) { said.textContent = ""; }
      return;
    }
    box.hidden = false;
    box.style.left = ((from / duration) * 100) + "%";
    box.style.width = (((to - from) / duration) * 100) + "%";
    if (said) {
      var inside = segments.filter(function (one) { return one.start < to && one.end > from; }).length;
      said.textContent = "Clip " + clock(from) + " to " + clock(to) + ", " + clock(to - from) + " long" +
        (window.VIEWER.hasTranscript ? ", " + inside + (inside === 1 ? " line" : " lines") : "");
      said.style.color = ink("--clip");
    }
  }

  var dropClip = document.getElementById("drop-clip");
  if (dropClip) {
    dropClip.addEventListener("click", function () {
      if (window.CLIPS) { window.CLIPS.clear(); }
    });
  }
  var previewStrip = document.getElementById("clip-preview-strip");
  if (previewStrip) {
    previewStrip.addEventListener("click", function () {
      if (window.CLIPS && window.CLIPS.preview) { window.CLIPS.preview(); }
    });
  }
  var saveGo = document.getElementById("clip-save-go");
  if (saveGo) {
    saveGo.addEventListener("click", function () {
      if (window.VIEWER.openTab) { window.VIEWER.openTab("clips"); }
      var title = document.getElementById("clip-title");
      if (title) { title.focus(); title.select(); }
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

  function sayTrouble(words, detail) {
    if (!trouble) { return; }
    trouble.textContent = "";
    trouble.appendChild(document.createTextNode(words + " "));
    if (detail) {
      var more = document.createElement("details");
      more.className = "inline";
      var summary = document.createElement("summary");
      summary.textContent = "Details";
      more.appendChild(summary);
      more.appendChild(document.createTextNode(detail));
      trouble.appendChild(more);
    }
    trouble.hidden = false;
  }
  window.VIEWER.sayTrouble = sayTrouble;

  if (player) {
    // A media element that fails does it silently: no message, no exception,
    // the Play button simply does nothing. Whatever went wrong is worth
    // saying, because the person watching cannot see the network.
    var WHY = {
      1: "The download was stopped.",
      2: "The download failed part way through.",
      3: "This browser could not decode the file.",
      4: "This browser will not play this file, or it could not be fetched."
    };
    player.addEventListener("error", function () {
      var code = player.error ? player.error.code : 0;
      // The first sentence is for a colleague; the detail sits behind a word.
      sayTrouble(
        "This recording will not play here. The transcript still works.",
        (WHY[code] || "An unknown fault.") + " Media error " + code + "."
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
      window.CLIPS.mark(segment.start, segment.end);
      return;
    }

    // The earlier of the two is the start, whichever was clicked first, so
    // marking upwards through the transcript works as well as downwards.
    var other = segments[clipStartsAt];
    var start = Math.min(other.start, segment.start);
    var end = Math.max(other.end, segment.end);
    stopMarking();
    window.CLIPS.mark(start, end);
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
        UI.alert({
          title: "That correction was not saved",
          body: "You may have been signed out. Open the page again and check before retyping it."
        });
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
    // Inside a case the rename box lists the case's people as the name is
    // typed; elsewhere the browser's own prompt does, as it always did.
    var renameBox = document.getElementById("rename-box");
    var renaming = null;
    // The case's people under the field: all of them until the person types
    // something other than the speaker's current name, then those that
    // contain what was typed.
    function showPeople() {
      var list = document.getElementById("people-pick");
      if (!list) { return; }
      var typed = document.getElementById("rename-input").value.trim().toLowerCase();
      var narrowing = typed && typed !== (renaming || "").toLowerCase();
      var shown = 0;
      list.querySelectorAll("li").forEach(function (row) {
        var name = row.querySelector(".pick").dataset.name.toLowerCase();
        var on = !narrowing || name.indexOf(typed) !== -1;
        row.hidden = !on;
        if (on) { shown += 1; }
      });
      var none = document.getElementById("people-none");
      if (none) { none.hidden = shown > 0; }
    }
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest(".speakerchip");
      if (!chip) { return; }
      if (renameBox) {
        renaming = chip.dataset.name;
        document.getElementById("rename-label").textContent = "Rename " + renaming + " to";
        var box = document.getElementById("rename-input");
        box.value = renaming;
        renameBox.hidden = false;
        showPeople();
        box.focus();
        box.select();
        return;
      }
      UI.prompt({ title: "Rename " + chip.dataset.name, body: "Every line this speaker spoke takes the new name.", value: chip.dataset.name, ok: "Rename" })
        .then(function (now) {
          if (!now || now === chip.dataset.name) { return; }
          rename(chip.dataset.name, now);
        });
    });
    if (renameBox) {
      document.getElementById("rename-save").addEventListener("click", function () {
        var now = document.getElementById("rename-input").value.trim();
        if (!now || now === renaming) { renameBox.hidden = true; return; }
        rename(renaming, now);
      });
      document.getElementById("rename-cancel").addEventListener("click", function () {
        renameBox.hidden = true;
      });
      document.getElementById("rename-input").addEventListener("keydown", function (event) {
        if (event.key === "Enter") { event.preventDefault(); document.getElementById("rename-save").click(); }
        if (event.key === "Escape") { renameBox.hidden = true; }
      });
      document.getElementById("rename-input").addEventListener("input", showPeople);
      var picks = document.getElementById("people-pick");
      if (picks) {
        picks.addEventListener("click", function (event) {
          var pick = event.target.closest(".pick");
          if (!pick) { return; }
          var now = pick.dataset.name;
          if (now === renaming) { renameBox.hidden = true; return; }
          rename(renaming, now);
        });
      }
    }

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
      var was = dragged;
      UI.confirm({
        title: "Merge " + was + " into " + onto.dataset.name + "?",
        body: "Every line of " + was + " becomes " + onto.dataset.name + ". Rename one of them afterwards if that was wrong.",
        ok: "Merge"
      }).then(function (yes) { if (yes) { rename(was, onto.dataset.name); } });
    });
  }

  var speakersToggle = document.getElementById("speakers-toggle");
  if (speakersToggle) {
    speakersToggle.addEventListener("click", function () {
      var hidden = document.body.classList.toggle("no-speakers");
      this.textContent = hidden ? "show" : "hide";
    });
  }

  // Fold the speakers away to one line, and remember it: somebody reading
  // a long transcript wants the words, not the cast, most of the time.
  var cast = document.getElementById("cast");
  var castToggle = document.getElementById("cast-toggle");
  function foldCast(folded) {
    if (!cast) { return; }
    cast.classList.toggle("folded", folded);
    if (castToggle) {
      castToggle.textContent = folded ? "unfold" : "fold";
      castToggle.title = folded ? "Show the speakers" : "Fold the speakers away to one line";
    }
    var count = document.getElementById("cast-count");
    if (count) {
      var n = cast.querySelectorAll(".speakerchip").length;
      count.textContent = folded && n ? n + (n === 1 ? " speaker" : " speakers") : "";
    }
  }
  if (castToggle) {
    castToggle.addEventListener("click", function () {
      var folded = !cast.classList.contains("folded");
      foldCast(folded);
      try { window.localStorage.setItem("cast-folded", folded ? "yes" : "no"); } catch (ignored) { /* this page only */ }
    });
    try {
      foldCast(window.localStorage.getItem("cast-folded") === "yes");
    } catch (ignored) { foldCast(false); }
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

  // Undo the last rename or merge: the lines it moved take their old name.
  var undoButton = document.getElementById("speakers-undo");
  if (undoButton) {
    undoButton.addEventListener("click", function () {
      var what = document.getElementById("speakers-undo-what").textContent;
      UI.confirm({ title: "Undo " + what + "?", body: "The lines that were moved take their old name back. Nothing else changes.", ok: "Undo" })
        .then(function (yes) {
          if (!yes) { return; }
          fetch("/recording/" + window.VIEWER.recording + "/speakers/undo", {
            method: "POST",
            headers: { "X-CSRFToken": cookie("csrftoken") }
          }).then(function () { window.location.reload(); });
        });
    });
  }

  // Rename the recording itself, after the fact.
  var renameTitle = document.getElementById("rename-title");
  if (renameTitle) {
    renameTitle.addEventListener("click", function () {
      var heading = document.getElementById("recording-title");
      UI.prompt({ title: "Rename this recording", body: "The new title is what every page and export shows. The file keeps its own name.", value: heading.textContent.trim(), ok: "Rename" })
        .then(function (now) {
          if (!now || now.trim() === heading.textContent.trim()) { return; }
          fetch("/recording/" + window.VIEWER.recording + "/rename", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
            body: JSON.stringify({ title: now.trim() })
          }).then(function (answer) { return answer.json(); }).then(function (said) {
            if (said.title) {
              heading.textContent = said.title;
              document.title = document.title.replace(/^[^·]*·/, said.title + " ·");
              UI.toast("Renamed.", { icon: "ok" });
            } else {
              UI.toast(said.error || "That could not be renamed.", { problem: true, icon: "warning" });
            }
          });
        });
    });
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

  // The work area -------------------------------------------------------------
  //
  // The tabs along the top of the work area: Transcript, Clips, Summary,
  // Chat, Moments, Details, one at a time at full width. The one chosen is
  // remembered, because somebody working through a case moves from one
  // recording to the next all day; a link that names a panel wins.

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
        drawMarks(body.marks || []);
      });
  }

  // The Marks a person dropped while recording live: each a time that seeks
  // the player, with its word, and Make a clip around it while Clips are on.
  function drawMarks(marks) {
    var box = document.getElementById("marks");
    if (!box) { return; }
    box.hidden = !marks.length;
    if (!marks.length) { return; }
    var list = box.querySelector("ul");
    list.innerHTML = marks.map(function (one) {
      return "<li><button type='button' class='cite' data-at='" + one.at + "'>" + escape(one.clock) + "</button>" +
        (one.word ? " <span>" + escape(one.word) + "</span>" : "") +
        (window.CLIPS ? " <button type='button' class='ghost tiny make-clip' data-at='" + one.at + "' data-word='" + escape(one.word || "") + "'>Make a clip</button>" : "") +
        "</li>";
    }).join("");
    list.addEventListener("click", function (event) {
      var cite = event.target.closest(".cite");
      if (cite) { window.VIEWER.showSegment(parseFloat(cite.dataset.at)); return; }
      var make = event.target.closest(".make-clip");
      if (make && window.CLIPS) {
        var at = parseFloat(make.dataset.at);
        window.CLIPS.mark(Math.max(0, at - 30), at + 30);
        var title = document.getElementById("clip-title");
        if (title && make.dataset.word && !title.value) { title.value = make.dataset.word; }
      }
    });
  }

  var panels = document.getElementById("panels");

  function rememberTab(what) {
    try {
      window.localStorage.setItem("tab", what);
    } catch (ignored) { /* a browser that forbids storage forgets it */ }
  }

  function openTab(which, keep) {
    if (!panels) { return; }
    if (!document.querySelector('.tab[data-panel="' + which + '"]')) { which = "transcript"; }
    Array.prototype.forEach.call(
      panels.querySelectorAll(".panel"),
      function (panel) { panel.hidden = panel.dataset.panel !== which; }
    );
    Array.prototype.forEach.call(
      document.querySelectorAll(".tab"),
      function (tab) { tab.classList.toggle("on", tab.dataset.panel === which); }
    );
    if (which === "details") { loadDetails(); }
    if (openWindowButton) { openWindowButton.hidden = which === "transcript"; }
    // `keep` is for restoring what was already chosen, which is not itself a
    // choice and must not overwrite one.
    if (!keep) { rememberTab(which); }
    document.dispatchEvent(new CustomEvent("tab-opened", { detail: which }));
  }
  window.VIEWER.openTab = openTab;
  // The name the clip tool and the assistant knew it by.
  window.VIEWER.openSheet = openTab;

  var openWindowButton = document.getElementById("open-window");
  Array.prototype.forEach.call(
    document.querySelectorAll(".tab"),
    function (tab) {
      tab.addEventListener("click", function () {
        // A tab that is out in its own window comes to the front instead.
        if (tab.classList.contains("away") && windowOf(tab.dataset.panel)) {
          windowOf(tab.dataset.panel).focus();
          return;
        }
        openTab(tab.dataset.panel);
      });
    }
  );

  // The tab comes back as it was left, now rather than when the transcript
  // arrives, so the page settles once. A link that names a panel wins, and
  // openWhereAsked() opens that one when it runs.
  (function () {
    var asked = new URLSearchParams(window.location.search);
    if (asked.get("clip") || asked.get("panel")) { openTab("transcript", true); return; }
    var was = null;
    try {
      was = window.localStorage.getItem("tab");
    } catch (ignored) { /* the transcript then, as always */ }
    openTab(was || "transcript", true);
  }());

  // Windows -------------------------------------------------------------------
  //
  // A tab opened in its own window, and the Speakers window, follow the
  // player through the browser's channel named for this recording: the page
  // sends the time and the line being spoken; a window sends seeks, clip
  // ranges, and word that something changed. On a second monitor the words
  // stay here and the tool sits there.

  var channel = ("BroadcastChannel" in window)
    ? new BroadcastChannel("transcribe-" + window.VIEWER.recording)
    : null;
  var windows = {};

  function tell(message) { if (channel) { channel.postMessage(message); } }

  function windowOf(panel) {
    var open = windows[panel];
    return open && !open.closed ? open : null;
  }

  function tabOf(panel) {
    return document.querySelector('.tab[data-panel="' + panel + '"]');
  }

  function markAway(panel, away) {
    var tab = tabOf(panel);
    if (!tab) { return; }
    tab.classList.toggle("away", away);
    tab.title = away ? "In its own window; press to bring it to the front" : "";
  }

  function openWindow(panel) {
    if (windowOf(panel)) { windowOf(panel).focus(); return; }
    var url = "/recording/" + window.VIEWER.recording + "/window/" + panel;
    var size = panel === "speakers" ? "width=560,height=720" : "width=780,height=900";
    windows[panel] = window.open(url, "transcribe-" + window.VIEWER.recording + "-" + panel, "popup," + size);
    if (!windows[panel]) {
      UI.toast("The browser blocked the window. Allow pop-ups for this site and try again.", { problem: true, icon: "warning" });
      return;
    }
    if (panel !== "speakers") {
      markAway(panel, true);
      openTab("transcript");
    }
  }
  window.VIEWER.openWindow = openWindow;

  if (openWindowButton) {
    openWindowButton.addEventListener("click", function () {
      var on = document.querySelector(".tab.on");
      if (on && on.dataset.panel !== "transcript") { openWindow(on.dataset.panel); }
    });
  }
  var tagSpeakers = document.getElementById("tag-speakers");
  if (tagSpeakers) {
    tagSpeakers.addEventListener("click", function () { openWindow("speakers"); });
  }

  // A window that closed without saying so gives its tab back.
  window.setInterval(function () {
    Object.keys(windows).forEach(function (panel) {
      if (windows[panel] && windows[panel].closed) {
        windows[panel] = null;
        markAway(panel, false);
      }
    });
  }, 2000);

  // The transcript fetched again after a line changed hands in a window:
  // the rows redrawn, the highlight and any search put back.
  function reloadSegments() {
    if (!window.VIEWER.hasTranscript) { return; }
    fetch("/recording/" + window.VIEWER.recording + "/segments")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        segments = body.segments || [];
        wordTiming = body.word_timestamps;
        draw();
        here = -1;
        if (player) { follow(); }
        if (search && search.value.trim()) { look(); }
      })
      .catch(function () { /* the next change will bring it */ });
  }

  if (channel) {
    channel.onmessage = function (event) {
      var said = event.data || {};
      if (said.kind === "seek") {
        window.VIEWER.seek(said.at);
      } else if (said.kind === "play") {
        window.VIEWER.play();
      } else if (said.kind === "pause") {
        window.VIEWER.pause();
      } else if (said.kind === "step") {
        step(said.by || 0);
        if (said.play) { window.VIEWER.play(); }
      } else if (said.kind === "window-time") {
        // The Speakers window has a player of its own. While it plays, the
        // sound is its and this page follows along; when it pauses, the
        // page's player takes its place quietly, so Play here carries on.
        if (said.playing && player && !player.paused) { player.pause(); }
        if (player && player.paused && Math.abs(player.currentTime - said.at) > 1) {
          player.currentTime = said.at;
        }
        followAt(said.at || 0);
      } else if (said.kind === "show") {
        window.VIEWER.showSegment(said.at);
      } else if (said.kind === "range") {
        if (!window.CLIPS) { return; }
        if (said.from === null || said.from === undefined) { window.CLIPS.clear(); }
        else { window.CLIPS.mark(said.from, said.to); }
      } else if (said.kind === "refresh") {
        document.dispatchEvent(new CustomEvent("changed-elsewhere"));
        if (window.CLIPS) { window.CLIPS.load(); }
      } else if (said.kind === "segments-changed") {
        reloadSegments();
      } else if (said.kind === "speakers-changed") {
        window.location.reload();
      } else if (said.kind === "window-open") {
        if (said.panel !== "speakers") {
          markAway(said.panel, true);
          var on = document.querySelector(".tab.on");
          if (on && on.dataset.panel === said.panel) { openTab("transcript"); }
        }
      } else if (said.kind === "window-closed") {
        markAway(said.panel, false);
      }
    };

    // The time, a few times a second, with the line being spoken.
    var lastTold = -1;
    if (player) {
      player.addEventListener("timeupdate", function () {
        var now = Math.floor(player.currentTime * 4);
        if (now === lastTold) { return; }
        lastTold = now;
        tell({ kind: "time", at: player.currentTime, here: here, playing: !player.paused });
      });
      player.addEventListener("pause", function () {
        tell({ kind: "time", at: player.currentTime, here: here, playing: false });
      });
      player.addEventListener("play", function () {
        tell({ kind: "time", at: player.currentTime, here: here, playing: true });
      });
    }
    window.addEventListener("beforeunload", function () { tell({ kind: "page-closed" }); });
  }

  // The shortcuts overlay and the pop-out --------------------------------------
  //
  // Both were lost in v1.46.0, when the sheet's code around them was replaced;
  // Escape and ? threw on the missing overlay until v1.49.0 put them back.

  var overlay = document.getElementById("shortcuts");
  function shortcuts(show) { if (overlay) { overlay.hidden = !show; } }
  var openShortcuts = document.getElementById("open-shortcuts");
  if (openShortcuts) {
    openShortcuts.addEventListener("click", function () { shortcuts(true); });
  }
  var closeShortcuts = document.getElementById("close-shortcuts");
  if (closeShortcuts) {
    closeShortcuts.addEventListener("click", function () { shortcuts(false); });
  }
  if (overlay) {
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) { shortcuts(false); }
    });
  }

  var popOut = document.getElementById("pop-out");
  if (popOut && player && player.requestPictureInPicture) {
    popOut.addEventListener("click", function () {
      if (document.pictureInPictureElement) {
        document.exitPictureInPicture();
      } else {
        player.requestPictureInPicture().catch(function () {
          UI.toast("This browser will not pop the video out.", { problem: true, icon: "warning" });
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
      return;
    }
    if (event.key === "d" || event.key === "D") { openTab("details"); return; }

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
      UI.confirm({
        title: "Cancel this recording?",
        body: "It is removed from your recordings as if it had never been uploaded, and would have to be uploaded again.",
        ok: "Cancel the recording",
        cancel: "Let it run",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        fetch("/recording/" + window.VIEWER.recording + "/delete", {
          method: "POST",
          headers: { "X-CSRFToken": cookie("csrftoken") }
        }).then(function () { window.location = "/"; });
      });
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
      if (window.VIEWER.clips) { openTab("clips"); }
      return;
    }
    if (asked.get("panel") === "details") {
      openTab("details");
      return;
    }
    // A dictation's memo: the Dictations page opens the viewer on the Summary tab.
    if (asked.get("panel") === "summary" && document.querySelector('[data-panel="summary"]')) {
      openTab("summary");
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

  // Resizing the stage --------------------------------------------------------
  //
  // On a wide window the stage is a column, and its width is the one thing
  // a person chooses: the picture and the work area share the rest. The
  // choice is remembered, because somebody who wants a big picture wants it
  // on the next recording too. On a laptop the picture has one size and
  // there is nothing to drag.

  var WIDE = window.matchMedia("(min-width: 1280px)");
  var NARROWEST_STAGE = 360;

  // The usual width follows the window, as the stylesheet's clamp has it:
  // 360 px on a small monitor, about 560 on a 1920 one, 800 at most.
  function usualStage() {
    return Math.round(Math.min(800, Math.max(NARROWEST_STAGE, window.innerWidth * 0.29)));
  }

  function widestStage() {
    // Never more than half the window: the words are the point of the page.
    return Math.max(NARROWEST_STAGE, Math.round(window.innerWidth * 0.5));
  }

  function setStage(pixels) {
    var wanted = Math.round(Math.min(widestStage(), Math.max(NARROWEST_STAGE, pixels)));
    document.documentElement.style.setProperty("--stage", wanted + "px");
    return wanted;
  }

  var stageGrip = document.getElementById("stage-grip");
  var stage = document.querySelector(".stage");

  try {
    var rememberedStage = window.localStorage.getItem("stage-width");
    if (rememberedStage) { setStage(parseInt(rememberedStage, 10) || usualStage()); }
  } catch (ignored) { /* a browser that forbids storage keeps the usual size */ }

  function rememberStage(pixels) {
    try {
      window.localStorage.setItem("stage-width", String(pixels));
    } catch (ignored) { /* the size lasts this page only */ }
  }

  if (stageGrip && stage) {
    // Named for the stage, and not `dragging`, which is the timeline's: this
    // whole file is one function, and a second `var dragging` would be the
    // same variable.
    var sizingStage = false;
    var stageFromX = 0;
    var stageWas = 0;

    stageGrip.addEventListener("pointerdown", function (event) {
      if (!WIDE.matches) { return; }
      sizingStage = true;
      stageFromX = event.clientX;
      stageWas = stage.getBoundingClientRect().width;
      stageGrip.setPointerCapture(event.pointerId);
      document.querySelector(".desk").classList.add("resizing");
      event.preventDefault();
    });

    stageGrip.addEventListener("pointermove", function (event) {
      if (!sizingStage) { return; }
      // The grip is on the stage's right edge: dragging right makes it wider.
      setStage(stageWas + (event.clientX - stageFromX));
      window.requestAnimationFrame(drawTimeline);
    });

    function letGo() {
      if (!sizingStage) { return; }
      sizingStage = false;
      document.querySelector(".desk").classList.remove("resizing");
      rememberStage(Math.round(stage.getBoundingClientRect().width));
      drawTimeline();
    }
    stageGrip.addEventListener("pointerup", letGo);
    stageGrip.addEventListener("pointercancel", letGo);
    stageGrip.addEventListener("lostpointercapture", letGo);
    window.addEventListener("pointerup", letGo);
    window.addEventListener("blur", letGo);

    stageGrip.addEventListener("dblclick", function () {
      rememberStage(setStage(usualStage()));
      drawTimeline();
    });

    // The keyboard reaches it too: the handle takes focus, and the arrows
    // move it in steps a person can predict.
    stageGrip.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 60 : 20;
      if (event.key === "ArrowLeft") { step = -step; }
      else if (event.key !== "ArrowRight") { return; }
      event.preventDefault();
      rememberStage(setStage(stage.getBoundingClientRect().width + step));
      drawTimeline();
    });

    // A window that shrinks below what was chosen takes the stage with it,
    // and the choice is left alone so it comes back on a wider window.
    window.addEventListener("resize", function () {
      if (!WIDE.matches) { return; }
      var now = stage.getBoundingClientRect().width;
      if (now > widestStage()) { setStage(widestStage()); }
      drawTimeline();
    });
  }
  if (WIDE.addEventListener) {
    WIDE.addEventListener("change", function () { drawTimeline(); });
  }

  drawTimeline();
})();

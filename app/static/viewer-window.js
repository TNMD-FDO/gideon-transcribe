// A tab of the recording page in a window of its own, or the Speakers window.
//
// The page is the player; this window has none. Everything the tab's script
// asks the page for (the time, a seek, the line being spoken, a clip range)
// goes through the browser's own channel between the two, named for the
// recording, so a citation clicked here seeks the page's player and a range
// typed here lights the page's timeline. The window fetches the transcript
// once for its own bearings.

(function () {
  "use strict";

  var V = window.VIEWER;
  if (!V) { return; }
  var channel = ("BroadcastChannel" in window)
    ? new BroadcastChannel("transcribe-" + V.recording)
    : null;
  var time = 0;
  var playing = false;
  var segments = [];
  var duration = 0;
  var state = document.getElementById("win-state");
  // The Speakers window's own player; a tab's window has none and asks the page.
  var player = document.getElementById("player");

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

  function icon(name) {
    return "<svg class='i' aria-hidden='true' focusable='false'><use href='#i-" + name + "'></use></svg>";
  }

  // The last segment that has started at the page's time.
  function at(when) {
    var found = -1;
    for (var i = 0; i < segments.length; i += 1) {
      if (segments[i].start <= when) { found = i; } else { break; }
    }
    return found;
  }

  // What the tab's script may ask this window for, in the page's own names.
  V.clock = clock;
  V.icon = icon;
  V.cookie = cookie;
  // The window's own clock while it plays; the page's while the page does.
  V.at = function () { return player && !player.paused ? player.currentTime : time; };
  V.length = function () { return duration; };
  V.segments = function () { return segments; };
  V.currentSegment = function () { var i = at(V.at()); return i >= 0 ? segments[i] : null; };
  V.seek = function (seconds) {
    if (player) { player.currentTime = Math.max(0, seconds); return; }
    tell({ kind: "seek", at: seconds });
  };
  V.play = function () { if (player) { player.play(); return; } tell({ kind: "play" }); };
  V.pause = function () { if (player) { player.pause(); return; } tell({ kind: "pause" }); };
  V.showSegment = function (seconds) { tell({ kind: "show", at: seconds }); };
  V.showRange = function (from, to) { tell({ kind: "range", from: from, to: to }); };
  V.tintRange = function () {};
  V.stopMarking = function () {};
  V.resumeFollowing = function () {};
  V.sayTrouble = function () {};
  V.redraw = function () {};
  V.openTab = function () {};
  V.openSheet = V.openTab;

  // The one panel here is shown, whatever the markup says.
  Array.prototype.forEach.call(document.querySelectorAll("#panels .panel"), function (panel) {
    panel.hidden = false;
  });

  // Word that something changed here reaches the page, which refreshes.
  document.addEventListener("transcribe-posted", function () { tell({ kind: "refresh" }); });

  if (channel) {
    channel.onmessage = function (event) {
      var said = event.data || {};
      if (said.kind === "time") {
        // The page's player. With a player of its own, this window yields
        // the sound to a page that is playing and keeps its place in step.
        time = said.at || 0;
        if (player) {
          if (said.playing && !player.paused) { player.pause(); }
          if (player.paused && Math.abs(player.currentTime - time) > 1) { player.currentTime = time; }
          if (state) { state.textContent = said.playing ? "The page is playing, " + clock(time) : "Paused at " + clock(time); }
        } else {
          playing = !!said.playing;
          if (state) { state.textContent = (playing ? "Playing, " : "Paused at ") + clock(time); }
        }
        if (showNow) { showNow(); }
      } else if (said.kind === "page-closed") {
        if (state) { state.textContent = "The recording's page has closed; open it again to carry on."; }
      }
    };
    tell({ kind: "window-open", panel: V.windowPanel });
    window.addEventListener("beforeunload", function () {
      tell({ kind: "window-closed", panel: V.windowPanel });
    });
  }

  function loadSegments() {
    if (!V.hasTranscript) { return Promise.resolve(); }
    return fetch("/recording/" + V.recording + "/segments")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        segments = body.segments || [];
        if (segments.length) { duration = segments[segments.length - 1].end; }
      })
      .catch(function () { /* the window still follows the player */ });
  }

  // The Speakers window ------------------------------------------------------
  //
  // The line being spoken at the top with its label; the roster under it,
  // a number key each. A number gives that line to that speaker; rename
  // and merge are the page's own calls, so the transcript, the chips and
  // the exports change together, and Undo is here too.

  var showNow = null;
  var roster = document.getElementById("roster");
  if (V.windowPanel === "speakers") {
    var rows = roster ? Array.prototype.slice.call(roster.querySelectorAll(".one")) : [];
    var nowWho = document.getElementById("now-who");
    var nowText = document.getElementById("now-text");
    var nowClock = document.getElementById("now-clock");
    var undoLine = document.getElementById("speakers-undo-line");
    var undoWhat = document.getElementById("speakers-undo-what");

    function send(url, body) {
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
        body: JSON.stringify(body || {})
      }).then(function (answer) {
        return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
      });
    }

    function sayUndo(words) {
      if (!undoLine) { return; }
      undoLine.hidden = !words;
      undoWhat.textContent = words || "";
    }

    function fill() {
      rows.forEach(function (row) {
        var name = row.dataset.name;
        var mine = segments.filter(function (one) { return one.speaker === name; });
        row.querySelector(".count").textContent =
          "\u00B7 " + mine.length + (mine.length === 1 ? " line" : " lines");
        row.querySelector(".sample").textContent = mine.length
          ? "\u201C" + mine[0].text + "\u201D " + clock(mine[0].start)
          : "";
      });
    }

    showNow = function () {
      var segment = V.currentSegment();
      nowClock.textContent = clock(time);
      nowWho.textContent = segment ? (segment.speaker || "") : "";
      nowText.textContent = segment ? segment.text : "Nothing is playing yet.";
      rows.forEach(function (row) {
        row.classList.toggle("here", !!segment && row.dataset.name === segment.speaker);
        if (segment && row.dataset.name === segment.speaker) {
          nowWho.style.setProperty("--speaker", row.style.getPropertyValue("--speaker"));
        }
      });
    };

    function give(row) {
      var segment = V.currentSegment();
      if (!segment) { UI.toast("Nothing is playing yet.", { icon: "info" }); return; }
      var name = row.dataset.name;
      if (segment.speaker === name) { return; }
      send("/recording/" + V.recording + "/segment/" + segment.id + "/speaker", { speaker: name })
        .then(function (answer) {
          if (!answer.ok) { UI.toast(answer.said.error || "That line was not changed.", { problem: true, icon: "warning" }); return; }
          segment.speaker = name;
          sayUndo(answer.said.undo);
          fill();
          showNow();
          tell({ kind: "segments-changed" });
        });
    }

    function renameSpeaker(row) {
      var was = row.dataset.name;
      UI.prompt({ title: "Rename " + was, body: "Every line this speaker spoke takes the new name.", value: was, ok: "Rename" })
        .then(function (now) {
          if (!now || now === was) { return; }
          send("/recording/" + V.recording + "/speakers", { from: was, to: now }).then(function (answer) {
            if (!answer.ok) { UI.toast(answer.said.error || "Not renamed.", { problem: true, icon: "warning" }); return; }
            segments.forEach(function (one) { if (one.speaker === was) { one.speaker = now; } });
            row.dataset.name = now;
            row.querySelector(".name").textContent = now;
            sayUndo(answer.said.undo);
            fill();
            showNow();
            tell({ kind: "speakers-changed" });
          });
        });
    }

    function mergeSpeaker(row) {
      var was = row.dataset.name;
      var others = rows.filter(function (one) { return one !== row; });
      if (!others.length) { return; }
      var choices = others.map(function (one) { return rows.indexOf(one) + 1 + " " + one.dataset.name; }).join(", ");
      UI.prompt({ title: was + " is the same person as...", body: "Type the number of the speaker: " + choices + ". Every line of " + was + " takes that name.", value: "", ok: "Merge" })
        .then(function (typed) {
          var onto = rows[parseInt(String(typed || "").trim(), 10) - 1];
          if (!onto || onto === row) { return; }
          send("/recording/" + V.recording + "/speakers", { from: was, to: onto.dataset.name }).then(function (answer) {
            if (!answer.ok) { UI.toast(answer.said.error || "Not merged.", { problem: true, icon: "warning" }); return; }
            segments.forEach(function (one) { if (one.speaker === was) { one.speaker = onto.dataset.name; } });
            row.remove();
            rows = rows.filter(function (one) { return one !== row; });
            rows.forEach(function (one, index) { one.querySelector(".k").textContent = String(index + 1); });
            sayUndo(answer.said.undo);
            fill();
            showNow();
            tell({ kind: "speakers-changed" });
          });
        });
    }

    if (roster) {
      roster.addEventListener("click", function (event) {
        var row = event.target.closest(".one");
        if (!row) { return; }
        if (event.target.closest(".play-line")) {
          var first = segments.filter(function (one) { return one.speaker === row.dataset.name; })[0];
          if (first) { V.seek(first.start); V.play(); }
        } else if (event.target.closest(".name-speaker")) {
          renameSpeaker(row);
        } else if (event.target.closest(".same-as")) {
          mergeSpeaker(row);
        } else {
          give(row);
        }
      });
    }

    // The window's own transport, when it has a player: the page's keys and
    // buttons, and the page told the time so it follows this window.
    if (player) {
      var lastTold = -1;
      function tellTime() {
        var now = Math.floor(player.currentTime * 4);
        if (now === lastTold) { return; }
        lastTold = now;
        tell({ kind: "window-time", at: player.currentTime, playing: !player.paused });
      }
      player.addEventListener("timeupdate", function () {
        time = player.currentTime;
        playing = !player.paused;
        document.getElementById("clock").textContent =
          clock(player.currentTime) + " / " + clock(player.duration || duration);
        if (state) { state.textContent = (playing ? "Playing, " : "Paused at ") + clock(time); }
        showNow();
        tellTime();
      });
      player.addEventListener("loadedmetadata", function () {
        if (isFinite(player.duration) && player.duration > 0) { duration = player.duration; }
        document.getElementById("clock").textContent = clock(player.currentTime) + " / " + clock(duration);
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
        if (state) { state.textContent = "This window cannot play the recording here; the page still can."; }
      });
      document.getElementById("play").addEventListener("click", function () {
        if (player.paused) { player.play(); } else { player.pause(); }
      });
      Array.prototype.forEach.call(document.querySelectorAll("[data-seek]"), function (button) {
        button.addEventListener("click", function () {
          player.currentTime = Math.max(0, player.currentTime + parseFloat(button.dataset.seek));
          if (button.dataset.seek === "-3") { player.play(); }
        });
      });
      document.getElementById("speed").addEventListener("change", function () {
        player.playbackRate = parseFloat(this.value);
      });
    }

    var undoButton = document.getElementById("speakers-undo");
    if (undoButton) {
      undoButton.addEventListener("click", function () {
        UI.confirm({ title: "Undo " + undoWhat.textContent + "?", body: "The lines that were moved take their old name back. Nothing else changes.", ok: "Undo" })
          .then(function (yes) {
            if (!yes) { return; }
            send("/recording/" + V.recording + "/speakers/undo").then(function (answer) {
              if (!answer.ok) { return; }
              sayUndo(answer.said.undo);
              loadSegments().then(function () { fill(); showNow(); });
              tell({ kind: "speakers-changed" });
            });
          });
      });
    }

    document.addEventListener("keydown", function (event) {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }
      if (/^[1-9]$/.test(event.key)) {
        var row = rows[parseInt(event.key, 10) - 1];
        if (row) { event.preventDefault(); give(row); }
      } else if (event.key === " ") {
        event.preventDefault();
        if (player ? !player.paused : playing) { V.pause(); } else { V.play(); }
      } else if (event.key === "b" || event.key === "B") {
        if (player) { player.currentTime = Math.max(0, player.currentTime - 3); player.play(); }
        else { tell({ kind: "step", by: -3, play: true }); }
      } else if (player && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
        event.preventDefault();
        var by = event.shiftKey ? 1 : (event.ctrlKey || event.metaKey ? 30 : 5);
        player.currentTime = Math.max(0, player.currentTime + (event.key === "ArrowLeft" ? -by : by));
      }
    });

    loadSegments().then(function () { fill(); showNow(); });
  } else {
    loadSegments();
  }
})();

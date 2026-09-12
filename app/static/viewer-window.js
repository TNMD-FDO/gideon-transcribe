// A tab of the recording page in a window of its own.
//
// The page is the player; this window has none (the Speakers page in a window
// plays for itself and has a script of its own). Everything the tab's script
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
  V.at = function () { return time; };
  V.length = function () { return duration; };
  V.segments = function () { return segments; };
  V.currentSegment = function () { var i = at(V.at()); return i >= 0 ? segments[i] : null; };
  V.seek = function (seconds) { tell({ kind: "seek", at: seconds }); };
  V.play = function () { tell({ kind: "play" }); };
  V.pause = function () { tell({ kind: "pause" }); };
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
        time = said.at || 0;
        playing = !!said.playing;
        if (state) { state.textContent = (playing ? "Playing, " : "Paused at ") + clock(time); }
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

  loadSegments();
})();

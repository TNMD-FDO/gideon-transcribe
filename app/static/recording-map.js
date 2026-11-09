// The map in the stage (Phase 13 chapter 2, v1.225.0; the drawing
// recording-map-desk.html, Direction A), beside the case's map script
// (map.js), which draws the map itself in its recording mode.
//
// 1. window.RecordingClock: the page's player as the map's clock, in
//    seconds of the day on the case's clock, with the transcript's lines
//    (for the pips) and the line being spoken; a press on a pip seeks the
//    player and follows again, so the transcript scrolls to the line.
// 2. The stage's switch (Picture, Map, Both), remembered in this browser,
//    and the Now line on the map's foot.
// 3. The waiting file's card (Add anyway, Remove) and the shape watcher: now
//    and then the page asks whether the map's shape changed and, if it did,
//    says so and loads itself again at the same moment.

(function () {
  "use strict";

  var script = document.getElementById("recording-map-script");
  var box = document.getElementById("stage-map");
  var stage = document.querySelector(".stage");
  var player = document.getElementById("player");

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function cookie(name) { var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  function hms(seconds) { seconds = Math.round(seconds); seconds = ((seconds % 86400) + 86400) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function elapsed(seconds) { seconds = Math.max(0, Math.round(seconds || 0)); var m = Math.floor(seconds / 60), s = seconds % 60; return m + ":" + (s < 10 ? "0" : "") + s; }
  function toast(words, bad) { if (window.UI && window.UI.toast) { window.UI.toast(words, bad ? { problem: true } : undefined); } }
  function segments() { return window.VIEWER && window.VIEWER.segments ? window.VIEWER.segments() : []; }
  function reloadHere() {
    var at = player ? player.currentTime : 0;
    window.location.replace(window.location.pathname + "?t=" + at.toFixed(1));
  }

  // 1. The clock -------------------------------------------------------------------
  var start = box ? parseFloat(box.dataset.clockStart) : NaN;
  var onClock = !isNaN(start);
  function hereIndex() {
    var row = document.querySelector("#transcript .seg.here");
    return row ? Array.prototype.indexOf.call(row.parentNode.children, row) : -1;
  }
  function seekLocal(t) {
    if (window.VIEWER && window.VIEWER.seek) { window.VIEWER.seek(t); }
    if (window.VIEWER && window.VIEWER.resumeFollowing) { window.VIEWER.resumeFollowing(t); }
  }
  if (box) {
    window.RecordingClock = {
      now: function () { return onClock && player ? start + player.currentTime : null; },
      seek: function (timeOfDay) { if (onClock) { seekLocal(timeOfDay - start); } },
      play: function () { if (player && player.paused) { player.play(); } },
      pause: function () { if (player && !player.paused) { player.pause(); } },
      playing: function () { return !!(player && !player.paused); },
      date: function () { return box.dataset.clockDate || ""; },
      lines: function () {
        return segments().map(function (one, i) { return { index: i, t: one.start, who: one.speaker || "", text: one.english || one.text || "" }; });
      },
      lineIndex: hereIndex,
      seekLocal: seekLocal
    };
  }

  // 2. The switch, and the Now line on the map ----------------------------------------
  var MODES = ["picture", "map", "both"];
  var sw = document.getElementById("stage-switch");
  function setMode(mode, keep) {
    if (!stage || MODES.indexOf(mode) < 0) { return; }
    stage.dataset.mode = mode;
    if (sw) { Array.prototype.forEach.call(sw.querySelectorAll("[data-mode]"), function (b) { b.classList.toggle("on", b.dataset.mode === mode); }); }
    if (!keep) { try { window.localStorage.setItem("stage-mode", mode); } catch (ignored) { /* this page only */ } }
    // The map and the picture take their new room.
    window.setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 60);
  }
  if (box && stage) {
    var remembered = null;
    try { remembered = window.localStorage.getItem("stage-mode"); } catch (ignored) { remembered = null; }
    setMode(MODES.indexOf(remembered) >= 0 ? remembered : "both", true);
    if (sw) {
      sw.addEventListener("click", function (event) {
        var b = event.target.closest("[data-mode]");
        if (b) { setMode(b.dataset.mode); }
      });
    }
  }
  var cap = { clock: document.getElementById("map-now-clock"), words: document.getElementById("map-now-words") };
  var lastCaption = "";
  function drawCaption() {
    if (!cap.clock) { return; }
    var at = player ? player.currentTime : 0;
    var who = document.getElementById("now-who"), text = document.getElementById("now-text");
    var whoWords = who ? who.textContent.trim() : "", textWords = text ? text.textContent.trim() : "";
    var key = Math.round(at) + "|" + whoWords + "|" + textWords;
    if (key === lastCaption) { return; }
    lastCaption = key;
    cap.clock.textContent = elapsed(at) + (onClock ? " · " + hms(start + at) : "");
    cap.words.innerHTML = textWords ? (whoWords ? "<span class='who' style='color: " + (who.style.color || "inherit") + "'>" + esc(whoWords) + "</span> " : "") + esc(textWords) : "<span class='muted'>Nothing is playing yet.</span>";
  }
  if (cap.clock) { window.setInterval(drawCaption, 400); drawCaption(); }

  // 3. The waiting file's card: Add anyway or Remove, then the page again.
  var waiting = document.getElementById("rec-map-waiting");
  if (waiting) {
    waiting.addEventListener("click", function (event) {
      var button = event.target.closest("[data-waiting]");
      if (!button) { return; }
      var url = button.dataset.waiting === "add" ? waiting.dataset.add : waiting.dataset.remove;
      var said = document.getElementById("rec-map-waiting-said");
      Array.prototype.forEach.call(waiting.querySelectorAll("button"), function (b) { b.disabled = true; });
      if (said) { said.textContent = button.dataset.waiting === "add" ? "Adding..." : "Removing..."; }
      fetch(url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": cookie("csrftoken") } })
        .then(function (answer) { return answer.json().then(function (told) { return { ok: answer.ok, told: told }; }); })
        .then(function (got) {
          if (!got.ok) { throw new Error((got.told && got.told.error) || "That did not work."); }
          toast(button.dataset.waiting === "add" ? "The file is this camera's now; the map is on its way." : "The waiting file is off the case.");
          window.setTimeout(reloadHere, 600);
        })
        .catch(function (error) {
          Array.prototype.forEach.call(waiting.querySelectorAll("button"), function (b) { b.disabled = false; });
          if (said) { said.textContent = error.message || "That did not work."; }
        });
    });
  }

  // The shape watcher.
  if (script && script.dataset.shapeUrl) {
    var shownShape = script.dataset.shape || "";
    window.setInterval(function () {
      if (window.UI && window.UI.pollingAllowed && !window.UI.pollingAllowed()) { return; }
      fetch(script.dataset.shapeUrl, { credentials: "same-origin" })
        .then(function (answer) { return answer.ok ? answer.json() : null; })
        .then(function (told) {
          if (!told || typeof told.shape !== "string" || told.shape === shownShape) { return; }
          shownShape = told.shape;
          toast(told.shape ? "A path file for this camera landed; the page loads the map." : "This camera's map went; the page loads again.");
          window.setTimeout(reloadHere, 1200);
        })
        .catch(function () { /* the next look will find it */ });
    }, 30000);
  }
})();

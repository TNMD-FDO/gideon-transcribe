// The Map tab on the recording page (Phase 13 chapter 2, release 3, v1.223.0;
// the drawing phase-13-recording-page.html, figures 6 and 9).
//
// Three things, all beside the case's map script (map.js), which draws the
// map itself in its recording mode:
//
// 1. window.RecordingClock: the page's player as the map's clock, in
//    seconds of the day on the case's clock, with the transcript's lines
//    (for the pips) and the line being spoken; and a press on a pip or a
//    row seeking the player and following again.
// 2. The Said here list beside the map (the line being spoken in the
//    middle, three before and three after, each a press) and the Now
//    caption under it; a dashed ring where this camera had no fix.
// 3. The shape watcher: now and then the page asks whether the Map tab's
//    shape changed (a path file landed, a waiting file was added) and, if
//    it did, says so and loads itself again at the same moment and tab.
//    The waiting file's card posts Add anyway or Remove and does the same.

(function () {
  "use strict";

  var script = document.getElementById("recording-map-script");
  var panel = document.getElementById("rec-map-panel");
  var player = document.getElementById("player");

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function cookie(name) { var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  function hms(seconds) { seconds = Math.round(seconds); seconds = ((seconds % 86400) + 86400) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function elapsed(seconds) { seconds = Math.max(0, Math.round(seconds || 0)); var m = Math.floor(seconds / 60), s = seconds % 60; return m + ":" + (s < 10 ? "0" : "") + s; }
  function toast(words, bad) { if (window.UI && window.UI.toast) { window.UI.toast(words, bad ? { problem: true } : undefined); } }
  function segments() { return window.VIEWER && window.VIEWER.segments ? window.VIEWER.segments() : []; }
  function currentPanel() { var on = document.querySelector(".tabbar .tab.on"); return on ? on.dataset.panel : "transcript"; }
  function reloadHere(tab) {
    var at = player ? player.currentTime : 0;
    window.location.replace(window.location.pathname + "?t=" + at.toFixed(1) + "&panel=" + encodeURIComponent(tab || currentPanel()));
  }

  // 1. The clock -------------------------------------------------------------------
  var start = panel ? parseFloat(panel.dataset.clockStart) : NaN;
  var onClock = !isNaN(start);
  function hereIndex() {
    var row = document.querySelector("#transcript .seg.here");
    return row ? Array.prototype.indexOf.call(row.parentNode.children, row) : -1;
  }
  function seekLocal(t) {
    if (window.VIEWER && window.VIEWER.seek) { window.VIEWER.seek(t); }
    if (window.VIEWER && window.VIEWER.resumeFollowing) { window.VIEWER.resumeFollowing(t); }
  }
  if (panel) {
    window.RecordingClock = {
      now: function () { return onClock && player ? start + player.currentTime : null; },
      seek: function (timeOfDay) { if (onClock) { seekLocal(timeOfDay - start); } },
      play: function () { if (player && player.paused) { player.play(); } },
      pause: function () { if (player && !player.paused) { player.pause(); } },
      playing: function () { return !!(player && !player.paused); },
      date: function () { return panel.dataset.clockDate || ""; },
      lines: function () {
        return segments().map(function (one, i) { return { index: i, t: one.start, who: one.speaker || "", text: one.english || one.text || "" }; });
      },
      lineIndex: hereIndex,
      seekLocal: seekLocal
    };
  }

  // 2. Said here, and the caption ---------------------------------------------------
  var list = document.getElementById("said-list");
  var cap = { clock: document.getElementById("rec-map-cap-clock"), words: document.getElementById("rec-map-cap-words") };
  var drawn = { index: null, count: 0, fixes: "" };
  var AROUND = 3;

  function fixKey(rows) {
    if (!window.CaseMap || !window.CaseMap.ready || !window.CaseMap.ready()) { return "?"; }
    return rows.map(function (one) { var has = window.CaseMap.hasFix(one.start); return has === null ? "-" : (has ? "y" : "n"); }).join("");
  }
  function drawSaid() {
    if (!list || panel.hidden) { return; }
    var all = segments();
    if (!all.length) { list.innerHTML = "<li class='muted small' style='padding: 8px'>No lines yet.</li>"; return; }
    var here = hereIndex();
    var middle = here >= 0 ? here : 0;
    var from = Math.max(0, middle - AROUND), to = Math.min(all.length - 1, middle + AROUND);
    var rows = all.slice(from, to + 1);
    var key = fixKey(rows);
    if (drawn.index === here && drawn.count === all.length && drawn.fixes === key && list.children.length) { return; }
    drawn.index = here; drawn.count = all.length; drawn.fixes = key;
    var html = "";
    rows.forEach(function (one, k) {
      var i = from + k;
      var has = key[k] === "y" ? true : (key[k] === "n" ? false : null);
      html += "<li class='said-row" + (i === here ? " here" : "") + (has === false ? " nofix" : "") + "'>" +
        "<button type='button' data-i='" + i + "' data-t='" + one.start + "' title='Play from this line'>" +
        "<i class='pip' aria-hidden='true'></i>" +
        "<span class='who'>" + esc(one.speaker || "") + (one.speaker ? " · " : "") + elapsed(one.start) + "</span>" +
        "<span class='w'>" + esc(one.english || one.text || "") + (has === false ? " <span class='muted'>· no fix here</span>" : "") + "</span>" +
        "</button></li>";
    });
    list.innerHTML = html;
    var hereRow = list.querySelector(".said-row.here");
    if (hereRow && hereRow.scrollIntoView) { hereRow.scrollIntoView({ block: "center" }); }
  }
  function drawCaption() {
    if (!cap.clock || panel.hidden) { return; }
    var at = player ? player.currentTime : 0;
    cap.clock.textContent = elapsed(at) + (onClock ? " · " + hms(start + at) : "");
    var who = document.getElementById("now-who"), text = document.getElementById("now-text");
    var whoWords = who ? who.textContent.trim() : "", textWords = text ? text.textContent.trim() : "";
    cap.words.innerHTML = textWords ? (whoWords ? "<span class='who' style='color: " + (who.style.color || "inherit") + "'>" + esc(whoWords) + "</span> " : "") + esc(textWords) : "<span class='muted'>Nothing is playing yet.</span>";
  }
  if (list) {
    list.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-t]");
      if (button) { seekLocal(parseFloat(button.dataset.t)); }
    });
    var whole = document.getElementById("said-whole");
    if (whole) { whole.addEventListener("click", function () { if (window.VIEWER && window.VIEWER.openTab) { window.VIEWER.openTab("transcript"); } }); }
    window.setInterval(function () { drawSaid(); drawCaption(); }, 400);
  }

  // The waiting file's card: Add anyway or Remove, then the page again.
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
          window.setTimeout(function () { reloadHere("map"); }, 600);
        })
        .catch(function (error) {
          Array.prototype.forEach.call(waiting.querySelectorAll("button"), function (b) { b.disabled = false; });
          if (said) { said.textContent = error.message || "That did not work."; }
        });
    });
  }

  // 3. The shape watcher ------------------------------------------------------------
  if (script && script.dataset.shapeUrl) {
    var shownShape = script.dataset.shape || "";
    var looked = 0;
    window.setInterval(function () {
      if (window.UI && window.UI.pollingAllowed && !window.UI.pollingAllowed()) { return; }
      looked += 1;
      fetch(script.dataset.shapeUrl, { credentials: "same-origin" })
        .then(function (answer) { return answer.ok ? answer.json() : null; })
        .then(function (told) {
          if (!told || typeof told.shape !== "string" || told.shape === shownShape) { return; }
          shownShape = told.shape;
          toast(told.shape ? "A path file for this camera landed; the page loads the map." : "This camera's map went; the page loads again.");
          window.setTimeout(function () { reloadHere(told.shape ? "map" : "transcript"); }, 1200);
        })
        .catch(function () { /* the next look will find it */ });
    }, 30000);
  }
})();

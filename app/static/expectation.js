// The time expectation under a written output (v1.95.0).
//
// The server works out, once, at the ask, how long this output usually takes
// on the office's own engine and keeps it on the run with when it was asked
// for and when the worker started. The page draws one line from that: the
// step the run is on, the figure, and how long it has been, ticking here
// once a second without asking the server; past the figure a second sentence
// says the run is working normally and why it can take longer. Loaded before
// the scripts that draw a memo, proposals, a comparison, a summary, a
// dictation's row or a chat, so window.Expectation is always there.

(function () {
  "use strict";

  function escape(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function capital(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
  }

  function clock(seconds) {
    var m = Math.floor(seconds / 60), s = seconds % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function secondsSince(iso) {
    var at = iso ? Date.parse(iso) : NaN;
    if (isNaN(at)) { return 0; }
    return Math.max(0, Math.round((Date.now() - at) / 1000));
  }

  function isOver(E) {
    if (!E || !E.started_at || !E.expected_seconds) { return false; }
    return secondsSince(E.started_at) > E.expected_seconds;
  }

  // The line: "<step>. Usually about 4 minutes · 1:12 so far" and, under it,
  // either the leave sentence or, past the figure, the reassurance. `state`
  // is queued or running; queued adds "once it starts" to the figure.
  function html(options) {
    var E = options.expectation || {};
    var step = options.step || (options.state === "queued" ? "Waiting for the engine" : "");
    var cls = options.inline ? "expect inline muted small" : "expect";
    if (!E.words) {
      return "<div class='" + cls + "'><p class='expect-line'>" + escape(step) + (step ? "..." : "") + "</p></div>";
    }
    var figure = capital(E.words) + (options.state === "queued" ? " once it starts" : "");
    var over = isOver(E);
    var second = over ? E.over_words : (options.leaveable === false ? "" : E.leave_words || "");
    return "<div class='" + cls + "' data-started='" + escape(E.started_at || "") + "' data-expected='" + (E.expected_seconds || 0) + "'" +
      " data-over='" + escape(E.over_words || "") + "' data-leave='" + escape(options.leaveable === false ? "" : E.leave_words || "") + "'>" +
      "<p class='expect-line'>" + escape(step) + (step ? ". " : "") +
      "<span class='expect-figure'>" + escape(figure) + "</span> &middot; " +
      "<span class='expect-elapsed' data-since='" + escape(E.asked_at || "") + "'>" + clock(secondsSince(E.asked_at)) + "</span> so far</p>" +
      "<p class='expect-second" + (over ? " over" : "") + "'" + (second ? "" : " hidden") + ">" + escape(second) + "</p>" +
      "</div>";
  }

  // Once a second: the count advances in place, and the second sentence
  // switches to the reassurance when the run passes its figure. Nothing is
  // redrawn, so a pulse elsewhere on the line never restarts.
  function tick() {
    var counters = document.querySelectorAll(".expect-elapsed[data-since]");
    for (var i = 0; i < counters.length; i += 1) {
      counters[i].textContent = clock(secondsSince(counters[i].dataset.since));
    }
    var boxes = document.querySelectorAll(".expect[data-started]");
    for (var j = 0; j < boxes.length; j += 1) {
      var box = boxes[j];
      var second = box.querySelector(".expect-second");
      if (!second || second.classList.contains("over")) { continue; }
      var over = isOver({ started_at: box.dataset.started, expected_seconds: Number(box.dataset.expected) });
      if (over && box.dataset.over) {
        second.textContent = box.dataset.over;
        second.classList.add("over");
        second.hidden = false;
      }
    }
  }

  window.setInterval(tick, 1000);

  window.Expectation = { html: html, tick: tick, clock: clock, secondsSince: secondsSince, isOver: isOver };
})();

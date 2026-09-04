// Marking a span and saving it as a clip, in the bottom sheet.
//
// Five ways to mark one, because a corrector's hands are on the keyboard and
// an occasional user's are on the mouse: I and O at the playhead, typing the
// times, S to snap to the current segment, "+ clip" on any segment, and a
// drag on the timeline. Any of them opens the sheet at Clips.

(function () {
  "use strict";

  var from = document.getElementById("clip-from");
  var to = document.getElementById("clip-to");
  var form = document.getElementById("clip-form");
  var list = document.getElementById("clip-list");
  var said = document.getElementById("clip-range");
  if (!from || !form) { return; }

  var recording = window.VIEWER.recording;
  var longest = 30 * 60;
  var stopAt = null;
  var waiting = null;

  var clock = window.VIEWER.clock;
  var cookie = window.VIEWER.cookie;

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function seconds(typed) {
    // "1:02:03", "2:03", and "123" all mean something, and anything else
    // means nothing rather than something wrong.
    var parts = String(typed || "").trim().split(":").map(Number);
    if (!parts.length || parts.some(isNaN) || String(typed || "").trim() === "") {
      return null;
    }
    return parts.reduce(function (total, part) { return total * 60 + part; }, 0);
  }

  function range() {
    var start = seconds(from.value);
    var end = seconds(to.value);
    if (start === null || end === null || end <= start) { return null; }
    return { from: start, to: end };
  }

  function say() {
    var span = range();
    if (!span) {
      said.textContent = "No range yet";
      window.VIEWER.showRange(null, null);
      window.VIEWER.tintRange();
      return;
    }
    var inside = window.VIEWER.segments().filter(function (one) {
      return one.start < span.to && one.end > span.from;
    }).length;
    said.textContent = clock(span.to - span.from) + " long" +
      (window.VIEWER.hasTranscript
        ? ", " + inside + (inside === 1 ? " segment" : " segments")
        : "");
    window.VIEWER.showRange(span.from, span.to);
    window.VIEWER.tintRange();
  }

  // What the viewer may ask this one for.
  window.CLIPS = {
    range: range,
    load: load,
    mark: function (start, end) {
      from.value = clock(start);
      to.value = clock(end);
      window.VIEWER.openSheet("clips");
      say();
    },
    addSegment: function (segment) {
      // "+ clip" extends the range to include that segment rather than
      // replacing it, so a person can build a range segment by segment.
      var span = range();
      var start = span ? Math.min(span.from, segment.start) : segment.start;
      var end = span ? Math.max(span.to, segment.end) : segment.end;
      window.CLIPS.mark(start, end);
    }
  };

  from.addEventListener("input", say);
  to.addEventListener("input", say);

  document.getElementById("clip-clear").addEventListener("click", function () {
    from.value = "";
    to.value = "";
    say();
  });

  var newClip = document.getElementById("new-clip");
  if (newClip) {
    newClip.addEventListener("click", function () {
      window.VIEWER.openSheet("clips");
      document.getElementById("clip-title").focus();
    });
  }

  // Marking -------------------------------------------------------------------

  function preview() {
    var span = range();
    if (!span) { return; }
    window.VIEWER.seek(span.from);
    stopAt = span.to;
    window.VIEWER.play();
  }

  document.getElementById("clip-preview").addEventListener("click", preview);

  var player = document.getElementById("player");
  if (player) {
    player.addEventListener("timeupdate", function () {
      if (stopAt !== null && player.currentTime >= stopAt) {
        window.VIEWER.pause();
        stopAt = null;
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }

    if (event.key === "i" || event.key === "I") {
      from.value = clock(window.VIEWER.at());
      window.VIEWER.openSheet("clips");
      say();
    } else if (event.key === "o" || event.key === "O") {
      to.value = clock(window.VIEWER.at());
      window.VIEWER.openSheet("clips");
      say();
    } else if (event.key === "s" || event.key === "S") {
      var segment = window.VIEWER.currentSegment();
      if (!segment) { return; }
      // With a start marked and no end, Snap extends the range to this
      // segment's end rather than starting over.
      if (seconds(from.value) !== null && seconds(to.value) === null) {
        to.value = clock(segment.end);
      } else {
        from.value = clock(segment.start);
        to.value = clock(segment.end);
      }
      window.VIEWER.openSheet("clips");
      say();
    } else if (event.key === "p" || event.key === "P") {
      preview();
    }
  });

  // Saving --------------------------------------------------------------------

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var problem = document.getElementById("clip-problem");
    var span = range();

    if (!span) {
      problem.textContent =
        "Mark a start and an end first, with I and O, by typing them, or by " +
        "dragging on the timeline.";
      problem.hidden = false;
      return;
    }
    if (span.to - span.from > longest) {
      problem.textContent = "That is longer than a clip may be (" +
        Math.round(longest / 60) + " minutes).";
      problem.hidden = false;
      return;
    }

    var burn = document.getElementById("clip-burn");
    send("/recording/" + recording + "/clips/save", {
      start: span.from,
      end: span.to,
      title: document.getElementById("clip-title").value,
      note: document.getElementById("clip-note").value,
      include_excerpt: document.getElementById("clip-excerpt").checked,
      burn_captions: burn ? burn.checked : false
    }).then(function (answer) {
      if (answer.error) {
        problem.textContent = answer.error;
        problem.hidden = false;
        return;
      }
      problem.hidden = true;
      document.getElementById("clip-note").value = "";
      load();
    });
  });

  function send(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (answer) { return answer.json(); });
  }

  // The list ------------------------------------------------------------------

  function draw(clips) {
    list.innerHTML = clips.map(function (one) {
      var doing = one.state === "rendering";
      var tools = "";
      if (!doing && one.state === "ready") {
        tools = "<a href='/clip/" + one.id + "/download'>Download</a>" +
          " &middot; <button type='button' class='plain clip-play'>Play</button>" +
          (one.stale
            ? " &middot; <button type='button' class='plain clip-rerender'>Re-render</button>"
            : "") +
          " &middot; <button type='button' class='plain clip-adjust'>Adjust</button>" +
          " &middot; <button type='button' class='plain clip-rename'>Rename</button>" +
          " &middot; <button type='button' class='plain clip-delete'>Delete</button>";
      } else if (!doing) {
        tools = "<button type='button' class='plain clip-rerender'>Retry</button>" +
          " &middot; <button type='button' class='plain clip-delete'>Delete</button>";
      }
      return "<li class='card' data-clip='" + one.id +
        "' data-start='" + one.start + "' data-end='" + one.end +
        "' data-title='" + escape(one.title) + "'>" +
        "<strong>" + escape(one.title) + "</strong>" +
        "<p class='quiet'>" + clock(one.start) + " to " + clock(one.end) +
        " &middot; " + clock(one.seconds) + " long &middot; " +
        escape(one.shown_state) +
        (one.size ? " &middot; " + Math.round(one.size / 1024 / 1024 * 10) / 10 + " MB" : "") +
        " &middot; " + escape(one.downloaded) + "</p>" +
        (tools ? "<p>" + tools + "</p>" : "") +
        "</li>";
    }).join("");

    window.clearTimeout(waiting);
    if (clips.some(function (one) { return one.state === "rendering"; })) {
      waiting = window.setTimeout(load, 5000);
    }
  }

  list.addEventListener("click", function (event) {
    var card = event.target.closest("[data-clip]");
    if (!card) { return; }
    var id = card.dataset.clip;

    if (event.target.closest(".clip-play")) {
      window.VIEWER.seek(parseFloat(card.dataset.start));
      window.VIEWER.play();
    } else if (event.target.closest(".clip-rerender")) {
      send("/clip/" + id + "/rerender").then(load);
    } else if (event.target.closest(".clip-adjust")) {
      // Adjust puts the clip's span back in the tool; saving the change
      // re-renders it.
      from.value = clock(parseFloat(card.dataset.start));
      to.value = clock(parseFloat(card.dataset.end));
      say();
      var wanted = window.prompt(
        "Adjust this clip. Change the times in the tool above, then press OK " +
        "to save them.",
        "save"
      );
      if (wanted === null) { return; }
      var span = range();
      if (!span) { return; }
      fetch("/clip/" + id, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken")
        },
        body: JSON.stringify({ start: span.from, end: span.to })
      }).then(load);
    } else if (event.target.closest(".clip-rename")) {
      var name = window.prompt("Rename this clip to:", card.dataset.title);
      if (!name) { return; }
      fetch("/clip/" + id, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken")
        },
        body: JSON.stringify({ title: name })
      }).then(load);
    } else if (event.target.closest(".clip-delete")) {
      if (!window.confirm("Delete this clip? The file goes with it.")) { return; }
      send("/clip/" + id + "/delete").then(load);
    }
  });

  function load() {
    fetch("/recording/" + recording + "/clips")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        if (!body.available) { return; }
        longest = body.longest_seconds || longest;
        var title = document.getElementById("clip-title");
        if (!title.value || title.dataset.auto === "yes") {
          title.value = body.next_title;
          title.dataset.auto = "yes";
        }
        draw(body.clips || []);
      });
  }

  document.getElementById("clip-title").addEventListener("input", function () {
    this.dataset.auto = "no";
  });

  load();
  say();
})();

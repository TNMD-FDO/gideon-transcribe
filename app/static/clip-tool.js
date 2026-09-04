// Marking a span and saving it as a clip.
//
// Two ways in: I and O while the recording plays, and the two time boxes. A
// preview plays the span and stops at its end, so nobody saves a clip that
// begins half a sentence late.

(function () {
  "use strict";

  var player = document.getElementById("player");
  var from = document.getElementById("clip-from");
  var to = document.getElementById("clip-to");
  var form = document.getElementById("clip-form");
  var list = document.getElementById("clip-list");
  if (!from || !form) { return; }

  var recording = window.VIEWER.recording;
  var longest = 30 * 60;
  var stopAt = null;

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

  function seconds(typed) {
    // "1:02:03", "2:03", and "123" all mean something, and anything else
    // means nothing rather than something wrong.
    var parts = String(typed || "").trim().split(":").map(Number);
    if (!parts.length || parts.some(isNaN)) { return null; }
    return parts.reduce(function (total, part) { return total * 60 + part; }, 0);
  }

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function send(url, body, method) {
    return fetch(url, {
      method: method || "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (answer) { return answer.json(); });
  }

  // Marking -------------------------------------------------------------------

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }
    if (!player) { return; }
    if (event.key === "i" || event.key === "I") {
      from.value = clock(player.currentTime);
    } else if (event.key === "o" || event.key === "O") {
      to.value = clock(player.currentTime);
    }
  });

  document.getElementById("clip-preview").addEventListener("click", function () {
    var start = seconds(from.value);
    var end = seconds(to.value);
    if (start === null || end === null || end <= start || !player) { return; }
    player.currentTime = start;
    stopAt = end;
    player.play();
  });

  if (player) {
    player.addEventListener("timeupdate", function () {
      if (stopAt !== null && player.currentTime >= stopAt) {
        player.pause();
        stopAt = null;
      }
    });
  }

  // Saving --------------------------------------------------------------------

  document.getElementById("clip-new").addEventListener("click", function () {
    form.hidden = false;
    document.getElementById("clip-problem").hidden = true;
    if (!document.getElementById("clip-title").value) {
      load();
    }
    document.getElementById("clip-title").focus();
  });

  document.getElementById("clip-cancel").addEventListener("click", function () {
    form.hidden = true;
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var problem = document.getElementById("clip-problem");
    var start = seconds(from.value);
    var end = seconds(to.value);

    if (start === null || end === null || end <= start) {
      problem.textContent = "Mark a start and an end first, with I and O or by typing them.";
      problem.hidden = false;
      return;
    }
    if (end - start > longest) {
      problem.textContent = "That is longer than a clip may be (" +
        Math.round(longest / 60) + " minutes).";
      problem.hidden = false;
      return;
    }

    send("/recording/" + recording + "/clips/save", {
      start: start,
      end: end,
      title: document.getElementById("clip-title").value,
      note: document.getElementById("clip-note").value,
      include_excerpt: document.getElementById("clip-excerpt").checked,
      burn_captions: document.getElementById("clip-burn").checked
    }).then(function (answer) {
      if (answer.error) {
        problem.textContent = answer.error;
        problem.hidden = false;
        return;
      }
      form.hidden = true;
      document.getElementById("clip-note").value = "";
      load();
    });
  });

  // The sheet -----------------------------------------------------------------

  function draw(clips) {
    list.innerHTML = clips.map(function (one) {
      var doing = one.state === "rendering";
      return "<li class='card' data-clip='" + one.id + "'>" +
        "<strong>" + escape(one.title) + "</strong>" +
        "<p class='quiet'>" + clock(one.start) + " to " + clock(one.end) +
        " &middot; " + escape(one.shown_state) + "</p>" +
        (doing ? "" :
          (one.state === "ready"
            ? "<p><a href='/clip/" + one.id + "/download'>Download</a>" +
              (one.stale
                ? " &middot; <button type='button' class='plain clip-rerender'>Re-render</button>"
                : "") +
              " &middot; <button type='button' class='plain clip-delete'>Delete</button></p>"
            : "<p><button type='button' class='plain clip-rerender'>Retry</button>" +
              " &middot; <button type='button' class='plain clip-delete'>Delete</button></p>")) +
        "</li>";
    }).join("");

    if (clips.some(function (one) { return one.state === "rendering"; })) {
      window.setTimeout(load, 5000);
    }
  }

  list.addEventListener("click", function (event) {
    var card = event.target.closest("[data-clip]");
    if (!card) { return; }
    if (event.target.closest(".clip-rerender")) {
      send("/clip/" + card.dataset.clip + "/rerender").then(load);
    } else if (event.target.closest(".clip-delete")) {
      if (!window.confirm("Delete this clip? The file goes with it.")) { return; }
      send("/clip/" + card.dataset.clip + "/delete").then(load);
    }
  });

  function load() {
    fetch("/recording/" + recording + "/clips")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        if (!body.available) { return; }
        longest = body.longest_seconds || longest;
        document.getElementById("clip-title").value = body.next_title;
        draw(body.clips || []);
      });
  }

  load();
})();

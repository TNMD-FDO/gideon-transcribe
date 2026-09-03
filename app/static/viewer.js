// The viewer: read a transcript, follow the audio through it, and correct it.
//
// The transcript is the page. Everything else is there to serve reading it, so
// the transcript is the only thing that scrolls in Follow mode, and every
// control is reachable from the keyboard without leaving it.

(function () {
  "use strict";

  var player = document.getElementById("player");
  var column = document.getElementById("transcript");
  if (!column) { return; }

  var segments = [];
  var wordTiming = false;
  var here = -1;
  var colours = {};

  var stored = document.getElementById("speaker-colours");
  if (stored) {
    JSON.parse(stored.textContent).forEach(function (one) {
      colours[one.name] = one.colour;
    });
  }

  function clock(seconds) {
    var whole = Math.floor(seconds || 0);
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

  // Drawing the transcript -----------------------------------------------------

  function draw() {
    column.innerHTML = "";
    segments.forEach(function (segment, index) {
      var row = document.createElement("li");
      row.className = "segment";
      row.dataset.index = index;
      if (segment.speaker) { row.style.setProperty("--speaker", colours[segment.speaker] || ""); }

      var at = document.createElement("div");
      at.className = "at";
      at.textContent = clock(segment.start);

      var body = document.createElement("div");
      if (segment.speaker) {
        var who = document.createElement("div");
        who.className = "who";
        who.textContent = segment.speaker + (segment.corrected ? " ✎" : "");
        body.appendChild(who);
      } else if (segment.corrected) {
        var mark = document.createElement("div");
        mark.className = "who";
        mark.textContent = "✎";
        body.appendChild(mark);
      }

      var said = document.createElement("p");
      said.className = "said";
      said.innerHTML = wordsOf(segment);
      body.appendChild(said);

      row.appendChild(at);
      row.appendChild(body);
      column.appendChild(row);
    });
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

  // Following ------------------------------------------------------------------

  function at(time) {
    // The last segment that has started. A binary search, because a
    // two-hour recording is thousands of segments and this runs on every
    // timeupdate.
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

  function follow() {
    if (!player) { return; }
    var time = player.currentTime;
    var index = at(time);
    if (index !== here) {
      var was = column.querySelector(".segment.here");
      if (was) { was.classList.remove("here"); }
      var now = column.children[index];
      if (now) {
        now.classList.add("here");
        if (document.getElementById("follow").checked) {
          now.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      here = index;
    }

    var row = column.children[here];
    if (row && wordTiming) {
      var words = row.querySelectorAll(".word");
      Array.prototype.forEach.call(words, function (word) {
        var start = parseFloat(word.dataset.start);
        var end = parseFloat(word.dataset.end);
        word.classList.toggle("now", !isNaN(start) && time >= start && time <= end);
      });
    }

    document.getElementById("clock").textContent =
      clock(time) + " / " + clock(player.duration);
  }

  // The transport --------------------------------------------------------------

  if (player) {
    player.addEventListener("timeupdate", follow);

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
          player.currentTime = Math.max(
            0, player.currentTime + parseFloat(button.dataset.seek)
          );
        });
      }
    );

    document.getElementById("speed").addEventListener("change", function () {
      player.playbackRate = parseFloat(this.value);
    });

    // Boost exists because browsers cap volume at 100% and quiet recordings
    // are common: a jail call at arm's length from the handset is not made
    // louder by turning the speakers up if the file itself is quiet.
    var boosted = null;
    var gain = null;
    document.getElementById("boost").addEventListener("input", function () {
      var per = parseInt(this.value, 10);
      document.getElementById("boost-figure").textContent = per + "%";
      if (per > 100 && !boosted) {
        boosted = new (window.AudioContext || window.webkitAudioContext)();
        gain = boosted.createGain();
        boosted.createMediaElementSource(player).connect(gain);
        gain.connect(boosted.destination);
      }
      if (gain) { gain.gain.value = per / 100; }
    });
  }

  column.addEventListener("click", function (event) {
    var row = event.target.closest(".segment");
    if (!row || row.querySelector("textarea")) { return; }
    var segment = segments[parseInt(row.dataset.index, 10)];
    if (player && segment) { player.currentTime = segment.start; }
  });

  column.addEventListener("dblclick", function (event) {
    var row = event.target.closest(".segment");
    if (row) { edit(parseInt(row.dataset.index, 10)); }
  });

  // Correcting -----------------------------------------------------------------

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function edit(index) {
    var segment = segments[index];
    var row = column.children[index];
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
        });
      }
    });
  }

  // Speakers -------------------------------------------------------------------

  var chips = document.getElementById("speakers");
  if (chips) {
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest(".chip");
      if (!chip) { return; }
      var now = window.prompt("Rename " + chip.dataset.name + " to:", chip.dataset.name);
      if (!now || now === chip.dataset.name) { return; }
      rename(chip.dataset.name, now);
    });

    var dragging = null;
    chips.addEventListener("dragstart", function (event) {
      dragging = event.target.dataset.name;
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
      if (!dragging || dragging === onto.dataset.name) { return; }
      if (!window.confirm(
        "Merge " + dragging + " into " + onto.dataset.name +
        "? Every segment of " + dragging + " becomes " + onto.dataset.name + "."
      )) { return; }
      rename(dragging, onto.dataset.name);
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

  // Searching ------------------------------------------------------------------

  var search = document.getElementById("search");
  search.addEventListener("input", function () {
    var wanted = search.value.trim().toLowerCase();
    var found = 0;
    Array.prototype.forEach.call(column.children, function (row, index) {
      var text = segments[index].text.toLowerCase();
      var hit = wanted && text.indexOf(wanted) !== -1;
      row.hidden = wanted !== "" && !hit;
      if (hit) { found += 1; }
    });
    document.getElementById("matches").textContent =
      wanted === "" ? "" : found + (found === 1 ? " match" : " matches");
  });

  // The keyboard ---------------------------------------------------------------

  document.addEventListener("keydown", function (event) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
    if (typing) { return; }

    var speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5];
    var speed = document.getElementById("speed");

    if (event.key === "/") { event.preventDefault(); search.focus(); return; }
    if (!player) { return; }

    if (event.key === " ") {
      event.preventDefault();
      if (player.paused) { player.play(); } else { player.pause(); }
    } else if (event.key === "b" || event.key === "B") {
      // The foot-pedal substitute: back three seconds and keep playing.
      player.currentTime = Math.max(0, player.currentTime - 3);
      player.play();
    } else if (event.key === "j" || event.key === "J") {
      player.currentTime = Math.max(0, player.currentTime - 5);
    } else if (event.key === "k" || event.key === "K") {
      player.currentTime = player.currentTime + 5;
    } else if (event.key === "[" || event.key === "]") {
      var step = speeds.indexOf(parseFloat(speed.value)) + (event.key === "]" ? 1 : -1);
      step = Math.max(0, Math.min(speeds.length - 1, step));
      speed.value = String(speeds[step]);
      player.playbackRate = speeds[step];
    } else if (event.key === "0") {
      speed.value = "1";
      player.playbackRate = 1;
    } else if (event.key === "f" || event.key === "F") {
      var box = document.getElementById("follow");
      box.checked = !box.checked;
    } else if (event.key === "e" || event.key === "E") {
      if (here >= 0) { event.preventDefault(); edit(here); }
    }
  });

  // Loading --------------------------------------------------------------------

  fetch("/recording/" + window.VIEWER.recording + "/segments")
    .then(function (answer) { return answer.json(); })
    .then(function (body) {
      segments = body.segments || [];
      wordTiming = body.word_timestamps;
      draw();
      if (player) { follow(); }
    });
})();

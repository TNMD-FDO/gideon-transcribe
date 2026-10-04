// The Preview (v1.98.0): a moment of a recording played over the page it
// was cited on, so a person reading a chat's answer or a search's hits never
// leaves them. A card at the bottom right, one at a time: the picture from
// ten seconds before the moment, the transcript moving under it with what
// the camera showed in its place among the lines, a note on any line, Open
// the recording and All cameras. The note is the line's own note, written
// by the recording page's own action, so on a synced camera it is an event
// on the chronology as it always was. Where nothing is being said at the
// moment, the note is kept at the moment itself (v1.99.0) and shown between
// the lines, and a silence of half a minute or more is said among them.
// Drag it by its head; Close or Escape puts it away. Nothing of what was
// looked at is logged.
//
// From v1.119.0 (Phase 9 chapter 4) the same card mounts into a page as
// well as floating: the Notes page's left side is one instance, and its
// pop-out of the whole call another (every line, not the minutes around the
// moment). Preview.mount(host, options) makes one; window.Preview is the
// floating instance as it always was.

(function () {
  "use strict";

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function cookie(name) {
    var found = document.cookie.split("; ").filter(function (one) { return one.indexOf(name + "=") === 0; })[0];
    return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
  }

  function make(options) {
    options = options || {};
    var host = options.host || null;   // an element to mount into, or null to float
    var card = null;       // the card on the page, or null
    var told = null;       // what the server answered for it
    var asked = null;      // { recording, seconds, from }
    var noting = null;     // what the note box is open on: a line's id, or { moment: id or null }
    var asking = 0;        // the latest ask, so a slow answer never overwrites a later one
    var lastFetch = 0;

    function media() { return card ? card.querySelector("video, audio") : null; }

    function close() {
      if (!card) { return; }
      var playing = media();
      if (playing) { playing.pause(); playing.removeAttribute("src"); }
      if (host) {
        card.innerHTML = "";
        card.classList.remove("preview-card", "mounted", "whole");
      } else {
        card.remove();
      }
      card = null; told = null; noting = null;
      if (asked && asked.from) { asked.from.classList.remove("previewing"); }
      asked = null;
    }

    function build() {
      card = host || document.createElement("div");
      card.className = "preview-card" + (host ? " mounted" : "") + (options.whole ? " whole" : "");
      card.setAttribute("role", host ? "region" : "dialog");
      card.setAttribute("aria-label", "Preview");
      card.innerHTML =
        "<div class='preview-head'><b class='grow' id='preview-title'></b>" +
        "<span class='mono muted' id='preview-clock'></span>" +
        (host ? "" : "<button type='button' class='tiny ghost' data-preview-act='close' aria-label='Close the preview'>Close</button>") + "</div>" +
        "<div class='preview-media'></div>" +
        "<div class='preview-lines' id='preview-lines'></div>" +
        "<div class='preview-foot'></div>" +
        "<div class='preview-note' hidden></div>";
      if (!host) { document.body.appendChild(card); }
      card.addEventListener("click", pressed);
      if (!host) { drag(card.querySelector(".preview-head")); }
    }

    // The rows under the picture: the lines and what was seen, by their times.
    function rows() {
      var all = (told.lines || []).map(function (one) { return { at: one.start, line: one }; })
        .concat((told.seen || []).map(function (one) { return { at: one.at, seen: one }; }))
        // The notes where nothing was said, and the silence the moment is in (v1.99.0).
        .concat((told.moment_notes || []).map(function (one) { return { at: one.at, kept: one }; }));
      if (told.silence) { all.push({ at: told.silence.from + 0.001, quiet: told.silence }); }
      all.sort(function (a, b) { return a.at - b.at; });
      return all;
    }

    function drawLines() {
      var box = card.querySelector(".preview-lines");
      var html = "";
      rows().forEach(function (row) {
        if (row.seen) {
          html += "<div class='preview-line seen" + (told.cited_seen === row.seen.id ? " cited" : "") + "' data-at='" + row.seen.at + "'>" +
            "<a href='#' class='t mono' data-preview-seek='" + row.seen.at + "'>" + escape(row.seen.clock) + "</a>" +
            "<span class='said'><span class='who'>Seen</span> " + escape(row.seen.text) + "</span><span></span></div>";
          return;
        }
        if (row.quiet) {
          html += "<div class='preview-line quiet' data-at='" + row.at + "'><span></span><span class='said'>" + escape(row.quiet.words) + "</span><span></span></div>";
          return;
        }
        if (row.kept) {
          html += "<div class='preview-line kept' data-kept='" + row.kept.id + "' data-at='" + row.kept.at + "'>" +
            "<a href='#' class='t mono' data-preview-seek='" + row.kept.at + "'>" + escape(row.kept.clock) + "</a>" +
            "<span class='said'><span class='who'>Note" + (row.kept.note_by ? ", " + escape(row.kept.note_by) : "") + "</span> " + escape(row.kept.note) + "</span>" +
            "<button type='button' class='tiny ghost' data-preview-kept='" + row.kept.id + "'" +
            (told.can_note ? " title='Change this note'" : " disabled title='" + escape(told.why_not) + "'") + ">edit note</button></div>";
          return;
        }
        var one = row.line;
        html += "<div class='preview-line" + (told.cited === one.id ? " cited" : "") + "' data-at='" + one.start + "' data-end='" + one.end + "' data-line='" + one.id + "'>" +
          "<a href='#' class='t mono' data-preview-seek='" + one.start + "'>" + escape(one.clock) + "</a>" +
          "<span class='said'>" + (one.speaker ? "<span class='who'>" + escape(one.speaker) + "</span> " : "") + escape(one.text) +
          (one.note ? "<span class='noted small'>Note" + (one.note_by ? ", " + escape(one.note_by) : "") + ": " + escape(one.note) + "</span>" : "") + "</span>" +
          "<button type='button' class='tiny ghost' data-preview-note='" + one.id + "'" +
          (told.can_note ? " title='A note on this line'" : " disabled title='" + escape(told.why_not) + "'") + ">" + (one.note ? "edit note" : "note") + "</button></div>";
      });
      if (!html) { html = "<p class='muted small preview-none'>No lines around this moment.</p>"; }
      box.innerHTML = html;
    }

    function lineById(id) {
      var found = null;
      (told.lines || []).some(function (one) { if (one.id === id) { found = one; return true; } return false; });
      return found;
    }

    function keptById(id) {
      var found = null;
      (told.moment_notes || []).some(function (one) { if (one.id === id) { found = one; return true; } return false; });
      return found;
    }
    // The note already kept at the moment cited, within a second of it.
    function keptAtTheMoment() {
      var found = null;
      (told.moment_notes || []).some(function (one) { if (Math.abs(one.at - told.seconds) <= 1) { found = one; return true; } return false; });
      return found;
    }

    function drawFoot() {
      var noteOn = told.note_on;
      // On the line being spoken; at the moment itself where nothing is (v1.99.0).
      card.querySelector(".preview-foot").innerHTML =
        "<button type='button' class='small primary' " + (noteOn === null ? "data-preview-moment='1'" : "data-preview-note='" + noteOn + "'") +
        (told.can_note ? "" : " disabled title='" + escape(told.why_not) + "'") + ">Note</button>" +
        (host ? "" : "<a class='btn small' href='" + escape(told.open) + "'>Open the recording</a>") +
        (told.all ? "<a class='btn small ghost' href='" + escape(told.all) + "'>All cameras</a>" : "");
    }

    // A note saved (v1.99.2): the box closes, the note is lit where it now
    // sits among the lines, and one line says so for a few seconds. The box
    // used to stay open with the words in it, and it was hard to tell that
    // anything had happened.
    var doneTimer = null;
    function saved(words, row) {
      noting = null;
      var box = card.querySelector(".preview-note");
      box.hidden = false;
      box.classList.add("done");
      box.innerHTML = "<p class='small preview-done' role='status'>" + escape(words) + "</p>";
      window.clearTimeout(doneTimer);
      doneTimer = window.setTimeout(function () {
        if (!card || noting !== null) { return; }
        var still = card.querySelector(".preview-note");
        if (still && still.classList.contains("done")) { still.hidden = true; still.innerHTML = ""; still.classList.remove("done"); }
      }, 6000);
      var lit = row ? card.querySelector(row) : null;
      if (lit) {
        var lines = card.querySelector(".preview-lines");
        lines.scrollTop = Math.max(0, lit.offsetTop - lines.offsetTop - lines.clientHeight / 3);
        lit.classList.add("just-noted");
        window.setTimeout(function () { lit.classList.remove("just-noted"); }, 2600);
      }
      if (options.onNoted) { options.onNoted(told); }
    }

    function saving() {
      var button = card.querySelector("[data-preview-act='save']");
      if (button) { button.disabled = true; button.textContent = "Saving..."; }
    }

    function drawNote(said) {
      var box = card.querySelector(".preview-note");
      window.clearTimeout(doneTimer);
      box.classList.remove("done");
      var label = "", words = "";
      if (noting !== null && typeof noting === "object") {
        var kept = noting.moment === null ? null : keptById(noting.moment);
        label = "A note at " + escape(kept ? kept.clock : told.clock) + ".";
        words = kept ? kept.note : "";
      } else {
        var one = noting === null ? null : lineById(noting);
        if (!one) { box.hidden = true; box.innerHTML = ""; return; }
        var spoken = told.cited_seen !== null && told.cited === null && one.id === told.note_on;
        label = "A note on the line at " + escape(one.clock) + (spoken ? ", the line being spoken when this was seen" : "");
        words = one.note || "";
      }
      if (said && said.words && said.keep !== undefined) { words = said.keep; }
      box.hidden = false;
      box.innerHTML =
        "<label class='small muted' for='preview-note-text'>" + label + "</label>" +
        "<textarea id='preview-note-text' maxlength='2000' rows='3'>" + escape(words) + "</textarea>" +
        "<div class='row' style='gap: 6px; align-items: center; flex-wrap: wrap'>" +
        "<button type='button' class='small primary' data-preview-act='save'>Save note</button>" +
        "<button type='button' class='small ghost' data-preview-act='cancel'>Cancel</button>" +
        "<span class='small preview-said" + (said && said.problem ? " problem" : "") + "'>" + escape(said ? said.words : "") + "</span></div>";
      if (!said) { box.querySelector("textarea").focus(); }
    }

    function draw(first) {
      card.querySelector("#preview-title").textContent = told.title;
      card.querySelector("#preview-clock").textContent = told.clock;
      if (first) {
        var holder = card.querySelector(".preview-media");
        if (!told.media) {
          holder.innerHTML = "<p class='muted small preview-none'>This recording has no copy to play yet. The lines are below.</p>";
        } else {
          var from = Math.max(0, told.seconds - 10);
          holder.innerHTML = told.is_video
            ? "<video controls autoplay playsinline preload='metadata'></video>"
            : "<audio controls autoplay preload='metadata'></audio>";
          var player = holder.firstChild;
          player.src = told.media + "#t=" + from;
          player.addEventListener("loadedmetadata", function () { try { player.currentTime = from; } catch (ignored) { /* the fragment then */ } }, { once: true });
          player.addEventListener("timeupdate", function () { follow(player.currentTime); });
        }
      }
      drawLines();
      drawFoot();
      drawNote(null);
      follow(media() && !first ? media().currentTime : told.seconds, true);
      if (options.onLoaded) { options.onLoaded(told, first); }
    }

    // The line being spoken is lit and kept in view; past the lines that were
    // read, the next ones are asked for.
    function follow(now, jump) {
      if (!card || !told) { return; }
      var lit = null;
      Array.prototype.forEach.call(card.querySelectorAll(".preview-line"), function (row) {
        var at = parseFloat(row.dataset.at);
        row.classList.remove("now");
        // A note kept at a moment is the office's, not the recording's: never lit.
        if (at <= now + 0.05 && !row.classList.contains("kept")) { lit = row; }
      });
      if (lit) {
        lit.classList.add("now");
        var box = card.querySelector(".preview-lines");
        var top = lit.offsetTop - box.offsetTop;
        if (jump || top < box.scrollTop || top + lit.offsetHeight > box.scrollTop + box.clientHeight) {
          box.scrollTop = Math.max(0, top - box.clientHeight / 3);
        }
      }
      if (options.onLit) { options.onLit(lit, now, told); }
      if (!options.whole && noting === null && (now > told.to - 10 || now < told.from) && Date.now() - lastFetch > 3000) {
        read(now, false);
      }
    }

    function url(seconds) {
      return "/recording/" + asked.recording + "/around?t=" + encodeURIComponent(seconds.toFixed(2)) + (options.whole ? "&whole=1" : "");
    }

    function read(seconds, first) {
      var mine = ++asking;
      lastFetch = Date.now();
      return fetch(url(seconds), { credentials: "same-origin" })
        .then(function (answer) { return answer.ok ? answer.json() : null; })
        .then(function (got) {
          if (!card || mine !== asking) { return; }
          if (!got) {
            if (first) { card.querySelector(".preview-lines").innerHTML = "<p class='muted small preview-none'>This recording cannot be read from here.</p>"; }
            return;
          }
          if (!first) {
            // The moment cited stays the moment cited while the lines move on.
            got.cited = told.cited; got.cited_seen = told.cited_seen; got.note_on = told.note_on;
            got.seconds = told.seconds; got.clock = told.clock; got.open = told.open; got.all = told.all;
            got.silence = told.silence;
          }
          told = got;
          draw(first);
        })
        .catch(function () { /* the lines stay as they were */ });
    }

    // A note at the moment (v1.99.0): the app keeps it on the line being spoken
    // when there is one after all, and at the moment itself when there is not.
    function saveAtTheMoment() {
      var box = card.querySelector("#preview-note-text");
      if (!box) { return; }
      var typed = box.value;
      var sent = noting.moment === null ? { at: told.seconds, note: typed } : { id: noting.moment, note: typed };
      saving();
      fetch(told.note_at_url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
        body: JSON.stringify(sent)
      }).then(function (answer) { return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }); })
        .then(function (got) {
          if (!card) { return; }
          if (!got.ok || !got.said.saved) {
            drawNote({ problem: true, words: got.said.error || "The note could not be saved.", keep: typed });
            return;
          }
          var chronology = told.on_chronology ? ", and an event on the incident's chronology." : ".";
          if (got.said.on === "line") {
            var line = lineById(got.said.line);
            if (line) { line.note = got.said.note; line.note_by = got.said.note_by; line.note_on = got.said.note_on; }
            drawLines();
            follow(media() ? media().currentTime : told.seconds);
            saved(got.said.note ? "Noted on the line at " + (line ? line.clock : told.clock) + chronology : "The note is removed.",
              ".preview-line[data-line='" + got.said.line + "']");
            return;
          }
          var kept = got.said.moment;
          told.moment_notes = (told.moment_notes || []).filter(function (one) { return one.id !== sent.id && one.id !== kept.id; });
          if (kept.id !== null && kept.note) { told.moment_notes.push(kept); }
          drawLines();
          follow(media() ? media().currentTime : told.seconds);
          saved(kept.note ? "Noted at " + kept.clock + chronology : "The note is removed.",
            kept.id !== null && kept.note ? ".preview-line.kept[data-kept='" + kept.id + "']" : "");
        })
        .catch(function () { if (card) { drawNote({ problem: true, words: "The note could not be saved. Try again.", keep: typed }); } });
    }

    function save() {
      if (noting !== null && typeof noting === "object") { saveAtTheMoment(); return; }
      var one = lineById(noting);
      var box = card.querySelector("#preview-note-text");
      if (!one || !box) { return; }
      var typed = box.value;
      saving();
      fetch(told.note_url + one.id + "/note", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
        body: JSON.stringify({ note: typed })
      }).then(function (answer) { return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }); })
        .then(function (got) {
          if (!card) { return; }
          if (!got.ok || !got.said.saved) {
            drawNote({ problem: true, words: got.said.error || "The note could not be saved.", keep: typed });
            return;
          }
          one.note = got.said.note; one.note_by = got.said.note_by; one.note_on = got.said.note_on;
          drawLines();
          follow(media() ? media().currentTime : told.seconds);
          var words = one.note
            ? "Noted on the line at " + one.clock + (told.on_chronology ? ", and an event on the incident's chronology." : ".")
            : "The note is removed.";
          saved(words, ".preview-line[data-line='" + one.id + "']");
        })
        .catch(function () { if (card) { drawNote({ problem: true, words: "The note could not be saved. Try again.", keep: typed }); } });
    }

    function pressed(event) {
      var act = event.target.closest("[data-preview-act]");
      if (act) {
        if (act.dataset.previewAct === "close") { close(); }
        else if (act.dataset.previewAct === "cancel") { noting = null; drawNote(null); }
        else if (act.dataset.previewAct === "save") { save(); }
        return;
      }
      var atMoment = event.target.closest("[data-preview-moment]");
      if (atMoment && !atMoment.disabled) {
        var there = keptAtTheMoment();
        noting = { moment: there ? there.id : null };
        drawNote(null);
        return;
      }
      var keptNote = event.target.closest("[data-preview-kept]");
      if (keptNote && !keptNote.disabled) {
        noting = { moment: parseInt(keptNote.dataset.previewKept, 10) };
        drawNote(null);
        return;
      }
      var note = event.target.closest("[data-preview-note]");
      if (note && !note.disabled && note.dataset.previewNote) {
        noting = parseInt(note.dataset.previewNote, 10);
        drawNote(null);
        return;
      }
      var seek = event.target.closest("[data-preview-seek]");
      if (seek) {
        event.preventDefault();
        seekTo(parseFloat(seek.dataset.previewSeek));
      }
    }

    function seekTo(at) {
      var player = media();
      if (player) { player.currentTime = at; player.play(); }
      follow(at, true);
    }

    // Dragged by its head, kept inside the window.
    function drag(head) {
      var from = null;
      head.addEventListener("pointerdown", function (event) {
        if (event.button !== 0 || event.target.closest("button")) { return; }
        var box = card.getBoundingClientRect();
        from = { x: event.clientX - box.left, y: event.clientY - box.top };
        head.setPointerCapture(event.pointerId);
        event.preventDefault();
      });
      head.addEventListener("pointermove", function (event) {
        if (!from || !card) { return; }
        var box = card.getBoundingClientRect();
        var left = Math.min(window.innerWidth - box.width - 4, Math.max(4, event.clientX - from.x));
        var top = Math.min(window.innerHeight - 40, Math.max(4, event.clientY - from.y));
        card.style.left = left + "px";
        card.style.top = top + "px";
        card.style.right = "auto";
        card.style.bottom = "auto";
      });
      function letGo() { from = null; }
      head.addEventListener("pointerup", letGo);
      head.addEventListener("pointercancel", letGo);
    }

    function open(given) {
      if (!given || !given.recording) { return; }
      var seconds = Math.max(0, parseFloat(given.seconds) || 0);
      var same = card && asked && asked.recording === given.recording;
      if (asked && asked.from && asked.from !== given.from) { asked.from.classList.remove("previewing"); }
      asked = { recording: given.recording, seconds: seconds, from: given.from || null };
      noting = null;
      if (!card) { build(); }
      if (same && media()) {
        // The same recording: the player goes there and the lines are read again.
        var player = media();
        var from = Math.max(0, seconds - 10);
        told = null;
        var mine = ++asking;
        lastFetch = Date.now();
        fetch(url(seconds), { credentials: "same-origin" })
          .then(function (answer) { return answer.ok ? answer.json() : null; })
          .then(function (got) {
            if (!card || mine !== asking || !got) { return; }
            told = got;
            draw(false);
            player.currentTime = given.keepTime ? player.currentTime : from;
            if (!given.quiet) { player.play(); }
            follow(given.keepTime ? player.currentTime : seconds, true);
          })
          .catch(function () { /* the card stays as it was */ });
        return;
      }
      card.querySelector(".preview-media").innerHTML = "";
      card.querySelector(".preview-lines").innerHTML = "<p class='muted small preview-none'>Reading the lines...</p>";
      card.querySelector(".preview-foot").innerHTML = "";
      told = null;
      read(seconds, true);
    }

    // The line lit now, for a page that wants to open the note on it (N).
    function noteOnLit() {
      if (!card) { return; }
      var lit = card.querySelector(".preview-line.now[data-line]");
      var button = lit ? lit.querySelector("[data-preview-note]") : card.querySelector(".preview-foot [data-preview-note], .preview-foot [data-preview-moment]");
      if (button && !button.disabled) { button.click(); }
    }

    if (!host) {
      document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape" || !card) { return; }
        if (noting !== null) { noting = null; drawNote(null); event.stopPropagation(); return; }
        if (event.target.closest && event.target.closest("textarea, input")) { return; }
        // The Preview goes first; the panel behind it stays open.
        event.stopPropagation();
        close();
      }, true);
    }

    return {
      open: open,
      close: close,
      isOpen: function () { return !!card; },
      media: media,
      told: function () { return told; },
      asked: function () { return asked; },
      seek: seekTo,
      noteOnLit: noteOnLit,
      cancelNote: function () { if (card && noting !== null) { noting = null; drawNote(null); return true; } return false; }
    };
  }

  var floating = make({});

  // A hit of the case page's Search plays here too: a button beside its time.
  document.addEventListener("click", function (event) {
    var hit = event.target.closest("[data-preview-recording]");
    if (!hit) { return; }
    event.preventDefault();
    floating.open({ recording: hit.dataset.previewRecording, seconds: hit.dataset.previewAt, from: hit });
  });

  window.Preview = {
    open: floating.open,
    close: floating.close,
    isOpen: floating.isOpen,
    mount: function (host, options) { return make(Object.assign({ host: host }, options || {})); }
  };
})();

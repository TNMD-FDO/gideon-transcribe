// The Notes page (Phase 9 chapter 4): the Case's work page for its notes.
//
// The right panel is drawn from one reading of the case (the list): every
// note grouped under its recording in call order, the recordings, the
// writers' and types' pills. The left is the Preview mounted into the page:
// press a note on the right and the left plays that moment, with the note
// under its line. Previous and Next step through the notes listed, or, from
// the Recordings tab, through the recordings themselves; Mark reviewed sits
// in the foot in both modes. Open the call opens the whole recording in a
// pop-out over the page; Esc or Close returns exactly. Nothing looked at is
// logged.

(function () {
  "use strict";

  var desk = document.getElementById("notes-desk");
  if (!desk || !window.Preview || !window.Preview.mount) { return; }

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function cookie(name) {
    var found = document.cookie.split("; ").filter(function (one) { return one.indexOf(name + "=") === 0; })[0];
    return found ? decodeURIComponent(found.slice(name.length + 1)) : "";
  }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  var state = {
    recordings: [], byId: {}, notes: [], writers: [], types: [], me: null, mayDirect: false,
    writer: null, type: null,          // the pills in force
    mode: "notes",                     // notes: the order is the notes listed; calls: the recordings
    order: [], current: -1,
    recFilter: "", recWho: "",        // the Recordings tab's box and pills
    peaks: null, peaksFor: null
  };

  // The left: the Preview mounted into the page -------------------------------------

  var left = window.Preview.mount(document.getElementById("moment"), {
    onLit: lit,
    onLoaded: loaded
  });
  var wave = document.getElementById("np-wave");
  var waveTimer = null;

  function current() {
    return state.order[state.current] || null;
  }
  function recordingOf(note) { return state.byId[note.recording]; }

  function openAt(recording, seconds, quiet) {
    left.open({ recording: recording.id, seconds: seconds, quiet: !!quiet });
    drawHead(recording);
  }

  function drawHead(recording) {
    document.getElementById("np-call-title").textContent = recording.title;
    var pills = "";
    if (recording.type) { pills += "<span class='pill small'>" + escape(recording.type) + "</span>"; }
    if (recording.length) { pills += "<span class='pill small mono'>" + escape(recording.length) + "</span>"; }
    if (recording.summarised) { pills += "<span class='pill small ok'>Summarised</span>"; }
    if (recording.reviewed) { pills += "<span class='pill small ok'>" + escape(recording.reviewed) + "</span>"; }
    else if (recording.assigned) { pills += "<span class='pill small" + (recording.assigned_id === state.me ? " on" : "") + "'>Assigned to " + escape(recording.assigned_id === state.me ? "you" : recording.assigned) + "</span>"; }
    document.getElementById("np-call-pills").innerHTML = pills;
    document.getElementById("np-call-facts").textContent =
      recording.date + " · " + plural(recording.notes, "note") + (recording.writers.length ? ", " + recording.writers.join(", ") : "");
    document.getElementById("np-open-call").hidden = false;
    document.getElementById("np-bar").hidden = false;
    drawMark(recording);
  }

  function loaded(told, first) {
    var fold = document.getElementById("np-overview");
    fold.hidden = !told.overview;
    document.getElementById("np-overview-text").textContent = told.overview || "";
    if (told.waveform && told.waveform !== state.peaksFor) {
      state.peaksFor = told.waveform;
      state.peaks = null;
      fetch(told.waveform, { credentials: "same-origin" }).then(function (answer) { return answer.ok ? answer.json() : null; })
        .then(function (got) { if (state.peaksFor === told.waveform) { state.peaks = got; drawWave(); } })
        .catch(function () { /* no waveform then */ });
    } else if (!told.waveform) {
      state.peaksFor = null; state.peaks = null;
    }
    drawWave();
    var player = left.media();
    if (player && first) {
      player.playbackRate = parseFloat(document.getElementById("np-speed").value) || 1;
    }
    // The bar's sentence by the kind of recording (v1.121.1): a video's
    // controls sit under the picture, a sound recording's above the lines.
    document.getElementById("np-bar-said").textContent = player && player.tagName === "VIDEO"
      ? "The player's own controls are under the picture."
      : "The player's own controls are above the lines.";
    showEventNote();
  }

  // A note on an event (v1.121.1): shown under the line nearest its moment,
  // read-only, since the chronology owns it, with the event's time of day
  // and a link to the event.
  function showEventNote() {
    var host = document.getElementById("moment");
    Array.prototype.forEach.call(host.querySelectorAll(".np-event-note"), function (one) { one.remove(); });
    var note = current();
    var asked = left.asked();
    if (!note || note.kind !== "event" || !asked || asked.recording !== note.recording) { return; }
    var after = null;
    Array.prototype.forEach.call(host.querySelectorAll(".preview-line[data-at]"), function (row) {
      if (parseFloat(row.dataset.at) <= note.at + 0.05) { after = row; }
    });
    var box = document.createElement("div");
    box.className = "np-event-note";
    box.innerHTML = "<span class='muted'>On the event &ldquo;" + escape(note.said) + "&rdquo; at " + escape(note.event_clock) +
      (note.by ? ", by " + escape(note.by) : "") + ":</span> " + escape(note.text) +
      " <a href='" + escape(note.event_url) + "'>Open the event</a>";
    if (after && after.parentNode) { after.parentNode.insertBefore(box, after.nextSibling); }
    else { var lines = host.querySelector(".preview-lines"); if (lines) { lines.insertBefore(box, lines.firstChild); } }
  }

  function drawWave() {
    if (!wave || !window.Waveform) { return; }
    var told = left.told();
    var recording = told ? state.byId[left.asked().recording] : null;
    if (!told || !recording) { wave.hidden = true; return; }
    wave.hidden = false;
    var player = left.media();
    var ticks = state.notes.filter(function (one) { return one.recording === recording.id; }).map(function (one) { return one.at; });
    window.Waveform.draw(wave, {
      peaks: state.peaks, duration: recording.seconds || (told.length_seconds || 0),
      time: player ? player.currentTime : told.seconds, ticks: ticks, height: 44
    });
  }
  window.setInterval(function () { if (left.media() && !left.media().paused) { drawWave(); } }, 1000);
  if (wave) {
    wave.addEventListener("click", function (event) {
      var told = left.told();
      var recording = told ? state.byId[left.asked().recording] : null;
      if (!recording || !recording.seconds) { return; }
      var box = wave.getBoundingClientRect();
      left.seek(((event.clientX - box.left) / box.width) * recording.seconds);
      drawWave();
    });
  }

  // The lit line on the left lights the note's row on the right.
  function lit(row, now) {
    var asked = left.asked();
    if (!asked) { return; }
    var mine = state.order.filter(function (one) { return one.kind && one.recording === asked.recording; });
    var at = -1;
    mine.forEach(function (one, n) { if (one.at <= now + 0.5) { at = n; } });
    var note = at >= 0 ? mine[at] : null;
    Array.prototype.forEach.call(document.querySelectorAll("#np-list .np-row.now"), function (one) { one.classList.remove("now"); });
    if (note) {
      var there = document.querySelector("#np-list .np-row[data-key='" + note.key + "']");
      if (there) {
        there.classList.add("now");
        var panel = document.getElementById("np-panels");
        var top = there.offsetTop - panel.offsetTop;
        if (top < panel.scrollTop || top + there.offsetHeight > panel.scrollTop + panel.clientHeight) {
          panel.scrollTop = Math.max(0, top - panel.clientHeight / 3);
        }
      }
    }
  }

  // The order and the stepping ------------------------------------------------------

  function listedNotes() {
    return state.notes.filter(function (one) {
      if (state.writer !== null && one.by_id !== state.writer) { return false; }
      if (state.type !== null && (recordingOf(one) || {}).type !== state.type) { return false; }
      return true;
    });
  }
  function listedRecordings() {
    var wanted = state.recFilter.trim().toLowerCase();
    return state.recordings.filter(function (one) {
      if (state.type !== null && one.type !== state.type) { return false; }
      if (state.recWho === "me" && one.assigned_id !== state.me) { return false; }
      if (state.recWho === "me-left" && (one.assigned_id !== state.me || one.reviewed)) { return false; }
      if (state.recWho === "reviewed" && !one.reviewed) { return false; }
      if (state.recWho === "nobody" && one.assigned_id) { return false; }
      if (wanted && (one.title + " " + one.type + " " + one.assigned).toLowerCase().indexOf(wanted) === -1) { return false; }
      return true;
    });
  }

  function setOrder(mode) {
    state.mode = mode;
    state.order = mode === "notes" ? listedNotes() : listedRecordings();
    document.getElementById("np-prev-word").textContent = mode === "notes" ? "Previous note" : "Previous call";
    document.getElementById("np-next-word").textContent = mode === "notes" ? "Next note" : "Next call";
    sayPosition();
  }

  // The Scope (Phase 9 chapter 6): the recordings in view by the pills and
  // the filters, for Gideon; the whole case when nothing narrows.
  function tellScope() {
    if (!window.CaseScope) { return; }
    var narrowedNotes = state.writer !== null || state.type !== null;
    var narrowedCalls = state.recWho !== "" || state.recFilter.trim() !== "" || state.type !== null;
    if (state.mode === "calls" && narrowedCalls) {
      window.CaseScope.set("notes", listedRecordings().map(function (one) { return one.id; }));
    } else if (state.mode !== "calls" && narrowedNotes) {
      var ids = [];
      listedNotes().forEach(function (note) { if (ids.indexOf(note.recording) === -1) { ids.push(note.recording); } });
      window.CaseScope.set("notes", ids);
    } else {
      window.CaseScope.clear();
    }
  }

  function sayPosition() {
    tellScope();
    var box = document.getElementById("np-position");
    if (!state.order.length) { box.textContent = state.mode === "notes" ? "No notes to step through." : "No recordings listed."; return; }
    var narrowed = state.mode === "notes"
      ? (state.writer !== null || state.type !== null)
      : (state.recWho !== "" || state.recFilter.trim() !== "" || state.type !== null);
    var word = state.mode === "notes" ? "Note" : "Call";
    var tail = state.mode === "calls" && state.recWho === "me-left" ? " left for you" : (narrowed ? " shown" : "");
    if (state.current < 0) {
      // Nothing opened from this list yet: say how many there are.
      box.textContent = plural(state.order.length, word.toLowerCase()) + tail + ". Press one, or Next.";
      return;
    }
    box.textContent = word + " " + (state.current + 1) + " of " + state.order.length + tail + (state.mode === "notes" ? ", by call date" : "");
  }

  function go(index) {
    if (!state.order.length) { return; }
    state.current = (index + state.order.length) % state.order.length;
    var here = current();
    if (state.mode === "notes") {
      openAt(recordingOf(here), here.at);
      Array.prototype.forEach.call(document.querySelectorAll("#np-list .np-row.on"), function (one) { one.classList.remove("on"); });
      var row = document.querySelector("#np-list .np-row[data-key='" + here.key + "']");
      if (row) { row.classList.add("on"); row.scrollIntoView({ block: "nearest" }); }
    } else {
      var first = state.notes.filter(function (one) { return one.recording === here.id; })[0];
      openAt(here, first ? first.at : 0);
    }
    sayPosition();
  }

  document.getElementById("np-prev").addEventListener("click", function () { go(state.current - 1); });
  document.getElementById("np-next").addEventListener("click", function () { go(state.current + 1); });

  // The right: the Notes tab --------------------------------------------------------

  function drawPills() {
    var box = document.getElementById("np-pills");
    var html = "<button type='button' class='pill small" + (state.writer === null ? " on" : "") + "' data-writer=''>All " + state.notes.length + "</button>";
    state.writers.forEach(function (one, n) {
      html += "<button type='button' class='pill small" + (state.writer === one.id ? " on" : "") + (n >= 4 && state.writer !== one.id ? " np-more-writer" : "") + "' data-writer='" + one.id + "'>" + escape(one.name) + " " + one.count + "</button>";
    });
    if (state.writers.length > 4) {
      html += "<button type='button' class='pill small' id='np-more-writers'>" + (state.writers.length - 4) + " more</button>";
    }
    box.innerHTML = html;
    var types = document.getElementById("np-type-pills");
    types.innerHTML = state.types.length > 1
      ? state.types.map(function (one) {
          return "<button type='button' class='pill small" + (state.type === one.name ? " on" : "") + "' data-type='" + escape(one.name) + "'>" + escape(one.name) + " " + one.count + "</button>";
        }).join("")
      : "";
    types.hidden = state.types.length <= 1;
  }

  function drawList() {
    var listed = listedNotes();
    var box = document.getElementById("np-list");
    var html = "";
    var lastRecording = null;
    var playing = left.asked() ? left.asked().recording : null;
    listed.forEach(function (note) {
      var recording = recordingOf(note);
      if (!recording) { return; }
      if (recording.id !== lastRecording) {
        lastRecording = recording.id;
        var count = listed.filter(function (one) { return one.recording === recording.id; }).length;
        html += "<div class='np-group" + (recording.id === playing ? " playing" : "") + "' data-recording='" + recording.id + "'>" +
          "<b>" + escape(recording.date) + "</b> <span class='muted'>&middot; " + escape(recording.title) + " &middot; " + plural(count, "note") + "</span>" +
          "<span class='grow'></span>" +
          (recording.assigned ? "<span class='muted small'>" + escape(recording.assigned) + "</span>" : "") +
          (recording.reviewed ? " <span class='pill small ok'>Reviewed</span>" : "") +
          " <button type='button' class='tiny ghost' data-open-call='" + recording.id + "'>Open</button></div>";
      }
      html += "<div class='np-row' data-key='" + note.key + "'>" +
        "<span class='t mono'>" + escape(note.clock) + "</span>" +
        "<span class='np-text'>" + escape(note.text) +
        (note.kind === "event" ? " <span class='pill small' title='A note on an event of the chronology, read there'>on the event &middot; " + escape(note.event_clock) + "</span>" : "") + "</span>" +
        (note.said ? "<span class='np-said muted small'>" + (note.who ? escape(note.who) + ": " : "") + "&ldquo;" + escape(note.said) + "&rdquo;</span>" : "<span class='np-said muted small'>a note at the moment, where nothing was said</span>") +
        "<span class='np-by muted small'>" + escape(note.by) + (note.when ? ", " + escape(note.when) : "") + "</span></div>";
    });
    if (!html) {
      html = "<p class='muted small' style='margin: 10px 0'>" + (state.notes.length ? "No notes by that filter." : "No notes yet. A note is written under a line of a transcript, here on the left or on the recording's page.") + "</p>";
    }
    box.innerHTML = html;
    document.getElementById("np-count-notes").textContent = state.notes.length;
    var foot = document.getElementById("np-list-foot");
    var noNote = state.recordings.filter(function (one) { return !one.notes; }).length;
    foot.innerHTML = "<span>" + plural(noNote, "recording") + " " + (noNote === 1 ? "has" : "have") + " no note yet</span>";
    if (current() && state.mode === "notes") {
      var on = box.querySelector(".np-row[data-key='" + current().key + "']");
      if (on) { on.classList.add("on"); }
    }
  }

  document.getElementById("np-pills").addEventListener("click", function (event) {
    var more = event.target.closest("#np-more-writers");
    if (more) { document.getElementById("np-pills").classList.add("all"); return; }
    var pill = event.target.closest("[data-writer]");
    if (!pill) { return; }
    state.writer = pill.dataset.writer === "" ? null : parseInt(pill.dataset.writer, 10);
    drawPills(); drawList(); setOrder("notes"); state.current = -1; sayPosition();
  });
  document.getElementById("np-type-pills").addEventListener("click", function (event) {
    var pill = event.target.closest("[data-type]");
    if (!pill) { return; }
    state.type = state.type === pill.dataset.type ? null : pill.dataset.type;
    drawPills(); drawList(); drawRecordings(); setOrder(state.mode); state.current = -1; sayPosition();
  });
  document.getElementById("np-list").addEventListener("click", function (event) {
    var open = event.target.closest("[data-open-call]");
    if (open) { popOut(state.byId[open.dataset.openCall]); return; }
    var row = event.target.closest(".np-row");
    if (!row) { return; }
    if (state.mode !== "notes") { setOrder("notes"); }
    var index = state.order.map(function (one) { return one.key; }).indexOf(row.dataset.key);
    if (index >= 0) { go(index); }
  });

  // The right: the Recordings tab ----------------------------------------------------

  function drawRecordings() {
    var listed = listedRecordings();
    var body = document.getElementById("np-recordings");
    // Cards (v1.121.1): the title and Listen on the first line, the facts
    // on the second, so nothing is off to the right at the panel's width.
    body.innerHTML = listed.map(function (one) {
      return "<div class='np-rec' data-recording='" + one.id + "'>" +
        "<div class='row'><b class='grow'>" + escape(one.title) + "</b><span class='mono muted small'>" + escape(one.length) + "</span>" +
        "<button type='button' class='small' data-listen='" + one.id + "'" + (one.words ? "" : " disabled title='No transcript yet'") + ">Listen</button></div>" +
        "<div class='muted small'>" + escape(one.date) + (one.type ? " &middot; " + escape(one.type) : "") +
        " &middot; " + (one.assigned ? escape(one.assigned_id === state.me ? "assigned to you" : one.assigned) + (one.reviewed ? " <span class='pill small ok'>" + escape(one.reviewed) + "</span>" : "") : "nobody") +
        " &middot; " + (one.notes ? plural(one.notes, "note") + (one.writers.length ? ", " + escape(one.writers.join(", ")) : "") : "no note yet") + "</div></div>";
    }).join("");
    document.getElementById("np-count-recordings").textContent = state.recordings.length;
    var mine = state.recordings.filter(function (one) { return one.assigned_id === state.me; });
    var left = mine.filter(function (one) { return !one.reviewed; });
    var reviewed = state.recordings.filter(function (one) { return one.reviewed; });
    var nobody = state.recordings.filter(function (one) { return !one.assigned_id; });
    var pills = [
      ["", "All " + state.recordings.length],
      ["me", "Mine " + mine.length],
      ["me-left", "Mine, not reviewed " + left.length],
      ["reviewed", "Reviewed " + reviewed.length],
      ["nobody", "Unassigned " + nobody.length]
    ];
    var anyAssigned = state.recordings.some(function (one) { return one.assigned_id; });
    document.getElementById("np-rec-pills").innerHTML = anyAssigned || state.mayDirect
      ? pills.map(function (one) { return "<button type='button' class='pill small" + (state.recWho === one[0] ? " on" : "") + "' data-who='" + one[0] + "'>" + one[1] + "</button>"; }).join("")
      : "";
    document.getElementById("np-rec-foot").textContent = listed.length + " of " + plural(state.recordings.length, "recording") + " listed. Listen opens one on the left from its first note, and Next steps through these.";
  }
  document.getElementById("np-rec-pills").addEventListener("click", function (event) {
    var pill = event.target.closest("[data-who]");
    if (!pill) { return; }
    state.recWho = pill.dataset.who;
    drawRecordings(); setOrder("calls"); state.current = -1; sayPosition();
  });
  document.getElementById("np-rec-filter").addEventListener("input", function (event) {
    state.recFilter = event.target.value;
    drawRecordings(); if (state.mode === "calls") { setOrder("calls"); state.current = -1; sayPosition(); }
  });
  document.getElementById("np-recordings").addEventListener("click", function (event) {
    var listen = event.target.closest("[data-listen]");
    if (!listen) { return; }
    setOrder("calls");
    var index = state.order.map(function (one) { return one.id; }).indexOf(listen.dataset.listen);
    if (index >= 0) { go(index); }
  });

  // Mark reviewed, in the foot ------------------------------------------------------

  function drawMark(recording) {
    var mark = document.getElementById("np-mark");
    var unmark = document.getElementById("np-unmark");
    var may = recording.assigned_id && (recording.assigned_id === state.me || state.mayDirect);
    mark.hidden = !(may && !recording.reviewed);
    unmark.hidden = !(may && recording.reviewed);
  }
  function sendMark(recording, fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (key) { body.append(key, fields[key]); });
    return fetch("/recording/" + recording.id + "/reviewed", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": cookie("csrftoken") },
      body: body.toString()
    }).then(function (answer) { return answer.json(); });
  }
  document.getElementById("np-mark").addEventListener("click", function () {
    var asked = left.asked();
    var recording = asked ? state.byId[asked.recording] : null;
    if (!recording) { return; }
    var notes = state.notes.filter(function (one) { return one.recording === recording.id && one.by_id === state.me; }).length;
    var none = notes === 0;
    UI.confirm({
      title: "Mark " + recording.title + " as reviewed?",
      body: none ? "You have left no note on it. Mark it reviewed with nothing to note?"
        : "You have left " + plural(notes, "note") + " on it. The team will see it as reviewed by you, today.",
      ok: none ? "Nothing to note, mark it" : "Mark reviewed",
      cancel: "Not yet"
    }).then(function (yes) {
      if (!yes) { return; }
      sendMark(recording, { action: "mark", nothing: none ? "1" : "" }).then(function (told) {
        if (!told.ok) { UI.toast("That could not be marked.", { problem: true, icon: "warning" }); return; }
        recording.reviewed = told.words;
        drawHead(recording); drawList(); drawRecordings();
        UI.toast("Marked reviewed." + (told.next ? " Next: " + told.next.title : ""), { icon: "ok" });
        if (state.mode === "calls" && state.current < state.order.length - 1) { go(state.current + 1); }
      });
    });
  });
  document.getElementById("np-unmark").addEventListener("click", function () {
    var asked = left.asked();
    var recording = asked ? state.byId[asked.recording] : null;
    if (!recording) { return; }
    sendMark(recording, { action: "unmark" }).then(function (told) {
      if (!told.ok) { UI.toast("That could not be taken back.", { problem: true, icon: "warning" }); return; }
      recording.reviewed = "";
      drawHead(recording); drawList(); drawRecordings();
      UI.toast("Not reviewed after all.", { icon: "ok" });
    });
  });

  // The pop-out: the whole call ------------------------------------------------------

  var popout = document.getElementById("np-popout");
  var pop = window.Preview.mount(document.getElementById("np-popout-host"), { whole: true });
  function popOut(recording) {
    if (!recording) { return; }
    var player = left.media();
    var at = player && left.asked() && left.asked().recording === recording.id ? player.currentTime : 0;
    if (player) { player.pause(); }
    document.getElementById("np-popout-title").textContent = recording.title;
    document.getElementById("np-popout-facts").textContent = recording.date + (recording.length ? " · " + recording.length : "");
    document.getElementById("np-popout-open").href = recording.open;
    popout.hidden = false;
    document.body.classList.add("np-popped");
    pop.open({ recording: recording.id, seconds: at });
  }
  function popBack() {
    if (popout.hidden) { return; }
    var popPlayer = pop.media();
    var at = popPlayer ? popPlayer.currentTime : null;
    pop.close();
    popout.hidden = true;
    document.body.classList.remove("np-popped");
    var player = left.media();
    if (player && at !== null) { player.currentTime = at; }
  }
  document.getElementById("np-popout-close").addEventListener("click", popBack);
  popout.addEventListener("click", function (event) { if (event.target === popout) { popBack(); } });
  document.getElementById("np-open-call").addEventListener("click", function () {
    var asked = left.asked();
    if (asked) { popOut(state.byId[asked.recording]); }
  });

  // The player bar --------------------------------------------------------------------

  document.getElementById("np-bar").addEventListener("click", function (event) {
    var seek = event.target.closest("[data-np-seek]");
    if (!seek) { return; }
    var player = left.media();
    if (player) { player.currentTime = Math.max(0, player.currentTime + parseFloat(seek.dataset.npSeek)); drawWave(); }
  });
  document.getElementById("np-speed").addEventListener("change", function (event) {
    var player = left.media();
    if (player) { player.playbackRate = parseFloat(event.target.value) || 1; }
  });

  // The tabs, the layer and Find ------------------------------------------------------

  var panels = document.getElementById("np-panels");
  var findLayer = document.getElementById("np-layer-find");
  function showTab(name) {
    findLayer.hidden = true; panels.hidden = false;
    Array.prototype.forEach.call(document.querySelectorAll("#np-work .tab"), function (tab) { tab.classList.toggle("on", tab.dataset.panel === name); });
    ["notes", "recordings", "details"].forEach(function (one) { document.getElementById("panel-" + one).hidden = one !== name; });
  }
  Array.prototype.forEach.call(document.querySelectorAll("#np-work .tab"), function (tab) {
    tab.addEventListener("click", function () { showTab(tab.dataset.panel); });
  });
  var findHits = document.getElementById("np-find-hits");
  // A hit pressed, or stepped to with Enter (v1.121.3): lit, played on the
  // left, and the foot says which of the hits it is.
  function goHit(index) {
    var hits = findHits.querySelectorAll(".inc-find-hit");
    if (!hits.length) { return; }
    state.hitAt = (index + hits.length) % hits.length;
    Array.prototype.forEach.call(hits, function (one, n) { one.classList.toggle("on", n === state.hitAt); });
    var hit = hits[state.hitAt];
    var recording = state.byId[hit.dataset.recording];
    if (recording) { openAt(recording, parseFloat(hit.dataset.at)); }
    if (hit.scrollIntoView) { hit.scrollIntoView({ block: "nearest" }); }
    document.getElementById("np-position").textContent =
      "Hit " + (state.hitAt + 1) + " of " + hits.length + " for \u201c" + findBox.value.trim() + "\u201d";
  }
  findLayer.addEventListener("click", function (event) {
    if (event.target.closest("[data-back]")) { closeFind(); return; }
    var hit = event.target.closest(".inc-find-hit");
    if (hit) { goHit(Array.prototype.indexOf.call(findHits.querySelectorAll(".inc-find-hit"), hit)); }
  });
  var findBox = document.getElementById("np-find");
  var findTimer = null;
  function closeFind() { findBox.value = ""; findLayer.hidden = true; panels.hidden = false; state.hitAt = -1; sayPosition(); }
  function drawFind(got) {
    var hits = got.hits || [];
    document.getElementById("np-find-title").textContent = plural(hits.length, "moment") + " for “" + findBox.value.trim() + "”";
    var html = "";
    var saidClose = false, saidHeard = false;
    hits.forEach(function (one) {
      if (one.close && !saidClose) { saidClose = true; html += "<p class='small muted inc-find-close'>Close matches" + (got.also && got.also.length ? ", also looked for: " + escape(got.also.join(", ")) : "") + "</p>"; }
      if (one.heard && !saidHeard) { saidHeard = true; html += "<p class='small muted inc-find-close'>Also heard as: " + escape((got.heard_forms || []).join(", ")) + "</p>"; }
      var recording = state.byId[one.recording];
      html += "<div class='inc-find-hit" + (one.close ? " close" : "") + "' data-recording='" + one.recording + "' data-at='" + one.at + "'>" +
        "<span class='t mono'>" + escape(one.clock) + "</span>" +
        "<span class='who small'>" + escape(one.kind === "note" ? "Note" + (one.who ? ", " + one.who : "") : one.who) + "</span>" +
        "<span class='grow'>" + one.html + "<div class='muted small'>" + escape(recording ? recording.title : "") + "</div></span></div>";
    });
    if (!html) { html = "<p class='small muted' style='padding: 10px 14px'>Nothing in the notes or the recordings' words says that.</p>"; }
    findHits.innerHTML = html;
    state.hitAt = -1;
    panels.hidden = true; findLayer.hidden = false;
  }
  findBox.addEventListener("input", function () {
    window.clearTimeout(findTimer);
    var typed = findBox.value.trim();
    if (typed.length < 2) { if (!typed) { findLayer.hidden = true; panels.hidden = false; } return; }
    findTimer = window.setTimeout(function () {
      fetch(desk.dataset.find + "?q=" + encodeURIComponent(typed), { credentials: "same-origin" })
        .then(function (answer) { return answer.ok ? answer.json() : null; })
        .then(function (got) { if (got && findBox.value.trim() === typed) { drawFind(got); } })
        .catch(function () { /* the hits stay */ });
    }, 300);
  });
  findBox.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { closeFind(); findBox.blur(); return; }
    if (event.key === "Enter") { event.preventDefault(); goHit(state.hitAt + 1); }
  });

  // The grip, as the incident page has it: the panel's width, kept in the browser.
  (function () {
    var grip = document.getElementById("work-grip");
    if (!grip) { return; }
    var KEY = "notes-page-work-width";
    try { var kept = parseInt(window.localStorage.getItem(KEY), 10); if (kept) { desk.style.setProperty("--work", kept + "px"); } } catch (ignored) { /* no storage */ }
    var from = null;
    grip.addEventListener("pointerdown", function (event) { from = { x: event.clientX, width: document.getElementById("np-work").getBoundingClientRect().width }; grip.setPointerCapture(event.pointerId); });
    grip.addEventListener("pointermove", function (event) {
      if (!from) { return; }
      var width = Math.round(Math.min(desk.clientWidth * 0.6, Math.max(360, from.width - (event.clientX - from.x))));
      desk.style.setProperty("--work", width + "px");
    });
    function letGo() {
      if (!from) { return; }
      from = null;
      try { window.localStorage.setItem(KEY, parseInt(getComputedStyle(desk).getPropertyValue("--work"), 10)); } catch (ignored) { /* no storage */ }
      drawWave();
    }
    grip.addEventListener("pointerup", letGo); grip.addEventListener("pointercancel", letGo);
    grip.addEventListener("dblclick", function () { desk.style.removeProperty("--work"); try { window.localStorage.removeItem(KEY); } catch (ignored) { /* no storage */ } drawWave(); });
  })();
  window.addEventListener("resize", drawWave);

  // Ask Gideon, from the head.
  var askGideon = document.getElementById("gideon-open-np");
  if (askGideon) {
    askGideon.addEventListener("click", function () {
      var button = document.getElementById("gideon-open");
      if (button) { button.click(); }
    });
  }

  // The keyboard ------------------------------------------------------------------------

  var overlay = document.getElementById("shortcuts");
  function shortcuts(show) { if (overlay) { overlay.hidden = !show; } }
  var closeShortcuts = document.getElementById("close-shortcuts");
  if (closeShortcuts) { closeShortcuts.addEventListener("click", function () { shortcuts(false); }); }
  if (overlay) { overlay.addEventListener("click", function (event) { if (event.target === overlay) { shortcuts(false); } }); }

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)) { return; }
    if (event.key === "?") { shortcuts(overlay && overlay.hidden); return; }
    if (event.key === "Escape") {
      if (overlay && !overlay.hidden) { shortcuts(false); return; }
      if (!popout.hidden) { if (!pop.cancelNote()) { popBack(); } return; }
      if (left.cancelNote()) { return; }
      if (!findLayer.hidden) { closeFind(); return; }
      return;
    }
    if (event.key === "/") { event.preventDefault(); findBox.focus(); return; }
    var view = popout.hidden ? left : pop;
    var player = view.media();
    if (event.key === " ") {
      if (player) { event.preventDefault(); if (player.paused) { player.play(); } else { player.pause(); } }
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      if (player) { event.preventDefault(); player.currentTime = Math.max(0, player.currentTime + (event.key === "ArrowRight" ? 5 : -5)); drawWave(); }
      return;
    }
    if (!popout.hidden) { return; }
    if (event.key === "j" || event.key === "J") { go(state.current + 1); return; }
    if (event.key === "k" || event.key === "K") { go(state.current - 1); return; }
    if (event.key === "n" || event.key === "N") { event.preventDefault(); left.noteOnLit(); return; }
    if (event.key === "r" || event.key === "R") {
      var mark = document.getElementById("np-mark");
      if (!mark.hidden) { event.preventDefault(); mark.click(); }
      return;
    }
    if (event.key === "o" || event.key === "O") {
      var asked = left.asked();
      if (asked) { popOut(state.byId[asked.recording]); }
    }
  });

  // The reading --------------------------------------------------------------------------

  function load() {
    return fetch(desk.dataset.list, { credentials: "same-origin" })
      .then(function (answer) { return answer.ok ? answer.json() : null; })
      .then(function (got) {
        if (!got) { document.getElementById("np-lead").textContent = "The notes could not be read."; return; }
        state.recordings = got.recordings; state.notes = got.notes; state.writers = got.writers; state.types = got.types;
        state.me = got.me; state.mayDirect = got.may_direct;
        state.byId = {};
        state.recordings.forEach(function (one) { state.byId[one.id] = one; });
        // The lead (v1.121.1): the notes on how many of the recordings, and
        // how many sit on an incident's events.
        var kinds = got.kinds || {};
        var onEvents = kinds.event || 0;
        document.getElementById("np-lead").textContent =
          plural(state.notes.length, "note") + " on " + (got.noted || 0) + " of " + plural(state.recordings.length, "recording") +
          (state.writers.length ? ", by " + plural(state.writers.length, "person").replace("persons", "people") : "") +
          (onEvents ? ": " + (state.notes.length - onEvents) + " on lines, " + plural(onEvents, "event").replace(/^(\d+) event/, "$1 on event") : "") +
          ". Press a note to hear its moment here.";
        drawPills(); drawList(); drawRecordings();
        setOrder("notes");
        var opening = desk.dataset.opening;
        var index = opening ? state.order.map(function (one) { return one.key; }).indexOf(opening) : -1;
        if (index < 0 && state.order.length) { index = 0; }
        if (index >= 0) { state.current = index; go(index); }
        else if (state.recordings.length) {
          var first = state.recordings.filter(function (one) { return one.words; })[0];
          if (first) { openAt(first, 0, true); }
        }
      })
      .catch(function () { document.getElementById("np-lead").textContent = "The notes could not be read."; });
  }
  load();
})();

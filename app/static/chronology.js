// The case's chronology (Phase 10 chapter 1): the case's notes on the
// recordings' own clocks, one day at a time. Drawn from chronology.json into
// #case-chronology on the Notes tab (the toggle Rows | Chronology) and on the
// Notes page's panel; the pressed entry plays in the page's own Preview or
// the Notes page's player. Nothing here invents a time: a recording with no
// clock sits on the rail until a person places it by a drag, a typed time,
// the day alone or the file's time.
(function () {
  "use strict";
  var host = document.getElementById("case-chronology");
  if (!host) { return; }
  var caseId = host.dataset.case;
  var onNotesPage = host.dataset.player === "notes-page";
  var state = { days: [], day: null, span: null, showAll: false, lit: null, open: {}, loaded: false, me: null };
  var keyShape = "notes-shape:" + caseId, keyAll = "chron-all:" + caseId;
  try { state.showAll = localStorage.getItem(keyAll) === "1"; } catch (e) { /* no storage */ }

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function hms(seconds) { seconds = Math.max(0, Math.round(seconds)) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function hm(seconds) { return hms(seconds).slice(0, 5); }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
  function cookie(name) { var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  function post(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") }, body: JSON.stringify(body || {}) })
      .then(function (answer) { return answer.json().then(function (told) { if (!answer.ok) { throw new Error(told.error || "That did not work."); } return told; }); });
  }
  function open(recordingId, seconds) {
    if (onNotesPage && window.NotesPageOpen) { window.NotesPageOpen(recordingId, seconds); return; }
    if (window.Preview && window.Preview.open) { window.Preview.open({ recording: recordingId, seconds: seconds, from: host }); }
  }

  // The address: the day and the span, so a link opens them.
  function params() {
    var p = new URLSearchParams(location.search);
    return { day: p.get("day") || "", from: p.get("from") || "", to: p.get("to") || "" };
  }
  function setAddress(day, span) {
    if (onNotesPage) { return; }
    var p = new URLSearchParams(location.search);
    p.set("tab", "notes"); p.set("shape", "chronology");
    if (day) { p.set("day", day); } else { p.delete("day"); }
    if (span) { p.set("from", hm(span[0])); p.set("to", hm(span[1])); } else { p.delete("from"); p.delete("to"); }
    history.replaceState(null, "", location.pathname + "?" + p.toString());
  }

  function load(day, span) {
    var url = host.dataset.json + "?day=" + encodeURIComponent(day || "");
    if (span) { url += "&from=" + encodeURIComponent(hm(span[0])) + "&to=" + encodeURIComponent(hm(span[1])); }
    host.innerHTML = "<p class='muted small'>Reading the notes...</p>";
    return fetch(url, { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      state.days = told.days || []; state.day = told.day; state.span = span || null; state.me = told.me; state.loaded = true;
      state.lit = null; state.open = {};
      setAddress(state.day ? state.day.date : "", state.span);
      draw();
    }).catch(function () { host.innerHTML = "<p class='muted small'>The chronology could not be read. Try again.</p>"; });
  }

  // Drawing ------------------------------------------------------------------
  function draw() {
    var d = state.day;
    if (!d) { host.innerHTML = "<p class='muted small'>No note of this case is on a recording with a clock yet. A video whose clock was read places itself; anything else is placed from the rail once it has a note.</p>"; return; }
    var html = "";
    html += leadRow(d);
    html += strip();
    html += rail(d);
    html += ruler(d);
    html += band(d);
    html += notesLane(d);
    html += incidentsLane(d);
    html += hints(d);
    html += spellsHtml(d);
    host.innerHTML = html;
    wire();
  }

  function leadRow(d) {
    var words = plural(d.count, "note") + (d.recordings ? " on " + plural(d.recordings, "recording") : "") + (d.span ? ", " + hm(d.ruler.from) + " to " + hm(d.ruler.to) : ", " + d.words);
    var right = "";
    if (d.span && d.incidents_on) { right += "<button type='button' class='small primary' data-act='make-span' title='An incident from the span in view: the recordings that ran in it, ticked'>Make an incident from this span</button> "; }
    if (d.span) { right += "<button type='button' class='small' data-act='back'>Back to the day</button> "; }
    if (d.fold) { right += "<button type='button' class='small ghost' data-act='open-all'>Open all</button> "; }
    var base = host.dataset.export.replace(/\.docx$/, "");
    right += "<details class='menu' id='chron-export'><summary class='btn small'>Export</summary><ul>" +
      "<li><a href='" + base + ".docx?day=" + d.date + "'>Chronology to Word, " + esc(d.words) + "</a></li>" +
      "<li><a href='" + base + ".csv?day=" + d.date + "'>As a spreadsheet, " + esc(d.words) + "</a></li>" +
      "<li><a href='" + base + ".docx'>Chronology to Word, every day</a></li>" +
      "<li><a href='" + base + ".csv'>As a spreadsheet, every day</a></li></ul></details>";
    return "<div class='lead-row'><span class='muted'>" + esc(words) + (d.fold && !d.span ? " · folded past forty" : "") + "</span><span class='row' style='gap: 8px'>" + right + "</span></div>";
  }

  function strip() {
    if (!state.days.length) { return ""; }
    var most = Math.max.apply(null, state.days.map(function (one) { return one.notes; })) || 1;
    var months = {}; var order = [];
    state.days.forEach(function (one) { if (!months[one.month]) { months[one.month] = []; order.push(one.month); } months[one.month].push(one); });
    var html = "<div class='strip' title='One bar per day with notes, its height the day&#39;s count; the arrow keys step days'>";
    order.forEach(function (name) {
      html += "<div class='month'><div class='days-bars'>";
      months[name].forEach(function (one) {
        var h = Math.max(3, Math.round(34 * one.notes / most));
        html += "<button type='button' data-day='" + one.date + "' class='" + (state.day && one.date === state.day.date ? "on" : "") + "' style='height: " + h + "px' title='" + esc(one.words + " · " + plural(one.notes, "note") + " · " + plural(one.recordings, "recording")) + "'></button>";
      });
      html += "</div><div class='name'>" + esc(name) + " · " + plural(months[name].length, "day") + "</div></div>";
    });
    html += "<span class='muted tiny' style='margin-left: auto; align-self: center'>" + (state.day ? esc(state.day.words) : "") + " · ← → step days</span></div>";
    return html;
  }

  function rail(d) {
    if (!d.rail.length && !d.rail_more) { return ""; }
    var html = "<div class='rail' id='chron-rail'><span>Not on the clock yet:</span>";
    d.rail.forEach(function (one) {
      html += "<button type='button' class='chip' draggable='true' data-rail='" + one.id + "' title='Drag onto the ruler, or press to type its time'><i></i>" + esc(one.title) + " · " + plural(one.notes, "note") + "</button>";
    });
    if (d.rail_more) { html += "<span class='tiny'>and " + d.rail_more + " more with notes</span>"; }
    html += "<button type='button' class='small' data-act='sheet' style='margin-left: auto'>Place recordings</button></div>";
    return html;
  }

  function x(seconds, d) { var w = d.ruler.to - d.ruler.from; return Math.max(0, Math.min(100, (seconds - d.ruler.from) * 100 / (w || 1))); }
  // A label centred near an edge would clip: it is kept a little inside.
  function inside(percent) { return Math.max(6, Math.min(94, percent)); }

  function ruler(d) {
    var html = "<div class='ruler' id='chron-ruler'>";
    var span = d.ruler.to - d.ruler.from, ticks = 6;
    for (var i = 0; i <= ticks; i++) { var at = d.ruler.from + span * i / ticks; html += "<span class='tick' style='left: " + (100 * i / ticks) + "%'>" + hm(at) + "</span>"; }
    html += "</div>";
    // The drag track (v1.164.1): a drag across it looks closer at the span;
    // a chip from the rail dropped on it places the recording there.
    html += "<div class='track' id='chron-track' title='Drag across a span to look closer; drop a recording from the rail here to place it'><span class='words'>" +
      (d.span ? "Drag across a narrower span, or Back to the day" : "Drag across a span to look closer") + "</span></div>";
    return html;
  }
  // A bar's short name: the camera's id from its stamp, else the title cut.
  function shortName(b) { if (b.camera) { return b.camera; } var t = b.title || ""; return t.length > 18 ? t.slice(0, 17) + "…" : t; }

  function band(d) {
    var html = "";
    var bars = d.bars.slice();
    if (d.shape === "coverage") {
      var n = d.coverage.length, most = Math.max.apply(null, d.coverage) || 1;
      var pts = d.coverage.map(function (c, i) { return (1000 * i / (n - 1)).toFixed(1) + "," + (56 - 52 * c / most).toFixed(1); });
      var peakAt = d.coverage.indexOf(most);
      html += "<div class='cover' id='chron-cover' title='How many recordings were running; press for the list'>" +
        "<svg viewBox='0 0 1000 56' preserveAspectRatio='none' aria-hidden='true'><path d='M0,56 L" + pts.join(" L") + " L1000,56 Z' fill='var(--accent)' opacity='0.28'></path><polyline points='" + pts.join(" ") + "' fill='none' stroke='var(--accent)' stroke-width='1.5'></polyline></svg>" +
        "<span class='peak' style='left: " + (100 * peakAt / (n - 1)) + "%; top: 2px'>" + most + " running</span><span class='lbl'>how many were running</span></div>";
    }
    var shown = bars.filter(function (b) { return b.lane !== null && b.lane !== undefined; });
    var folded = d.folded || [];
    var all = state.showAll && folded.length;
    var rows = all ? shown.concat(folded.filter(function (b) { return b.notes > 0 || d.shape !== "coverage"; })) : shown;
    var capped = all && rows.length > 8;
    html += "<div class='band" + (capped ? " capped" : "") + "' id='chron-band'>";
    if (d.shape === "coverage" || all) {
      rows.forEach(function (b) { html += barRow(b, d); });
    } else {
      var lanes = Math.max.apply(null, shown.map(function (b) { return b.lane; }).concat([0])) + 1;
      for (var lane = 0; lane < lanes; lane++) {
        html += "<div class='bar'>";
        shown.filter(function (b) { return b.lane === lane; }).forEach(function (b) { html += barPiece(b, d, true); });
        html += "</div>";
      }
    }
    html += "</div>";
    if (folded.length) {
      var withNotes = folded.filter(function (b) { return b.notes > 0; }).length, without = folded.length - withNotes;
      var words = d.shape === "coverage"
        ? withNotes + " more with notes, and " + without + " with none, in the shade above"
        : "and " + plural(folded.length, "more recording") + " on this day";
      html += "<div class='band'><div class='bar'><i class='fold'></i><span class='more'>" + esc(words) + " · <a href='#' data-act='toggle-all'>" + (state.showAll ? "Show fewer" : (d.shape === "coverage" ? "Show all with notes" : "Show all")) + "</a></span></div></div>";
    }
    html += legend(d);
    return html;
  }

  function barRow(b, d) { return "<div class='bar'>" + barPiece(b, d, false) + "</div>"; }
  function barPiece(b, d, idOnly) {
    var left = x(b.from, d), width = Math.max(0.4, x(b.to, d) - left);
    var lit = state.lit === b.id ? " lit" : "";
    // The label sits inside the bar, cut to its width (v1.164.1); a bar too
    // narrow for a name carries none, and the whole title is on hover.
    var pixels = width * (host.clientWidth || 900) / 100;
    var label = pixels < 56 ? "" : (idOnly || pixels < 120 ? shortName(b) : shortName(b) + " · " + plural(b.notes, "note"));
    return "<i class='" + (b.movable ? "movable" : "") + lit + (label ? "" : " narrow") + "' data-bar='" + b.id + "' style='left: " + left + "%; width: " + width + "%; background: " + b.colour + "' title='" + esc(b.title + " · " + plural(b.notes, "note") + " · " + b.placed + (b.movable ? " · press to move or take off the clock" : " · press to light its notes")) + "'>" + esc(label) + "</i>";
  }

  function legend(d) {
    var parts = [];
    var placed = d.bars.length, byHand = d.bars.filter(function (b) { return b.how === "hand" || b.how === "file" || b.how === "day"; }).length;
    if (d.shape === "coverage") { parts.push("The " + Math.min(8, d.bars.length) + " with the most notes have a bar; press the shade at a moment for every recording running then."); }
    else if (d.shape === "packed") { parts.push(placed + " recordings on the clock, packed into lanes; " + (placed - byHand) + " by clock, " + byHand + " by hand."); }
    else { d.bars.forEach(function (b) { parts.push("<i style='background: " + b.colour + "'></i>" + esc(b.title) + " · " + esc(b.placed)); }); }
    if (d.shape !== "lanes") { parts.push("Hover a bar for the recording; press it to light its notes."); }
    return "<div class='legend'>" + parts.map(function (p) { return "<span>" + p + "</span>"; }).join("") + "</div>";
  }

  function notesLane(d) {
    var html = "<div class='notes-lane' id='chron-marks'>";
    var marks = d.marks.slice().sort(function (a, b) { return a.seconds - b.seconds; });
    var width = host.clientWidth || 900, px = (d.ruler.to - d.ruler.from) / width;
    var clusters = [];
    marks.forEach(function (m) {
      var last = clusters[clusters.length - 1];
      if (last && (m.seconds - last.last) < 9 * px) { last.items.push(m); last.last = m.seconds; }
      else { clusters.push({ items: [m], first: m.seconds, last: m.seconds }); }
    });
    clusters.forEach(function (c) {
      var mid = (c.first + c.last) / 2;
      if (c.items.length === 1) { html += "<i data-mark='" + c.items[0].n + "' style='left: " + x(mid, d) + "%; background: " + (c.items[0].colour || "var(--muted)") + "' title='Note " + c.items[0].n + " at " + hms(mid) + "'></i>"; }
      else { html += "<em data-marks='" + c.items.map(function (m) { return m.n; }).join(",") + "' style='left: " + inside(x(mid, d)) + "%' title='" + c.items.length + " notes, " + hm(c.first) + " to " + hm(c.last) + "; press to open them'>×" + c.items.length + "</em>"; }
    });
    html += "<span class='lbl'>notes</span></div>";
    return html;
  }

  function hints(d) {
    if (!d.hints.length) { return ""; }
    var html = "<div class='hint'>";
    d.hints.forEach(function (h) {
      var left = x(h.from, d), width = Math.max(1, x(h.to, d) - left);
      html += "<span style='left: " + left + "%; width: " + width + "%'></span><span class='hl' style='left: " + inside(left + width / 2) + "%'><b data-hint='" + h.from + "," + h.to + "' title='Press to look at this span'>" + esc(h.words) + "</b>" +
        (d.incidents_on ? "<button type='button' class='mk' data-make='" + h.from + "," + h.to + "' title='Make an incident from this span'>Make an incident</button>" : "") + "</span>";
    });
    html += "</div>";
    return html;
  }

  function spellsHtml(d) {
    var html = "";
    d.spells.forEach(function (group, index) {
      var folded = d.fold && !state.open[index] && !state.open.all;
      var title = group.notes === 1 ? group.from : group.from + " to " + group.to;
      var inc = sameIncident(group.entries);
      html += "<div class='spell' data-spell='" + index + "'><div class='sh'><span class='chev'>" + (folded ? "›" : "⌄") + "</span><b>" + esc(title) + "</b><span class='muted'>" + plural(group.notes, "note") + " · " + plural(group.recordings, "recording") + (state.lit ? litWords(group) : "") + "</span>" + (inc ? "<span class='pill small inc' title='Every note here is an event of this incident'>" + esc(inc.name) + "</span>" : "") + "</div>";
      if (!folded) { group.entries.forEach(function (e) { html += entry(e); }); }
      html += "</div>";
    });
    if (d.unknown.length) {
      html += "<div class='unknown'><div class='sh' style='display: flex; gap: 10px; align-items: baseline'><b style='font-family: var(--mono); font-size: 13px'>Time unknown on " + esc(d.words) + "</b><span class='muted'>" + plural(d.unknown.length, "note") + "</span></div>";
      d.unknown.forEach(function (e) { html += entry(e); });
      html += "</div>";
    }
    return html;
  }
  function litWords(group) { var n = group.entries.filter(function (e) { return e.recording === state.lit; }).length; return n ? " · " + n + " lit" : ""; }

  function entry(e) {
    var cls = "entry" + (state.lit ? (e.recording === state.lit ? " lit" : " dim") : "");
    var under = e.said ? "“" + esc(e.said) + "”" : (e.kind === "event" ? "on the event" + (e.event_time ? " at " + esc(e.event_time) : "") : "at a moment, nothing said");
    return "<div class='" + cls + "' data-entry='" + esc(e.key) + "' data-recording='" + e.recording + "' data-at='" + e.at + "' data-n='" + e.number + "'" + (e.outside ? " data-outside='" + esc(JSON.stringify(e.outside)) + "'" : "") + ">" +
      "<span class='num' style='background: " + (e.colour || "var(--muted)") + "'>" + e.number + "</span>" +
      "<div><div class='top'><button type='button' class='t' data-act='play' title='Play the moment'>" + (e.time || "the day") + "</button><button type='button' class='play' data-act='play' title='Play the moment'>▶</button>" +
      (e.how === "day" ? "<span class='pill small'>placed by the day</span>" : "") + (e.to_check ? "<span class='pill small warn'>To check</span>" : "") + "</div>" +
      "<div class='words' data-act='edit' title='" + (e.kind === "event" ? "A note on an incident&#39;s event: edit it there" : "Press to edit") + "'>" + esc(e.text).replace(/\n/g, "<br>") + "</div>" +
      "<div class='line'>" + under + " · " + esc(e.title) + "</div>" +
      "<div class='meta'><span class='pill small'>" + esc(e.by) + (e.when ? ", " + esc(e.when) : "") + "</span><span class='chip'><i style='background: " + (e.colour || "var(--muted)") + "'></i>" + esc(e.title) + "</span>" +
      (e.kind !== "event" ? "<button type='button' class='small ghost' data-act='check' title='A question for a colleague; pressed on or off by anyone on the case'>" + (e.to_check ? "Clear To check" : "To check") + "</button>" : "") +
      "<a class='small ghost' href='/recording/" + e.recording + "?t=" + e.at + "' title='The whole call, on its own page'>Open the call</a>" +
      (e.incident ? (e.incident.event ? "<span class='pill small inc' title='This note is an event of the incident'>an event of " + esc(e.incident.name) + "</span>" : "<span class='pill small inc' title='Its camera is in the incident but not on its clock yet; the note is an event once it is synced'>in " + esc(e.incident.name) + ", not synced yet</span>") : "") + "</div>" +
      (e.outside ? "<div class='outside'>inside " + esc(e.outside.name) + "; " + esc(e.title) + " is not in it <button type='button' class='small' data-act='add-outside' title='The camera joins the incident on its clock as it sits here; this note is then an event of it'>Add " + esc(e.title) + " to the incident</button></div>" : "") +
      "</div></div>";
  }

  // Wiring ---------------------------------------------------------------------
  function wire() {
    host.querySelectorAll("[data-day]").forEach(function (b) { b.addEventListener("click", function () { load(b.dataset.day, null); }); });
    var r = host.querySelector("#chron-track");
    if (r) { wireRuler(r); }
    host.querySelectorAll("[data-rail]").forEach(function (chip) {
      chip.addEventListener("dragstart", function (ev) { ev.dataTransfer.setData("text/plain", chip.dataset.rail); ev.dataTransfer.effectAllowed = "move"; chip.classList.add("dragging"); });
      chip.addEventListener("dragend", function () { chip.classList.remove("dragging"); clearGuide(); });
      chip.addEventListener("click", function () { placeBox(findRail(chip.dataset.rail), null); });
    });
    host.querySelectorAll("[data-bar]").forEach(function (bar) {
      bar.addEventListener("click", function () {
        var b = state.day.bars.filter(function (one) { return one.id === bar.dataset.bar; })[0];
        if (b && b.movable) { moveBox(b); return; }
        state.lit = state.lit === bar.dataset.bar ? null : bar.dataset.bar; draw();
      });
    });
    var cover = host.querySelector("#chron-cover");
    if (cover) { cover.addEventListener("click", function (ev) { var rect = cover.getBoundingClientRect(); var at = state.day.ruler.from + (ev.clientX - rect.left) / rect.width * (state.day.ruler.to - state.day.ruler.from); runningList(at); }); }
    host.querySelectorAll("[data-mark]").forEach(function (m) { m.addEventListener("click", function () { goTo(parseInt(m.dataset.mark, 10), true); }); });
    host.querySelectorAll("[data-marks]").forEach(function (m) { m.addEventListener("click", function () { var first = parseInt(m.dataset.marks.split(",")[0], 10); goTo(first, false); }); });
    host.querySelectorAll("[data-hint]").forEach(function (h) { h.addEventListener("click", function () { var p = h.dataset.hint.split(","); load(state.day.date, [parseFloat(p[0]), parseFloat(p[1])]); }); });
    host.querySelectorAll("[data-make]").forEach(function (m) { m.addEventListener("click", function () { var p = m.dataset.make.split(","); makeSheet(parseFloat(p[0]), parseFloat(p[1])); }); });
    host.querySelectorAll("[data-spell] .sh").forEach(function (sh) { sh.addEventListener("click", function () { var i = sh.parentNode.dataset.spell; state.open[i] = !state.open[i]; draw(); }); });
    host.querySelectorAll("[data-act]").forEach(function (b) {
      b.addEventListener("click", function (ev) {
        var act = b.dataset.act;
        if (act === "back") { load(state.day.date, null); }
        else if (act === "open-all") { state.open.all = true; draw(); }
        else if (act === "toggle-all") { ev.preventDefault(); state.showAll = !state.showAll; try { localStorage.setItem(keyAll, state.showAll ? "1" : "0"); } catch (e) { /* no storage */ } draw(); }
        else if (act === "sheet") { sheet(); }
        else if (act === "make-span") { if (state.span) { makeSheet(state.span[0], state.span[1]); } }
        else if (act === "add-outside") { addOutside(b.closest(".entry")); }
        else if (act === "play") { var e = b.closest(".entry"); open(e.dataset.recording, parseFloat(e.dataset.at)); light(e); }
        else if (act === "check") { check(b.closest(".entry")); }
        else if (act === "edit") { edit(b.closest(".entry")); }
      });
    });
  }

  function findRail(id) { return (state.day.rail_all || state.day.rail).filter(function (one) { return one.id === id; })[0]; }
  function light(e) { host.querySelectorAll(".entry.lit").forEach(function (one) { one.classList.remove("lit"); }); e.classList.add("lit"); }
  function goTo(n, play) {
    var e = host.querySelector(".entry[data-n='" + n + "']");
    if (!e) { state.open.all = true; draw(); e = host.querySelector(".entry[data-n='" + n + "']"); }
    if (!e) { return; }
    e.scrollIntoView({ block: "center", behavior: "smooth" }); light(e);
    if (play) { open(e.dataset.recording, parseFloat(e.dataset.at)); }
  }

  // The ruler: a drag selects a span; a chip dropped places a recording.
  var guide = null;
  function clearGuide() { if (guide) { guide.remove(); guide = null; } var r = host.querySelector("#chron-track"); if (r) { r.classList.remove("over"); } }
  function secondsAt(r, clientX) { var rect = r.getBoundingClientRect(); var share = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)); return state.day.ruler.from + share * (state.day.ruler.to - state.day.ruler.from); }
  function wireRuler(r) {
    r.addEventListener("dragover", function (ev) { ev.preventDefault(); r.classList.add("over"); var at = secondsAt(r, ev.clientX); if (!guide) { guide = document.createElement("span"); guide.className = "guide"; guide.innerHTML = "<b></b>"; r.appendChild(guide); } guide.style.left = x(at, state.day) + "%"; guide.firstChild.textContent = hm(at); });
    r.addEventListener("dragleave", function () { clearGuide(); });
    r.addEventListener("drop", function (ev) { ev.preventDefault(); var id = ev.dataTransfer.getData("text/plain"); var at = secondsAt(r, ev.clientX); clearGuide(); var one = findRail(id); if (one) { placeBox(one, at); } });
    var from = null, sel = null;
    r.addEventListener("pointerdown", function (ev) { if (ev.button !== 0) { return; } from = secondsAt(r, ev.clientX); r.setPointerCapture(ev.pointerId); });
    r.addEventListener("pointermove", function (ev) { if (from === null) { return; } var to = secondsAt(r, ev.clientX); if (!sel) { sel = document.createElement("span"); sel.className = "sel"; r.appendChild(sel); } var a = Math.min(from, to), b = Math.max(from, to); sel.style.left = x(a, state.day) + "%"; sel.style.width = (x(b, state.day) - x(a, state.day)) + "%"; var words = r.querySelector(".words"); if (words) { words.textContent = hm(a) + " to " + hm(b); } });
    r.addEventListener("pointerup", function (ev) { if (from === null) { return; } var to = secondsAt(r, ev.clientX); var a = Math.min(from, to), b = Math.max(from, to); from = null; if (sel) { sel.remove(); sel = null; } if (b - a >= 60) { load(state.day.date, [Math.floor(a), Math.ceil(b)]); } else { draw(); } });
  }

  // Layers: the place box, the move box, the sheet, the running list.
  function layer(inner) {
    var wrap = document.createElement("div"); wrap.className = "chron-layer"; wrap.innerHTML = inner;
    wrap.addEventListener("click", function (ev) { if (ev.target === wrap) { wrap.remove(); } });
    document.body.appendChild(wrap);
    // Every Close and Cancel in the layer closes it (v1.164.1: the sheet has
    // both, and only the first used to work).
    wrap.querySelectorAll("[data-close]").forEach(function (closer) { closer.addEventListener("click", function () { wrap.remove(); }); });
    return wrap;
  }
  function placeBox(one, at) {
    if (!one) { return; }
    var day = state.day.date;
    var wrap = layer("<div class='box chron'><h4 style='margin: 0'>Place " + esc(one.title) + (at !== null ? " by hand?" : "") + "</h4>" +
      "<div class='field'><span class='muted'>Date</span><input type='date' name='date' value='" + day + "'></div>" +
      "<div class='field'><span class='muted'>Starts at</span><input type='text' name='start' placeholder='hh:mm' value='" + (at !== null ? hms(at) : "") + "'></div>" +
      "<label class='small' style='display: flex; gap: 6px; align-items: center'><input type='checkbox' name='alone'> The day alone; the time is not known</label>" +
      (one.file ? "<p class='small muted' style='margin: 0'>The file says it began at " + esc(one.file.words) + ", unchecked. <button type='button' class='small ghost' data-file>Use the file's time</button></p>" : "") +
      "<p class='small muted' style='margin: 0'>Its " + plural(one.notes, "note") + " land from then on. It reads Placed by hand under your name, and anyone on the case may move it or take it off the clock.</p>" +
      "<p class='small' data-error style='margin: 0; color: var(--danger)'></p>" +
      "<div class='row' style='justify-content: flex-end; gap: 8px'><button type='button' class='small' data-close>Cancel</button><button type='button' class='small primary' data-place>Place</button></div></div>");
    var how = "";
    var useFile = wrap.querySelector("[data-file]");
    if (useFile) { useFile.addEventListener("click", function () { wrap.querySelector("[name=start]").value = hms(one.file.seconds); how = "file"; }); }
    wrap.querySelector("[data-place]").addEventListener("click", function () {
      var alone = wrap.querySelector("[name=alone]").checked;
      post("/recording/" + one.id + "/clock", { date: wrap.querySelector("[name=date]").value, start: wrap.querySelector("[name=start]").value, day_alone: alone, how: alone ? "day" : how })
        .then(function () { wrap.remove(); load(state.day.date, state.span); })
        .catch(function (err) { wrap.querySelector("[data-error]").textContent = err.message; });
    });
  }
  function moveBox(b) {
    var wrap = layer("<div class='box chron'><h4 style='margin: 0'>" + esc(b.title) + "</h4><p class='small muted' style='margin: 0'>Placed " + esc(b.placed) + ". Move it to another time, or take it off the clock.</p>" +
      "<div class='field'><span class='muted'>Date</span><input type='date' name='date' value='" + state.day.date + "'></div>" +
      "<div class='field'><span class='muted'>Starts at</span><input type='text' name='start' placeholder='hh:mm' value='" + hms(b.from) + "'></div>" +
      "<p class='small' data-error style='margin: 0; color: var(--danger)'></p>" +
      "<div class='row' style='justify-content: flex-end; gap: 8px'><button type='button' class='small ghost danger' data-off>Take off the clock</button><button type='button' class='small' data-close>Cancel</button><button type='button' class='small primary' data-place>Move</button></div></div>");
    wrap.querySelector("[data-place]").addEventListener("click", function () {
      post("/recording/" + b.id + "/clock", { date: wrap.querySelector("[name=date]").value, start: wrap.querySelector("[name=start]").value, how: "hand" })
        .then(function () { wrap.remove(); load(state.day.date, state.span); })
        .catch(function (err) { wrap.querySelector("[data-error]").textContent = err.message; });
    });
    wrap.querySelector("[data-off]").addEventListener("click", function () {
      post("/recording/" + b.id + "/clock/off", {}).then(function () { wrap.remove(); load(state.day.date, state.span); });
    });
  }
  function sheet() {
    var rows = state.day.rail_all || state.day.rail;
    var html = "<div class='sheet chron'><div class='row' style='justify-content: space-between; align-items: baseline'><b>Place recordings</b><button type='button' class='small ghost' data-close>Close</button></div>" +
      "<div class='muted tiny'>" + rows.length + " recordings with notes are not on the clock. Type what you know; a row with nothing typed is left as it is. Press ▶ to hear the date said.</div><table><tr><th></th><th>Recording</th><th>Notes</th><th>Date</th><th>Starts at</th><th>Day alone</th></tr>";
    rows.forEach(function (one) {
      html += "<tr data-row='" + one.id + "'><td><button type='button' class='play' data-hear='" + one.id + "' title='Play from the start'>▶</button></td><td>" + esc(one.title) + "</td><td>" + one.notes + "</td><td><input type='date' name='date'" + (state.day ? " value='" + state.day.date + "'" : "") + "></td><td><input type='text' name='start' placeholder='hh:mm'" + (one.file ? " title='The file says " + esc(one.file.words) + "'" : "") + "></td><td><input type='checkbox' name='alone'></td></tr>";
    });
    html += "</table><p class='small' data-error style='margin: 0; color: var(--danger)'></p><div class='row' style='justify-content: flex-end; gap: 8px'><button type='button' class='small' data-close>Cancel</button><button type='button' class='small primary' data-place-all>Place the rows typed</button></div></div>";
    var wrap = layer(html);
    wrap.querySelectorAll("[data-hear]").forEach(function (b) { b.addEventListener("click", function () { open(b.dataset.hear, 0); }); });
    wrap.querySelector("[data-place-all]").addEventListener("click", function () {
      var todo = [];
      wrap.querySelectorAll("tr[data-row]").forEach(function (tr) {
        var start = tr.querySelector("[name=start]").value.trim(), alone = tr.querySelector("[name=alone]").checked, date = tr.querySelector("[name=date]").value;
        if (date && (start || alone)) { todo.push({ id: tr.dataset.row, body: { date: date, start: start, day_alone: alone, how: alone ? "day" : "hand" } }); }
      });
      if (!todo.length) { wrap.querySelector("[data-error]").textContent = "Nothing typed yet."; return; }
      var chain = Promise.resolve();
      todo.forEach(function (t) { chain = chain.then(function () { return post("/recording/" + t.id + "/clock", t.body); }); });
      chain.then(function () { wrap.remove(); load(state.day.date, state.span); }).catch(function (err) { wrap.querySelector("[data-error]").textContent = err.message; });
    });
  }
  function runningList(at) {
    fetch(host.dataset.running + "?day=" + state.day.date + "&at=" + encodeURIComponent(hms(at)), { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      var rows = told.rows || [];
      var html = "<div class='running chron'><div class='row' style='justify-content: space-between; align-items: baseline'><b>Running at " + hm(at) + "</b><button type='button' class='small ghost' data-close>Close</button></div><div class='muted tiny'>" + plural(rows.length, "recording") + ", " + rows.filter(function (r) { return r.notes; }).length + " with notes first. Press a row to light its notes; ▶ plays it there.</div>";
      rows.forEach(function (r) { html += "<div class='row' data-run='" + r.id + "'><button type='button' class='play' data-hear='" + r.id + "' data-into='" + r.into + "'>▶</button><span>" + esc(r.title) + "</span><span class='muted'>" + plural(r.notes, "note") + "</span><span class='pill small'>" + esc(r.placed) + "</span></div>"; });
      html += "</div>";
      var wrap = layer(html);
      wrap.querySelectorAll("[data-hear]").forEach(function (b) { b.addEventListener("click", function (ev) { ev.stopPropagation(); open(b.dataset.hear, parseFloat(b.dataset.into)); }); });
      wrap.querySelectorAll("[data-run]").forEach(function (row) { row.addEventListener("click", function () { state.lit = row.dataset.run; wrap.remove(); draw(); }); });
    });
  }

  // An incident from a span (Phase 10 chapter 2, v1.167.0; the drawing
  // phase-10-incident-from-span.html). The case's incidents are drawn as a
  // lane of brackets, so nobody makes one twice; Make on a span that touches
  // an incident leads with Add to it; a note on a camera outside an incident
  // but inside its span offers to add the camera. Nothing is made without a
  // press.
  function incidentsLane(d) {
    if (!d.incidents_on || !d.incidents || !d.incidents.length) { return ""; }
    var html = "<div class='inc-lane' id='chron-incidents'>";
    d.incidents.forEach(function (one) {
      var left = x(one.from, d), width = Math.max(1, x(one.to, d) - left);
      html += "<a class='br' href='" + esc(one.url) + "' style='left: " + left + "%; width: " + width + "%' title='" + esc(one.words + " · " + hm(one.from) + " to " + hm(one.to) + "; press to open it") + "'><b>" + esc(one.words) + "</b></a>";
    });
    html += "<span class='lbl'>incidents</span></div>";
    return html;
  }
  function sameIncident(entries) {
    var first = entries[0] && entries[0].incident;
    if (!first) { return null; }
    return entries.every(function (e) { return e.incident && e.incident.id === first.id; }) ? first : null;
  }
  function spanUrl(path, from, to) { return "/case/" + caseId + path + "?day=" + state.day.date + "&from=" + encodeURIComponent(from) + "&to=" + encodeURIComponent(to); }
  function makeSheet(from, to) {
    fetch(spanUrl("/chronology/span", hm(from), hm(to)), { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      if (told.incidents && told.incidents.length) { addFirstSheet(told); } else { pickerSheet(told); }
    }).catch(function () { alert("The span could not be read. Try again."); });
  }
  function rowHtml(r, ticked, inIt) {
    var tick = inIt ? "<input type='checkbox' checked disabled title='Already in it'>" : "<input type='checkbox' name='pick'" + (ticked ? " checked" : "") + " aria-label='" + esc(r.title) + "'>";
    return "<tr data-row='" + r.id + "'" + (r.notes ? "" : " class='quiet'") + "><td>" + tick + "</td><td>" + esc(r.title) + "</td><td>" + r.notes + "</td><td><span class='pill small'>" + esc(r.placed) + "</span></td><td class='mono'>" + esc(r.from) + " to " + esc(r.to) + "</td>" +
      (inIt === undefined ? "" : "<td class='muted tiny'>" + (inIt ? "already in it" : "not in it yet") + "</td>") + "</tr>";
  }
  function picked(wrap) { return Array.prototype.map.call(wrap.querySelectorAll("tr[data-row] input[name=pick]:checked"), function (box) { return box.closest("tr").dataset.row; }); }
  // The sitting bar (Phase 8 chapter 10) for the cameras ticked, with the
  // incident's own when adding; redrawn on each tick.
  function sittingBar(wrap, ids, already, afterAdding) {
    var box = wrap.querySelector("[data-sitting]"); if (!box) { return; }
    var all = ids.slice();
    (already || []).forEach(function (id) { if (all.indexOf(id) < 0) { all.push(id); } });
    var most = parseInt(wrap.dataset.most, 10) || 20;
    var count = "<span class='small'><b>" + all.length + " of " + most + " cameras</b>" + (afterAdding ? " after adding" : "") + "</span>";
    box.innerHTML = count;
    if (!all.length) { return; }
    fetch("/case/" + caseId + "/chronology/sitting?recordings=" + all.join(","), { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      var T = told.sitting;
      if (!T || !T.on) { return; }
      box.innerHTML = count.replace("</span>", " · " + esc(T.figure) + "</span>") + "<span class='sit " + esc(T.zone) + "'><i style='width: " + T.percent + "%'></i></span><span class='muted tiny'>" + esc(T.capacity_words) + "</span>";
    }).catch(function () { /* the count stands */ });
  }
  function pickerSheet(told) {
    var quiet = told.rows.filter(function (r) { return !r.notes; });
    var html = "<div class='sheet chron make' data-most='" + told.most + "'><div class='row' style='justify-content: space-between; align-items: baseline'><b>Make an incident from " + esc(told.words) + ", " + esc(told.from) + " to " + esc(told.to) + "</b><button type='button' class='small ghost' data-close>Close</button></div>" +
      "<div class='muted tiny'>The recordings that ran in the span, the most noted first and ticked. Each arrives on the incident's clock as it sits here; nothing is placed again. A camera with no notes is tickable, and a note on it afterwards is an event.</div>" +
      "<table><tr><th></th><th>Recording</th><th>Notes</th><th>Placed</th><th>In the span</th></tr>";
    told.rows.forEach(function (r) { html += rowHtml(r, r.ticked); });
    html += "</table>" + (quiet.length ? "<div class='muted tiny' data-more-line>and " + plural(quiet.length, "recording") + " ran in this span with no notes · <button type='button' class='small ghost' data-more>Choose more</button></div>" : "") +
      "<div class='row' data-sitting style='gap: 10px; align-items: center; flex-wrap: wrap'></div>" +
      "<div class='field'><span class='muted'>Name</span><input type='text' name='name' value='" + esc(told.name) + "' maxlength='200' style='width: 280px; font-family: inherit'></div>" +
      "<p class='small' data-error style='margin: 0; color: var(--danger)'></p>" +
      "<div class='row' style='justify-content: flex-end; gap: 8px'><button type='button' class='small' data-close>Cancel</button><button type='button' class='small primary' data-make-it>Make the incident</button></div></div>";
    var wrap = layer(html);
    wrap.querySelectorAll("tr.quiet").forEach(function (tr) { tr.hidden = true; });
    var more = wrap.querySelector("[data-more]");
    if (more) { more.addEventListener("click", function () { wrap.querySelectorAll("tr.quiet").forEach(function (tr) { tr.hidden = false; }); wrap.querySelector("[data-more-line]").hidden = true; }); }
    function refresh() { sittingBar(wrap, picked(wrap)); }
    wrap.querySelectorAll("input[name=pick]").forEach(function (box) { box.addEventListener("change", refresh); });
    refresh();
    wrap.querySelector("[data-make-it]").addEventListener("click", function () {
      var ids = picked(wrap), error = wrap.querySelector("[data-error]");
      if (!ids.length) { error.textContent = "Tick at least one recording."; return; }
      if (ids.length > told.most) { error.textContent = "At most " + told.most + " cameras in an incident (the Panel's Most cameras in an incident)."; return; }
      post("/case/" + caseId + "/chronology/incident", { day: told.date, from: told.from, to: told.to, name: wrap.querySelector("[name=name]").value, recordings: ids })
        .then(function (made) { location.href = made.url; })
        .catch(function (err) { error.textContent = err.message; });
    });
  }
  function addFirstSheet(told) {
    var inc = told.incidents[0], others = told.incidents.slice(1);
    var inIt = {}; inc.in_ids.forEach(function (id) { inIt[id] = true; });
    var fresh = told.rows.filter(function (r) { return !inIt[r.id]; });
    // Nothing to add and nothing to widen: the incident is the answer.
    var nothing = !fresh.length && !inc.widens;
    var html = "<div class='sheet chron make' data-most='" + told.most + "'><div class='row' style='justify-content: space-between; align-items: baseline'><b>This span " + (inc.inside ? "lies inside" : "runs past") + " an incident</b><button type='button' class='small ghost' data-close>Close</button></div>" +
      "<div class='notice small'><b>" + esc(inc.name) + "</b> runs " + esc(inc.from) + " to " + esc(inc.to) + " and has " + plural(inc.cameras, "camera") + ". Your span, " + esc(told.from) + " to " + esc(told.to) + ", " + (inc.inside ? "is inside it." : "overlaps it.") + (nothing ? " Everything that ran in the span is already in it." : "") + "</div>" +
      "<table><tr><th></th><th>Recording</th><th>Notes</th><th>Placed</th><th>In the span</th><th></th></tr>";
    told.rows.forEach(function (r) { html += rowHtml(r, true, !!inIt[r.id]); });
    html += "</table>" + (inc.widens ? "<div class='muted tiny'>Adding widens the incident to <b>" + esc(inc.union_from) + " to " + esc(inc.union_to) + "</b>; its cameras keep their places.</div>" : "") +
      "<div class='row' data-sitting style='gap: 10px; align-items: center; flex-wrap: wrap'></div>";
    others.forEach(function (o) { html += "<div class='muted tiny'>The span also touches <b>" + esc(o.name) + "</b>, " + esc(o.from) + " to " + esc(o.to) + ". <a href='" + esc(o.url) + "'>Open it</a></div>"; });
    html += "<p class='small' data-error style='margin: 0; color: var(--danger)'></p>" +
      "<div class='row' style='justify-content: flex-end; gap: 8px'><button type='button' class='small ghost' data-new title='A second incident over this span, on purpose'>Make a new one anyway</button>" +
      (nothing ? "<a class='btn small primary' href='" + esc(inc.url) + "'>Open " + esc(inc.name) + "</a>" : "<button type='button' class='small primary' data-add>" + (fresh.length ? "Add to " + esc(inc.name) + (inc.widens ? " and widen it" : "") : "Widen " + esc(inc.name)) + "</button>") + "</div></div>";
    var wrap = layer(html);
    function refresh() { sittingBar(wrap, picked(wrap), inc.camera_ids, true); }
    wrap.querySelectorAll("input[name=pick]").forEach(function (box) { box.addEventListener("change", refresh); });
    refresh();
    wrap.querySelector("[data-new]").addEventListener("click", function () { wrap.remove(); pickerSheet(told); });
    var add = wrap.querySelector("[data-add]");
    if (add) { add.addEventListener("click", function () {
      post("/case/" + caseId + "/incident/" + inc.id + "/add-from-chronology", { day: told.date, from: told.from, to: told.to, recordings: picked(wrap) })
        .then(function (done) { location.href = done.url; })
        .catch(function (err) { wrap.querySelector("[data-error]").textContent = err.message; });
    }); }
  }
  // The entry's line: its camera added to the incident whose span it is in.
  function addOutside(e) {
    var inc = JSON.parse(e.dataset.outside);
    post("/case/" + caseId + "/incident/" + inc.id + "/add-from-chronology", { day: state.day.date, from: inc.from, to: inc.to, recordings: [e.dataset.recording] })
      .then(function () { load(state.day.date, state.span); })
      .catch(function (err) { alert(err.message); });
  }
  function check(e) {
    var key = e.dataset.entry.split(":"), wanted = !e.querySelector(".pill.warn");
    post("/recording/" + e.dataset.recording + "/note/to-check", { kind: key[0], id: key[1], wanted: wanted }).then(function () { load(state.day.date, state.span); });
  }
  function edit(e) {
    var key = e.dataset.entry.split(":");
    if (key[0] === "event") { return; }
    var words = e.querySelector(".words"); if (words.querySelector("textarea")) { return; }
    var was = words.textContent;
    words.innerHTML = "<textarea></textarea><div class='row' style='gap: 6px; margin-top: 4px'><button type='button' class='small primary' data-save>Save</button><button type='button' class='small' data-cancel>Cancel</button></div>";
    words.querySelector("textarea").value = was; words.querySelector("textarea").focus();
    words.querySelector("[data-cancel]").addEventListener("click", function (ev) { ev.stopPropagation(); words.textContent = was; });
    words.querySelector("[data-save]").addEventListener("click", function (ev) {
      ev.stopPropagation();
      var text = words.querySelector("textarea").value;
      // The line's note and the note at a moment have their own addresses (Phase 8 chapter 2, v1.99.0).
      var line = key[0] === "line";
      var url = line ? "/recording/" + e.dataset.recording + "/segment/" + key[1] + "/note" : "/recording/" + e.dataset.recording + "/note-at";
      var body = line ? { note: text, was: was } : { id: key[1], note: text, at: parseFloat(e.dataset.at) };
      post(url, body).then(function () { load(state.day.date, state.span); }).catch(function (err) { words.textContent = was; alert(err.message); });
    });
  }

  // Keys: the arrow keys step days while the chronology shows.
  document.addEventListener("keydown", function (ev) {
    if (host.hidden || !state.day || ev.target.closest("input, textarea, select")) { return; }
    if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") { return; }
    var i = state.days.findIndex(function (one) { return one.date === state.day.date; });
    var next = state.days[i + (ev.key === "ArrowRight" ? 1 : -1)];
    if (next) { ev.preventDefault(); load(next.date, null); }
  });

  // Where it shows: the Notes tab's toggle, or the Notes page's panel.
  function show() {
    host.hidden = false;
    if (!state.loaded) { var p = params(); var span = (p.from && p.to) ? [toSeconds(p.from), toSeconds(p.to)] : null; load(p.day, span); }
  }
  function toSeconds(text) { var parts = text.split(":"); return parseInt(parts[0], 10) * 3600 + parseInt(parts[1] || "0", 10) * 60 + parseInt(parts[2] || "0", 10); }
  window.CaseChronology = { show: show, reload: function () { if (state.loaded) { load(state.day ? state.day.date : "", state.span); } } };

  var toggle = document.getElementById("notes-shape");
  if (toggle) {
    var rowsOf = host.dataset.rows ? document.querySelectorAll(host.dataset.rows) : [];
    function setShape(shape) {
      toggle.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b.dataset.shape === shape); });
      var chron = shape === "chronology";
      Array.prototype.forEach.call(rowsOf, function (el) { el.hidden = chron; });
      host.hidden = !chron;
      if (chron) { show(); } else if (!onNotesPage) { var p = new URLSearchParams(location.search); p.delete("shape"); p.delete("day"); p.delete("from"); p.delete("to"); history.replaceState(null, "", location.pathname + "?" + p.toString()); }
      try { localStorage.setItem(keyShape, shape); } catch (e) { /* no storage */ }
    }
    toggle.addEventListener("click", function (ev) { var b = ev.target.closest("[data-shape]"); if (b) { setShape(b.dataset.shape); } });
    var wanted = params().day || new URLSearchParams(location.search).get("shape") === "chronology" ? "chronology" : null;
    if (!wanted) { try { wanted = localStorage.getItem(keyShape); } catch (e) { wanted = null; } }
    if (wanted === "chronology") { setShape("chronology"); }
  }
})();

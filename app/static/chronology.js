// The case's chronology (Phase 10 chapter 1): the case's notes on the
// recordings' own clocks, one day at a time. Drawn from chronology.json into
// #case-chronology on the Notes tab (the toggle Rows | Chronology) and on the
// Notes page's panel; the pressed entry plays in the page's own Preview or
// the Notes page's player. Nothing here invents a time: a recording with no
// clock sits on the rail until a person places it by a drag, a typed time,
// the day alone or the file's time.
(function () {
  "use strict";
  // Two hosts share this script (v1.169.0, Phase 10 chapter 4): the Notes
  // tab's chronology, and the Proposed events tab, which lays the case's
  // proposals out the same way (data-mode="proposed") with Accept, Accept
  // and edit and Dismiss on each entry, and the Preview's window on a press.
  function mount(host) {
  var caseId = host.dataset.case;
  var proposed = host.dataset.mode === "proposed";
  // The Incidents tab's strip (Phase 10 chapter 5, v1.180.0): the band
  // without the spells, a forming lane, cards under it; polled by the minute.
  var stripMode = host.dataset.mode === "strip";
  var stripTimer = null;
  var onNotesPage = host.dataset.player === "notes-page";
  var state = { days: [], day: null, span: null, showAll: false, lit: null, open: {}, loaded: false, me: null, unplaced: [], run: null, railOnly: { rail: [], rail_more: 0, rail_all: [] } };
  var pollTimer = null;
  var keyShape = "notes-shape:" + caseId, keyAll = "chron-all:" + caseId;
  try { state.showAll = localStorage.getItem(keyAll) === "1"; } catch (e) { /* no storage */ }

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function hms(seconds) { seconds = Math.max(0, Math.round(seconds)) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function hm(seconds) { return hms(seconds).slice(0, 5); }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
  // A camera's colour (v1.179.0, the dark walk): the server names it by the
  // light palette's hex, which the exports draw with on white; the page
  // paints the same camera in its own token, so dark gets the look's dark
  // palette and the ink on it reads. Anything else is the muted tone.
  var PAINT = { "#1f6fb2": 1, "#c2410c": 2, "#2e7d32": 3, "#8e24aa": 4, "#00838f": 5, "#ad1457": 6, "#6d4c41": 7, "#546e7a": 8 };
  function paint(hex) { var n = PAINT[String(hex || "").toLowerCase()]; return n ? "var(--sp" + n + ")" : "var(--muted)"; }
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
    // The Notes page and the Incidents tab's strip keep their own address.
    if (onNotesPage || stripMode) { return; }
    var p = new URLSearchParams(location.search);
    p.set("tab", proposed ? "proposed" : "notes"); if (!proposed) { p.set("shape", "chronology"); }
    if (day) { p.set("day", day); } else { p.delete("day"); }
    if (span) { p.set("from", hm(span[0])); p.set("to", hm(span[1])); } else { p.delete("from"); p.delete("to"); }
    history.replaceState(null, "", location.pathname + "?" + p.toString());
  }

  function load(day, span, quiet) {
    var url = host.dataset.json + "?day=" + encodeURIComponent(day || "");
    if (span) { url += "&from=" + encodeURIComponent(hm(span[0])) + "&to=" + encodeURIComponent(hm(span[1])); }
    // While it reads (v1.176.0): the box keeps a height and shows three grey
    // rows, so the page does not jump when the chronology lands.
    if (!quiet) { host.classList.add("loading"); host.innerHTML = "<p class='muted small'>" + (proposed ? "Reading the proposals..." : stripMode ? "Reading the clocks..." : "Reading the notes...") + "</p><div class='skeleton' aria-hidden='true'><i></i><i></i><i></i></div>"; }
    return fetch(url, { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      state.days = told.days || []; state.day = told.day; state.span = span || null; state.me = told.me; state.loaded = true;
      state.unplaced = told.unplaced || []; state.run = told.run || null;
      state.most = told.most || 20; state.mayMake = told.may_make !== false;
      // The rail on its own (v1.170.1): the recordings to place, day or no day.
      state.railOnly = { rail: told.rail || [], rail_more: told.rail_more || 0, rail_all: told.rail_all || [] };
      state.lit = null; if (!quiet) { state.open = {}; }
      setAddress(state.day ? state.day.date : "", state.span);
      draw();
    }).catch(function () { host.classList.remove("loading"); host.innerHTML = "<p class='muted small'>The chronology could not be read. Try again.</p>"; });
  }

  // Drawing ------------------------------------------------------------------
  function draw() {
    var d = state.day;
    host.classList.remove("loading");
    if (proposed) { drawProposed(d); return; }
    if (stripMode) { drawStrip(d); return; }
    if (!d) {
      // No day yet (v1.170.1): the message, and the rail under it so the
      // first placing can happen from here.
      host.innerHTML = "<p class='muted small'>No note of this case is on a recording with a clock yet. A video whose clock was read places itself; " + (state.railOnly.rail.length ? "place the rest from the rail below, and the day opens." : "anything else is placed from the rail once it has a note.") + "</p>" + rail(state.railOnly);
      wire();
      return;
    }
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

  // The Incidents tab's strip (Phase 10 chapter 5, v1.180.0): the day chips,
  // the rail, the ruler without its drag track, the band, the notes lane,
  // the incidents lane and the forming lane; the cards under the strip; a
  // read by the minute while the tab is open, so a note written elsewhere
  // shows here.
  function drawStrip(d) {
    if (stripTimer) { window.clearTimeout(stripTimer); stripTimer = null; }
    if (!d) {
      host.innerHTML = "<p class='muted small'>No video of this case is on the clock yet. A video whose clock was read places itself; the rest are placed on the Notes tab's chronology, by a drag or a typed time.</p>";
      return;
    }
    host.innerHTML = dayChips() + ruler(d) + band(d) + notesLane(d) + incidentsLane(d) + formingLane(d) + rail(d);
    wire();
    cards(d);
    stripTimer = window.setTimeout(function () { if (document.body.contains(host) && state.day) { load(state.day.date, null, true); } }, 60000);
  }
  function dayChips() {
    if (!state.days.length) { return ""; }
    var html = "<div class='days'><span class='lbl'>Days</span>";
    state.days.forEach(function (one) {
      var words = esc(one.words) + " · " + plural(one.videos, "video") + (one.notes ? " · " + plural(one.notes, "note") : "") + (one.forming ? " · " + one.forming + " forming" : "");
      html += "<button type='button' data-day='" + one.date + "' class='" + (state.day && one.date === state.day.date ? "on" : "") + "'>" + words + "</button>";
    });
    return html + "</div>";
  }
  function formingLane(d) {
    var runs = d.hints || [];
    if (!runs.length || !d.incidents_on) { return ""; }
    var html = "<div class='form-lane' id='chron-forming'>";
    runs.forEach(function (h) {
      var left = x(h.from, d), width = Math.max(1, x(h.to, d) - left);
      var faint = h.faint || h.declined;
      var words = faint ? plural(h.cameras, "camera") + (h.declined ? ", not these" : "") : "Forming · " + esc(h.words);
      var title = esc(h.words + (h.declined ? " · put away with Not these" : ""));
      // The bracket, then its words centred on it and kept inside the strip,
      // as the chronology's own brackets are.
      html += "<span class='br" + (faint ? " faint" : "") + "' style='left: " + left + "%; width: " + width + "%' title='" + title + "'></span>" +
        "<span class='hl" + (faint ? " faint" : "") + "' style='left: " + inside(left + width / 2) + "%' title='" + title + "'><b>" + words + "</b>" +
        (!faint && state.mayMake ? "<button type='button' class='mk' data-make='" + h.from + "," + h.to + "' title='Make an incident from this span: the picker opens with these videos ticked'>Make it</button>" : "") + "</span>";
    });
    return html + "<span class='lbl'>forming</span></div>";
  }
  // The cards under the strip: the day's forming brackets with notes, not
  // declined and not already an offer's card, three cards at most with the
  // offers counted, the most noted first.
  function cards(d) {
    var box = document.querySelector(host.dataset.cards || "#forming-cards");
    if (!box) { return; }
    box.querySelectorAll("[data-forming]").forEach(function (one) { one.remove(); });
    var have = {}; box.querySelectorAll("[data-key]").forEach(function (one) { have[one.dataset.key] = true; });
    var worth = (d.hints || []).filter(function (h) { return h.notes && !h.declined && !have[h.key]; });
    worth.sort(function (a, b) { return b.notes - a.notes; });
    var room = Math.max(0, 3 - Object.keys(have).length);
    var shown = worth.slice(0, room), more = worth.length - shown.length;
    shown.forEach(function (h) { box.insertAdjacentHTML("beforeend", cardHtml(h, d)); });
    if (more > 0) { box.insertAdjacentHTML("beforeend", "<p class='muted small forming-more m0' data-forming='more'>and " + more + " more forming on the strip.</p>"); }
    box.querySelectorAll("[data-forming] [data-make]").forEach(function (m) { m.addEventListener("click", function () { var p = m.dataset.make.split(","); makeSheet(parseFloat(p[0]), parseFloat(p[1])); }); });
    box.querySelectorAll("[data-forming] [data-decline]").forEach(function (b) { b.addEventListener("click", function () { decline(b.dataset.decline); }); });
    shown.forEach(function (h) { var card = box.querySelector("[data-forming='" + h.key + "']"); if (card) { sittingBar(card, h.ids); } });
    // The box keeps its margin only while it holds a card.
    box.hidden = !box.children.length;
  }
  function cardHtml(h, d) {
    var bars = d.bars.filter(function (b) { return h.ids.indexOf(b.id) >= 0; });
    var names = bars.map(function (b) { return esc(shortName(b)); });
    var span = (h.to - h.from) || 1;
    var mini = "<div class='mini' aria-hidden='true'>";
    bars.slice(0, 3).forEach(function (b, i) {
      var l = Math.max(0, (b.from - h.from) * 100 / span), w = Math.max(2, (Math.min(b.to, h.to) - Math.max(b.from, h.from)) * 100 / span);
      mini += "<i style='left: " + l + "%; width: " + w + "%; top: " + (4 + i * 6) + "px; background: " + paint(b.colour) + "'></i>";
    });
    (d.marks || []).forEach(function (m) { if (m.seconds >= h.from && m.seconds <= h.to) { mini += "<em style='left: " + ((m.seconds - h.from) * 100 / span) + "%; background: " + paint(m.colour) + "'></em>"; } });
    mini += "</div>";
    var list = names.length > 3 ? names.slice(0, 3).join(", ") + " and " + (names.length - 3) + " more" : names.join(", ");
    return "<div class='card forming-card' data-forming='" + esc(h.key) + "' data-most='" + state.most + "'>" +
      "<div class='h'><b>Forming · " + hm(h.from) + " to " + hm(h.to) + " on " + esc(d.words) + "</b><span class='pill small'>" + plural(h.notes, "note") + "</span></div>" + mini +
      "<div class='small muted'>" + list + " ran together, and the notes gather here. <span data-sitting></span></div>" +
      "<div class='acts'>" + (state.mayMake ? "<button type='button' class='small primary' data-make='" + h.from + "," + h.to + "'>Make it</button><button type='button' class='small choose-myself' data-recordings='" + h.ids.join(" ") + "'>Choose myself</button>" : "") +
      "<button type='button' class='small ghost' data-decline='" + esc(h.key) + "' title='Put this one away; the bracket stays faint on the strip'>Not these</button></div></div>";
  }
  function decline(key) {
    var body = new FormData();
    body.append("key", key);
    body.append("csrfmiddlewaretoken", cookie("csrftoken"));
    fetch(host.dataset.decline, { method: "POST", credentials: "same-origin", headers: { "Accept": "application/json", "X-CSRFToken": cookie("csrftoken") }, body: body })
      .then(function () { load(state.day ? state.day.date : "", null, true); })
      .catch(function () { window.UI.toast("That did not work. Try again.", { problem: true, icon: "warning" }); });
  }

  // The Proposed events tab (v1.169.0): the run's button and words, then
  // the day as the chronology draws it with the proposals as its entries, a
  // lane of the day's notes under the proposed lane, and the proposals on
  // recordings not yet placed under Not yet placed.
  function drawProposed(d) {
    var typed = host.querySelector("#proposed-look-for") ? host.querySelector("#proposed-look-for").value : "";
    var html = proposedLead(d);
    if (d) {
      html += strip() + ruler(d) + band(d) + marksLane(d.marks, "proposed", "prop-lane", true) + marksLane(d.notes_marks || [], "notes", "quiet-lane", false) + incidentsLane(d) + spellsHtml(d);
    } else if (!state.unplaced.length) {
      html += "<p class='muted small'>Nothing waiting. Propose events reads every recording in the case that has a transcript and proposes what it finds; nothing becomes a note until you accept it.</p>";
    }
    html += unplacedHtml();
    host.innerHTML = html;
    var box = host.querySelector("#proposed-look-for");
    if (box && typed) { box.value = typed; }
    wire();
    window.clearTimeout(pollTimer);
    if (state.run && state.run.busy) { pollTimer = window.setTimeout(function () { load(state.day ? state.day.date : "", state.span, true); }, 5000); }
  }
  function proposedLead(d) {
    var r = state.run || {};
    var left = "<span class='row' style='gap: 8px; align-items: center; flex-wrap: wrap'>";
    if (r.on) {
      left += "<button type='button' class='small primary' data-act='propose'" + (r.possible && !r.busy ? "" : " disabled") + " title='Reads every recording in the case that has a transcript: the watch phrases first, then the assistant in stretches with a second look; nothing becomes a note until you accept it'>" + (r.state === "done" ? "Propose again" : "Propose events") + "</button>";
      if (r.assistant) { left += "<input type='text' id='proposed-look-for' class='small' maxlength='300' placeholder='Look for, this run only' aria-label='Look for, this run only' title='With something typed the run reads every recording once and proposes only what bears on it'" + (r.possible && !r.busy ? "" : " disabled") + ">"; }
    }
    left += "<span class='muted small' id='proposed-said'>" + (r.busy && r.expectation && r.expectation.words && window.Expectation ? window.Expectation.html({ step: (r.words || "").replace(/\.\.\.$/, ""), state: r.state, expectation: r.expectation, inline: true }) : esc(r.words || (r.possible === false && r.on ? "Nothing to read yet: no recording has a transcript." : ""))) + "</span></span>";
    var right = "";
    if (d) { right += "<span class='muted small'>" + esc(plural(d.count, "proposed event") + (d.recordings ? " on " + plural(d.recordings, "recording") : "") + (d.span ? ", " + hm(d.ruler.from) + " to " + hm(d.ruler.to) : ", " + d.words)) + "</span> "; }
    if (d && d.span) { right += "<button type='button' class='small' data-act='back'>Back to the day</button> "; }
    if (d && d.fold) { right += "<button type='button' class='small ghost' data-act='open-all'>Open all</button> "; }
    if (r.pending) { right += "<button type='button' class='small ghost' data-act='dismiss-all'" + (r.busy ? " disabled" : "") + " title='Every waiting proposal in the case put away'>Dismiss all</button> <button type='button' class='small ghost' data-act='accept-all'" + (r.busy ? " disabled" : "") + " title='Every waiting proposal in the case written as a note'>Accept all</button>"; }
    return "<div class='lead-row'>" + left + "<span class='row' style='gap: 8px; align-items: center'>" + right + "</span></div>";
  }
  function unplacedHtml() {
    if (!proposed || !state.unplaced.length) { return ""; }
    var html = "<div class='unknown'><div class='sh' style='display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap'><b style='font-family: var(--mono); font-size: 13px'>Not yet placed</b><span class='muted'>" + plural(state.unplaced.length, "proposed event") + " on recordings with no day yet; the time is into the recording.</span>" +
      (state.railOnly.rail_all.length ? "<button type='button' class='small' data-act='sheet' style='margin-left: auto' title='Place these recordings on the clock by date and start, or by the day alone'>Place recordings</button>" : "") + "</div>";
    state.unplaced.forEach(function (e) { html += entry(e); });
    return html + "</div>";
  }
  function proposalEntry(e) {
    var cls = "entry prop" + (e.state === "accepted" ? " done" : "") + (state.lit ? (e.recording === state.lit ? " lit" : " dim") : "");
    var acts = e.state === "accepted"
      ? "<span class='pill small ok'>accepted · " + esc(e.became) + "</span>" + (e.note_url ? "<a class='small' href='" + esc(e.note_url) + "'>Open the note</a>" : "")
      : "<button type='button' class='small primary' data-act='accept' title='The sentence becomes a note on the recording at this moment, in your name'>Accept</button><button type='button' class='small' data-act='accept-edit' title='Write the note in your own words first'>Accept and edit</button><button type='button' class='small ghost' data-act='dismiss' title='Put away; a later run does not offer it again'>Dismiss</button>";
    return "<div class='" + cls + "' data-entry='" + esc(e.key) + "' data-id='" + esc(e.id) + "' data-recording='" + e.recording + "' data-at='" + e.at + "' data-n='" + e.number + "'>" +
      "<span class='num' style='background: " + paint(e.colour) + "'>" + e.number + "</span>" +
      "<div><div class='top'><button type='button' class='t' data-act='play' title='Play the moment, with the lines'>" + (e.time || "the day") + "</button><button type='button' class='play' data-act='play' title='Play the moment'>▶</button>" + (e.how === "day" ? "<span class='pill small'>placed by the day</span>" : "") + "</div>" +
      "<div class='words'>" + esc(e.text) + "</div>" +
      (e.why ? "<div class='why small'>Why it matters: " + esc(e.why) + "</div>" : "") +
      "<div class='line'>" + (e.said ? "“" + esc(e.said) + "”" : "at a moment, nothing said") + " · " + esc(e.title) + "</div>" +
      "<div class='meta'><span class='pill small " + (e.source === "watch" ? "inc" : "warn") + "'>" + esc(e.source_words) + "</span><span class='chip'><i style='background: " + paint(e.colour) + "'></i>" + esc(e.title) + "</span>" +
      (e.for_incident ? "<span class='pill small inc' title='Proposed by a run on this incident'>for " + esc(e.for_incident) + "</span>" : "") +
      (e.incident ? (e.incident.event ? "<span class='pill small inc' title='Its camera is on the incident&#39;s clock; accepted, the note is an event of it'>on a camera of " + esc(e.incident.name) + "</span>" : "<span class='pill small inc' title='Its camera is in the incident but not on its clock yet'>in " + esc(e.incident.name) + ", not synced yet</span>") : "") +
      acts + "</div></div></div>";
  }
  function proposalOf(e) {
    var key = e.dataset.entry;
    var all = (state.day ? state.day.spells.reduce(function (acc, g) { return acc.concat(g.entries); }, []).concat(state.day.unknown || []) : []).concat(state.unplaced);
    var one = all.filter(function (p) { return p.key === key; })[0];
    if (!one) { return null; }
    return { id: one.id, text: one.text, why: one.why, source_words: one.source_words, state: one.state, act: host.dataset.act, done: function () { load(state.day ? state.day.date : "", state.span, true); } };
  }
  function say(words) { var s = host.querySelector("#proposed-said"); if (s && words) { s.textContent = words; } }
  function decide(action, e, text) {
    var body = { action: action };
    if (e) { body.id = e.dataset.id; }
    if (text !== undefined) { body.text = text; }
    return post(host.dataset.act, body).then(function (told) { say(told.said); load(state.day ? state.day.date : "", state.span, true); }).catch(function (err) { window.UI.toast(err.message || "That did not work. Try again.", { problem: true, icon: "warning" }); });
  }
  function acceptEdit(e) {
    var words = e.querySelector(".words"); if (words.querySelector("textarea")) { return; }
    var was = words.textContent;
    words.innerHTML = "<textarea maxlength='2000'></textarea><div class='row' style='gap: 6px; margin-top: 4px'><button type='button' class='small primary' data-save>Accept as written</button><button type='button' class='small' data-cancel>Cancel</button></div>";
    var box = words.querySelector("textarea"); box.value = was; box.focus();
    words.querySelector("[data-cancel]").addEventListener("click", function (ev) { ev.stopPropagation(); words.textContent = was; });
    words.querySelector("[data-save]").addEventListener("click", function (ev) { ev.stopPropagation(); decide("accept_edit", e, box.value); });
  }
  function propose() {
    var box = host.querySelector("#proposed-look-for");
    post(host.dataset.act, { action: "propose", look_for: box ? box.value : "" }).then(function () { load(state.day ? state.day.date : "", state.span, true); }).catch(function (err) { window.UI.toast(err.message || "That did not work. Try again.", { problem: true, icon: "warning" }); });
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
    // The strip's rail (chapter 5) holds the videos with no clock; the
    // chronology's rail every noted recording.
    var rows = d.rail, more = d.rail_more;
    if (stripMode) { rows = (d.rail_all || d.rail).filter(function (one) { return one.video; }); more = 0; }
    if (!rows.length && !more) { return ""; }
    var html = "<div class='rail' id='chron-rail'><span>Not on the clock yet:</span>";
    rows.forEach(function (one) {
      html += "<button type='button' class='chip' draggable='true' data-rail='" + one.id + "' title='Drag onto the ruler, or press to type its time'><i></i>" + esc(one.title) + " · " + plural(one.notes, "note") + "</button>";
    });
    if (more) { html += "<span class='tiny'>and " + more + " more with notes</span>"; }
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
    // The strip has no drag: it reads, the Notes tab looks closer.
    if (stripMode) { return html; }
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
    return "<i class='" + (b.movable ? "movable" : "") + lit + (label ? "" : " narrow") + "' data-bar='" + b.id + "' style='left: " + left + "%; width: " + width + "%; background: " + paint(b.colour) + "' title='" + esc(b.title + " · " + plural(b.notes, "note") + " · " + b.placed + (b.movable ? " · press to move or take off the clock" : " · press to light its notes")) + "'>" + esc(label) + "</i>";
  }

  function legend(d) {
    var parts = [];
    var placed = d.bars.length, byHand = d.bars.filter(function (b) { return b.how === "hand" || b.how === "file" || b.how === "day"; }).length;
    if (d.shape === "coverage") { parts.push("The " + Math.min(8, d.bars.length) + " with the most notes have a bar; press the shade at a moment for every recording running then."); }
    else if (d.shape === "packed") { parts.push(placed + " recordings on the clock, packed into lanes; " + (placed - byHand) + " by clock, " + byHand + " by hand."); }
    else { d.bars.forEach(function (b) { parts.push("<i style='background: " + paint(b.colour) + "'></i>" + esc(b.title) + " · " + esc(b.placed)); }); }
    if (d.shape !== "lanes") { parts.push("Hover a bar for the recording; press it to light its notes."); }
    return "<div class='legend'>" + parts.map(function (p) { return "<span>" + p + "</span>"; }).join("") + "</div>";
  }

  function notesLane(d) { return marksLane(d.marks, "notes", "", true); }
  function marksLane(given, label, cls, live) {
    var d = state.day;
    var html = "<div class='notes-lane " + cls + "'" + (live ? " id='chron-marks'" : "") + ">";
    var marks = (given || []).slice().sort(function (a, b) { return a.seconds - b.seconds; });
    var width = host.clientWidth || 900, px = (d.ruler.to - d.ruler.from) / width;
    var clusters = [];
    marks.forEach(function (m) {
      var last = clusters[clusters.length - 1];
      if (last && (m.seconds - last.last) < 9 * px) { last.items.push(m); last.last = m.seconds; }
      else { clusters.push({ items: [m], first: m.seconds, last: m.seconds }); }
    });
    clusters.forEach(function (c) {
      var mid = (c.first + c.last) / 2;
      if (c.items.length === 1) { html += "<i " + (live ? "data-mark='" + c.items[0].n + "' " : "") + "style='left: " + x(mid, d) + "%; background: " + paint(c.items[0].colour) + "' title='" + (label === "notes" ? "Note " : "Proposed event ") + c.items[0].n + " at " + hms(mid) + "'></i>"; }
      else { html += "<em " + (live ? "data-marks='" + c.items.map(function (m) { return m.n; }).join(",") + "' " : "") + "style='left: " + inside(x(mid, d)) + "%' title='" + c.items.length + " " + label + ", " + hm(c.first) + " to " + hm(c.last) + (live ? "; press to open them" : "") + "'>×" + c.items.length + "</em>"; }
    });
    html += "<span class='lbl'>" + label + "</span></div>";
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
      html += "<div class='spell' data-spell='" + index + "'><div class='sh'><span class='chev'>" + (folded ? "›" : "⌄") + "</span><b>" + esc(title) + "</b><span class='muted'>" + plural(group.notes, proposed ? "proposed event" : "note") + " · " + plural(group.recordings, "recording") + (state.lit ? litWords(group) : "") + "</span>" + (inc ? "<span class='pill small inc' title='" + (proposed ? "Every proposal here is on a camera of this incident" : "Every note here is an event of this incident") + "'>" + esc(inc.name) + "</span>" : "") + "</div>";
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
    if (e.kind === "proposal") { return proposalEntry(e); }
    var cls = "entry" + (state.lit ? (e.recording === state.lit ? " lit" : " dim") : "");
    var under = e.said ? "“" + esc(e.said) + "”" : (e.kind === "event" ? "on the event" + (e.event_time ? " at " + esc(e.event_time) : "") : "at a moment, nothing said");
    return "<div class='" + cls + "' data-entry='" + esc(e.key) + "' data-recording='" + e.recording + "' data-at='" + e.at + "' data-n='" + e.number + "'" + (e.outside ? " data-outside='" + esc(JSON.stringify(e.outside)) + "'" : "") + ">" +
      "<span class='num' style='background: " + paint(e.colour) + "'>" + e.number + "</span>" +
      "<div><div class='top'><button type='button' class='t' data-act='play' title='Play the moment'>" + (e.time || "the day") + "</button><button type='button' class='play' data-act='play' title='Play the moment'>▶</button>" +
      (e.how === "day" ? "<span class='pill small'>placed by the day</span>" : "") + (e.to_check ? "<span class='pill small warn'>To check</span>" : "") + "</div>" +
      "<div class='words' data-act='edit' title='" + (e.kind === "event" ? "A note on an incident&#39;s event: edit it there" : "Press to edit") + "'>" + esc(e.text).replace(/\n/g, "<br>") + "</div>" +
      "<div class='line'>" + under + " · " + esc(e.title) + "</div>" +
      "<div class='meta'><span class='pill small'>" + esc(e.by) + (e.when ? ", " + esc(e.when) : "") + "</span><span class='chip'><i style='background: " + paint(e.colour) + "'></i>" + esc(e.title) + "</span>" +
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
        else if (act === "play") { var e = b.closest(".entry"); if (proposed && window.Preview && window.Preview.open) { window.Preview.open({ recording: e.dataset.recording, seconds: parseFloat(e.dataset.at), from: host, proposed: proposalOf(e) }); } else { open(e.dataset.recording, parseFloat(e.dataset.at)); } light(e); }
        else if (act === "check") { check(b.closest(".entry")); }
        else if (act === "edit") { edit(b.closest(".entry")); }
        else if (act === "propose") { propose(); }
        else if (act === "accept") { decide("accept", b.closest(".entry")); }
        else if (act === "dismiss") { decide("dismiss", b.closest(".entry")); }
        else if (act === "accept-edit") { acceptEdit(b.closest(".entry")); }
        else if (act === "accept-all") { window.UI.confirm({ title: "Write every waiting proposal in the case as a note?", body: "Each becomes a note on its recording in your name; nothing is lost, and a note can be changed or removed where it sits.", ok: "Accept all" }).then(function (yes) { if (yes) { decide("accept_all"); } }); }
        else if (act === "dismiss-all") { decide("dismiss_all"); }
      });
    });
  }

  function railRows() { return state.day && (state.day.rail_all || state.day.rail).length ? (state.day.rail_all || state.day.rail) : state.railOnly.rail_all; }
  function findRail(id) { return railRows().filter(function (one) { return one.id === id; })[0]; }
  // The day to open after a placing: the one typed, else the day shown.
  function afterPlacing(dateTyped) { load(dateTyped || (state.day ? state.day.date : ""), state.span); }
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
    // With no day to borrow from (v1.170.1) the date is typed; a recording
    // is rarely made today, so today is never assumed.
    var day = state.day ? state.day.date : "";
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
        .then(function () { wrap.remove(); afterPlacing(wrap.querySelector("[name=date]").value); })
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
    var rows = railRows();
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
      chain.then(function () { wrap.remove(); afterPlacing(todo.length ? todo[0].body.date : ""); }).catch(function (err) { wrap.querySelector("[data-error]").textContent = err.message; });
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
    }).catch(function () { window.UI.toast("The span could not be read. Try again.", { problem: true, icon: "warning" }); });
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
      .catch(function (err) { window.UI.toast(err.message || "That did not work. Try again.", { problem: true, icon: "warning" }); });
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
      post(url, body).then(function () { load(state.day.date, state.span); }).catch(function (err) { words.textContent = was; window.UI.toast(err.message || "That did not work. Try again.", { problem: true, icon: "warning" }); });
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
  if (proposed) {
    window.CaseProposed = { reload: function () { if (state.loaded) { load(state.day ? state.day.date : "", state.span, true); } } };
    show();
    return;
  }
  // The Incidents tab's strip reads at once and keeps its own global, so
  // the Notes tab's host, mounted first, keeps CaseChronology.
  if (stripMode) {
    window.IncidentStrip = { reload: function () { if (state.loaded) { load(state.day ? state.day.date : "", null, true); } } };
    load("", null);
    return;
  }
  window.CaseChronology = { show: show, reload: function () { if (state.loaded) { load(state.day ? state.day.date : "", state.span); } } };

  var toggle = document.getElementById("notes-shape");
  if (toggle) {
    var rowsOf = host.dataset.rows ? document.querySelectorAll(host.dataset.rows) : [];
    // Three shapes (v1.172.0): Rows, Chronology, and Page, the Notes page
    // drawn inside the tab by notes-page.js when first shown.
    var deskWrap = document.getElementById("case-notes-desk");
    function setShape(shape) {
      if (shape === "page" && !deskWrap) { shape = "rows"; }
      toggle.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b.dataset.shape === shape); });
      var chron = shape === "chronology", pageShape = shape === "page";
      Array.prototype.forEach.call(rowsOf, function (el) { el.hidden = chron || pageShape; });
      host.hidden = !chron;
      if (deskWrap) { deskWrap.hidden = !pageShape; }
      if (chron) { show(); }
      else if (pageShape) {
        var q = new URLSearchParams(location.search); q.set("tab", "notes"); q.set("shape", "page"); q.delete("day"); q.delete("from"); q.delete("to");
        history.replaceState(null, "", location.pathname + "?" + q.toString());
        if (window.NotesPage && window.NotesPage.show) { window.NotesPage.show(); }
      }
      else if (!onNotesPage) { var p = new URLSearchParams(location.search); p.delete("shape"); p.delete("day"); p.delete("from"); p.delete("to"); history.replaceState(null, "", location.pathname + "?" + p.toString()); }
      try { localStorage.setItem(keyShape, shape); } catch (e) { /* no storage */ }
    }
    toggle.addEventListener("click", function (ev) { var b = ev.target.closest("[data-shape]"); if (b) { setShape(b.dataset.shape); } });
    var askedShape = new URLSearchParams(location.search).get("shape");
    var wanted = params().day || askedShape === "chronology" ? "chronology" : (askedShape === "page" ? "page" : null);
    if (!wanted) { try { wanted = localStorage.getItem(keyShape); } catch (e) { wanted = null; } }
    if (wanted === "chronology" || wanted === "page") { setShape(wanted); }
  }
  }

  var notesHost = document.getElementById("case-chronology");
  if (notesHost) { mount(notesHost); }
  var proposedHost = document.getElementById("case-proposed");
  if (proposedHost) { mount(proposedHost); }
  var stripHost = document.getElementById("incident-strip");
  if (stripHost) { mount(stripHost); }
})();

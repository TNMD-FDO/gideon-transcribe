// The guided Speakers page (Phase 5 chapter 3, "The guided page", v1.148.0;
// the drawing docs/spec/mockups/phase-5-speakers-page-redesign.html). One
// question at a time with its context beside it; the guide at the top says
// where you are, what to do now and what comes next, with Back and Undo
// beside the one primary. Every screen is drawn from the check's state
// (the recording's /assistant answer) and the transcript (/segments); every
// act goes through the endpoints the page already had: rename and merge,
// the line's speaker, accept or dismiss a proposal, Sounds like, the unit's
// book, the stages, Undo. Nothing here decides anything by itself.

(function () {
  "use strict";

  var V = window.VIEWER;
  var root = document.getElementById("sg");
  if (!V || !root || !document.getElementById("sg-focus")) { return; }
  var UI = window.UI || { toast: function () {}, icon: function () { return ""; } };
  var cards = JSON.parse(document.getElementById("sg-cards").textContent);

  var el = {
    step: document.getElementById("sg-step"),
    bars: document.getElementById("sg-bars"),
    count: document.getElementById("sg-count"),
    chips: document.getElementById("sg-chips"),
    undo: document.getElementById("sg-undo"),
    back: document.getElementById("sg-back"),
    next: document.getElementById("sg-next"),
    now: document.getElementById("sg-now"),
    focus: document.getElementById("sg-focus"),
    context: document.getElementById("sg-context"),
    play: document.getElementById("sg-play"),
    time: document.getElementById("sg-time"),
    scrub: document.getElementById("sg-scrub"),
    whole: document.getElementById("sg-whole"),
    windowButton: document.getElementById("sg-window"),
    player: document.getElementById("player")
  };

  // What the page holds -------------------------------------------------------

  var state = null;      // the /assistant answer
  var check = {};        // state.speaker_check
  var segments = [];     // the transcript's lines
  var mode = "words";    // "voices" where the voice listened and the run left a stage
  var steps = [];        // the steps of this recording
  var step = 1;          // the step on screen
  var index = 0;         // the voice or the line on screen, inside the step
  var sub = "";          // step 2's first screen ("choice") or the lines ("lines"); step 3's "lines"
  var wholeCall = false; // the context shows every line
  var busy = false;

  // Small helpers --------------------------------------------------------------

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }
  function plural(n, word, words) { return n + " " + (n === 1 ? word : (words || word + "s")); }
  function clock(seconds) {
    var s = Math.max(0, Math.floor(seconds || 0));
    var m = Math.floor(s / 60);
    return m + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
  }
  function send(url, body, asForm) {
    var options = { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") } };
    if (asForm) {
      options.headers["Content-Type"] = "application/x-www-form-urlencoded";
      options.body = new URLSearchParams(body || {});
    } else {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body || {});
    }
    return fetch(url, options).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }, function () { return { ok: answer.ok, said: {} }; });
    }).catch(function () { return { ok: false, said: { error: "The app did not answer." } }; });
  }
  function problem(said, fallback) {
    UI.toast((said && (said.error || said.why)) || fallback || "That was not changed.", { problem: true, icon: "warning" });
  }
  function colourOf(name) {
    var card = cards.find(function (one) { return one.name === name; });
    return card ? card.colour : "";
  }
  function isLabel(name) { return /^Speaker \d+$/.test(name || ""); }
  function shortName(name) { return isLabel(name) ? name : String(name || "").split(" ")[0]; }
  function remember(key, value) { try { sessionStorage.setItem("sg-" + V.recording + "-" + key, String(value)); } catch (e) { /* no storage */ } }
  function recall(key) { try { return sessionStorage.getItem("sg-" + V.recording + "-" + key); } catch (e) { return null; } }

  // The player -------------------------------------------------------------------

  var stopAt = null;
  function play(start, end) {
    if (!el.player) { return; }
    el.player.currentTime = Math.max(0, start || 0);
    stopAt = end || null;
    el.player.play();
  }
  function toggle() {
    if (!el.player) { return; }
    if (el.player.paused) { stopAt = null; el.player.play(); } else { el.player.pause(); }
  }
  function playSamples(card) {
    var samples = card.samples || [];
    if (!samples.length) { return; }
    var i = 0;
    function next() {
      if (i >= samples.length) { el.player.removeEventListener("sg-stopped", next); return; }
      var one = samples[i++];
      play(Math.max(0, one.start - 0.5), one.end + 0.5);
    }
    el.player.addEventListener("sg-stopped", next);
    next();
  }
  if (el.player) {
    el.player.addEventListener("timeupdate", function () {
      if (stopAt !== null && el.player.currentTime >= stopAt) {
        el.player.pause();
        stopAt = null;
        el.player.dispatchEvent(new Event("sg-stopped"));
      }
      if (el.time) { el.time.textContent = clock(el.player.currentTime) + " / " + clock(el.player.duration); }
      if (el.scrub && el.player.duration && !el.scrub.matches(":active")) { el.scrub.value = Math.round(1000 * el.player.currentTime / el.player.duration); }
    });
    el.player.addEventListener("loadedmetadata", function () { if (el.time) { el.time.textContent = "0:00 / " + clock(el.player.duration); } });
    el.player.addEventListener("play", function () { if (el.play) { el.play.innerHTML = UI.icon("pause") + " Pause"; } });
    el.player.addEventListener("pause", function () { if (el.play) { el.play.innerHTML = UI.icon("play") + " Play"; } });
    if (el.play) { el.play.addEventListener("click", toggle); }
    if (el.scrub) { el.scrub.addEventListener("input", function () { if (el.player.duration) { stopAt = null; el.player.currentTime = el.player.duration * el.scrub.value / 1000; } }); }
  }

  // The data -------------------------------------------------------------------------

  function load() {
    return Promise.all([
      fetch("/recording/" + V.recording + "/assistant").then(function (a) { return a.json(); }),
      fetch("/recording/" + V.recording + "/segments?words=0").then(function (a) { return a.json(); })
    ]).then(function (both) {
      state = both[0] || {};
      check = state.speaker_check || {};
      segments = (both[1] && both[1].segments) || [];
      compute();
      render();
    }).catch(function () {
      el.step.textContent = "The check's state could not be read.";
      el.now.textContent = "Reload the page; if it keeps failing, the recording's page still works.";
    });
  }

  function voicesInOrder() {
    var people = cards.filter(function (one) { return !one.system; });
    var unnamed = people.filter(function (one) { return !one.named; });
    var named = people.filter(function (one) { return one.named; });
    return unnamed.concat(named).concat(cards.filter(function (one) { return one.system; }));
  }
  function pendingRows() { return (check.pending || []).slice(); }
  function agreeRows() {
    return pendingRows().filter(function (one) { return one.voice === "agrees" && one.words === "agrees" && one.split_at === null; });
  }

  function compute() {
    mode = check.stage ? "voices" : "words";
    steps = mode === "voices"
      ? [{ name: "Who is speaking" }, { name: "Lines in doubt" }, { name: "Done" }]
      : [{ name: "Who is speaking" }, { name: "The check's proposals" }];
    if (mode === "voices") {
      step = Math.min(Math.max(check.stage, 1), 3);
    } else {
      var kept = parseInt(recall("step") || "", 10);
      var anyUnnamed = cards.some(function (one) { return !one.named && !one.system; });
      step = kept === 2 ? 2 : (anyUnnamed ? 1 : 2);
    }
    var pick = new URLSearchParams(window.location.search).get("pick");
    if (pick && step === 1) {
      var at = voicesOrder().findIndex(function (one) { return one.name === pick; });
      if (at >= 0) { index = at; }
    }
    if (step === 2 && !sub) { sub = (mode === "voices" && agreeRows().length) ? "choice" : "lines"; }
    if (step !== 2 && step !== 3) { sub = ""; }
    index = Math.max(0, index);
    el.undo.hidden = false;
  }
  function voicesOrder() { return voicesInOrder(); }

  // The guide ------------------------------------------------------------------------

  function renderGuide(opts) {
    el.step.textContent = "Step " + step + " of " + steps.length + " · " + steps[step - 1].name;
    el.bars.innerHTML = steps.map(function (one, i) {
      var n = i + 1;
      return "<i class='" + (n < step ? "done" : n === step ? "on" : "") + "'></i>";
    }).join("");
    el.count.textContent = opts.count || "";
    var voices = voicesOrder();
    el.chips.innerHTML = voices.map(function (one, i) {
      var cls = "sg-chip" + (one.system ? " sys" : "") + (one.named ? " done" : "") + (step === 1 && i === index ? " on" : "");
      return "<button type='button' class='" + cls + "' data-voice='" + i + "' style='--speaker: " + escape(one.colour) + "' title='" + escape(one.name) + "'>" + (one.named ? "✓ " : "") + escape(one.system ? "phone system" : one.name) + "</button>";
    }).join("");
    el.now.textContent = opts.now || "";
    el.next.textContent = opts.next || "Next";
    el.next.disabled = !!opts.nextOff;
    el.back.disabled = !!opts.backOff;
    el.next.onclick = opts.onNext || null;
    el.back.onclick = opts.onBack || null;
  }

  // Step 1: one voice at a time ----------------------------------------------------------

  function candidatesFor(card) {
    var out = [];
    var label = card.name;
    var book = check.voice_book || {};
    ((check.voice_matches || {}).matches || []).forEach(function (group) {
      if (group.speaker !== label || group.kind === "side") { return; }
      // Weak in conflict (v1.150.0): two or more people over one voice and
      // none of them better than medium. Such answers never lead the screen;
      // they fold under Choose..., to be heard before anything is pressed.
      var weak = group.kind === "conflict" && group.people.every(function (person) { return person.rating !== "high"; });
      group.people.forEach(function (person) {
        out.push({
          kind: "case", name: person.name, role: person.role, rating: person.rating, weak: weak, cross: !!person.cross_kind,
          why: "their voice on " + plural(person.recordings, "recording") + " of this case" + (group.kind === "conflict" ? " · two of the case's voices claim this one" : "") + (person.caution ? " · " + person.caution : ""),
          heard: person.heard || [],
          act: function () { return send("/voice-match/" + person.id + "/accept").then(function (a) { if (!a.ok) { problem(a.said); return false; } return true; }); }
        });
      });
    });
    (book.checks || []).forEach(function (group) {
      if (group.speaker !== label) { return; }
      if (group.kind === "none") {
        out.push({ kind: "none", name: "No voice in the " + group.unit + " unit's book sounds like this one", why: group.compared + " compared, " + group.at, again: true });
        return;
      }
      group.voices.forEach(function (voice) {
        out.push({
          kind: "book", name: voice.name, role: voice.role, rating: voice.rating,
          why: "the " + group.unit + " unit's known voices, " + plural(voice.cases, "case"),
          heard: voice.heard || [], openable: voice.openable,
          act: function () { return send("/book-check/" + voice.id + "/accept").then(function (a) { if (!a.ok) { problem(a.said); return false; } return true; }); }
        });
      });
    });
    if (book.on && book.can && book.can[label] && !(book.checks || []).some(function (g) { return g.speaker === label; })) {
      out.push({ kind: "bookcheck", unit: book.unit, ok: book.can[label].ok, why: book.can[label].why });
    }
    (state.pending || []).forEach(function (hint) {
      if (hint.speaker !== label || hint.kind !== "name") { return; }
      out.push({ kind: "hint", name: hint.name, why: "at " + clock(hint.start) + ": “" + hint.quote + "” · a name said on the call; the words only, no voice", start: hint.start,
        act: function () { return rename(label, hint.name, ""); } });
    });
    var best = out.findIndex(function (one) { return one.kind === "case" && one.rating === "high"; });
    if (best < 0) { best = out.findIndex(function (one) { return (one.kind === "case" && !one.weak) || one.kind === "book"; }); }
    if (best >= 0) { out[best].best = true; }
    return out;
  }

  function choiceRow(one, i) {
    var pill = one.kind === "hint" ? "<span class='pill small'>a name said on the call</span>" : "<span class='pill small " + (one.rating === "high" ? "ok" : "") + "'>" + ratingWords(one.rating) + "</span>" + (one.cross ? " <span class='pill small warn' title='Taught on another kind of recording'>another kind of recording</span>" : "");
    var button = one.kind === "hint" ? "Use this name" : "It’s " + escape(shortName(one.name));
    return "<div class='sg-choice" + (one.best ? " best" : "") + (one.weak ? " weak" : "") + "' data-candidate='" + i + "'><div><span class='nm'>" + escape(one.name) + "</span> " + (one.role ? "<span class='pill small'>" + escape(one.role) + "</span> " : "") + pill + "<div class='why'>" + escape(one.why) + "</div></div><div class='acts'>" + (one.kind === "hint" ? "<button type='button' class='sg-play tiny' data-start='" + one.start + "' data-end='" + (one.start + 6) + "'>" + UI.icon("play") + "</button>" : hearButtons(one)) + "<button type='button' class='small" + (one.best ? " primary" : "") + " sg-candidate' data-candidate='" + i + "'>" + button + "</button></div></div>";
  }

  function ratingWords(rating) { return rating === "high" ? "sounds very like" : "sounds a bit like"; }

  function hearButtons(candidate) {
    return (candidate.heard || []).slice(0, 1).map(function (one) {
      // The Preview opens as the page's panel (v1.151.0) with the person,
      // their role, a tab per recording that taught the print, and their
      // samples on the recording it plays.
      return "<button type='button' class='sg-prev' data-preview-recording='" + escape(one.recording) + "' data-preview-at='" + one.start + "' data-preview-person='" + escape(candidate.name) + "' data-preview-role='" + escape(candidate.role || "") + "' data-preview-speaker='" + escape(candidate.name) + "' data-preview-tabs='" + escape(JSON.stringify((candidate.heard || []).map(function (h) { return { recording: h.recording, title: h.title, start: h.start }; }))) + "' title='Hear " + escape(candidate.name) + " on " + escape(one.title) + "'>" + UI.icon("play") + " hear " + escape(shortName(candidate.name)) + "</button>";
    }).join("") + (!(candidate.heard || []).length && candidate.kind === "book" && !candidate.openable ? "<span class='pill small' title='The voice is heard only from a recording you may open'>heard on a case you may not open</span>" : "");
  }

  function renderVoice() {
    var voices = voicesOrder();
    if (!voices.length) { el.focus.innerHTML = "<p class='muted'>No voices on this recording.</p>"; return; }
    index = Math.min(index, voices.length - 1);
    var card = voices[index];
    var named = voices.filter(function (one) { return one.named; }).length;
    var total = voices.filter(function (one) { return !one.system; }).length;
    var last = index === voices.length - 1;
    var nextLabel = last ? (mode === "voices" ? "Next: lines in doubt" : "Next: the proposals") : "Next voice";
    var now = card.system
      ? "This is the phone system, not a person. Nothing to name; check its lines if you like."
      : card.named
        ? "This voice is named. Change it if the name is wrong, or go on."
        : "Listen to this voice, then say who it is. Skip it if you are not sure; you can come back.";
    renderGuide({
      count: "Voice " + (index + 1) + " of " + voices.length + " · " + named + " named",
      now: now, next: nextLabel,
      backOff: index === 0,
      onBack: function () { index -= 1; render(); },
      onNext: function () { if (last) { leaveStepOne(); } else { index += 1; render(); } }
    });

    var html = "<div class='sg-h'>" +
      "<button type='button' class='sg-bigplay" + (card.system ? " sys" : "") + "' id='sg-bigplay' title='Play the samples in a row'>" + UI.icon("play") + "</button>" +
      "<div><div class='sg-q' style='--speaker: " + escape(card.colour) + "'><span class='sg-dot'></span>" + escape(card.system ? "The phone system" : card.name) + (card.role ? " <span class='pill small role'>" + escape(card.role) + "</span>" : "") + (card.named ? " <span class='pill small ok'>named</span>" : card.system ? " <span class='pill small'>not a person</span>" : " <span class='pill small warn'>unnamed</span>") + "</div>" +
      "<div class='tiny muted'>" + plural(card.lines, "line") + ", " + escape(card.talking_text) + " talking, first at " + escape(card.first_clock) + "</div></div>" +
      "<span class='sg-lab'>" + escape(card.label) + "</span></div>";
    html += "<div class='sg-samples'>" + (card.samples || []).map(function (one) {
      return "<div class='sg-sample'><button type='button' class='sg-play' data-start='" + one.start + "' data-end='" + one.end + "'>" + UI.icon("play") + " " + escape(one.clock) + "</button><span class='sg-quote'>" + (one.quote ? "“" + escape(one.quote) + "”" : "") + "</span>" + (card.system ? "" : "<button type='button' class='quiet tiny sg-notvoice' data-segment='" + one.id + "' data-start='" + one.start + "' data-end='" + one.end + "' data-quote='" + escape(one.quote) + "'>not this voice</button>") + "</div>";
    }).join("") + "</div>";

    if (card.system) {
      html += "<p class='tiny muted'>Its lines never move, never take a name, and stay out of the check; the memo says the call system announced them.</p>";
    } else if (card.named) {
      html += "<div class='sg-choices'><div class='sg-choice plain'><div>Named <b>" + escape(card.name) + "</b>. Not them?</div><div class='acts'><button type='button' class='small sg-else'>Change...</button></div></div></div>";
    } else {
      var candidates = candidatesFor(card);
      var weak = candidates.filter(function (one) { return one.weak; });
      var leads = candidates.some(function (one) { return one.best; });
      html += "<div class='sg-q small'>Who is this?</div><div class='sg-choices'>";
      candidates.forEach(function (one, i) {
        if (one.weak) { return; }
        if (one.kind === "none") {
          html += "<div class='sg-choice plain'><div>" + escape(one.name) + "<div class='why'>" + escape(one.why) + "</div></div><div class='acts'><button type='button' class='small sg-bookcheck'>Check again</button></div></div>";
        } else if (one.kind === "bookcheck") {
          html += "<div class='sg-choice plain'><div>The " + escape(one.unit) + " unit's known voices" + (one.ok ? "" : "<div class='why'>" + escape(one.why) + "</div>") + "</div><div class='acts'><button type='button' class='small sg-bookcheck'" + (one.ok ? "" : " disabled title='" + escape(one.why) + "'") + ">Check</button></div></div>";
        } else {
          html += choiceRow(one, i);
        }
      });
      // The honest lead (v1.150.0): with no answer better than the weak
      // ones, Choose... is the primary and the weak matches fold under it.
      html += "<div class='sg-choice plain" + (leads ? "" : " best") + "'><div>Someone else, or the same person as another voice</div><div class='acts'><button type='button' class='small" + (leads ? "" : " primary") + " sg-else'>Choose...</button></div></div>";
      if (weak.length) {
        html += "<details class='sg-weak'><summary>" + weak.length + " weak matches in conflict · listen before choosing</summary><div class='sg-choices'>" +
          weak.map(function (one) { return choiceRow(one, candidates.indexOf(one)); }).join("") +
          "<div class='tiny muted'>Two of the case's voices both lean toward this one and neither is sure. Hear each, and hear the samples above, before you press anything.</div></div></details>";
      }
      html += "</div>";
      html += "<div class='sg-walk'><span>Accept names every line of this voice. Undo takes it back.</span><button type='button' class='quiet tiny sg-skip'>Skip this voice</button></div>";
    }
    el.focus.innerHTML = html;
    el.focus.dataset.candidates = "";
    el.focus._candidates = card.system || card.named ? [] : candidatesFor(card);
    el.focus._card = card;
    renderContextForVoice(card);
  }

  function leaveStepOne() {
    if (mode === "voices") {
      setStage(2).then(function (ok) { if (ok) { sub = agreeRows().length ? "choice" : "lines"; index = 0; render(); } });
    } else {
      step = 2; remember("step", 2); sub = "lines"; index = 0; render();
    }
  }

  function setStage(n) {
    busy = true;
    return send("/recording/" + V.recording + "/stage/" + n).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said, "The step could not be moved."); return false; }
      if (a.said.queued === "reading") { UI.toast("The words are reading the lines in doubt against the names; their reading lands in a few seconds.", { icon: "info" }); }
      if (a.said.queued === "words") { UI.toast("The words are reading the whole call against the names.", { icon: "info" }); }
      return reload().then(function () { return true; });
    });
  }

  // Step 2: the lines ------------------------------------------------------------------------

  function renderChoice() {
    var rows = pendingRows();
    var agree = agreeRows();
    var against = rows.filter(function (one) { return one.words === "against"; });
    var unsure = rows.filter(function (one) { return !one.voice; });
    var reading = check.reading || {};
    var notYet = reading.state && reading.state !== "done";
    renderGuide({
      count: plural(rows.length, "line") + " · " + (check.settled || []).length + " decided",
      now: notYet
        ? "The words are reading the " + rows.length + " lines in doubt against the names you gave. Their reading lands in a few seconds; you can start one by one now."
        : "The words read the " + rows.length + " lines against the names you gave. On " + agree.length + " of them the voice and the words agree. Accept those first, or go through them one by one.",
      next: agree.length ? "Accept all " + agree.length : "Go one by one",
      onBack: function () { setStage(1).then(function (ok) { if (ok) { index = 0; render(); } }); },
      onNext: function () { if (agree.length) { acceptMany(agree.map(function (one) { return one.id; })); } else { sub = "lines"; index = 0; render(); } }
    });
    el.focus.innerHTML = "<div class='sg-summary'>" +
      "<div class='sg-stat'><div class='n'>" + agree.length + "</div><div class='w'>voice and words agree</div></div>" +
      "<div class='sg-stat'><div class='n'>" + against.length + "</div><div class='w'>the words read the other way</div></div>" +
      "<div class='sg-stat'><div class='n'>" + unsure.length + "</div><div class='w'>the voice cannot tell</div></div></div>" +
      "<div class='sg-walk'><button type='button' class='small sg-onebyone'>Go one by one instead</button><span>Accepting moves the lines as the number keys do; Undo takes it back.</span></div>";
    el.context.innerHTML = "";
  }

  function acceptMany(ids) {
    busy = true;
    send("/recording/" + V.recording + "/corrections/accept-many", { ids: ids.join(",") }, true).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said); return; }
      UI.toast("Accepted " + plural(ids.length, "line") + ".", { icon: "ok" });
      sub = "lines"; index = 0;
      reload();
    });
  }

  function lineWords(row) {
    var voice = row.voice === "agrees" ? "<b style='--speaker: " + escape(colourOf(row.to)) + "'>" + escape(row.to) + "</b>, near their print"
      : row.voice === "against" ? "<b>" + escape(row.from) + "</b>, not " + escape(row.to)
      : "<span class='pill small'>cannot tell between " + escape(row.from) + " and " + escape(row.to) + "</span>";
    var words = row.words === "agrees" ? "<b>" + escape(row.to) + "</b>" + (row.words_why ? " <span class='muted tiny'>" + escape(row.words_why) + "</span>" : "")
      : row.words === "against" ? "<b>" + escape(row.from) + "</b>" + (row.words_why ? " <span class='muted tiny'>" + escape(row.words_why) + "</span>" : "")
      : row.source === "words" ? "<b>" + escape(row.to) + "</b> <span class='muted tiny'>" + escape(row.reason) + "</span>"
      : "<span class='muted'>not read yet</span>";
    return { voice: voice, words: words };
  }

  function renderLine() {
    var rows = pendingRows();
    if (!rows.length) { renderReceipt(); return; }
    index = Math.min(index, rows.length - 1);
    var row = rows[index];
    var last = index === rows.length - 1;
    var mixed = row.split_at !== null && row.split_at !== undefined;
    var now = mixed ? "This line carries two voices: the second part sounds like " + row.to + ". Split it at the marked word, or leave it."
      : !row.voice && row.source === "voice" ? "The voice cannot tell whose line this is. Listen, then choose."
      : row.words === "against" ? "The voice and the words disagree here. Listen, then say whose line it is."
      : row.source === "words" && !row.voice ? "The check thinks this line was given to the wrong speaker."
      : "The voice says " + row.to + (row.words === "agrees" ? " and the words agree." : ".") + " Listen, then confirm.";
    var decided = (check.settled || []).length;
    renderGuide({
      count: "Line " + (index + 1) + " of " + rows.length + " · " + decided + " decided",
      now: now,
      next: last ? (mode === "voices" && step === 2 ? "Next: done" : "Finish") : "Next line",
      backOff: false,
      onBack: function () {
        if (index > 0) { index -= 1; render(); return; }
        if (mode === "voices" && step === 2 && agreeRows().length) { sub = "choice"; render(); return; }
        if (mode === "voices" && step === 2) { setStage(1).then(function (ok) { if (ok) { index = 0; render(); } }); return; }
        if (mode === "voices" && step === 3) { setStage(2).then(function (ok) { if (ok) { sub = "lines"; index = 0; render(); } }); return; }
        step = 1; remember("step", 1); index = 0; render();
      },
      onNext: function () {
        if (!last) { index += 1; render(); return; }
        if (mode === "voices" && step === 2) { setStage(3).then(function (ok) { if (ok) { sub = ""; index = 0; render(); } }); return; }
        window.location.href = V.backUrl;
      }
    });
    var said = lineWords(row);
    // The clock verdict (v1.151.0): on a marked line the play runs to where
    // the sound is, the clock says what the audio suggests, and a strip
    // under the question shows the window, the line's clock and the sound.
    // A line the re-read placed again (v1.152.0) is a sure line: no strip,
    // the voice's word stands, and the clock line says what it was.
    var verdict = verdictOf(row);
    var retimed = verdict && verdict.retimed ? verdict : null;
    if (retimed) { verdict = null; }
    var playFrom = verdict ? verdict.play_from : Math.max(0, row.start - 0.5);
    var playTo = verdict ? verdict.play_to : segmentEnd(row) + 0.5;
    var clockLine = clock(row.start) + (verdict ? " <span class='sg-about'>· heard about " + clock(verdict.about) + "</span> · plays " + clock(playFrom) + " to " + clock(playTo) : "") + (retimed ? " <span class='sg-about ok'>· clock re-read, was " + clock(retimed.was) + "</span>" : "");
    var html = "<div class='sg-h'><button type='button' class='sg-bigplay sg-play' data-start='" + playFrom + "' data-end='" + playTo + "' title='Play this line" + (verdict ? ", on to where the sound is" : "") + "'>" + UI.icon("play") + "</button><div><div class='sg-q'>Whose line is this?</div><div class='tiny muted mono'>" + clockLine + "</div></div></div>";
    if (verdict) { html += stripHtml(row, verdict, playFrom, playTo); }
    html += "<div class='sg-line here'>" + (mixed ? markedQuote(row) : "“" + escape(row.quote) + "”") + "</div>";
    html += "<div class='sg-sounds'><div class='sg-sound'><span class='k'>now marked</span><span><b>" + escape(row.from) + "</b></span></div>";
    if (verdict) { html += "<div class='sg-sound'><span class='k'>the voice says</span><span class='muted'>nothing: this line’s clock is unsure, so the voice did not measure it</span></div>"; }
    else if (row.source === "voice" || row.voice) { html += "<div class='sg-sound'><span class='k'>the voice says</span><span>" + said.voice + "</span></div>"; }
    html += "<div class='sg-sound'><span class='k'>the words say</span><span>" + said.words + "</span></div></div>";
    html += "<div class='sg-choices'>";
    if (mixed) {
      html += "<div class='sg-choice best'><div><span class='nm'>Split at the word</span><div class='why'>the " + escape(row.split_part) + " part becomes " + escape(row.to) + "'s; Undo puts it back whole</div></div><div class='acts'><button type='button' class='small primary sg-accept'>Split at the word</button></div></div>";
    } else {
      var primaryTo = row.words !== "against";
      html += "<div class='sg-choice" + (primaryTo ? " best" : "") + "'><div><span class='nm' style='--speaker: " + escape(colourOf(row.to)) + "'>" + escape(row.to) + "</span><div class='why'>" + (row.source === "voice" ? "what the voice says" : "what the words say") + "</div></div><div class='acts'>" + sampleButton(row.to) + "<button type='button' class='small" + (primaryTo ? " primary" : "") + " sg-accept'>It’s " + escape(shortName(row.to)) + "</button></div></div>";
      html += "<div class='sg-choice" + (primaryTo ? "" : " best") + "'><div><span class='nm' style='--speaker: " + escape(colourOf(row.from)) + "'>" + escape(row.from) + "</span><div class='why'>as marked now</div></div><div class='acts'>" + sampleButton(row.from) + "<button type='button' class='small" + (primaryTo ? "" : " primary") + " sg-dismiss'>Keep " + escape(shortName(row.from)) + "</button></div></div>";
      html += "<div class='sg-choice plain'><div>Someone else</div><div class='acts'><button type='button' class='small sg-lineelse' data-segment='" + row.segment + "'>Choose...</button></div></div>";
    }
    html += "</div><div class='sg-walk'><button type='button' class='quiet tiny sg-leave'>Leave it for now</button>" + (mode === "words" && pendingRows().some(function (one) { return one.voice === "agrees"; }) ? "<button type='button' class='quiet tiny sg-acceptbacked'>Accept all " + pendingRows().filter(function (one) { return one.voice === "agrees"; }).length + " the voice backs</button>" : "") + "</div>";
    el.focus.innerHTML = html;
    el.focus._row = row;
    renderContextForLine(row);
  }

  function markedQuote(row) {
    var words = (row.quote || "").split(" ");
    var at = row.split_at;
    return "“" + escape(words.slice(0, at).join(" ")) + " <u style='--speaker: " + escape(colourOf(row.to)) + "'>" + escape(words.slice(at).join(" ")) + "</u>”";
  }
  function segmentEnd(row) {
    var seg = segments.find(function (one) { return one.id === row.segment; });
    return seg ? seg.end : row.start + 5;
  }
  // The clock verdict of a line (v1.151.0), from the segments the page read.
  function verdictOf(row) {
    var seg = segments.find(function (one) { return one.id === row.segment; });
    return seg && seg.clock ? seg.clock : null;
  }
  // The sound strip under a marked line's question: the window being played
  // as a bar, the line's own clock marked, and where the sound is lit.
  function stripHtml(row, verdict, from, to) {
    var span = Math.max(1, to - from);
    function pct(t) { return Math.max(0, Math.min(100, 100 * (t - from) / span)); }
    var hole = verdict.hole && verdict.hole.length === 2 ? verdict.hole : [verdict.about, verdict.to];
    return "<div class='sg-strip' aria-hidden='true'><div class='bar'>" +
      "<i class='sound' style='left: " + pct(hole[0]).toFixed(1) + "%; width: " + (pct(hole[1]) - pct(hole[0])).toFixed(1) + "%'></i>" +
      "<b class='own' style='left: " + pct(row.start).toFixed(1) + "%'></b></div>" +
      "<div class='scale mono'><span>" + clock(from) + "</span><span>the line’s clock</span><span>where the sound is</span><span>" + clock(to) + "</span></div>" +
      "<span class='pill small warn'>clock unsure · up to " + Math.round(verdict.bound) + " s early</span></div>";
  }
  function sampleButton(name) {
    var card = cards.find(function (one) { return one.name === name; });
    var sample = card && card.samples && card.samples[0];
    if (!sample) { return ""; }
    return "<button type='button' class='sg-prev sg-play' data-start='" + Math.max(0, sample.start - 0.5) + "' data-end='" + (sample.end + 0.5) + "' title='Hear " + escape(name) + "'>" + UI.icon("play") + " hear " + escape(shortName(name)) + "</button>";
  }

  function decideLine(verdict) {
    var row = el.focus._row;
    if (!row || busy) { return; }
    busy = true;
    send("/recording/" + V.recording + "/corrections/" + verdict + "-many", { ids: row.id }, true).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said); return; }
      UI.toast(verdict === "accept" ? (row.split_at !== null && row.split_at !== undefined ? "Split at the word." : "Given to " + row.to + ".") : "Kept as " + row.from + ".", { icon: "ok" });
      reload();
    });
  }

  // Step 3 and the words-first end: the receipt ------------------------------------------------

  function renderReceipt() {
    var voices = voicesOrder().filter(function (one) { return !one.system; });
    var named = voices.filter(function (one) { return one.named; }).length;
    var settled = (check.settled || []).length;
    var left = pendingRows().length;
    var checked = check.reading && check.reading.state === "done";
    var neverRan = !check.stage && !settled && !left && !(check.offered || []).length;
    renderGuide({
      count: mode === "voices" ? "checked against the names" : (neverRan ? "the check has not run" : plural(left, "line") + " left"),
      now: neverRan ? "The check has not run on this recording yet. Run it, or finish with the names as they are."
        : left ? "There " + (left === 1 ? "is " : "are ") + plural(left, "line") + " still to look at. Look at " + (left === 1 ? "it" : "them") + " now, or finish and come back later."
        : "Nothing is left to decide. Finish, or run the check again with the names as they stand.",
      next: "Finish",
      onBack: function () {
        if (mode === "voices") { setStage(2).then(function (ok) { if (ok) { sub = "lines"; index = 0; render(); } }); }
        else { step = 1; remember("step", 1); index = 0; render(); }
      },
      onNext: function () { window.location.href = V.backUrl; }
    });
    var html = "<div class='sg-summary'>" +
      "<div class='sg-stat'><div class='n'>" + named + " of " + voices.length + "</div><div class='w'>voices named</div></div>" +
      "<div class='sg-stat'><div class='n'>" + settled + "</div><div class='w'>lines decided</div></div>" +
      "<div class='sg-stat'><div class='n'>" + left + "</div><div class='w'>left to look at</div></div>" +
      (checked ? "<div class='sg-stat'><div class='n'>" + ((check.doubt || {}).agree || 0) + "</div><div class='w'>voice and words agreed</div></div>" : "") +
      "</div>";
    html += "<div class='sg-walk'>" + (left ? "<button type='button' class='small primary sg-lookleft'>Look at the " + left + " left, one by one</button>" : "") +
      (V.assistant && V.assistant.speakerCheck ? "<button type='button' class='quiet tiny sg-runagain'>" + (neverRan ? "Run the check" : "Run the check again") + "</button>" : "") +
      (left ? "<span>The recording page's pill reads “" + plural(left, "line") + " to look at” until they are decided or left.</span>" : "") + "</div>";
    el.focus.innerHTML = html;
    el.context.innerHTML = "";
    sub = "";
  }

  // The context --------------------------------------------------------------------------------------

  function lineHtml(seg, cls) {
    // A line whose clock is unsure (v1.151.0) carries a dotted rule and,
    // at the head of its block, the clock the audio suggests.
    var mark = seg.clock ? (seg.clock.retimed ? " retimed" : " unsure") : "";
    var about = seg.clock && seg.clock.head ? (seg.clock.retimed ? " <span class='sg-about ok'>was " + clock(seg.clock.was) + "</span>" : " <span class='sg-about'>→ ~" + clock(seg.clock.about) + "</span>") : "";
    return "<div class='sg-ctx-line " + cls + mark + "' data-start='" + (seg.clock ? seg.clock.play_from : seg.start) + "' data-end='" + (seg.clock ? seg.clock.play_to : seg.end) + "'><span class='t'>" + clock(seg.start) + about + "</span><span class='s' style='--speaker: " + escape(colourOf(seg.speaker)) + "'>" + escape(seg.speaker) + "</span><span>" + escape(seg.text) + "</span></div>";
  }
  function renderContextForVoice(card) {
    if (!segments.length) { el.context.innerHTML = ""; return; }
    var html = "<div class='sg-label'>" + (wholeCall ? "The whole call" : "This voice’s lines, in the call") + "</div>";
    var shown = 0;
    if (wholeCall) {
      html += segments.map(function (seg) { return lineHtml(seg, seg.speaker === card.name ? "lit" : "dim"); }).join("");
    } else {
      var keep = segments.map(function (seg, i) {
        return seg.speaker === card.name || (segments[i - 1] && segments[i - 1].speaker === card.name) || (segments[i + 1] && segments[i + 1].speaker === card.name);
      });
      var gapFrom = null;
      segments.forEach(function (seg, i) {
        if (keep[i]) {
          if (gapFrom !== null) { html += "<div class='sg-gap'>" + clock(gapFrom) + " to " + clock(seg.start) + ", the others</div>"; gapFrom = null; }
          html += lineHtml(seg, seg.speaker === card.name ? "lit" : "dim");
          shown += 1;
        } else if (gapFrom === null) { gapFrom = seg.start; }
      });
      if (gapFrom !== null) { html += "<div class='sg-gap'>" + clock(gapFrom) + " to the end, the others</div>"; }
    }
    el.context.innerHTML = html;
    var lit = el.context.querySelector(".lit");
    if (lit) { lit.scrollIntoView({ block: "nearest" }); }
  }
  function renderContextForLine(row) {
    if (!segments.length) { el.context.innerHTML = ""; return; }
    var at = segments.findIndex(function (one) { return one.id === row.segment; });
    var html = "<div class='sg-label'>" + (wholeCall ? "The whole call" : "Around this line") + "</div>";
    var from = wholeCall ? 0 : Math.max(0, at - 2);
    var to = wholeCall ? segments.length : Math.min(segments.length, at + 3);
    html += segments.slice(from, to).map(function (seg) { return lineHtml(seg, seg.id === row.segment ? "here" : "dim"); }).join("");
    el.context.innerHTML = html;
    var here = el.context.querySelector(".here");
    if (here) { here.scrollIntoView({ block: "center" }); }
  }

  // Render ---------------------------------------------------------------------------------------------

  function render() {
    if (step === 1) { renderVoice(); return; }
    if (step === 2 && mode === "voices" && sub === "choice") { renderChoice(); return; }
    if (step === 2) { renderLine(); return; }
    if (sub === "lines") { renderLine(); return; }
    renderReceipt();
  }

  function reload() {
    return load();
  }

  // The acts -------------------------------------------------------------------------------------------

  function rename(from, to, role) {
    busy = true;
    return send("/recording/" + V.recording + "/speakers", { from: from, to: to, role: role || "" }).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said); return false; }
      UI.toast("Named " + to + ".", { icon: "ok" });
      return true;
    });
  }
  function merge(from, onto) {
    busy = true;
    return send("/recording/" + V.recording + "/speakers", { from: from, to: onto }).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said); return false; }
      UI.toast(from + " merged into " + onto + ".", { icon: "ok" });
      return true;
    });
  }
  function giveLine(segmentId, name, role) {
    busy = true;
    return send("/recording/" + V.recording + "/segment/" + segmentId + "/speaker", { speaker: name, role: role || "" }).then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said); return false; }
      UI.toast("Given to " + name + ".", { icon: "ok" });
      return true;
    });
  }
  function afterNaming(ok) {
    if (!ok) { return; }
    reloadCards().then(function () { reload(); });
  }
  function reloadCards() {
    // The cards come with the page; a name changes them, so the page is
    // loaded again at this voice, as the old page did (reloadHere).
    var voices = voicesOrder();
    var pick = voices[Math.min(index, voices.length - 1)];
    window.location.replace(window.location.pathname + "?pick=" + encodeURIComponent(pick ? pick.name : ""));
    return new Promise(function () {});
  }

  function openPicker(options) {
    if (!window.Picker) { UI.toast("The picker did not load.", { problem: true }); return; }
    window.Picker.open(Object.assign({
      recording: V.recording,
      anchor: el.focus,
      beside: el.focus,
      play: function (start, end) { play(start, end); },
      manageUrl: ""
    }, options));
  }

  el.focus.addEventListener("click", function (event) {
    var card = el.focus._card;
    var playButton = event.target.closest(".sg-play");
    if (playButton) { play(parseFloat(playButton.dataset.start), parseFloat(playButton.dataset.end)); return; }
    if (event.target.closest("#sg-bigplay") && card) { playSamples(card); return; }
    var candidate = event.target.closest(".sg-candidate");
    if (candidate && !busy) {
      var one = (el.focus._candidates || [])[parseInt(candidate.dataset.candidate, 10)];
      if (!one) { return; }
      candidate.disabled = true;
      one.act().then(afterNaming);
      return;
    }
    if (event.target.closest(".sg-bookcheck") && card && !busy) {
      busy = true;
      UI.toast("Comparing with the unit's voices…", { icon: "info" });
      send("/recording/" + V.recording + "/book-check", { speaker: card.name }).then(function (a) { busy = false; if (!a.ok) { problem(a.said); return; } reload(); });
      return;
    }
    if (event.target.closest(".sg-skip")) { index += 1; render(); return; }
    if (event.target.closest(".sg-else") && card) {
      openPicker({
        question: card.name + " is",
        current: card.name,
        newSpeaker: true,
        newGo: "Name",
        onPick: function (picked, role) {
          if (!picked) { return; }
          var onCall = cards.some(function (c) { return c.name === picked && c.name !== card.name; });
          return (onCall ? merge(card.name, picked) : rename(card.name, picked, role)).then(afterNaming);
        }
      });
      return;
    }
    var notVoice = event.target.closest(".sg-notvoice");
    if (notVoice && card) {
      openPicker({
        question: "Whose line is this?",
        quote: notVoice.dataset.quote,
        current: card.name,
        newSpeaker: true,
        onPick: function (picked, role) { return giveLine(notVoice.dataset.segment, picked, role).then(afterNaming); }
      });
      return;
    }
    if (event.target.closest(".sg-accept")) { decideLine("accept"); return; }
    if (event.target.closest(".sg-dismiss")) { decideLine("dismiss"); return; }
    if (event.target.closest(".sg-leave")) { var rows = pendingRows(); if (index < rows.length - 1) { index += 1; render(); } else { el.next.click(); } return; }
    if (event.target.closest(".sg-onebyone")) { sub = "lines"; index = 0; render(); return; }
    if (event.target.closest(".sg-acceptbacked")) { acceptMany(pendingRows().filter(function (one) { return one.voice === "agrees"; }).map(function (one) { return one.id; })); return; }
    if (event.target.closest(".sg-lookleft")) { sub = "lines"; index = 0; render(); return; }
    if (event.target.closest(".sg-runagain") && !busy) {
      busy = true;
      send("/recording/" + V.recording + "/speaker-check").then(function (a) { busy = false; if (!a.ok) { problem(a.said, "The check could not be started."); return; } UI.toast("Checking the speakers… the result lands here.", { icon: "info" }); setTimeout(reload, 4000); });
      return;
    }
    var lineElse = event.target.closest(".sg-lineelse");
    if (lineElse) {
      var row = el.focus._row;
      openPicker({
        question: "Whose line is this?",
        quote: row ? row.quote : "",
        current: row ? row.from : "",
        newSpeaker: true,
        onPick: function (picked, role) { return giveLine(lineElse.dataset.segment, picked, role).then(function (ok) { if (ok) { reload(); } }); }
      });
    }
  });

  el.context.addEventListener("click", function (event) {
    var line = event.target.closest(".sg-ctx-line");
    if (line) { play(parseFloat(line.dataset.start), parseFloat(line.dataset.end)); }
  });

  el.chips.addEventListener("click", function (event) {
    var chip = event.target.closest(".sg-chip");
    if (!chip) { return; }
    var go = function () { step = 1; sub = ""; index = parseInt(chip.dataset.voice, 10); render(); };
    if (mode === "voices" && step !== 1) { setStage(1).then(function (ok) { if (ok) { go(); } }); } else { remember("step", 1); go(); }
  });

  el.undo.addEventListener("click", function () {
    if (busy) { return; }
    busy = true;
    send("/recording/" + V.recording + "/speakers/undo").then(function (a) {
      busy = false;
      if (!a.ok) { problem(a.said, "Nothing to undo."); return; }
      UI.toast("Undone.", { icon: "ok" });
      if (step === 1) { reloadCards(); } else { reload(); }
    });
  });

  if (el.whole) {
    el.whole.addEventListener("click", function () {
      wholeCall = !wholeCall;
      el.whole.textContent = wholeCall ? "Show only what bears on this" : "Show the whole call";
      render();
    });
  }
  if (el.windowButton) {
    el.windowButton.addEventListener("click", function () {
      window.open(el.windowButton.dataset.href + "?t=" + Math.floor(el.player ? el.player.currentTime : 0), "transcribe-" + V.recording + "-speakers", "popup,width=1100,height=800");
    });
  }

  document.addEventListener("keydown", function (event) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName) || document.querySelector(".picker")) { return; }
    if (event.key === " ") { event.preventDefault(); toggle(); return; }
    if (event.key === "ArrowRight" && !el.next.disabled) { el.next.click(); return; }
    if (event.key === "ArrowLeft" && !el.back.disabled) { el.back.click(); return; }
    if (/^[1-9]$/.test(event.key)) {
      var buttons = el.focus.querySelectorAll(".sg-candidate, .sg-accept, .sg-dismiss");
      var button = buttons[parseInt(event.key, 10) - 1];
      if (button) { button.click(); }
    }
  });

  load();
})();

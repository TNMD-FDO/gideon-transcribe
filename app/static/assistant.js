// The AI assistant in the viewer: the Summary, Chat and Moments panels on the
// Bench and Suggest names in the Speakers panel. Everything here reads one state answer
// from the app and sends one request per thing a person does; the calls
// themselves run on llm-worker and this page polls every two seconds while
// anything is in progress, then stops. Nothing is streamed: an answer arrives
// whole. A time in an answer that the app matched to a segment is a Citation,
// a link that seeks the player; an unmatched time stays as text.

(function () {
  "use strict";

  if (!window.VIEWER || !window.VIEWER.assistant) { return; }
  var features = window.VIEWER.assistant;
  var recording = window.VIEWER.recording;
  var EVERY = 2000;

  var summaryList = document.getElementById("summary-list");
  var suggestLine = document.getElementById("suggest-line");
  var suggestionList = document.getElementById("suggestions");
  var momentList = document.getElementById("moment-list");
  var cueList = document.getElementById("cue-list");
  var describeNow = document.getElementById("describe-now");
  var findMoments = document.getElementById("find-moments");
  var findSaid = document.getElementById("find-said");
  var describeIntervals = document.getElementById("describe-intervals");
  var intervalsSaid = document.getElementById("intervals-said");
  var intervalsNote = document.getElementById("intervals-note");
  var momentsSaid = document.getElementById("moments-said");
  var momentsHeading = document.getElementById("moments-heading");

  var state = null;
  var timer = null;

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken"), "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  // Text with its Citations as links. Only the times the app matched become
  // links; the pattern is the chapter's [hh:mm:ss].
  function withCitations(text, citations) {
    return escape(text).replace(/\[(\d{1,2}):(\d{2}):(\d{2})\]/g, function (whole) {
      if (citations && Object.prototype.hasOwnProperty.call(citations, whole)) {
        return "<a href='#' class='cite' data-seconds='" + citations[whole] + "'>" + whole + "</a>";
      }
      return whole;
    });
  }

  document.addEventListener("click", function (event) {
    var cite = event.target.closest(".cite");
    if (!cite || cite.classList.contains("play")) { return; }
    event.preventDefault();
    window.VIEWER.seek(parseFloat(cite.dataset.seconds));
    window.VIEWER.play();
    if (window.VIEWER.showSegment) { window.VIEWER.showSegment(parseFloat(cite.dataset.seconds)); }
  });

  function paragraphs(text, citations) {
    return text.split(/\n+/).filter(function (line) { return line.trim(); }).map(function (line) {
      return "<p>" + withCitations(line, citations) + "</p>";
    }).join("");
  }

  function unavailable(button) {
    if (!state) { return; }
    button.disabled = !state.reachable;
    button.title = state.reachable ? "" : state.unavailable_line;
  }

  // A time as the Chat shows one: the clock alone today, the day before it
  // otherwise, in the browser's own zone (the same as chat-ui.js).
  function when(iso) {
    if (!iso) { return ""; }
    var date = new Date(iso);
    if (isNaN(date.getTime())) { return ""; }
    var today = new Date();
    var sameDay = date.toDateString() === today.toDateString();
    var time = date.toTimeString().slice(0, 5);
    if (sameDay) { return time; }
    return date.getDate() + " " + date.toLocaleString(undefined, { month: "short" }) + " " + time;
  }

  // Summaries -------------------------------------------------------------------

  var newSummary = document.getElementById("new-summary");
  var summaryDialog = document.getElementById("summary-dialog");

  function drawSummaries() {
    if (!summaryList || !state) { return; }
    if (newSummary) { unavailable(newSummary); }
    var templateChoice = document.getElementById("summary-template");
    if (templateChoice) {
      templateChoice.innerHTML = state.templates.map(function (one) {
        return "<option value='" + one.id + "'" +
          (one.id === state.default_template ? " selected" : "") + ">" +
          escape(one.name) + (one.description ? " (" + escape(one.description) + ")" : "") + "</option>";
      }).join("");
      document.getElementById("summary-template-line").hidden = state.templates.length < 2;
      // Why this one: the recording's type chose it.
      var typeLine = document.getElementById("summary-type-line");
      if (typeLine) {
        typeLine.textContent = state.type_line || "";
        typeLine.hidden = !state.type_line;
      }
    }
    if (!state.summaries.length) {
      summaryList.innerHTML = "<p class='muted small'>No summaries yet. New summary reads the whole transcript and writes one.</p>";
      return;
    }
    summaryList.innerHTML = state.summaries.map(function (one) {
      var head = "<div class='row'><b class='grow'>" + escape(one.template) + "</b>" +
        "<span class='muted small'>" + escape(one.length) +
        (one.focus ? " · focus: " + escape(one.focus) : "") + " · " + escape(one.when) + "</span></div>";
      var body;
      if (one.state === "queued" || one.state === "running") {
        var looking = state.cue_runs && state.cue_runs.interval;
        if (one.describe_first && looking && (looking.state === "queued" || looking.state === "running")) {
          body = "<p class='muted'>Looking at the picture first" + (looking.total ? " (" + looking.found + " of " + looking.total + ")" : "") + "...</p>";
        } else {
          body = "<p class='muted'>Reading the transcript...</p>";
        }
      } else if (one.state === "failed") {
        body = "<p class='problem'>" + escape(one.said) + "</p>";
      } else {
        body = (one.notice ? "<p class='notice small'>" + escape(one.notice) + "</p>" : "") +
          (one.earlier ? "<p class='muted small'>" + escape(one.earlier) + "</p>" : "") +
          "<div class='answer'>" + paragraphs(one.text, one.citations) + "</div>" +
          (one.cut_short ? "<p class='muted small'>The answer was cut short.</p>" : "");
      }
      var tools = "<div class='row' style='margin-top:6px'>" +
        (one.state === "done" ? "<a class='btn small' href='/summary/" + one.id + "/export'>Export to Word</a>" : "") +
        "<button type='button' class='small regenerate' data-summary='" + one.id + "'>Regenerate</button>" +
        "<span class='grow'></span>" +
        "<button type='button' class='small ghost danger delete-summary' data-summary='" + one.id + "'>Delete</button></div>";
      return "<div class='card summary'>" + head + body + tools + "</div>";
    }).join("");
    Array.prototype.forEach.call(summaryList.querySelectorAll(".regenerate"), unavailable);
  }

  if (newSummary && summaryDialog) {
    newSummary.addEventListener("click", function () {
      summaryDialog.hidden = !summaryDialog.hidden;
      if (!summaryDialog.hidden) { document.getElementById("summary-focus").focus(); }
    });
    document.getElementById("summary-cancel").addEventListener("click", function () {
      summaryDialog.hidden = true;
    });
    document.getElementById("summary-write").addEventListener("click", function () {
      var templateChoice = document.getElementById("summary-template");
      var describeFirst = document.getElementById("summary-describe-first");
      post("/recording/" + recording + "/summaries", {
        template: templateChoice ? templateChoice.value : "",
        focus: document.getElementById("summary-focus").value,
        length: document.getElementById("summary-length").value,
        describe_first: !!(describeFirst && describeFirst.checked)
      }).then(function () {
        summaryDialog.hidden = true;
        document.getElementById("summary-focus").value = "";
        refresh();
      });
    });
  }

  if (summaryList) {
    summaryList.addEventListener("click", function (event) {
      var again = event.target.closest(".regenerate");
      if (again) {
        UI.confirm({ title: "Write this summary again?", body: "The summary here is replaced by a new one with the same choices.", ok: "Write it again" })
          .then(function (yes) { if (yes) { post("/summary/" + again.dataset.summary + "/regenerate").then(refresh); } });
        return;
      }
      var gone = event.target.closest(".delete-summary");
      if (gone) {
        UI.confirm({ title: "Delete this summary?", body: "Export it first to keep a copy.", ok: "Delete summary", danger: true })
          .then(function (yes) { if (yes) { post("/summary/" + gone.dataset.summary + "/delete").then(refresh); } });
      }
    });
  }

  // Chat --------------------------------------------------------------------------
  // The shared component draws it; this page owns the state and the polling.

  var chat = null;
  var chatRoot = document.getElementById("chat-root");
  if (chatRoot && window.ChatUI) {
    chat = window.ChatUI.mount(chatRoot, {
      citationPattern: /\[(\d{1,2}):(\d{2}):(\d{2})\]/g,
      citation: function (whole, citations) {
        if (!Object.prototype.hasOwnProperty.call(citations, whole)) { return null; }
        var seconds = citations[whole];
        var line = "";
        (window.VIEWER.segments() || []).some(function (segment) {
          if (Math.floor(segment.start) === Math.floor(seconds)) {
            line = (segment.speaker ? segment.speaker + ": " : "") + segment.text;
            return true;
          }
          return false;
        });
        return { clock: whole.slice(1, -1), seconds: seconds, line: line };
      },
      onCite: function (seconds) {
        window.VIEWER.seek(seconds);
        window.VIEWER.play();
        if (window.VIEWER.showSegment) { window.VIEWER.showSegment(seconds); }
      },
      grounding: function () { return "Answers come from this transcript only, not from any other recording."; },
      readingLine: function () { return "Reading the transcript..."; },
      expectation: "usually 5 to 20 seconds",
      placeholder: "Ask anything about this recording",
      crossLink: window.VIEWER.caseChatUrl
        ? { text: "Ask about the whole case instead.", href: window.VIEWER.caseChatUrl }
        : null,
      exportHref: function (chatId) { return "/chat/" + chatId + "/export"; },
      newChat: function () {
        return post("/recording/" + recording + "/chats").then(function (answer) {
          return answer.ok ? answer.said.id : null;
        });
      },
      ask: function (chatId, question) { return post("/chat/" + chatId + "/ask", { question: question }); },
      remove: function (chatId) { return post("/chat/" + chatId + "/delete"); },
      refresh: function () { return refresh(); }
    });
  }

  function drawChat() {
    if (!chat || !state) { return; }
    chat.update({
      reachable: state.reachable,
      unavailable_line: state.unavailable_line,
      chats: state.chats || [],
      starters: state.starters || [],
      busy: state.busy
    });
  }

  // Opening the Chat panel puts the cursor in the box.
  document.addEventListener("click", function (event) {
    var tab = event.target.closest(".sheet-tab[data-panel='chat']");
    if (tab && chat) { window.setTimeout(chat.focus, 50); }
  });

  // Speaker suggestions -------------------------------------------------------------

  function drawSuggestions() {
    if (!suggestLine || !state) { return; }
    var show = features.suggestions && state.unnamed && state.unnamed.length >= 2;
    suggestLine.hidden = !show;
    var button = document.getElementById("suggest-names");
    var said = document.getElementById("suggest-said");
    var run = state.suggestion_run;
    if (button) {
      unavailable(button);
      if (run && (run.state === "queued" || run.state === "running")) {
        button.disabled = true;
        said.textContent = "Reading the transcript...";
      } else if (run && run.state === "failed") {
        said.textContent = run.said;
      } else if (run && run.state === "done" && !state.pending.length) {
        said.textContent = "Nothing in the transcript shows who these speakers are.";
      } else {
        said.textContent = "";
      }
    }

    // The pending suggestions, each with its reason, and the dashed pill on
    // the speaker's first segment.
    Array.prototype.forEach.call(document.querySelectorAll(".pill.suggested"), function (pill) {
      pill.remove();
    });
    if (!suggestionList) { return; }
    suggestionList.innerHTML = state.pending.map(function (one) {
      return "<li class='suggestion' title='" + escape(one.quote) + " at " + escape(one.clock) + "'>" +
        "<span class='grow'><b>" + escape(one.speaker) + "</b> " + window.VIEWER.icon("forward") + " " + escape(one.name) + (one.role ? " (" + escape(one.role) + ")" : "") +
        " <span class='muted small'>(" + escape(one.confidence) + ", " + escape(one.kind) + ")</span>" +
        "<br><span class='muted small'>“" + escape(one.quote) + "” <a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a></span></span>" +
        "<button type='button' class='small accept' data-suggestion='" + one.id + "'>Accept</button>" +
        "<button type='button' class='small ghost reject' data-suggestion='" + one.id + "'>Reject</button></li>";
    }).join("");
    state.pending.forEach(function (one) {
      var rows = document.querySelectorAll("#transcript .seg .name");
      for (var i = 0; i < rows.length; i += 1) {
        if (rows[i].textContent.trim() === one.speaker) {
          var pill = document.createElement("span");
          pill.className = "pill side suggested";
          pill.textContent = "Suggested: " + one.name + (one.role ? " (" + one.role + ")" : "");
          pill.title = one.quote + " at " + one.clock;
          rows[i].parentNode.insertBefore(pill, rows[i].nextSibling);
          break;
        }
      }
    });
  }

  if (suggestLine) {
    document.getElementById("suggest-names").addEventListener("click", function () {
      post("/recording/" + recording + "/suggest").then(refresh);
    });
    suggestionList.addEventListener("click", function (event) {
      var accept = event.target.closest(".accept");
      var reject = event.target.closest(".reject");
      var button = accept || reject;
      if (!button) { return; }
      button.disabled = true;
      post("/suggestion/" + button.dataset.suggestion + "/" + (accept ? "accept" : "reject"))
        .then(function () {
          // Accept renamed every segment of that speaker: the rows, the
          // chips and the colours all change, so the page is loaded again.
          if (accept) { window.location.reload(); } else { refresh(); }
        });
    });
  }

  // Moments -------------------------------------------------------------------------
  // What the camera showed at a time. Two panels: the first the head, the
  // whole-recording presses and the cue lines; the second the Moments kept.
  // The rows carry a describe button each, a Camera? button on a cue line,
  // and a camera line under the row nearest each described Moment.

  var momentsOn = !!(features.moments && window.VIEWER.isVideo);

  function describe(body) {
    return post("/recording/" + recording + "/moments", body).then(function (answer) {
      if (!answer.ok && answer.said && answer.said.error) {
        UI.toast(answer.said.error, { problem: true, icon: "warning" });
      }
      return refresh();
    });
  }

  // "every minute", "every 2 minutes", "every 90 seconds": the interval in words.
  function everyWord(seconds) {
    var n = Number(seconds);
    if (!n || n <= 0) { return "at regular intervals"; }
    if (n % 60 === 0) {
      var minutes = n / 60;
      return minutes === 1 ? "every minute" : "every " + minutes + " minutes";
    }
    return "every " + n + " seconds";
  }

  // How sure a finder was, in plain words.
  function sureWord(confidence) {
    if (confidence === "high") { return "sure"; }
    if (confidence === "medium") { return "fairly sure"; }
    if (confidence === "low") { return "unsure"; }
    return confidence;
  }

  // What Describe the whole recording would do now, in numbers, from the
  // state's cue_runs.intervals; the template's own words until it arrives.
  // The summary form is the tick's note in the summary dialog.
  function intervalsLine(summary) {
    var intervals = state && state.cue_runs && state.cue_runs.intervals;
    if (!intervals) {
      return summary
        ? "A description at regular intervals (one engine call each) before the summary is written, so it can say what the camera showed."
        : "A description at regular intervals through the recording, one engine call each. Times already described are skipped.";
    }
    var every = everyWord(intervals.every);
    if (summary) {
      if (intervals.count === 0) {
        return "Every interval is described already, so the summary can say what the camera showed without waiting.";
      }
      return "A description " + every + " (" + intervals.count + " for this recording, one engine call each) before the summary is written, so it can say what the camera showed.";
    }
    return "A description " + every + ", " + intervals.count + " in all for this recording, one engine call each. Times already described are skipped.";
  }

  // One box for both: empty means describe the clip, words mean a question
  // answered from a few frames at the camera's own detail.
  function askOrDescribe(body) {
    UI.prompt({
      title: "Describe the picture at " + window.VIEWER.clock(body.at),
      body: "Leave the box empty to have the picture described. Or type a question about it, such as \"what is on the passenger seat?\", and the answer says what is visible, what it is consistent with, and what cannot be told.",
      value: "",
      placeholder: "A question about the picture (optional)",
      ok: "Describe"
    }).then(function (text) {
      if (text === null || text === undefined) { return; }
      var question = String(text).trim();
      if (question) { body.question = question; }
      describe(body);
    });
  }

  // The summary dialog's tick starts as the office set it, once, and says
  // what it costs.
  var describeFirstSet = false;
  function drawDescribeFirst() {
    var tick = document.getElementById("summary-describe-first");
    if (!tick || !state || !state.cue_runs) { return; }
    if (!describeFirstSet) { tick.checked = !!state.cue_runs.describe_first_default; describeFirstSet = true; }
    var note = document.getElementById("summary-describe-note");
    if (note) { note.textContent = intervalsLine(true); }
  }

  function busyRun(run) {
    return !!(run && (run.state === "queued" || run.state === "running"));
  }

  function sayOrHide(line, text, problem) {
    if (!line) { return; }
    line.textContent = text || "";
    line.hidden = !text;
    line.classList.toggle("problem", !!problem);
  }

  function drawMoments() {
    if (!momentsOn || !state) { return; }
    if (describeNow) { unavailable(describeNow); }
    if (momentsSaid) {
      momentsSaid.textContent = state.reachable ? "" : state.unavailable_line;
      momentsSaid.hidden = !!state.reachable;
    }
    drawDescribeFirst();
    var runs = state.cue_runs || {};
    if (describeIntervals) {
      unavailable(describeIntervals);
      var interval = runs.interval;
      var intervals = runs.intervals;
      var nothingLeft = !!(intervals && intervals.count === 0 && !busyRun(interval));
      if (busyRun(interval) || nothingLeft) { describeIntervals.disabled = true; }
      if (intervalsNote) {
        // During a run every interval is a queued Moment, so the count reads
        // zero; the caption then goes without it.
        intervalsNote.textContent = nothingLeft
          ? "Every interval is described already."
          : (busyRun(interval) && intervals
              ? "A description " + everyWord(intervals.every) + ", one engine call each. Times already described are skipped."
              : intervalsLine(false));
      }
      if (busyRun(interval)) {
        sayOrHide(intervalsSaid, "Describing the recording" + (interval.total ? ": " + interval.found + " of " + interval.total : "") + "...");
      } else if (interval && interval.state === "failed") {
        sayOrHide(intervalsSaid, interval.said, true);
      } else if (interval && interval.state === "done" && interval.total) {
        sayOrHide(intervalsSaid, (interval.found < interval.total ? interval.found + " of " + interval.total : interval.total) +
          (interval.total === 1 ? " moment" : " moments") + " described across the recording.");
      } else {
        sayOrHide(intervalsSaid, "");
      }
    }
    var moments = state.moments || [];
    var finished = moments.filter(function (one) { return one.state === "done"; }).length;
    if (momentsHeading) {
      momentsHeading.textContent = "Described moments" + (finished ? " (" + finished + ")" : "");
    }
    if (momentList) {
      momentList.innerHTML = moments.length ? moments.map(function (one) {
        var source = one.question ? "a question"
          : (one.source === "cue" ? "from a suggestion"
            : (one.source === "interval" ? "from the whole recording" : "asked for"));
        var stamp = when(one.when);
        var head = "<div class='row'><a href='#' class='cite' data-seconds='" + one.at + "'><b>" + escape(one.clock) + "</b></a>" +
          "<span class='muted small grow'>" + source +
          (one.edited ? " · edited" : "") + (stamp ? " · " + escape(stamp) : "") + "</span></div>" +
          (one.question ? "<p class='question'><b>Asked:</b> " + escape(one.question) + "</p>" : "");
        var busy = one.state === "queued" || one.state === "running";
        var body;
        if (one.state === "queued") {
          body = "<p class='muted'>Waiting its turn...</p>";
        } else if (one.state === "running") {
          body = "<p class='muted'>" + (one.question ? "Looking closely..." : "Looking at the clip...") + "</p>";
        } else if (one.state === "failed") {
          body = "<p class='problem'>" + escape(one.said) + "</p>";
        } else {
          body = (one.notice ? "<p class='notice small'>" + escape(one.notice) + "</p>" : "") +
            "<div class='answer'>" + paragraphs(one.text, {}) + "</div>";
        }
        var tools = "<div class='row' style='margin-top:6px'>" +
          (one.state === "done" ? "<button type='button' class='small edit-moment' data-moment='" + one.id + "'>Edit</button>" : "") +
          "<button type='button' class='small moment-again' data-moment='" + one.id + "'" +
          (busy ? " disabled title='Being described now'" : "") + ">" +
          (one.question ? "Ask again" : "Describe again") + "</button>" +
          (one.state === "done" && window.CLIPS ? "<button type='button' class='small moment-clip' data-moment='" + one.id + "'>Make a clip</button>" : "") +
          "<span class='grow'></span>" +
          "<button type='button' class='small ghost danger delete-moment' data-moment='" + one.id + "'>Delete</button></div>";
        return "<div class='card moment" + (one.state === "failed" ? " failed" : "") + "' data-moment='" + one.id + "'>" + head + body + tools + "</div>";
      }).join("") : "<p class='muted small'>No moments yet. <b>Describe this moment</b> describes the picture at the player's time; hold the pointer over any transcript line and press <b>describe</b> for that line. Either takes a question instead.</p>";
      Array.prototype.forEach.call(momentList.querySelectorAll(".moment-again"), function (button) {
        if (!button.disabled) { unavailable(button); }
      });
    }
    if (findMoments) {
      unavailable(findMoments);
      var finders = runs.finders || {};
      var findersOff = runs.finders && !finders.transcript && !finders.media;
      var running = busyRun(runs.transcript) || busyRun(runs.media);
      if (running || findersOff) { findMoments.disabled = true; }
      var lines = [];
      var trouble = false;
      if (findersOff) {
        lines.push("Both finders are off for your office.");
      } else {
        if (runs.transcript) {
          if (busyRun(runs.transcript)) { lines.push("Reading the transcript..."); }
          else if (runs.transcript.state === "failed") { lines.push(runs.transcript.said); trouble = true; }
          else if (runs.transcript.state === "done" && !runs.transcript.found) { lines.push("Nothing in the words calls for a look."); }
          else if (runs.transcript.state === "done") { lines.push(runs.transcript.found + (runs.transcript.found === 1 ? " line" : " lines") + " suggested from the words."); }
        }
        if (runs.media) {
          if (busyRun(runs.media)) { lines.push("Scanning the picture and sound..."); }
          else if (runs.media.state === "failed") { lines.push(runs.media.said); trouble = true; }
          else if (runs.media.state === "done" && runs.media.found) { lines.push(runs.media.found + (runs.media.found === 1 ? " change" : " changes") + " found in the picture and sound."); }
        }
      }
      sayOrHide(findSaid, lines.filter(Boolean).join(" "), trouble);
    }
    if (cueList) {
      var cues = state.cues || [];
      var segments = window.VIEWER.segments() || [];
      var textOf = {};
      segments.forEach(function (segment) { textOf[segment.id] = segment.text; });
      cueList.innerHTML = cues.length ? cues.map(function (one) {
        var from = one.source === "picture" ? "the picture" : (one.source === "sound" ? "the sound" : "the words");
        var quote = one.segment_id && textOf[one.segment_id] ? textOf[one.segment_id] : "";
        return "<li class='suggestion'><span class='grow'>" +
          "<a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a> " +
          "<span class='pill'>" + escape(one.kind) + "</span> " + escape(one.reason) +
          " <span class='muted small'>(" + escape(sureWord(one.confidence)) + ", from " + from + ")</span>" +
          (quote ? "<span class='muted small quote'>“" + escape(quote) + "”</span>" : "") + "</span>" +
          "<button type='button' class='small accept-cue' data-cue='" + one.id + "'>Describe</button>" +
          "<button type='button' class='small ghost dismiss-cue' data-cue='" + one.id + "'>Dismiss</button></li>";
      }).join("") : "<li class='muted small'>Nothing suggested yet.</li>";
      Array.prototype.forEach.call(cueList.querySelectorAll(".accept-cue"), unavailable);
    }
    decorateRows();
  }

  // The rows: a describe button each, a Camera? button on a cue line, and
  // the camera lines under the rows nearest the described Moments. Rebuilt
  // after every state and whenever viewer.js redraws the transcript.
  function decorateRows() {
    if (!momentsOn || !state) { return; }
    var rows = document.querySelectorAll("#transcript .seg");
    var segments = window.VIEWER.segments() || [];
    Array.prototype.forEach.call(document.querySelectorAll("#transcript .camera-line, #transcript .pill.cue"), function (old) {
      old.remove();
    });
    Array.prototype.forEach.call(rows, function (row) {
      var actions = row.querySelector(".actions");
      if (!actions) { return; }
      var button = actions.querySelector(".camera-row");
      if (!button) {
        button = document.createElement("button");
        button.type = "button";
        button.className = "ghost tiny camera-row";
        button.innerHTML = window.VIEWER.icon("camera") + " describe";
        actions.appendChild(button);
      }
      button.disabled = !state.reachable;
      button.title = state.reachable
        ? "Describe the picture at this line, or ask a question about it"
        : state.unavailable_line;
    });
    var bySegment = {};
    Array.prototype.forEach.call(rows, function (row) {
      var segment = segments[parseInt(row.dataset.index, 10)];
      if (segment) { bySegment[segment.id] = row; }
    });
    (state.cues || []).forEach(function (one) {
      var row = bySegment[one.segment_id];
      if (!row) { return; }
      var who = row.querySelector(".who");
      var name = row.querySelector(".name");
      if (!who || !name) { return; }
      var pill = document.createElement("button");
      pill.type = "button";
      pill.className = "pill side cue";
      pill.textContent = "Camera?";
      pill.title = state.reachable ? one.reason.replace(/\.$/, "") + ". Press to describe the picture here." : state.unavailable_line;
      pill.disabled = !state.reachable;
      pill.dataset.cue = one.id;
      // After the last pill on the name line (a Suggested: name, say), else
      // straight after the name.
      var pills = who.querySelectorAll(".pill");
      var after = pills.length ? pills[pills.length - 1] : name;
      after.parentNode.insertBefore(pill, after.nextSibling);
    });
    (state.moments || []).forEach(function (one) {
      if (one.state === "failed") { return; }
      var index = rowFor(segments, one.at);
      if (index < 0 || !rows[index]) { return; }
      var line = document.createElement("p");
      line.className = "camera-line" + (one.state === "done" ? "" : " waiting");
      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = "Camera";
      line.appendChild(tag);
      var cite = document.createElement("a");
      cite.href = "#";
      cite.className = "cite";
      cite.dataset.seconds = one.at;
      cite.textContent = one.clock;
      line.appendChild(cite);
      var words;
      if (one.state === "done") { words = one.text; }
      else if (one.state === "queued") { words = "waiting its turn..."; }
      else { words = one.question ? "looking closely..." : "looking at the clip..."; }
      if (one.question) { words = "(asked \u201C" + one.question + "\u201D) " + words; }
      line.appendChild(document.createTextNode(" " + words));
      // The line's words are not the row: a click on them neither seeks nor
      // opens the row's correction box. The clock still seeks.
      ["click", "dblclick"].forEach(function (kind) {
        line.addEventListener(kind, function (event) {
          event.stopPropagation();
          var clock = event.target.closest(".cite");
          if (kind === "click" && clock) {
            event.preventDefault();
            window.VIEWER.seek(parseFloat(clock.dataset.seconds));
            window.VIEWER.play();
            if (window.VIEWER.showSegment) { window.VIEWER.showSegment(parseFloat(clock.dataset.seconds)); }
          }
        });
      });
      var txt = rows[index].querySelector(".txt");
      if (txt) { txt.parentNode.insertBefore(line, txt.nextSibling); }
    });
  }

  // The row a time belongs to: the last one that starts at or before it.
  function rowFor(segments, seconds) {
    var found = -1;
    for (var i = 0; i < segments.length; i += 1) {
      if (segments[i].start <= seconds) { found = i; } else { break; }
    }
    return found < 0 && segments.length ? 0 : found;
  }

  if (momentsOn) {
    if (describeNow) {
      describeNow.addEventListener("click", function () {
        askOrDescribe({ at: window.VIEWER.at(), source: "asked" });
      });
    }
    document.addEventListener("click", function (event) {
      var camera = event.target.closest("#transcript .camera-row");
      var pill = event.target.closest("#transcript .pill.cue");
      if (camera) {
        var row = camera.closest(".seg");
        var segment = (window.VIEWER.segments() || [])[parseInt(row.dataset.index, 10)];
        if (segment) { askOrDescribe({ at: segment.start, segment: segment.id, source: "asked" }); }
        return;
      }
      var clipOf = event.target.closest("#moment-list .moment-clip");
      if (clipOf && window.CLIPS) {
        var chosen = (state.moments || []).filter(function (one) { return one.id === clipOf.dataset.moment; })[0];
        if (!chosen) { return; }
        var from = chosen.span_end > chosen.span_start ? chosen.span_start : Math.max(0, chosen.at - 5);
        var to = chosen.span_end > chosen.span_start ? chosen.span_end : chosen.at + 5;
        window.CLIPS.mark(from, to);
        var title = document.getElementById("clip-title");
        var note = document.getElementById("clip-note");
        if (title && !title.value) { title.value = chosen.question ? chosen.question.slice(0, 120) : "Camera at " + chosen.clock; }
        if (note && !note.value) { note.value = chosen.text.slice(0, 1000); }
        return;
      }
      if (pill) {
        // Says it is looking until the next state replaces it with a camera line.
        pill.disabled = true;
        pill.textContent = "Looking...";
        describe({ cue: pill.dataset.cue, source: "cue" });
        return;
      }
      var accept = event.target.closest("#cue-list .accept-cue");
      if (accept) {
        accept.disabled = true;
        describe({ cue: accept.dataset.cue, source: "cue" });
        return;
      }
      var dismiss = event.target.closest("#cue-list .dismiss-cue");
      if (dismiss) {
        dismiss.disabled = true;
        post("/cue/" + dismiss.dataset.cue + "/dismiss").then(refresh);
        return;
      }
      if (event.target.closest("#find-moments")) {
        findMoments.disabled = true;
        post("/recording/" + recording + "/find-moments").then(function (answer) {
          if (!answer.ok && answer.said && answer.said.error) {
            UI.toast(answer.said.error, { problem: true, icon: "warning" });
          }
          return refresh();
        });
        return;
      }
      if (event.target.closest("#describe-intervals")) {
        UI.confirm({ title: "Describe the whole recording?", body: intervalsLine(false), ok: "Describe it" })
          .then(function (yes) {
            if (!yes) { return; }
            describeIntervals.disabled = true;
            post("/recording/" + recording + "/describe-intervals").then(function (answer) {
              if (!answer.ok && answer.said && answer.said.error) {
                UI.toast(answer.said.error, { problem: true, icon: "warning" });
              }
              return refresh();
            });
          });
        return;
      }
      var edit = event.target.closest("#moment-list .edit-moment");
      if (edit) {
        var current = (state.moments || []).filter(function (one) { return one.id === edit.dataset.moment; })[0];
        UI.prompt({ title: "Edit this description", body: "Your words replace the assistant's; the card is marked edited.", value: current ? current.text : "", ok: "Save" })
          .then(function (text) {
            if (!text || !text.trim()) { return; }
            post("/moment/" + edit.dataset.moment + "/edit", { text: text.trim() }).then(refresh);
          });
        return;
      }
      var again = event.target.closest("#moment-list .moment-again");
      if (again) {
        var asked = (state.moments || []).filter(function (one) { return one.id === again.dataset.moment; })[0];
        var question = !!(asked && asked.question);
        UI.confirm(question
          ? { title: "Ask this question again?", body: "The answer here is replaced by a new one from the same frames. One engine call.", ok: "Ask again" }
          : { title: "Describe this moment again?", body: "The description here, and any edit you made to it, is replaced by a new one. One engine call.", ok: "Describe again" })
          .then(function (yes) { if (yes) { post("/moment/" + again.dataset.moment + "/again").then(refresh); } });
        return;
      }
      var gone = event.target.closest("#moment-list .delete-moment");
      if (gone) {
        UI.confirm({ title: "Delete this moment?", body: "Its description goes from the viewer and the exports.", ok: "Delete moment", danger: true })
          .then(function (yes) { if (yes) { post("/moment/" + gone.dataset.moment + "/delete").then(refresh); } });
      }
    });
  }

  // Polling -------------------------------------------------------------------------

  function draw() {
    drawSummaries();
    drawChat();
    drawSuggestions();
    drawMoments();
  }

  function refresh() {
    return fetch("/recording/" + recording + "/assistant")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        state = body;
        draw();
        window.clearTimeout(timer);
        if (state.busy || (chat && chat.pendingCount())) {
          timer = window.setTimeout(refresh, EVERY);
        }
      })
      .catch(function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(refresh, EVERY * 3);
      });
  }

  // The transcript rows are drawn by viewer.js once the segments arrive; the
  // suggestion pills go on after that, and again whenever the rows are redrawn.
  document.addEventListener("transcript-drawn", function () { drawSuggestions(); decorateRows(); });

  refresh();
})();

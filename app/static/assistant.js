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
  var describeNow = document.getElementById("describe-now");
  var recordLines = document.getElementById("record-lines");
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
      // Word of the change, for a window and the page to keep in step.
      document.dispatchEvent(new CustomEvent("transcribe-posted"));
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  // Something changed in another window of this recording: read the state again.
  document.addEventListener("changed-elsewhere", function () { refresh(); });

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  // The described Moment at a cited second, if any: a citation of a camera
  // line is drawn with the camera glyph and the description as its title, so
  // a reader sees at once that the fact came from the picture.
  function cameraAt(seconds) {
    if (!state || !state.moments) { return null; }
    var whole = Math.floor(seconds);
    for (var i = 0; i < state.moments.length; i += 1) {
      var one = state.moments[i];
      if (one.state === "done" && one.text && Math.floor(one.at) === whole) { return one; }
    }
    return null;
  }

  function quoted(text) {
    return escape(text).replace(/'/g, "&#39;");
  }

  // Text with its Citations as links. Only the times the app matched become
  // links; the pattern is the chapter's [hh:mm:ss].
  function withCitations(text, citations) {
    return escape(text).replace(/\[(\d{1,2}):(\d{2}):(\d{2})\]/g, function (whole) {
      if (citations && Object.prototype.hasOwnProperty.call(citations, whole)) {
        var seen = cameraAt(citations[whole]);
        if (seen) {
          return "<a href='#' class='cite camera' data-seconds='" + citations[whole] + "' title='Camera: " + quoted(seen.text) + "'>" +
            window.VIEWER.icon("camera") + whole + "</a>";
        }
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

  // Whether the assistant's answers on this page draw on the camera: a video
  // with Moments on, and the office handing them to answers.
  function answersUseMoments() {
    return !!(momentsOn && state && state.cue_runs && state.cue_runs.answers_use_moments);
  }

  function describedCount() {
    return answersUseMoments() ? (state.cue_runs.described || 0) : 0;
  }

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  function drawSummaries() {
    if (!summaryList || !state) { return; }
    if (newSummary) {
      unavailable(newSummary);
      newSummary.textContent = answersUseMoments() ? "Summarise this video" : "New summary";
    }
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
      summaryList.innerHTML = answersUseMoments()
        ? "<p class='muted small'>No summaries yet. Summarise this video looks at the picture at intervals, then writes from the words and the moments together.</p>"
        : "<p class='muted small'>No summaries yet. New summary reads the whole transcript and writes one.</p>";
      return;
    }
    summaryList.innerHTML = state.summaries.map(function (one) {
      var head = "<div class='row'><b class='grow'>" + escape(one.template) + "</b>" +
        "<span class='muted small'>" + escape(one.length) +
        (one.focus ? " · focus: " + escape(one.focus) : "") +
        (one.digest_parts ? " · from the digest" : (one.moments_used ? " · " + plural(one.moments_used, "moment") : "")) +
        " · " + escape(one.when) + "</span></div>";
      var body;
      if (one.state === "queued" || one.state === "running") {
        var looking = state.cue_runs && state.cue_runs.interval;
        var told = describedCount();
        if (one.describe_first && looking && (looking.state === "queued" || looking.state === "running")) {
          body = "<p class='muted'>Looking at the picture first" + (looking.total ? " (" + looking.found + " of " + looking.total + ")" : "") + "...</p>";
        } else if (one.stage && one.stage.indexOf("condensing") === 0) {
          // "condensing 2 of 5": the digest's parts being made (chapter 6).
          body = "<p class='muted'>Condensing the recording (" + escape(one.stage.replace("condensing ", "")) + ")...</p>";
        } else if (told) {
          body = "<p class='muted'>Reading the transcript and " + plural(told, "moment") + "...</p>";
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
        var seen = cameraAt(seconds);
        if (seen) {
          return { clock: whole.slice(1, -1), seconds: seconds, line: "Camera: " + seen.text, camera: true };
        }
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
      grounding: function (s) {
        if (s && s.digest && s.digest.parts && s.described) {
          return "Answers come from this transcript and its record of " + plural(s.described, "description") +
            ", made " + s.digest.made + (s.digest.current ? "" : " (the transcript or the moments have changed since)") +
            ", not from any other recording. What the camera showed is a model's description.";
        }
        if (s && s.described) {
          return "Answers come from this transcript and its " + plural(s.described, "described moment") +
            ", not from any other recording. What the camera showed is a model's description.";
        }
        return "Answers come from this transcript only, not from any other recording.";
      },
      readingLine: function (s) {
        return s && s.described ? "Reading the transcript and " + plural(s.described, "moment") + "..." : "Reading the transcript...";
      },
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
      busy: state.busy,
      described: describedCount()
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
      var rows = document.querySelectorAll("#transcript .seg");
      for (var i = 0; i < rows.length; i += 1) {
        var name = rows[i].querySelector(".name");
        var tags = rows[i].querySelector(".tags");
        if (name && tags && name.textContent.trim() === one.speaker) {
          var pill = document.createElement("span");
          pill.className = "pill side suggested";
          pill.textContent = "Suggested: " + one.name + (one.role ? " (" + one.role + ")" : "");
          pill.title = one.quote + " at " + one.clock;
          tags.appendChild(pill);
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
  // What the camera showed. Two panels: the first the head and the picture
  // record's press; the second the Moments kept. Since v1.51.0 nothing about
  // the camera sits among the transcript's rows.

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

  // What Describe the whole recording would do now, in numbers, from the
  // state's cue_runs.intervals: the spans of the cut, an estimate by the
  // clock alone until the picture is scanned; the template's own words
  // until the state arrives.
  function intervalsLine() {
    var intervals = state && state.cue_runs && state.cue_runs.intervals;
    if (!intervals) {
      return "The picture record: the recording cut where the picture and the sound change, each span described once, one engine call each. Spans already described are skipped.";
    }
    return "The picture record: the recording cut where the picture and the sound change, no span longer than " + spanWord(intervals.every) + ", " +
      (intervals.estimated ? "up to " : "") + plural(intervals.count, "description") + " for this recording, one engine call each" +
      (intervals.estimated ? " (fewer once the picture is scanned and still stretches are joined)" : "") + ". Spans already described are skipped.";
  }

  // hh:mm:ss, the shape the state's clocks come in, for a span's end.
  function longClock(seconds) {
    var whole = Math.max(0, Math.floor(seconds || 0));
    var pad = function (n) { return String(n).padStart(2, "0"); };
    return pad(Math.floor(whole / 3600)) + ":" + pad(Math.floor((whole % 3600) / 60)) + ":" + pad(whole % 60);
  }

  // "15 seconds", "a minute", "2 minutes": a span's ceiling in words.
  function spanWord(seconds) {
    var n = Number(seconds);
    if (!n || n <= 0) { return "a stretch"; }
    if (n % 60 === 0) { return n === 60 ? "a minute" : (n / 60) + " minutes"; }
    return n + " seconds";
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

  // The summary dialog's look-first line, in one of three forms: the tick
  // with its cost while intervals are left to describe (starting as the
  // server's rule says, set once); a line saying the summary draws on what
  // is described when nothing is left; and a line saying the office writes
  // from the words alone when it hands no moments to answers.
  var describeFirstSet = false;
  function drawLookFirst() {
    var tick = document.getElementById("summary-describe-first");
    var line = document.getElementById("summary-describe-line");
    var note = document.getElementById("summary-describe-note");
    if (!tick || !line || !note || !state || !state.cue_runs) { return; }
    var runs = state.cue_runs;
    var intervals = runs.intervals || { every: 0, count: 0, minutes: 0 };
    var described = runs.described || 0;
    if (!runs.answers_use_moments) {
      line.hidden = true;
      tick.checked = false;
      note.textContent = "Your office does not hand moments to summaries, so this one is written from the words alone.";
    } else if (intervals.count === 0) {
      line.hidden = true;
      tick.checked = false;
      note.textContent = described
        ? "The summary draws on the " + plural(described, "described moment") + "."
        : "Nothing is left to describe, and no moment is described yet.";
    } else {
      line.hidden = false;
      if (!describeFirstSet) { tick.checked = !!runs.describe_first_default; describeFirstSet = true; }
      note.textContent = (intervals.estimated ? "Up to " : "") + plural(intervals.count, "description") +
        " where the picture changes, none longer than " + spanWord(intervals.every) +
        ", one engine call each, about " + plural(intervals.minutes || 1, "minute") +
        (runs.digest ? ", then the digest the summary is written from" : "") + "." +
        (described ? " " + plural(described, "moment") + (described === 1 ? " is" : " are") + " described already." : "");
    }
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
    drawLookFirst();
    var runs = state.cue_runs || {};
    if (describeIntervals) {
      unavailable(describeIntervals);
      var interval = runs.interval;
      var intervals = runs.intervals;
      var nothingLeft = !!(intervals && intervals.count === 0 && !busyRun(interval));
      if (busyRun(interval) || nothingLeft) { describeIntervals.disabled = true; }
      if (intervalsNote) {
        // During a run every span is a queued Moment, so the count reads
        // zero; the caption then goes without it.
        intervalsNote.textContent = nothingLeft
          ? "Every span of the recording is described already."
          : (busyRun(interval) && intervals
              ? "The picture record, one engine call per span. Spans already described are skipped."
              : intervalsLine());
      }
      if (busyRun(interval)) {
        sayOrHide(intervalsSaid, "Describing the recording" + (interval.total ? ": " + interval.found + " of " + interval.total : "") + "...");
      } else if (interval && interval.state === "failed") {
        sayOrHide(intervalsSaid, interval.said, true);
      } else if (interval && interval.state === "done" && interval.total) {
        sayOrHide(intervalsSaid, (interval.found < interval.total ? interval.found + " of " + interval.total : interval.total) +
          (interval.total === 1 ? " span" : " spans") + " described across the recording.");
      } else {
        sayOrHide(intervalsSaid, "");
      }
    }
    if (recordLines) {
      var lines = [];
      if (runs.stamp) { lines.push("The camera's stamp: " + runs.stamp + "."); }
      if (runs.digest && runs.digest.parts) {
        lines.push("The digest the summary and the chat are written from was made at " + runs.digest.made +
          " from the transcript and " + plural(runs.digest.moments, "description") + ", in " + plural(runs.digest.parts, "part") +
          (runs.digest.current ? "." : "; the transcript or the moments have changed since, and the next summary remakes it."));
      }
      sayOrHide(recordLines, lines.join(" "));
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
            : (one.source === "interval" ? "the picture record" : "asked for"));
        var stamp = when(one.when);
        var span = one.span_end > one.span_start && one.source === "interval"
          ? escape(one.clock) + " to " + longClock(one.span_end)
          : escape(one.clock);
        var head = "<div class='row'><a href='#' class='cite' data-seconds='" + one.at + "'><b>" + span + "</b></a>" +
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
      }).join("") : "<p class='muted small'>No moments yet. <b>Describe this moment</b> describes the picture at the player's time, or answers a question about it; <b>Describe the whole recording</b> makes the picture record a summary is written from.</p>";
      Array.prototype.forEach.call(momentList.querySelectorAll(".moment-again"), function (button) {
        if (!button.disabled) { unavailable(button); }
      });
    }
  }

  if (momentsOn) {
    if (describeNow) {
      describeNow.addEventListener("click", function () {
        askOrDescribe({ at: window.VIEWER.at(), source: "asked" });
      });
    }
    document.addEventListener("click", function (event) {
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
      if (event.target.closest("#describe-intervals")) {
        UI.confirm({ title: "Describe the whole recording?", body: intervalsLine(), ok: "Describe it" })
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
  document.addEventListener("transcript-drawn", function () { drawSuggestions(); });

  refresh();
})();

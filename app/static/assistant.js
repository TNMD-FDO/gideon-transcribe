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
  var describeIntervals = document.getElementById("describe-intervals");
  var intervalsSaid = document.getElementById("intervals-said");
  var intervalsNote = document.getElementById("intervals-note");

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
        (one.digest_parts ? " · from the words and the camera" : (one.moments_used ? " · " + plural(one.moments_used, "moment") : "")) +
        " · " + escape(one.when) + "</span></div>";
      var body;
      if (one.state === "queued" || one.state === "running") {
        var told = describedCount();
        if (one.stage === "preparing") {
          body = "<p class='muted'>" + (preparingLine() || "Preparing the recording...") + "</p>";
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
      post("/recording/" + recording + "/summaries", {
        template: templateChoice ? templateChoice.value : "",
        focus: document.getElementById("summary-focus").value,
        length: document.getElementById("summary-length").value
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
        var preparing = preparingLine();
        if (preparing) { return preparing; }
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

  // The preparation (chapter 7) -----------------------------------------------------
  // A video is prepared by itself as its transcript lands, on first use, or
  // from the case page; nobody presses anything here. What this page says:
  // the summary dialog's line, and the cards' "Preparing the recording".

  // "15 seconds", "a minute", "2 minutes": a span's ceiling in words.
  function spanWord(seconds) {
    var n = Number(seconds);
    if (!n || n <= 0) { return "a stretch"; }
    if (n % 60 === 0) { return n === 60 ? "a minute" : (n / 60) + " minutes"; }
    return n + " seconds";
  }

  // "about 18 minutes", "about 2 h 10 min", "under a minute".
  function aboutWord(seconds) {
    if (!seconds || seconds < 60) { return "under a minute"; }
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) { return "about " + plural(minutes, "minute"); }
    var hours = Math.floor(minutes / 60);
    var rest = minutes % 60;
    return "about " + hours + " h" + (rest ? " " + (rest < 10 ? "0" : "") + rest + " min" : "");
  }

  // The preparation's own words for a card while it runs.
  function preparingLine() {
    var prepare = state && state.cue_runs && state.cue_runs.prepare;
    if (!prepare || (prepare.state !== "running" && prepare.state !== "queued")) { return ""; }
    return "Preparing the recording" + (prepare.total ? " (" + prepare.done + " of " + prepare.total + ")" : "") +
      ", " + aboutWord(prepare.seconds_left) + "...";
  }
  window.VIEWER.preparingLine = preparingLine;

  function drawPrepareNote() {
    var note = document.getElementById("summary-prepare-note");
    if (!note || !state || !state.cue_runs) { return; }
    var runs = state.cue_runs;
    var prepare = runs.prepare;
    var intervals = runs.intervals || { every: 0, count: 0 };
    if (!runs.answers_use_moments || !prepare) {
      note.hidden = true;
      return;
    }
    note.hidden = false;
    if (prepare.state === "done") {
      note.textContent = "Written from the words and the camera's descriptions together" +
        (runs.stamp ? "; the camera's clock is known" : "") + ".";
    } else if (prepare.state === "running" || prepare.state === "queued") {
      note.textContent = "The recording is being prepared first: " + preparingLine().replace(/\.\.\.$/, ".");
    } else if (prepare.state === "failed") {
      note.textContent = "The picture could not be described (" + prepare.line.replace(/^Not prepared: /, "") + "); the summary is written from the words alone.";
    } else {
      note.textContent = "The recording is prepared first: " + (intervals.estimated ? "up to " : "") +
        plural(intervals.count, "description") + " where the picture changes, none longer than " + spanWord(intervals.every) +
        ", then the digest the summary is written from, " + aboutWord(prepare.seconds_left) + ".";
    }
  }

  // Polling -------------------------------------------------------------------------

  function draw() {
    drawSummaries();
    drawChat();
    drawSuggestions();
    drawPrepareNote();
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

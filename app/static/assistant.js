// The AI assistant in the viewer: the Summary and Chat panels on the Bench and
// Suggest names in the Speakers panel. Everything here reads one state answer
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
  var chatThreads = document.getElementById("chat-threads");
  var chatTurns = document.getElementById("chat-turns");
  var suggestLine = document.getElementById("suggest-line");
  var suggestionList = document.getElementById("suggestions");

  var state = null;
  var currentChat = null;
  var timer = null;
  var pending = {};  // asked questions not yet in the state answer, by chat id

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
    if (!cite) { return; }
    event.preventDefault();
    window.VIEWER.seek(parseFloat(cite.dataset.seconds));
    window.VIEWER.play();
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
        body = "<p class='muted'>Reading the transcript...</p>";
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
        if (!window.confirm("Replace this summary?")) { return; }
        post("/summary/" + again.dataset.summary + "/regenerate").then(refresh);
        return;
      }
      var gone = event.target.closest(".delete-summary");
      if (gone) {
        if (!window.confirm("Delete this summary? Export it first if you want to keep it.")) { return; }
        post("/summary/" + gone.dataset.summary + "/delete").then(refresh);
      }
    });
  }

  // Chat --------------------------------------------------------------------------

  var askBox = document.getElementById("chat-question");
  var askButton = document.getElementById("chat-ask");

  function theChat() {
    if (!state || !state.chats.length) { return null; }
    var found = null;
    state.chats.forEach(function (one) { if (one.id === currentChat) { found = one; } });
    if (!found) { found = state.chats[0]; currentChat = found.id; }
    return found;
  }

  function drawChat() {
    if (!chatThreads || !state) { return; }
    var chat = theChat();
    chatThreads.innerHTML =
      "<button type='button' class='small' id='chat-new'>New chat</button>" +
      state.chats.map(function (one) {
        return "<button type='button' class='thread" + (chat && one.id === chat.id ? " on" : "") +
          "' data-chat='" + one.id + "'>" + escape(one.name) + "</button>";
      }).join("");
    unavailable(document.getElementById("chat-new"));

    var tools = document.getElementById("chat-tools");
    if (!chat) {
      chatTurns.innerHTML = "<p class='muted small'>Ask a question about this transcript. The answer comes from the transcript and nothing else.</p>";
      if (tools) { tools.hidden = true; }
      if (askBox) { askBox.disabled = !state.reachable; askButton.disabled = !state.reachable; }
      return;
    }
    if (tools) {
      tools.hidden = false;
      document.getElementById("chat-export").setAttribute("href", "/chat/" + chat.id + "/export");
      document.getElementById("chat-export").hidden = !chat.turns.some(function (one) { return one.state === "done"; });
    }
    var html = "";
    if (chat.notice) { html += "<p class='notice small'>" + escape(chat.notice) + "</p>"; }
    if (chat.earlier) { html += "<p class='muted small'>" + escape(chat.earlier) + "</p>"; }
    chat.turns.forEach(function (turn) {
      html += "<div class='turn'><p class='question'><b>You:</b> " + escape(turn.question) + "</p>";
      if (turn.state === "queued" || turn.state === "running") {
        html += "<p class='muted'>Reading the transcript...</p>";
      } else if (turn.state === "failed") {
        html += "<p class='problem'>" + escape(turn.said) + "</p>";
      } else {
        html += "<div class='answer'>" + paragraphs(turn.answer, turn.citations) + "</div>" +
          (turn.cut_short ? "<p class='muted small'>The answer was cut short.</p>" : "") +
          "<button type='button' class='ghost tiny copy' data-answer='" + escape(turn.answer) + "'>Copy</button>";
      }
      html += "</div>";
    });
    if (pending[chat.id]) {
      html += "<div class='turn'><p class='question'><b>You:</b> " + escape(pending[chat.id]) + "</p><p class='muted'>Reading the transcript...</p></div>";
    }
    chatTurns.innerHTML = html;
    chatTurns.scrollTop = chatTurns.scrollHeight;
    var busy = chat.busy || !!pending[chat.id];
    if (askBox) {
      askBox.disabled = busy || !state.reachable;
      askButton.disabled = busy || !state.reachable;
      askBox.placeholder = state.reachable ? "Ask about this transcript" : state.unavailable_line;
    }
  }

  if (chatThreads) {
    chatThreads.addEventListener("click", function (event) {
      if (event.target.closest("#chat-new")) {
        post("/recording/" + recording + "/chats").then(function (answer) {
          if (answer.ok) { currentChat = answer.said.id; }
          refresh();
        });
        return;
      }
      var thread = event.target.closest(".thread");
      if (thread) { currentChat = thread.dataset.chat; drawChat(); }
    });
    chatTurns.addEventListener("click", function (event) {
      var copy = event.target.closest(".copy");
      if (!copy) { return; }
      var text = copy.dataset.answer;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(function () {
          copy.textContent = "Copied";
          window.setTimeout(function () { copy.textContent = "Copy"; }, 1500);
        });
      }
    });
    function ask() {
      var question = askBox.value.trim();
      if (!question) { return; }
      var chat = theChat();
      var send = function (chatId) {
        pending[chatId] = question;
        askBox.value = "";
        drawChat();
        post("/chat/" + chatId + "/ask", { question: question }).then(function () {
          delete pending[chatId];
          refresh();
        });
      };
      if (chat) { send(chat.id); return; }
      post("/recording/" + recording + "/chats").then(function (answer) {
        if (answer.ok) { currentChat = answer.said.id; send(answer.said.id); }
      });
    }
    askButton.addEventListener("click", ask);
    askBox.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(); }
    });
    document.getElementById("chat-delete").addEventListener("click", function () {
      var chat = theChat();
      if (!chat) { return; }
      if (!window.confirm("Delete this chat? Export it first if you want to keep it.")) { return; }
      post("/chat/" + chat.id + "/delete").then(function () { currentChat = null; refresh(); });
    });
  }

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
        "<span class='grow'><b>" + escape(one.speaker) + "</b> → " + escape(one.name) + (one.role ? " (" + escape(one.role) + ")" : "") +
        " <span class='muted small'>(" + escape(one.confidence) + ", " + escape(one.kind) + ")</span>" +
        "<br><span class='muted small'>“" + escape(one.quote) + "” <a href='#' class='cite' data-seconds='" + one.start + "'>" + escape(one.clock) + "</a></span></span>" +
        "<button type='button' class='small accept' data-suggestion='" + one.id + "'>Accept</button>" +
        "<button type='button' class='small ghost reject' data-suggestion='" + one.id + "'>Reject</button></li>";
    }).join("");
    state.pending.forEach(function (one) {
      var rows = document.querySelectorAll("#transcript .seg .name");
      for (var i = 0; i < rows.length; i += 1) {
        if (rows[i].textContent.replace(" ✎", "") === one.speaker) {
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

  // Polling -------------------------------------------------------------------------

  function draw() {
    drawSummaries();
    drawChat();
    drawSuggestions();
  }

  function refresh() {
    return fetch("/recording/" + recording + "/assistant")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        state = body;
        draw();
        window.clearTimeout(timer);
        if (state.busy || Object.keys(pending).length) {
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

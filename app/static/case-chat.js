// The Chat tab of a case page: a Chat whose ground is every transcript in the
// case. Drawn from one state answer the way the viewer's Chat panel is, and
// polled every two seconds while a question runs; an answer arrives whole. A
// citation the app matched is a link that opens that recording in the viewer at
// that moment; one whose recording has left the case is marked and goes nowhere.

(function () {
  "use strict";

  var root = document.getElementById("case-chat");
  if (!root) { return; }
  var caseId = root.dataset.case;
  var EVERY = 2000;

  var lead = document.getElementById("case-chat-lead");
  var chatThreads = document.getElementById("chat-threads");
  var chatTurns = document.getElementById("chat-turns");
  var askBox = document.getElementById("chat-question");
  var askButton = document.getElementById("chat-ask");
  var tools = document.getElementById("chat-tools");

  var state = null;
  var currentChat = null;
  var timer = null;
  var pending = {};

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

  // "[Recording 3, 00:12:45]" becomes the recording's title and time, a link to
  // the viewer at that moment; an unmatched reference stays as written.
  function withCitations(text, citations) {
    return escape(text).replace(/\[Recording \d{1,3}, \d{1,2}:\d{2}:\d{2}\]/g, function (whole) {
      if (!citations || !Object.prototype.hasOwnProperty.call(citations, whole)) { return whole; }
      var where = citations[whole];
      if (where.removed) {
        return "<span class='cite removed' title='This recording has left the case'>" + whole + " (recording removed)</span>";
      }
      return "<a href='" + escape(where.href) + "' class='cite'>" + escape(where.title) + " at " + escape(where.clock) + "</a>";
    });
  }

  function paragraphs(text, citations) {
    return text.split(/\n+/).filter(function (line) { return line.trim(); }).map(function (line) {
      return "<p>" + withCitations(line, citations) + "</p>";
    }).join("");
  }

  function theChat() {
    if (!state || !state.chats.length) { return null; }
    var found = null;
    state.chats.forEach(function (one) { if (one.id === currentChat) { found = one; } });
    if (!found) { found = state.chats[0]; currentChat = found.id; }
    return found;
  }

  function readingLine() {
    if (!state) { return "Reading the case..."; }
    return "Reading " + state.readable + " transcript" + (state.readable === 1 ? "" : "s") + "...";
  }

  function draw() {
    if (!state) { return; }
    var chat = theChat();
    if (lead) {
      lead.textContent = state.readable
        ? "Ask about every transcript in this case: " + state.readable + " to read" +
          (state.skipped ? ", " + state.skipped + " not ready yet" : "") + "."
        : "No recording in this case has a transcript to read yet.";
    }
    chatThreads.innerHTML =
      "<button type='button' class='small' id='chat-new'>New chat</button>" +
      state.chats.map(function (one) {
        return "<button type='button' class='thread" + (chat && one.id === chat.id ? " on" : "") +
          "' data-chat='" + one.id + "'>" + escape(one.name) + "</button>";
      }).join("");
    var newButton = document.getElementById("chat-new");
    newButton.disabled = !state.reachable;
    newButton.title = state.reachable ? "" : state.unavailable_line;

    var canAsk = state.reachable && state.readable > 0;
    if (!chat) {
      chatTurns.innerHTML = "<p class='muted small'>Ask a question about this case. The answer comes from its transcripts and nothing else; every question reads them afresh.</p>";
      tools.hidden = true;
      askBox.disabled = !canAsk;
      askButton.disabled = !canAsk;
      askBox.placeholder = state.reachable ? "Ask about the recordings in this case" : state.unavailable_line;
      return;
    }
    tools.hidden = false;
    var exportLink = document.getElementById("chat-export");
    exportLink.setAttribute("href", "/case-chat/" + chat.id + "/export");
    exportLink.hidden = !chat.turns.some(function (one) { return one.state === "done"; });

    var html = "";
    if (chat.notice) { html += "<p class='notice small'>" + escape(chat.notice) + "</p>"; }
    if (chat.earlier) { html += "<p class='muted small'>" + escape(chat.earlier) + "</p>"; }
    chat.turns.forEach(function (turn) {
      html += "<div class='turn'><p class='question'><b>You:</b> " + escape(turn.question) + "</p>";
      if (turn.state === "queued" || turn.state === "running") {
        html += "<p class='muted'>" + escape(turn.reading || readingLine()) + "</p>";
      } else if (turn.state === "failed") {
        html += "<p class='problem'>" + escape(turn.said) + " <button type='button' class='ghost tiny again' data-question='" + escape(turn.question) + "'>Try again</button></p>";
      } else {
        html += "<div class='answer'>" + paragraphs(turn.answer, turn.citations) + "</div>" +
          (turn.cut_short ? "<p class='muted small'>The answer was cut short.</p>" : "") +
          "<button type='button' class='ghost tiny copy' data-answer='" + escape(turn.answer) + "'>Copy</button>";
      }
      html += "</div>";
    });
    if (pending[chat.id]) {
      html += "<div class='turn'><p class='question'><b>You:</b> " + escape(pending[chat.id]) + "</p><p class='muted'>" + escape(readingLine()) + "</p></div>";
    }
    chatTurns.innerHTML = html;
    chatTurns.scrollTop = chatTurns.scrollHeight;
    var busy = chat.busy || !!pending[chat.id];
    askBox.disabled = busy || !canAsk;
    askButton.disabled = busy || !canAsk;
    askBox.placeholder = state.reachable ? "Ask about the recordings in this case" : state.unavailable_line;
  }

  function send(chatId, question) {
    pending[chatId] = question;
    askBox.value = "";
    draw();
    post("/case-chat/" + chatId + "/ask", { question: question }).then(function () {
      delete pending[chatId];
      refresh();
    });
  }

  function ask(question) {
    question = (question || askBox.value).trim();
    if (!question) { return; }
    var chat = theChat();
    if (chat) { send(chat.id, question); return; }
    post("/case/" + caseId + "/chats").then(function (answer) {
      if (answer.ok) { currentChat = answer.said.id; send(answer.said.id, question); }
    });
  }

  chatThreads.addEventListener("click", function (event) {
    if (event.target.closest("#chat-new")) {
      post("/case/" + caseId + "/chats").then(function (answer) {
        if (answer.ok) { currentChat = answer.said.id; }
        refresh();
      });
      return;
    }
    var thread = event.target.closest(".thread");
    if (thread) { currentChat = thread.dataset.chat; draw(); }
  });

  chatTurns.addEventListener("click", function (event) {
    var again = event.target.closest(".again");
    if (again) { ask(again.dataset.question); return; }
    var copy = event.target.closest(".copy");
    if (!copy) { return; }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(copy.dataset.answer).then(function () {
        copy.textContent = "Copied";
        window.setTimeout(function () { copy.textContent = "Copy"; }, 1500);
      });
    }
  });

  askButton.addEventListener("click", function () { ask(); });
  askBox.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(); }
  });
  document.getElementById("chat-delete").addEventListener("click", function () {
    var chat = theChat();
    if (!chat) { return; }
    if (!window.confirm("Delete this chat? Export it first if you want to keep it.")) { return; }
    post("/case-chat/" + chat.id + "/delete").then(function () { currentChat = null; refresh(); });
  });

  function refresh() {
    return fetch("/case/" + caseId + "/chat")
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

  refresh();
})();

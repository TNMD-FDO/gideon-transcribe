// The Chat tab of a case page: the shared Chat (chat-ui.js) grounded in every
// transcript in the case. This page owns the state and the polling; the
// component draws the conversation. A citation names the recording and opens
// it in the viewer at that moment.

(function () {
  "use strict";

  var root = document.getElementById("case-chat");
  if (!root || !window.ChatUI) { return; }
  var caseId = root.dataset.case;
  var EVERY = 2000;
  var post = window.ChatUI.post;
  var state = null;
  var timer = null;

  var chat = window.ChatUI.mount(root, {
    citationPattern: /\[Recording \d{1,3}, \d{1,2}:\d{2}:\d{2}\]/g,
    citation: function (whole, citations) {
      if (!Object.prototype.hasOwnProperty.call(citations, whole)) { return null; }
      var where = citations[whole];
      if (where.removed) { return { removed: true }; }
      return { name: where.title, clock: where.clock, href: where.href, line: where.line };
    },
    starters: [
      "Who are the people in these recordings, and what is each one's part?",
      "What do the recordings say about the same event, and where do they differ?",
      "When is the subject first mentioned, and in which recording?",
      "Summarise this case"
    ],
    grounding: function (now) {
      if (!now.readable) { return "No recording in this case has a transcript to read yet."; }
      return "Answers come from the " + now.readable + " transcript" + (now.readable === 1 ? "" : "s") +
        " in this case" + (now.skipped ? ", with " + now.skipped + " not ready yet" : "") + ", read afresh for every question.";
    },
    canAsk: function (now) { return now.readable > 0; },
    readingLine: function (now) {
      var count = now ? now.readable : 0;
      return "Reading " + count + " transcript" + (count === 1 ? "" : "s") + "...";
    },
    expectation: "a small case takes under a minute, a large one a few",
    placeholder: "Ask anything about the recordings in this case",
    crossLink: null,
    exportHref: function (chatId) { return "/case-chat/" + chatId + "/export"; },
    newChat: function () {
      return post("/case/" + caseId + "/chats").then(function (answer) { return answer.ok ? answer.said.id : null; });
    },
    ask: function (chatId, question) { return post("/case-chat/" + chatId + "/ask", { question: question }); },
    remove: function (chatId) { return post("/case-chat/" + chatId + "/delete"); },
    refresh: function () { return refresh(); }
  });

  function refresh() {
    return fetch("/case/" + caseId + "/chat")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        state = body;
        chat.update(state);
        window.clearTimeout(timer);
        if (state.busy || chat.pendingCount()) {
          timer = window.setTimeout(refresh, EVERY);
        }
      })
      .catch(function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(refresh, EVERY * 3);
      });
  }

  refresh().then(function () { chat.focus(); });
})();

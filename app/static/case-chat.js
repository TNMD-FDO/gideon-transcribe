// The Chat tab of a case page: the shared Chat (chat-ui.js) grounded in every
// transcript in the case. This page owns the state and the polling; the
// component draws the conversation. A citation names the recording and plays
// the moment in the Preview over the chat (v1.98.0); Open the recording, on
// the Preview, goes to the viewer at that moment.

(function () {
  "use strict";

  if (!window.ChatUI) { return; }

  // One conversation list per root: the Chat tab, and the drawer (Phase 7
  // chapter 5) mount the same thing.
  window.CaseChatMount = function (root, caseId, extra) {
  var EVERY = 2000;
  var post = window.ChatUI.post;
  var state = null;
  var timer = null;
  extra = extra || {};

  var chat = window.ChatUI.mount(root, {
    onPreview: extra.onPreview,
    citationPattern: /\[Recording \d{1,3}, \d{1,2}:\d{2}:\d{2}\]/g,
    citation: function (whole, citations) {
      if (!Object.prototype.hasOwnProperty.call(citations, whole)) { return null; }
      var where = citations[whole];
      if (where.removed) { return { removed: true }; }
      // The recording, the moment and the copy to play go with it (v1.98.0):
      // without them the citation was a plain link and the chat was left.
      return { name: where.title, clock: where.clock, href: where.href, line: where.line, all: where.all,
        seconds: where.seconds, media: where.media, recording: where.recording };
    },
    grounding: function (now) {
      if (!now.readable) { return "No recording in this case has a transcript to read yet."; }
      // The scope (Phase 9 chapter 6): the narrowing on the page, or the
      // whole case and how it is read when it is over the ceiling.
      var scope = window.CaseScope && window.CaseScope.narrowed() ? window.CaseScope.get() : null;
      if (scope) {
        return "Reads the " + scope.recordings.length + " recording" + (scope.recordings.length === 1 ? "" : "s") +
          " you have narrowed to on this page, whole, read afresh for every question. Clear the narrowing to ask about the whole case.";
      }
      if (now.over && now.summarised) {
        return "This case is " + now.hours + " hours of talk, more than the " + now.hours_allowed + " a question reads whole: " +
          "Gideon reads the overviews of " + now.summarised + " recording" + (now.summarised === 1 ? "" : "s") + " first, then the recordings they point to, whole." +
          (now.no_summary ? " " + now.no_summary + " recording" + (now.no_summary === 1 ? " has" : "s have") + " no summary yet and will not be read; the case page offers to write them tonight." : "") +
          " Narrow the list on the page to ask about fewer recordings.";
      }
      if (now.over) {
        return "This case is " + now.hours + " hours of talk, more than the " + now.hours_allowed + " a question reads whole, and no recording has a summary yet, so a question about the whole case will be refused. " +
          "Write the summaries tonight on the case page, or narrow the list on the page and ask about those recordings.";
      }
      return "Answers come from the " + now.readable + " transcript" + (now.readable === 1 ? "" : "s") +
        " in this case" + (now.skipped ? ", with " + now.skipped + " not ready yet" : "") + ", read afresh for every question.";
    },
    canAsk: function (now) { return now.readable > 0; },
    readingLine: function (now) {
      var count = now ? now.readable : 0;
      if (window.CaseScope && window.CaseScope.narrowed()) { count = window.CaseScope.get().recordings.length; }
      else if (now && now.over && now.summarised) { return "Reading the overviews of " + now.summarised + " recordings..."; }
      return "Reading " + count + " transcript" + (count === 1 ? "" : "s") + "...";
    },
    expectation: "a small case takes under a minute, a large one a few",
    placeholder: "Ask anything about the recordings in this case",
    crossLink: null,
    exportHref: function (chatId) { return "/case-chat/" + chatId + "/export"; },
    newChat: function () {
      return post("/case/" + caseId + "/chats").then(function (answer) { return answer.ok ? answer.said.id : null; });
    },
    ask: function (chatId, question) {
      // The question carries the scope (Phase 9 chapter 6): kinds and ids, nothing typed.
      var scope = window.CaseScope ? window.CaseScope.get() : { kind: "all", recordings: [] };
      return post("/case-chat/" + chatId + "/ask", { question: question, scope: scope });
    },
    remove: function (chatId) { return post("/case-chat/" + chatId + "/delete"); },
    refresh: function () { return refresh(); }
  });

  // The drawer's head says what a question will read, and follows the page's
  // narrowing as it changes.
  function sayScope() {
    var line = document.getElementById("gideon-head-line");
    if (line && window.CaseScope) { line.textContent = window.CaseScope.words(state ? state.head : ""); }
    if (state) { chat.update(state); }
  }
  document.addEventListener("case-scope", sayScope);

  function refresh() {
    return fetch("/case/" + caseId + "/chat")
      .then(function (answer) { return answer.json(); })
      .then(function (body) {
        state = body;
        chat.update(state);
        var line = document.getElementById("gideon-head-line");
        if (line && window.CaseScope) { line.textContent = window.CaseScope.words(state.head); }
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

  refresh().then(function () { if (extra.focus !== false) { chat.focus(); } });
  return chat;
  };

  var root = document.getElementById("case-chat");
  if (root) { window.CaseChatMount(root, root.dataset.case); }
})();

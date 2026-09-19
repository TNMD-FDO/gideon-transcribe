// Gideon (Phase 7 chapter 5): the chat with a place of its own. A round
// button at the bottom right of the case page, the recording page and the
// incident page opens a drawer beside the page; the chat inside it is the
// shared chat (chat-ui.js) grounded in what the page is about. On the case
// page the drawer mounts the case's conversations; on the recording page it
// takes the page's own Chat panel in and gives it back on close; on the
// incident page it mounts the incident's conversations, whose citations seek
// every camera. Open or closed is remembered per person per kind of page.

(function () {
  "use strict";

  var shell = document.getElementById("gideon");
  if (!shell || !window.ChatUI) { return; }
  var kind = shell.dataset.kind;
  var button = document.getElementById("gideon-open");
  var drawer = document.getElementById("gideon-drawer");
  var body = document.getElementById("gideon-body");
  var closeButton = document.getElementById("gideon-close");
  var key = "gideon-" + kind;
  var mounted = false;
  var moved = null;   // the recording page's own chat panel, while it is in the drawer
  var post = window.ChatUI.post;

  function remember(open) {
    try { window.localStorage.setItem(key, open ? "open" : "closed"); } catch (ignored) { /* a browser that forbids storage forgets it */ }
  }
  function remembered() {
    try { return window.localStorage.getItem(key) === "open"; } catch (ignored) { return false; }
  }

  function mountIncident() {
    var caseId = shell.dataset.case;
    var incidentId = shell.dataset.incident;
    var EVERY = 2000;
    var state = null;
    var timer = null;
    var chat = window.ChatUI.mount(body, {
      citationPattern: /\[(\d{1,2}):(\d{2}):(\d{2})\]/g,
      citation: function (whole, citations) {
        if (!Object.prototype.hasOwnProperty.call(citations, whole)) { return null; }
        var where = citations[whole];
        return { clock: where.clock, seconds: where.seconds, href: where.href, camera: true };
      },
      onCite: function (seconds) {
        // The cameras are the preview: every camera seeks there.
        if (window.INCIDENT_PAGE && window.INCIDENT_PAGE.seek) { window.INCIDENT_PAGE.seek(seconds); }
      },
      onPlus: function (seconds, line) {
        if (window.INCIDENT_PAGE && window.INCIDENT_PAGE.addEvent) { window.INCIDENT_PAGE.addEvent(seconds, line); }
      },
      grounding: function (now) {
        if (!now.readable) { return "No synced camera of this incident has a transcript to read yet."; }
        return "Answers come from the incident record of " + now.readable + " synced camera" + (now.readable === 1 ? "" : "s") +
          " and the chronology" + (now.left_out && now.left_out.length ? "; " + now.left_out.join(", ") + " not synced and left out" : "") + ".";
      },
      canAsk: function (now) { return now.readable > 0; },
      readingLine: function () { return "Reading the incident record..."; },
      expectation: "about a minute",
      placeholder: "Ask anything about this incident",
      crossLink: null,
      exportHref: function (chatId) { return "/case-chat/" + chatId + "/export"; },
      newChat: function () {
        return post("/case/" + caseId + "/incident/" + incidentId + "/chats").then(function (answer) { return answer.ok ? answer.said.id : null; });
      },
      ask: function (chatId, question) { return post("/case-chat/" + chatId + "/ask", { question: question }); },
      remove: function (chatId) { return post("/case-chat/" + chatId + "/delete"); },
      refresh: function () { return refresh(); }
    });
    function refresh() {
      return fetch("/case/" + caseId + "/incident/" + incidentId + "/chat")
        .then(function (answer) { return answer.json(); })
        .then(function (got) {
          state = got;
          chat.update(state);
          window.clearTimeout(timer);
          if (state.busy || chat.pendingCount()) { timer = window.setTimeout(refresh, EVERY); }
        })
        .catch(function () { window.clearTimeout(timer); timer = window.setTimeout(refresh, EVERY * 3); });
    }
    refresh().then(function () { chat.focus(); });
  }

  function mount() {
    if (mounted) { return; }
    mounted = true;
    if (kind === "case" && window.CaseChatMount) {
      window.CaseChatMount(body, shell.dataset.case, { onPreview: null });
    } else if (kind === "recording") {
      var panel = document.getElementById("chat-root");
      if (panel) {
        moved = { panel: panel, parent: panel.parentNode, next: panel.nextSibling };
        var note = document.createElement("p");
        note.className = "muted small";
        note.id = "gideon-moved-note";
        note.textContent = shell.dataset.name + " is open beside the page.";
        panel.parentNode.insertBefore(note, panel);
        body.appendChild(panel);
      }
    } else if (kind === "incident") {
      mountIncident();
    }
  }

  function giveBack() {
    if (!moved) { return; }
    var note = document.getElementById("gideon-moved-note");
    moved.parent.insertBefore(moved.panel, moved.next);
    if (note) { note.remove(); }
    moved = null;
    mounted = false;
  }

  function open() {
    drawer.hidden = false;
    document.body.classList.add("gideon-open");
    button.setAttribute("aria-expanded", "true");
    mount();
    remember(true);
  }
  function close() {
    drawer.hidden = true;
    document.body.classList.remove("gideon-open");
    button.setAttribute("aria-expanded", "false");
    var playing = drawer.querySelector(".chat-preview video");
    if (playing) { playing.pause(); }
    giveBack();
    remember(false);
  }

  button.addEventListener("click", function () { if (drawer.hidden) { open(); } else { close(); } });
  closeButton.addEventListener("click", close);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !drawer.hidden && !event.target.closest("textarea, input")) { close(); }
  });
  if (!button.disabled && remembered()) { open(); }
}());

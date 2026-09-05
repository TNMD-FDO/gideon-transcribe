// The one Chat, drawn the same wherever it appears: the viewer's Chat panel,
// grounded in one transcript, and the case page's Chat tab, grounded in every
// transcript in the case. The page that mounts it owns the state and the
// polling; this draws the conversation and turns what a person does into the
// calls the page gave it. Starter questions when there is nothing yet, a
// conversation of bubbles and cards, citations as play pills with the line
// they point to, an honest wait, Try again, and a list of earlier chats.

(function () {
  "use strict";

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

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

  // A time as a person reads it in a pill: "12:45", or "1:02:45" past an hour.
  function shortClock(clock) {
    var parts = clock.split(":");
    if (parts.length === 3 && parseInt(parts[0], 10) === 0) { return parts[1] + ":" + parts[2]; }
    if (parts.length === 3) { return String(parseInt(parts[0], 10)) + ":" + parts[1] + ":" + parts[2]; }
    return clock;
  }

  // The answer's text, made readable: escaped, then simple lists, bold, and
  // short lines that end in a colon as headings. Nothing else is interpreted.
  function inline(text, cite) {
    var html = escape(text).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    return cite(html);
  }

  function body(text, cite) {
    var lines = text.split("\n");
    var html = "";
    var list = null;
    lines.forEach(function (raw) {
      var line = raw.trim();
      if (!line) { if (list) { html += "</" + list + ">"; list = null; } return; }
      var bullet = line.match(/^(?:[-*•]\s+|\d+[.)]\s+)(.*)$/);
      if (bullet) {
        var kind = /^\d/.test(line) ? "ol" : "ul";
        if (list !== kind) { if (list) { html += "</" + list + ">"; } html += "<" + kind + ">"; list = kind; }
        html += "<li>" + inline(bullet[1], cite) + "</li>";
        return;
      }
      if (list) { html += "</" + list + ">"; list = null; }
      var plain = line.replace(/^#+\s*/, "").replace(/\*\*/g, "");
      if (plain.length <= 60 && plain.endsWith(":")) {
        html += "<p class='heading'>" + escape(plain.slice(0, -1)) + "</p>";
        return;
      }
      html += "<p>" + inline(line.replace(/^#+\s*/, ""), cite) + "</p>";
    });
    if (list) { html += "</" + list + ">"; }
    return html;
  }

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

  function mount(root, options) {
    if (!root) { return null; }
    var state = null;
    var currentChat = null;
    var pending = {};        // question asked, not yet in the state, by chat id
    var startedAt = {};      // when a running turn was first seen, by turn id
    var ticker = null;
    var followBottom = true;

    root.classList.add("chat-ui");
    root.innerHTML =
      "<div class='chat-head'>" +
        "<button type='button' class='small' data-act='new'>New chat</button>" +
        "<details class='chat-list'><summary class='small'>Earlier chats</summary><ul></ul></details>" +
        "<span class='grow'></span>" +
        "<span class='chat-tools' hidden>" +
          "<a class='btn small' data-act='export' href='#'>Export to Word</a>" +
          "<button type='button' class='ghost small danger' data-act='delete'>Delete chat</button>" +
        "</span>" +
      "</div>" +
      "<div class='chat-body'></div>" +
      "<div class='chat-foot'>" +
        "<div class='row asking'>" +
          "<textarea rows='1' class='grow' aria-label='Your question'></textarea>" +
          "<button type='button' class='primary small' data-act='ask'>Ask</button>" +
        "</div>" +
        "<p class='muted tiny hint'>Enter to ask, Shift+Enter for a new line." +
          (options.crossLink ? " <a href='" + escape(options.crossLink.href) + "'>" + escape(options.crossLink.text) + "</a>" : "") +
        "</p>" +
      "</div>";

    var head = root.querySelector(".chat-head");
    var list = root.querySelector(".chat-list ul");
    var listBox = root.querySelector(".chat-list");
    var tools = root.querySelector(".chat-tools");
    var bodyBox = root.querySelector(".chat-body");
    var askBox = root.querySelector("textarea");
    var askButton = root.querySelector("[data-act='ask']");

    function theChat() {
      if (!state || !state.chats || !state.chats.length) { return null; }
      var found = null;
      state.chats.forEach(function (one) { if (one.id === currentChat) { found = one; } });
      if (!found) { found = state.chats[0]; currentChat = found.id; }
      return found;
    }

    // A citation the app matched becomes a play pill: the recording's name
    // when there are several, the time, and the line it points to on hover.
    function citer(citations) {
      return function (html) {
        return html.replace(options.citationPattern, function (whole) {
          var where = options.citation(whole, citations || {});
          if (!where) { return whole; }
          if (where.removed) {
            return "<span class='cite removed' title='This recording has left the case'>" + whole + " (recording removed)</span>";
          }
          var title = where.line ? " title='" + escape(where.line) + "'" : "";
          var label = (where.name ? escape(where.name) + ", " : "") + shortClock(where.clock);
          return "<a href='" + escape(where.href || "#") + "' class='cite play'" +
            (where.seconds !== undefined ? " data-seconds='" + where.seconds + "'" : "") + title + ">" +
            "<span aria-hidden='true'>&#9654;</span> " + label + "</a>";
        });
      };
    }

    function grow() {
      askBox.style.height = "auto";
      askBox.style.height = Math.min(160, askBox.scrollHeight) + "px";
    }

    function elapsed(turn) {
      var since = startedAt[turn.id] || (turn.asked_at ? new Date(turn.asked_at).getTime() : Date.now());
      startedAt[turn.id] = since;
      return Math.max(0, Math.round((Date.now() - since) / 1000));
    }

    function waiting(turn) {
      var seconds = turn ? elapsed(turn) : 0;
      var line = (turn && turn.reading) || options.readingLine(state);
      var expect = (turn && turn.parts_done !== undefined && turn.parts)
        ? "Part " + turn.parts_done + " of " + turn.parts + " read"
        : options.expectation;
      return "<div class='waiting'><span class='pulse' aria-hidden='true'></span>" +
        "<span class='grow'>" + escape(line) + "</span>" +
        "<span class='muted tiny'>" + (expect ? escape(expect) + " &middot; " : "") + seconds + " s</span></div>";
    }

    function drawList(chat) {
      var chats = state.chats || [];
      var others = chats.filter(function (one) { return !chat || one.id !== chat.id; });
      listBox.hidden = chats.length < 2 && !others.length;
      list.innerHTML = chats.map(function (one) {
        var count = one.turns ? one.turns.length : 0;
        return "<li><button type='button' class='thread" + (chat && one.id === chat.id ? " on" : "") +
          "' data-chat='" + one.id + "'><span class='name'>" + escape(one.name) + "</span>" +
          "<span class='muted tiny'>" + (one.started ? escape(when(one.started)) + " &middot; " : "") +
          count + " question" + (count === 1 ? "" : "s") + "</span></button></li>";
      }).join("");
      var summary = listBox.querySelector("summary");
      summary.textContent = chat ? "Chats (" + chats.length + ")" : "Earlier chats";
    }

    function draw() {
      if (!state) { return; }
      var chat = theChat();
      var canAsk = state.reachable && (options.canAsk ? options.canAsk(state) : true);
      head.querySelector("[data-act='new']").disabled = !state.reachable;
      head.querySelector("[data-act='new']").title = state.reachable ? "" : state.unavailable_line;
      drawList(chat);

      var atBottom = bodyBox.scrollHeight - bodyBox.scrollTop - bodyBox.clientHeight < 40;
      var html = "";
      var grounding = options.grounding ? options.grounding(state) : "";
      if (!chat || !chat.turns.length) {
        html += "<div class='starters'>" +
          (grounding ? "<p class='muted small'>" + escape(grounding) + "</p>" : "") +
          "<p class='small'>Try one of these, or ask your own question.</p>" +
          "<div class='chips'>" + (options.starters || []).map(function (one) {
            return "<button type='button' class='chip starter' data-question='" + escape(one) + "'" + (canAsk ? "" : " disabled") + ">" + escape(one) + "</button>";
          }).join("") + "</div></div>";
      }
      if (chat) {
        if (chat.notice) { html += "<p class='notice quiet tiny'><span aria-hidden='true'>&#9432;</span> " + escape(chat.notice) + "</p>"; }
        if (chat.earlier) { html += "<p class='muted tiny'>" + escape(chat.earlier) + "</p>"; }
        chat.turns.forEach(function (turn) {
          html += "<div class='turn'>" +
            "<div class='bubble you'><p>" + escape(turn.question) + "</p>" +
              (turn.asked_at ? "<span class='muted tiny stamp'>" + escape(when(turn.asked_at)) + "</span>" : "") + "</div>";
          if (turn.state === "queued" || turn.state === "running") {
            html += waiting(turn);
          } else if (turn.state === "failed") {
            html += "<div class='card answer problem'><p>" + escape(turn.said) + "</p>" +
              "<button type='button' class='small again' data-question='" + escape(turn.question) + "'>Try again</button></div>";
          } else {
            html += "<div class='card answer'>" + body(turn.answer, citer(turn.citations)) +
              (turn.cut_short ? "<p class='muted tiny'>The answer was cut short. Ask for the rest, or ask a narrower question.</p>" : "") +
              "<div class='row tools'><button type='button' class='ghost tiny copy' data-answer='" + escape(turn.answer) + "'>Copy</button>" +
              (turn.answered_at ? "<span class='muted tiny'>" + escape(when(turn.answered_at)) + "</span>" : "") + "</div></div>";
          }
          html += "</div>";
        });
        if (pending[chat.id]) {
          html += "<div class='turn'><div class='bubble you'><p>" + escape(pending[chat.id]) + "</p></div>" + waiting(null) + "</div>";
        }
      } else if (pending.__new) {
        html += "<div class='turn'><div class='bubble you'><p>" + escape(pending.__new) + "</p></div>" + waiting(null) + "</div>";
      }
      bodyBox.innerHTML = html;
      if (atBottom || followBottom) { bodyBox.scrollTop = bodyBox.scrollHeight; followBottom = false; }

      tools.hidden = !chat;
      if (chat) {
        var exportLink = tools.querySelector("[data-act='export']");
        exportLink.setAttribute("href", options.exportHref(chat.id));
        exportLink.hidden = !chat.turns.some(function (one) { return one.state === "done"; });
      }
      var busy = (chat && chat.busy) || Object.keys(pending).length > 0;
      askBox.disabled = busy || !canAsk;
      askButton.disabled = busy || !canAsk;
      askBox.placeholder = !state.reachable ? state.unavailable_line
        : (options.placeholder || "Ask anything about this recording");
      var running = busy || (chat && chat.turns.some(function (one) { return one.state === "queued" || one.state === "running"; }));
      window.clearInterval(ticker);
      ticker = running ? window.setInterval(draw, 1000) : null;
    }

    function send(chatId, question) {
      pending[chatId] = question;
      askBox.value = "";
      grow();
      followBottom = true;
      draw();
      options.ask(chatId, question).then(function () {
        delete pending[chatId];
        return options.refresh();
      });
    }

    function ask(question) {
      question = (question || askBox.value).trim();
      if (!question) { return; }
      var chat = theChat();
      if (chat) { send(chat.id, question); return; }
      pending.__new = question;
      askBox.value = "";
      draw();
      options.newChat().then(function (id) {
        delete pending.__new;
        if (!id) { draw(); return; }
        currentChat = id;
        send(id, question);
      });
    }

    root.addEventListener("click", function (event) {
      var target = event.target;
      var newButton = target.closest("[data-act='new']");
      if (newButton) {
        options.newChat().then(function (id) { if (id) { currentChat = id; } return options.refresh(); })
          .then(function () { askBox.focus(); });
        return;
      }
      var thread = target.closest(".thread");
      if (thread) { currentChat = thread.dataset.chat; followBottom = true; listBox.open = false; draw(); return; }
      var starter = target.closest(".starter, .again");
      if (starter) { ask(starter.dataset.question); return; }
      var copy = target.closest(".copy");
      if (copy && navigator.clipboard) {
        navigator.clipboard.writeText(copy.dataset.answer).then(function () {
          copy.textContent = "Copied";
          window.setTimeout(function () { copy.textContent = "Copy"; }, 1500);
        });
        return;
      }
      if (target.closest("[data-act='delete']")) {
        var chat = theChat();
        if (!chat) { return; }
        if (!window.confirm("Delete this chat? Export it first if you want to keep it.")) { return; }
        options.remove(chat.id).then(function () { currentChat = null; return options.refresh(); });
        return;
      }
      var play = target.closest(".cite.play");
      if (play && options.onCite && play.dataset.seconds !== undefined) {
        event.preventDefault();
        options.onCite(parseFloat(play.dataset.seconds));
      }
    });

    askButton.addEventListener("click", function () { ask(); });
    askBox.addEventListener("input", grow);
    askBox.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(); }
    });
    bodyBox.addEventListener("scroll", function () {
      followBottom = bodyBox.scrollHeight - bodyBox.scrollTop - bodyBox.clientHeight < 40;
    });

    return {
      update: function (next) { state = next; draw(); },
      focus: function () { if (!askBox.disabled) { askBox.focus(); } },
      pendingCount: function () { return Object.keys(pending).length; },
      current: function () { return theChat(); }
    };
  }

  window.ChatUI = { mount: mount, post: post, escape: escape };
})();

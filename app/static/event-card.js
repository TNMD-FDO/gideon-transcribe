// The Event card (Phase 8 chapter 11): one card from any mark of an event.
//
// Hovering a mark (the strip's Events lane, the focus camera's scrub bar,
// the viewer's mark of a noted line) or resting keyboard focus on it shows
// the card light: the time, the line and where it came from. A press, Enter
// or Space opens it whole: the detail, the cameras it is seen on, what it
// rests on, the note with its writer, the why, the clip mark, and the
// actions the page gives it. One at a time; Close, Escape, a press outside
// or on the same mark closes it. The card floats over the page from the
// body: the wall, the strip and the rows never move for it. On a touch
// screen there is no light state; a press opens the card whole.
//
// A mark is any element with data-event-card="<id>". The page sets the card
// up once with what it knows: how to say a time, how to find an event by its
// id, and which actions an event gets from where it was opened.

(function () {
  "use strict";

  var given = {
    time: function (at) { return String(at); },
    find: function () { return null; },
    acts: function () { return []; },
    seek: null,
    restsOn: null,
    clipsUrl: null
  };
  var card = null;
  var anchor = null;
  var state = "";
  var home = "";
  var hoverTimer = null;
  var leaveTimer = null;
  var HOVER_IN = 250;
  var HOVER_OUT = 150;
  var GAP = 8;
  var EDGE = 8;
  var noHover = window.matchMedia ? window.matchMedia("(hover: none)") : null;

  function escape(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

  function touchOnly() { return !!(noHover && noHover.matches); }

  // Where a mark lives, so the same mark can be found again after the page
  // redraws it: the strip's lanes, the Chronology tab, the focus camera's bar,
  // the proposals layer, the viewer's timeline.
  function homeOf(el) {
    var found = el.closest("#lanes, #panel-chronology, #layer-proposals, #timeline, .player-bar");
    if (!found) { return ""; }
    return found.id ? "#" + found.id : ".player-bar";
  }

  function fromOf(el) {
    if (el.closest("#panel-chronology, #layer-proposals")) { return "row"; }
    if (el.closest("#lanes")) { return "strip"; }
    if (el.closest(".player-bar")) { return "bar"; }
    if (el.closest("#timeline")) { return "timeline"; }
    return "";
  }

  function clearTimers() {
    window.clearTimeout(hoverTimer);
    window.clearTimeout(leaveTimer);
    hoverTimer = null;
    leaveTimer = null;
  }

  // Focus goes back to the mark when the card is closed by a key or Close;
  // that focus must not light the card again.
  var quiet = false;

  function close(back) {
    clearTimers();
    var was = anchor;
    var wasOpen = state === "open";
    if (card) { card.remove(); card = null; }
    if (anchor) { anchor.classList.remove("card-open"); }
    anchor = null;
    state = "";
    home = "";
    if (back && wasOpen && was && document.contains(was) && typeof was.focus === "function") {
      quiet = true;
      try { was.focus({ preventScroll: true }); } catch (ignored) { was.focus(); }
      quiet = false;
    }
  }

  function pillClass(ev) {
    return "pill src src-" + escape(ev.source || "person") + (ev.proposed ? " warn" : "");
  }

  function headHtml(ev, whole) {
    var time = given.seek
      ? "<a class='cite t' href='#' data-card-seek='1' title='Play every camera from here'>" + escape(given.time(ev.at)) + "</a>"
      : "<span class='t'>" + escape(given.time(ev.at)) + "</span>";
    return "<div class='event-card-head'>" + time +
      (ev.until ? "<span class='muted small'>to " + escape(given.time(ev.until)) + "</span>" : "") +
      (ev.source_words ? "<span class='" + pillClass(ev) + "' title='" + escape(ev.source_words).replace(/'/g, "&#39;") + "'>" + escape(ev.source_words) + "</span>" : "") +
      "<span class='grow'></span>" +
      (whole ? "<button type='button' class='tiny ghost event-card-close' aria-label='Close'>Close</button>" : "") +
      "</div>";
  }

  function lineHtml(ev) {
    return "<p class='event-card-line'>" + escape(ev.line || ev.text || "") +
      (ev.to_check ? " <span class='pill warn small' title='The office has not settled this'>To check</span>" : "") +
      (ev.proposed ? " <span class='pill warn small'>Proposed</span>" : "") +
      "</p>";
  }

  function bodyHtml(ev) {
    var html = "";
    if (ev.detail) { html += "<p class='event-card-detail'>" + escape(ev.detail) + "</p>"; }
    if (ev.source === "note") {
      // A note event: the note is the line above; under it, the words it sits on.
      if (ev.line_words) { html += "<p class='muted small'>On the line: " + escape(ev.line_words) + "</p>"; }
      if (ev.note_by || ev.note_on) { html += "<p class='muted small'>Written by " + escape(ev.note_by || "a person") + (ev.note_on ? ", " + escape(ev.note_on) : "") + "</p>"; }
    }
    if (ev.seen_on) { html += "<p class='muted small'>Seen on " + escape(ev.seen_on) + "</p>"; }
    if (ev.rests_on) {
      html += "<p class='muted small'>" + (given.restsOn ? given.restsOn(ev.rests_on) : "rests on: " + escape(ev.rests_on)) + "</p>";
    }
    if (ev.note && ev.source !== "note") {
      html += "<p class='event-card-note'><i>Note: " + escape(ev.note) + "</i>" + (ev.note_by ? " <span class='muted small'>(" + escape(ev.note_by) + (ev.note_on ? ", " + escape(ev.note_on) : "") + ")</span>" : "") + "</p>";
    }
    if (ev.why) { html += "<p class='event-card-why'>" + escape(ev.why) + "</p>"; }
    if (ev.clips && ev.clips_words) {
      var url = given.clipsUrl ? given.clipsUrl() : "";
      html += "<p>" + (url ? "<a class='clipmark' href='" + escape(url) + "' title='Open the case&#39;s Clips tab, where the clip is'>" + escape(ev.clips_words) + "</a>" : escape(ev.clips_words)) + "</p>";
    }
    return html;
  }

  function actsHtml(acts) {
    if (!acts || !acts.length) { return ""; }
    return "<div class='event-card-acts'>" + acts.map(function (one, i) {
      if (!one) { return ""; }
      var cls = "small" + (one.danger ? " ghost danger" : (one.primary ? " primary" : " ghost"));
      var title = one.title ? " title='" + escape(one.title).replace(/'/g, "&#39;") + "'" : "";
      if (one.href) {
        return "<a class='btn " + cls + "' href='" + escape(one.href) + "'" + title + ">" + escape(one.words) + "</a>";
      }
      return "<button type='button' class='" + cls + "' data-card-act='" + i + "'" + (one.disabled ? " disabled" : "") + title + ">" + escape(one.words) + "</button>";
    }).join("") + "</div>";
  }

  function build(ev, whole, acts) {
    var box = document.createElement("div");
    box.className = "event-card " + (whole ? "open" : "light") + (ev.proposed ? " proposed" : "") + (ev.source === "note" ? " note" : "");
    box.dataset.event = ev.id;
    var html = headHtml(ev, whole) + lineHtml(ev);
    if (whole) { html += bodyHtml(ev) + actsHtml(acts); }
    box.innerHTML = html;
    if (whole) {
      box.setAttribute("role", "dialog");
      box.setAttribute("aria-label", "Event at " + given.time(ev.at));
      box.setAttribute("tabindex", "-1");
      var closeButton = box.querySelector(".event-card-close");
      if (closeButton) { closeButton.addEventListener("click", function () { close(true); }); }
      Array.prototype.forEach.call(box.querySelectorAll("[data-card-act]"), function (button) {
        button.addEventListener("click", function () {
          var act = acts[parseInt(button.dataset.cardAct, 10)];
          close(false);
          if (act && act.act) { act.act(); }
        });
      });
      box.addEventListener("focusout", function (event) {
        var to = event.relatedTarget;
        if (!to || box.contains(to) || (anchor && anchor.contains(to))) { return; }
        close(false);
      });
    } else {
      box.setAttribute("aria-hidden", "true");
    }
    var seekLink = box.querySelector("[data-card-seek]");
    if (seekLink) {
      seekLink.addEventListener("click", function (event) {
        event.preventDefault();
        if (given.seek) { given.seek(ev.at); }
      });
    }
    return box;
  }

  // Beside its mark, on the side with more room, kept inside the window.
  function place() {
    if (!card || !anchor) { return; }
    if (!document.contains(anchor)) {
      var again = home ? (document.querySelector(home) || document).querySelector("[data-event-card='" + anchor.dataset.eventCard + "']") : null;
      if (!again) { close(false); return; }
      anchor.classList.remove("card-open");
      anchor = again;
      if (state === "open") { anchor.classList.add("card-open"); }
    }
    var at = anchor.getBoundingClientRect();
    if (!at.width && !at.height) { close(false); return; }
    var width = card.offsetWidth;
    var height = card.offsetHeight;
    var viewWidth = document.documentElement.clientWidth;
    var viewHeight = window.innerHeight;
    var below = viewHeight - at.bottom;
    var above = at.top;
    var top;
    if (below >= height + GAP || below >= above) {
      top = Math.min(at.bottom + GAP, viewHeight - height - EDGE);
    } else {
      top = Math.max(EDGE, at.top - GAP - height);
    }
    var left = at.left + at.width / 2 - width / 2;
    left = Math.max(EDGE, Math.min(left, viewWidth - width - EDGE));
    card.style.top = Math.max(EDGE, top) + "px";
    card.style.left = left + "px";
  }

  function show(el, whole) {
    var id = el.dataset.eventCard;
    var ev = given.find(id);
    if (!ev) { return false; }
    var acts = whole ? given.acts(ev, fromOf(el)) : [];
    if (card) { card.remove(); }
    if (anchor && anchor !== el) { anchor.classList.remove("card-open"); }
    anchor = el;
    home = homeOf(el);
    state = whole ? "open" : "light";
    card = build(ev, whole, acts);
    document.body.appendChild(card);
    place();
    if (whole) {
      el.classList.add("card-open");
      try { card.focus({ preventScroll: true }); } catch (ignored) { card.focus(); }
    }
    return true;
  }

  function light(el) {
    if (touchOnly()) { return false; }
    if (state === "open") { return false; }
    return show(el, false);
  }

  function open(el) {
    if (anchor === el && state === "open") { close(true); return true; }
    return show(el, true);
  }

  function refresh() {
    if (!card || !anchor) { return; }
    if (state !== "open") { close(false); return; }
    var ev = given.find(anchor.dataset.eventCard);
    if (!ev) { close(false); return; }
    var acts = given.acts(ev, fromOf(anchor));
    var drawn = build(ev, true, acts);
    card.replaceWith(drawn);
    card = drawn;
    place();
  }

  document.addEventListener("click", function (event) {
    var mark = event.target.closest("[data-event-card]");
    if (mark) {
      if (event.ctrlKey || event.metaKey || event.shiftKey) { return; }
      open(mark);
      return;
    }
    if (card && !event.target.closest(".event-card")) { close(false); }
  });

  document.addEventListener("pointerover", function (event) {
    if (event.pointerType === "touch") { return; }
    var mark = event.target.closest("[data-event-card]");
    if (!mark) { return; }
    clearTimers();
    if (state === "open") { return; }
    hoverTimer = window.setTimeout(function () { light(mark); }, HOVER_IN);
  });

  document.addEventListener("pointerout", function (event) {
    var mark = event.target.closest("[data-event-card]");
    if (!mark) { return; }
    var to = event.relatedTarget;
    if (to && mark.contains(to)) { return; }
    window.clearTimeout(hoverTimer);
    hoverTimer = null;
    if (state === "light") {
      leaveTimer = window.setTimeout(function () { if (state === "light") { close(false); } }, HOVER_OUT);
    }
  });

  document.addEventListener("focusin", function (event) {
    if (quiet) { return; }
    var mark = event.target.closest("[data-event-card]");
    if (!mark) { return; }
    if (state === "open" && anchor === mark) { return; }
    light(mark);
  });

  document.addEventListener("focusout", function (event) {
    var mark = event.target.closest("[data-event-card]");
    if (!mark || state !== "light" || anchor !== mark) { return; }
    var to = event.relatedTarget;
    if (to && mark.contains(to)) { return; }
    close(false);
  });

  // Escape closes the card alone, caught before the page's own listeners so a
  // layer under it stays open; Enter or Space on a mark opens the card.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && card) { close(true); event.stopPropagation(); return; }
    if (event.key !== "Enter" && event.key !== " ") { return; }
    var mark = event.target.closest ? event.target.closest("[data-event-card]") : null;
    if (!mark || mark.closest("input, textarea, select")) { return; }
    event.preventDefault();
    event.stopPropagation();
    open(mark);
  }, true);

  document.addEventListener("scroll", function () { if (card) { place(); } }, { capture: true, passive: true });
  window.addEventListener("resize", function () { if (card) { place(); } });

  window.EVENT_CARD = {
    setup: function (options) {
      Object.keys(options || {}).forEach(function (key) { given[key] = options[key]; });
    },
    light: light,
    open: open,
    close: function () { close(false); },
    place: place,
    refresh: refresh,
    current: function () { return card && anchor ? anchor.dataset.eventCard : null; }
  };
})();

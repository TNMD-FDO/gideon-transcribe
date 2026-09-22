// The paragraph card (Phase 8 chapter 6): the report comes to the reader.
//
// A press on any citation to a paragraph (a pill in a Gideon answer, a
// comparison row, a chronology row that rests on a paragraph, a Search hit)
// opens one card in place, under the citation: the document's title and
// place, the page's picture scrolled so the paragraph is in view with its
// box drawn on it, the words before and after, and Open the document one
// press further. One card at a time; Escape, a press outside it or on the
// citation again closes it; the page under it never moves.
//
// A citation is any element with data-para-card, carrying data-doc-url (the
// document page's address), data-page and data-para, and data-title. The
// card reads the document's state endpoint once per document.

(function () {
  "use strict";

  var states = {};
  var card = null;
  var opener = null;

  function escape(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

  function pct(value, whole) { return whole ? (value / whole) * 100 : 0; }

  function stateOf(url) {
    if (!states[url]) {
      states[url] = fetch(url + "/state").then(function (answer) { return answer.ok ? answer.json() : null; }).catch(function () { return null; });
    }
    return states[url];
  }

  function close() {
    if (card) { card.remove(); card = null; }
    if (opener) { opener.classList.remove("card-open"); opener = null; }
  }

  function hostOf(anchor) {
    return anchor.closest("td, .turn, .answer, .card, li, .inc-said-line, p, div") || anchor.parentNode;
  }

  function draw(anchor, state, page, n, title) {
    var row = (state && state.pages_rows || []).filter(function (one) { return one.number === page; })[0];
    var paragraphs = row ? (row.paragraphs || []) : [];
    var index = -1;
    paragraphs.forEach(function (one, i) { if (one.n === n) { index = i; } });
    var here = index >= 0 ? paragraphs[index] : null;
    var before = index > 0 ? paragraphs[index - 1] : null;
    var after = index >= 0 && index + 1 < paragraphs.length ? paragraphs[index + 1] : null;
    var name = (state && state.title) || title || "Document";
    var docUrl = anchor.dataset.docUrl;
    var box = document.createElement("div");
    box.className = "para-card";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", name + ", page " + page + ", paragraph " + n);
    var html = "<div class='para-card-head'><b>" + escape(name) + "</b><span class='muted small'>page " + page + ", paragraph " + n +
      (row && row.ocr ? "; read by OCR, so check the page" : "") + "</span><span class='grow'></span>" +
      "<button type='button' class='tiny ghost para-card-close' aria-label='Close'>Close</button></div>";
    if (row) {
      html += "<div class='para-card-sheet'><div class='para-card-page' style='aspect-ratio: " + row.width + " / " + row.height + "'>" +
        "<img src='" + escape(row.picture) + "' alt='Page " + page + "'>" +
        (here ? "<span class='doc-box lit' style='left: " + pct(here.box[0], row.width) + "%; top: " + pct(here.box[1], row.height) + "%; width: " +
          pct(here.box[2] - here.box[0], row.width) + "%; height: " + pct(here.box[3] - here.box[1], row.height) + "%'></span>" : "") +
        "</div></div>";
    } else {
      html += "<p class='muted small'>The page could not be read just now.</p>";
    }
    html += "<div class='para-card-words'>" +
      (before ? "<p class='muted small'>" + escape(before.text) + "</p>" : "") +
      (here ? "<p class='doc-cited'>" + escape(here.text) + "</p>" : (anchor.dataset.text ? "<p class='doc-cited'>" + escape(anchor.dataset.text) + "</p>" : "<p class='muted'>Paragraph " + n + " was not found on page " + page + ".</p>")) +
      (after ? "<p class='muted small'>" + escape(after.text) + "</p>" : "") + "</div>";
    html += "<div class='row small para-card-acts'>" +
      "<a class='btn small' href='" + escape(docUrl + "?page=" + page + "&para=" + n) + "'>Open the document</a>" +
      "<button type='button' class='small ghost para-card-copy'>Copy the citation</button>" +
      "<span class='muted small para-card-said'></span></div>";
    box.innerHTML = html;
    box.querySelector(".para-card-close").addEventListener("click", close);
    box.querySelector(".para-card-copy").addEventListener("click", function () {
      var words = name + ", page " + page + ", paragraph " + n;
      var said = box.querySelector(".para-card-said");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(words).then(function () { said.textContent = "Copied"; }, function () { said.textContent = words; });
      } else { said.textContent = words; }
    });
    var img = box.querySelector("img");
    var sheet = box.querySelector(".para-card-sheet");
    if (img && here && sheet) {
      // The picture scrolled so the paragraph is in view, once it has a size.
      var bring = function () {
        var top = (pct(here.box[1], row.height) / 100) * img.clientHeight;
        sheet.scrollTop = Math.max(0, top - 36);
      };
      if (img.complete && img.clientHeight) { bring(); } else { img.addEventListener("load", bring, { once: true }); }
    }
    return box;
  }

  function open(anchor) {
    var page = parseInt(anchor.dataset.page, 10), n = parseInt(anchor.dataset.para, 10);
    var url = anchor.dataset.docUrl || "";
    if (!url || isNaN(page) || isNaN(n)) { return false; }
    if (opener === anchor) { close(); return true; }
    close();
    opener = anchor;
    anchor.classList.add("card-open");
    var host = hostOf(anchor);
    var waiting = document.createElement("div");
    waiting.className = "para-card";
    waiting.innerHTML = "<p class='muted small'>Reading the page...</p>";
    card = waiting;
    host.appendChild(waiting);
    stateOf(url).then(function (state) {
      if (opener !== anchor) { return; }
      var drawn = draw(anchor, state, page, n, anchor.dataset.title);
      if (card && card.parentNode) { card.parentNode.replaceChild(drawn, card); } else { host.appendChild(drawn); }
      card = drawn;
      drawn.scrollIntoView({ block: "nearest" });
    });
    return true;
  }

  document.addEventListener("click", function (event) {
    var anchor = event.target.closest("[data-para-card]");
    if (anchor) {
      if (event.ctrlKey || event.metaKey || event.shiftKey) { return; }
      event.preventDefault();
      open(anchor);
      return;
    }
    if (card && !event.target.closest(".para-card")) { close(); }
  });
  // Escape closes the card alone: caught before the page's own listeners,
  // so a layer or the chat under it stays open.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && card) { close(); event.stopPropagation(); }
  }, true);

  window.PARAGRAPH_CARD = { open: open, close: close };
})();

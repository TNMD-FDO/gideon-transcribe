// The passage window (Phase 12 chapter 11, v1.220.0): the report comes to
// the reader, whole.
//
// A press on a finding's quote on the Comparison page opens one floating
// window of the Preview's kind: the report's pages stacked in one scroll,
// opened at the cited paragraph with it outlined a third of the way down,
// so what surrounds the citation is a scroll away. A bar holds the zoom
// (Fit, 100%, 150%), the page arrows, Back to the citation once the reader
// has scrolled away, and Open the document. The cited words, as read, stand
// in the foot. The window is dragged by its head and resized at its corner;
// its size and zoom are remembered in this browser. The next quote pressed
// scrolls the window to that paragraph; a press on any paragraph's box
// tells the page (hooks.onParagraph), which lights the findings that rest
// on it. Escape or Close closes it.
//
// open({stateUrl, docUrl, title, page, n, finding, onParagraph}) draws or
// turns the window; the document's state (every page's picture, size and
// paragraph boxes in points) is read once per document.

(function () {
  "use strict";

  var KEY = "passage-window";
  var win = null, doc = null, foot = null, place = null, pageWord = null, back = null, openLink = null;
  var states = {};
  var state = null, shownUrl = "", pages = [], cited = null, hooks = {}, docUrl = "", title = "";
  var zoom = "fit";
  var remembered = read();
  var watcher = null;

  function read() {
    try { return JSON.parse(window.localStorage.getItem(KEY) || "{}") || {}; } catch (error) { return {}; }
  }
  function remember(part) {
    Object.keys(part).forEach(function (k) { remembered[k] = part[k]; });
    try { window.localStorage.setItem(KEY, JSON.stringify(remembered)); } catch (error) { /* a browser without storage keeps nothing */ }
  }
  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function pct(part, whole) { return whole ? (100 * part / whole).toFixed(3) : "0"; }

  function stateOf(url) {
    if (!states[url]) {
      states[url] = fetch(url).then(function (answer) { return answer.ok ? answer.json() : null; }).catch(function () { return null; });
    }
    return states[url];
  }

  function pageOf(number) {
    return pages.filter(function (one) { return one.number === number; })[0] || null;
  }

  // The picture is stored at 110 dots an inch; a page's width in points
  // times 110/72 is its picture's width in pixels, the 100% of the zoom.
  function pageWidth(one) {
    var inner = doc.clientWidth - 28;
    if (zoom === "fit") { return Math.max(200, inner); }
    return Math.round(one.width * 110 / 72 * parseFloat(zoom));
  }

  function build() {
    win = document.createElement("div");
    win.className = "passage-win";
    win.setAttribute("role", "dialog");
    win.innerHTML =
      "<div class='passage-head'><b class='pw-title'></b><span class='grow pw-place'></span>" +
      "<button type='button' class='tiny ghost pw-close' aria-label='Close'>Close</button></div>" +
      "<div class='passage-bar'>" +
      "<span class='pw-zoom' role='group' aria-label='Zoom'><button type='button' data-zoom='fit' title='The page as wide as the window'>Fit</button>" +
      "<button type='button' data-zoom='1' title='The page as the app stores it, about one and a half times print'>100%</button>" +
      "<button type='button' data-zoom='1.5' title='Larger still, for a soft scan'>150%</button></span>" +
      "<span class='muted pw-page-word'></span>" +
      "<button type='button' class='tiny' data-step='-1' title='The page before'>&lsaquo;</button>" +
      "<button type='button' class='tiny' data-step='1' title='The page after'>&rsaquo;</button>" +
      "<span class='grow'></span>" +
      "<button type='button' class='tiny ghost pw-back' hidden>Back to the citation</button>" +
      "<a class='btn tiny pw-open' href='#'>Open the document</a></div>" +
      "<div class='passage-doc' tabindex='0'></div>" +
      "<div class='passage-foot'><span class='muted small'>The cited paragraph, as read:</span><p class='pw-words'></p></div>";
    doc = win.querySelector(".passage-doc");
    foot = win.querySelector(".pw-words");
    place = win.querySelector(".pw-place");
    pageWord = win.querySelector(".pw-page-word");
    back = win.querySelector(".pw-back");
    openLink = win.querySelector(".pw-open");
    var w = Math.min(remembered.w || 640, window.innerWidth - 40);
    var h = Math.min(remembered.h || 560, window.innerHeight - 40);
    win.style.width = w + "px";
    win.style.height = h + "px";
    zoom = remembered.zoom || "fit";
    document.body.appendChild(win);

    win.querySelector(".pw-close").addEventListener("click", close);
    win.addEventListener("click", function (event) {
      var z = event.target.closest("[data-zoom]");
      if (z) { setZoom(z.dataset.zoom); return; }
      var step = event.target.closest("[data-step]");
      if (step) { stepPage(parseInt(step.dataset.step, 10)); return; }
      if (event.target.closest(".pw-back")) { bring(false); return; }
      var box = event.target.closest(".passage-doc .doc-box");
      if (box) {
        Array.prototype.forEach.call(doc.querySelectorAll(".doc-box.hit"), function (b) { b.classList.remove("hit"); });
        box.classList.add("hit");
        if (hooks.onParagraph) { hooks.onParagraph(parseInt(box.dataset.page, 10), parseInt(box.dataset.n, 10)); }
      }
    });
    doc.addEventListener("scroll", onScroll);
    drag(win.querySelector(".passage-head"));
    if (window.ResizeObserver) {
      var first = true;
      watcher = new ResizeObserver(function () {
        if (!win) { return; }
        if (first) { first = false; return; }
        remember({ w: Math.round(win.getBoundingClientRect().width), h: Math.round(win.getBoundingClientRect().height) });
        if (zoom === "fit") { layout(); bring(true); }
      });
      watcher.observe(win);
    }
  }

  // Dragged by its head, kept inside the window, as the Preview is.
  function drag(head) {
    var from = null;
    head.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest("button")) { return; }
      var box = win.getBoundingClientRect();
      from = { x: event.clientX - box.left, y: event.clientY - box.top };
      head.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    head.addEventListener("pointermove", function (event) {
      if (!from || !win) { return; }
      var box = win.getBoundingClientRect();
      var left = Math.min(window.innerWidth - box.width - 4, Math.max(4, event.clientX - from.x));
      var top = Math.min(window.innerHeight - 40, Math.max(4, event.clientY - from.y));
      win.style.left = left + "px";
      win.style.top = top + "px";
      win.style.right = "auto";
      win.style.bottom = "auto";
    });
    function letGo() { from = null; }
    head.addEventListener("pointerup", letGo);
    head.addEventListener("pointercancel", letGo);
  }

  function setZoom(given) {
    zoom = given;
    remember({ zoom: zoom });
    layout();
    bring(true);
  }

  // Every page at the zoom's width, its paragraphs' boxes on it, a label
  // between pages; the cited paragraph lit.
  function layout() {
    var html = "";
    pages.forEach(function (one, i) {
      var w = pageWidth(one);
      if (i) { html += "<div class='pw-gap'>page " + one.number + " of " + pages.length + "</div>"; }
      html += "<div class='pw-page' data-page='" + one.number + "' style='width: " + w + "px; aspect-ratio: " + one.width + " / " + one.height + "'>" +
        "<img src='" + escape(one.picture) + "' alt='Page " + one.number + "' loading='lazy'>";
      (one.paragraphs || []).forEach(function (p) {
        var lit = cited && cited.page === one.number && cited.n === p.n;
        html += "<span class='doc-box" + (lit ? " lit" : "") + "' data-page='" + one.number + "' data-n='" + p.n + "' title='Page " + one.number + ", paragraph " + p.n + "' style='left: " +
          pct(p.box[0], one.width) + "%; top: " + pct(p.box[1], one.height) + "%; width: " + pct(p.box[2] - p.box[0], one.width) + "%; height: " + pct(p.box[3] - p.box[1], one.height) + "%'></span>";
      });
      html += "</div>";
    });
    doc.innerHTML = html || "<p class='muted small'>The report's pages could not be read just now.</p>";
    Array.prototype.forEach.call(win.querySelectorAll("[data-zoom]"), function (b) { b.classList.toggle("on", b.dataset.zoom === zoom); });
  }

  function litBox() { return doc.querySelector(".doc-box.lit"); }

  // The cited paragraph a third of the way down the window, and across the
  // middle when the page is wider than the window.
  function bring(atOnce) {
    var box = litBox();
    if (!box) { return; }
    var top = box.offsetTop + box.offsetParent.offsetTop - doc.offsetTop;
    var left = box.offsetLeft + box.offsetParent.offsetLeft - doc.offsetLeft;
    var y = Math.max(0, top - doc.clientHeight / 3);
    var x = Math.max(0, left - (doc.clientWidth - box.offsetWidth) / 2);
    if (atOnce || !doc.scrollTo) { doc.style.scrollBehavior = "auto"; doc.scrollTop = y; doc.scrollLeft = x; doc.style.scrollBehavior = ""; }
    else { doc.scrollTo({ top: y, left: x, behavior: "smooth" }); }
    onScroll();
  }

  function onScroll() {
    if (!win) { return; }
    var box = litBox();
    if (box) {
      var b = box.getBoundingClientRect(), d = doc.getBoundingClientRect();
      var away = b.bottom < d.top + 4 || b.top > d.bottom - 4;
      back.hidden = !away;
    } else { back.hidden = true; }
    var line = doc.scrollTop + doc.clientHeight / 3;
    var current = pages.length ? pages[0].number : 0;
    Array.prototype.forEach.call(doc.querySelectorAll(".pw-page"), function (p) {
      if (p.offsetTop - doc.offsetTop <= line) { current = parseInt(p.dataset.page, 10); }
    });
    pageWord.textContent = pages.length ? "Page " + current + " of " + pages.length : "";
    pageWord.dataset.page = current;
    Array.prototype.forEach.call(win.querySelectorAll("[data-step]"), function (b) {
      b.disabled = !pageOf(current + parseInt(b.dataset.step, 10));
    });
  }

  function stepPage(step) {
    var current = parseInt(pageWord.dataset.page || "0", 10);
    var target = doc.querySelector(".pw-page[data-page='" + (current + step) + "']");
    if (target) { doc.scrollTo({ top: target.offsetTop - doc.offsetTop - 10, behavior: "smooth" }); }
  }

  function words() {
    var row = cited ? pageOf(cited.page) : null;
    var here = row ? (row.paragraphs || []).filter(function (p) { return p.n === cited.n; })[0] : null;
    return here ? here.text : "";
  }

  function head() {
    win.querySelector(".pw-title").textContent = (state && state.title) || title || "Document";
    var row = cited ? pageOf(cited.page) : null;
    place.textContent = (cited ? "page " + cited.page + ", paragraph " + cited.n : "") +
      (row && row.ocr ? " · read by OCR, so check the page" : "") +
      (cited && cited.finding ? " · " + cited.finding : "");
    win.setAttribute("aria-label", win.querySelector(".pw-title").textContent + ", " + place.textContent);
    openLink.href = docUrl ? docUrl + "?page=" + (cited ? cited.page : 1) + "&para=" + (cited ? cited.n : 1) : "#";
    var said = words();
    foot.textContent = said || (cited ? "Paragraph " + cited.n + " was not found on page " + cited.page + "." : "");
    foot.parentNode.hidden = !said && !cited;
  }

  function show() {
    pages = (state && state.pages_rows) || [];
    layout();
    head();
    bring(true);
    doc.focus({ preventScroll: true });
  }

  // Draws the window at the given paragraph, or turns an open one to it.
  function open(given) {
    if (!given || !given.stateUrl || !given.page) { return false; }
    var same = win && shownUrl === given.stateUrl;
    hooks = { onParagraph: given.onParagraph };
    docUrl = given.docUrl || "";
    title = given.title || "";
    cited = { page: parseInt(given.page, 10), n: parseInt(given.n, 10), finding: given.finding || "" };
    if (!win) { build(); }
    if (same) {
      Array.prototype.forEach.call(doc.querySelectorAll(".doc-box.lit, .doc-box.hit"), function (b) { b.classList.remove("lit"); b.classList.remove("hit"); });
      var box = doc.querySelector(".doc-box[data-page='" + cited.page + "'][data-n='" + cited.n + "']");
      if (box) { box.classList.add("lit"); }
      head();
      bring(false);
      return true;
    }
    shownUrl = given.stateUrl;
    doc.innerHTML = "<p class='muted small'>Reading the report...</p>";
    place.textContent = "page " + cited.page + ", paragraph " + cited.n;
    win.querySelector(".pw-title").textContent = title || "Document";
    stateOf(given.stateUrl).then(function (got) {
      if (!win || shownUrl !== given.stateUrl) { return; }
      state = got;
      show();
    });
    return true;
  }

  function close() {
    if (watcher) { watcher.disconnect(); watcher = null; }
    if (win) { win.remove(); }
    win = null; doc = null; shownUrl = ""; state = null; pages = []; cited = null;
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && win) { close(); event.stopPropagation(); }
  }, true);

  window.PASSAGE_WINDOW = { open: open, close: close, isOpen: function () { return !!win; } };
})();

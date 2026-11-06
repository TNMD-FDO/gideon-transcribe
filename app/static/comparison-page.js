// The Comparison page (Phase 12 chapter 11, v1.213.0).
//
// The findings in the wide column are report-panel.js's drawing; this script
// stands the report's page beside them: the page picture with its paragraph
// boxes, following the finding pressed with its paragraph lit, the pages
// stepped with the arrows, and a press on a paragraph's box lighting the
// findings that rest on it. A moment against an incident plays every camera
// of the incident at the time of day in the Preview's all-cameras shape.

(function () {
  "use strict";

  var page = document.getElementById("comparison");
  if (!page || !window.REPORT_PANEL) { return; }
  var box = document.getElementById("compare-box");
  var sheet = document.getElementById("cmp-sheet");
  var img = document.getElementById("cmp-sheet-img");
  var title = document.getElementById("cmp-page-title");
  var note = document.getElementById("cmp-page-note");
  var pages = [];
  var shown = 0;     // the page number in view
  var lit = null;    // {page, n} the paragraph lit

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function pct(part, whole) { return whole ? (100 * part / whole).toFixed(2) : "0"; }

  function pageOf(number) { return pages.filter(function (one) { return one.number === number; })[0] || null; }

  function showPage(number, litPara) {
    var one = pageOf(number);
    if (!one) { return; }
    shown = number;
    lit = litPara ? { page: number, n: litPara } : null;
    img.src = one.picture;
    sheet.style.aspectRatio = one.width + " / " + one.height;
    Array.prototype.forEach.call(sheet.querySelectorAll(".doc-box"), function (b) { b.remove(); });
    (one.paragraphs || []).forEach(function (p) {
      var b = document.createElement("span");
      b.className = "doc-box" + (lit && lit.n === p.n ? " lit" : "");
      b.dataset.page = number; b.dataset.n = p.n;
      b.title = "Page " + number + ", paragraph " + p.n;
      b.style.left = pct(p.box[0], one.width) + "%"; b.style.top = pct(p.box[1], one.height) + "%";
      b.style.width = pct(p.box[2] - p.box[0], one.width) + "%"; b.style.height = pct(p.box[3] - p.box[1], one.height) + "%";
      sheet.appendChild(b);
    });
    title.textContent = "Page " + number + " of " + pages.length;
    note.textContent = (one.ocr ? "read by OCR" : "") + (one.poor ? (one.ocr ? ", " : "") + "poorly read" : "");
    var litBox = sheet.querySelector(".doc-box.lit");
    if (litBox && litBox.scrollIntoView) { litBox.scrollIntoView({ block: "nearest" }); }
    Array.prototype.forEach.call(page.querySelectorAll("[data-page-step]"), function (b) {
      var step = parseInt(b.dataset.pageStep, 10);
      b.disabled = !pageOf(number + step);
    });
  }

  // The rows that rest on a paragraph light; the first scrolls into view.
  function lightRows(number, n) {
    var rows = box.querySelectorAll("tr[data-finding]");
    var first = null;
    Array.prototype.forEach.call(rows, function (row) {
      var on = String(row.dataset.page) === String(number) && String(row.dataset.n) === String(n);
      row.classList.toggle("lit", on);
      if (on && !first) { first = row; }
    });
    if (first) { first.scrollIntoView({ block: "center", behavior: "smooth" }); }
    else if (window.UI && window.UI.toast) { window.UI.toast("No finding rests on that paragraph."); }
  }

  fetch(page.dataset.documentState).then(function (answer) { return answer.ok ? answer.json() : null; }).then(function (state) {
    if (!state) { note.textContent = "The report's pages could not be read just now."; return; }
    pages = state.pages_rows || [];
    if (pages.length) { showPage(lit ? lit.page : 1, lit ? lit.n : 0); }
    else { title.textContent = "No pages"; }
  });

  page.addEventListener("click", function (event) {
    var step = event.target.closest("[data-page-step]");
    if (step) { showPage(shown + parseInt(step.dataset.pageStep, 10), 0); return; }
    var paraBox = event.target.closest("#cmp-sheet .doc-box");
    if (paraBox) { showPage(parseInt(paraBox.dataset.page, 10), parseInt(paraBox.dataset.n, 10)); lightRows(paraBox.dataset.page, paraBox.dataset.n); return; }
  });

  // A press on a finding's paragraph citation turns the page here rather
  // than opening the paragraph card: the page is already open beside it.
  box.addEventListener("click", function (event) {
    var cite = event.target.closest("a[data-para-card]");
    if (cite) {
      event.preventDefault();
      event.stopPropagation();
      showPage(parseInt(cite.dataset.page, 10), parseInt(cite.dataset.para, 10));
      Array.prototype.forEach.call(box.querySelectorAll("tr.lit"), function (r) { r.classList.remove("lit"); });
      var row = cite.closest("tr"); if (row) { row.classList.add("lit"); }
      return;
    }
    var hit = event.target.closest("tr[data-finding][data-page]");
    if (hit && !event.target.closest("a, button")) {
      Array.prototype.forEach.call(box.querySelectorAll("tr.lit"), function (r) { r.classList.remove("lit"); });
      hit.classList.add("lit");
      showPage(parseInt(hit.dataset.page, 10), parseInt(hit.dataset.n, 10));
    }
  }, true);

  var urls = {
    comparison: page.dataset.comparison,
    compare: page.dataset.compare,
    act: page.dataset.comparison + "/act",
    home: page.dataset.home,
    homeId: page.dataset.homeId,
    title: page.dataset.title
  };
  window.REPORT_PANEL.drawComparison(box, urls, null, {
    // Against an incident a finding has no recording: the moment plays every
    // camera of the incident at that time of day, in the Preview.
    playIncident: function (at, from) {
      if (window.Preview && window.Preview.open && urls.home === "incident" && from.dataset.recording) {
        window.Preview.open({ recording: from.dataset.recording, seconds: at, from: from });
        return;
      }
      var open = urls.home === "incident" ? "/case/" + page.dataset.case + "/incident/" + urls.homeId + "?t=" + encodeURIComponent(at) : "";
      if (open) { window.open(open, "_blank", "noopener"); }
    }
  });
})();

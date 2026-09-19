// The Report tab (Phase 8 chapter 4, part 2).
//
// One drawing for two places: the incident page's work panel and the
// recording page's work area. Each document linked there is drawn from its
// state (every page's picture and words): the pages stacked at the panel's
// width, the words under each page paragraph by paragraph with their
// numbers, a page read by OCR saying so, and Open for the document's own
// page. A press on a paragraph's box on the picture lights its words.

(function () {
  "use strict";

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function pct(part, whole) { return whole ? (100 * part / whole).toFixed(2) : "0"; }

  function drawDocument(state) {
    var html = "<section class='report-doc' data-document='" + escape(state.id) + "'>" +
      "<div class='row' style='align-items: baseline; gap: 8px; flex-wrap: wrap'>" +
      "<b class='grow'>" + escape(state.title) + "</b>" +
      "<span class='muted small'>" + escape(state.pages_line) + "</span>" +
      "<a class='btn small' href='" + escape(state.url) + "'>Open</a>" +
      "<a class='btn small ghost' href='" + escape(state.download) + "'>Download</a>" +
      "</div>";
    (state.pages_rows || []).forEach(function (page) {
      html += "<figure class='report-sheet' style='aspect-ratio: " + page.width + " / " + page.height + "'>" +
        "<img src='" + escape(page.picture) + "' alt='Page " + page.number + "' loading='lazy'>" +
        "<figcaption class='muted small'>Page " + page.number + (page.ocr ? " &middot; read by OCR" : "") + (page.poor ? " &middot; <span class='warn-ink'>poorly read</span>" : "") + "</figcaption>";
      (page.paragraphs || []).forEach(function (p) {
        html += "<span class='doc-box' data-page='" + page.number + "' data-n='" + p.n + "' title='Page " + page.number + ", paragraph " + p.n + "' style='left: " +
          pct(p.box[0], page.width) + "%; top: " + pct(p.box[1], page.height) + "%; width: " + pct(p.box[2] - p.box[0], page.width) + "%; height: " + pct(p.box[3] - p.box[1], page.height) + "%'></span>";
      });
      html += "</figure><div class='report-words'>";
      if (page.poor) { html += "<p class='notice warn small'>This page was poorly read. Read the picture, not the words.</p>"; }
      (page.paragraphs || []).forEach(function (p) {
        html += "<p class='doc-para' data-page='" + page.number + "' data-n='" + p.n + "'><span class='doc-n muted small'>" + p.n + "</span> " + escape(p.text) + "</p>";
      });
      if (!(page.paragraphs || []).length) { html += "<p class='muted small'>No words were read from this page.</p>"; }
      html += "</div>";
    });
    return html + "</section>";
  }

  function light(root, page, n) {
    Array.prototype.forEach.call(root.querySelectorAll(".lit"), function (one) { one.classList.remove("lit"); });
    var box = root.querySelector(".doc-box[data-page='" + page + "'][data-n='" + n + "']");
    var line = root.querySelector(".doc-para[data-page='" + page + "'][data-n='" + n + "']");
    if (box) { box.classList.add("lit"); }
    if (line) { line.classList.add("lit"); line.scrollIntoView({ block: "center" }); }
  }

  // Draw every document named by the box's data-documents (JSON: [{id, url,
  // state}]) into it, once, when asked.
  function draw(box) {
    if (!box || box.dataset.drawn === "yes") { return; }
    box.dataset.drawn = "yes";
    var listed = [];
    try { listed = JSON.parse(box.dataset.documents || "[]"); } catch (ignored) { listed = []; }
    if (!listed.length) {
      box.innerHTML = "<p class='muted'>No report is linked here yet. Add the report on the Details tab.</p>";
      return;
    }
    box.innerHTML = "<p class='muted small'>Reading the report...</p>";
    Promise.all(listed.map(function (one) {
      return fetch(one.state).then(function (answer) { return answer.ok ? answer.json() : null; }).catch(function () { return null; });
    })).then(function (states) {
      box.innerHTML = states.map(function (state, index) {
        if (!state) { return "<p class='muted'>" + escape(listed[index].title || "A document") + " could not be read just now.</p>"; }
        return drawDocument(state);
      }).join("");
    });
    box.addEventListener("click", function (event) {
      var target = event.target.closest(".doc-box, .doc-para");
      if (!target) { return; }
      light(box, target.dataset.page, target.dataset.n);
    });
  }

  window.REPORT_PANEL = { draw: draw };
})();

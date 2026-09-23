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

  function drawDocument(state, home) {
    var html = "<section class='report-doc' data-document='" + escape(state.id) + "'>" +
      "<div class='row' style='align-items: baseline; gap: 8px; flex-wrap: wrap'>" +
      "<b class='grow'>" + escape(state.title) + "</b>" +
      "<span class='muted small'>" + escape(state.pages_line) + "</span>" +
      "<a class='btn small' href='" + escape(state.url) + "'>Open</a>" +
      "<a class='btn small ghost' href='" + escape(state.download) + "'>Download</a>" +
      "</div>";
    // The comparison (part 3): against the home this panel belongs to, when
    // the document is the report for it.
    if (home && home.kind && state[home.kind] === home.id) {
      html += "<div class='compare-box' data-comparison='" + escape(state.comparison) + "' data-compare='" + escape(state.compare) +
        "' data-home='" + escape(home.kind) + "' data-home-id='" + escape(home.id) + "' data-title='" + escape(state.title) + "'>" +
        (window.INCIDENT_PAGE ? "<button type='button' class='small' data-open-comparison>Compare with the report</button> <span class='muted small compare-said'></span>" : "") +
        "</div>";
    }
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

  // The comparison (Phase 8 chapter 4, part 3) ----------------------------------------------
  //
  // One drawing for the layer on the incident page and the block on the
  // recording page: the state line, Compare (again), the marks as pills that
  // filter, one row per finding with the paragraph and the moment as
  // citations, and on each row Make it an event, a note and Dismiss.

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(url, fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (key) { body.append(key, fields[key]); });
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") }, body: body })
      .then(function (answer) { return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }); });
  }

  var comparisons = {};

  // The Export menu's Comparison to Word (Phase 8 chapter 6): a link while a
  // comparison is done, greyed with the reason until then.
  function setExportLink(C) {
    var link = document.getElementById("export-comparison");
    var off = document.getElementById("export-comparison-off");
    if (!link || !off) { return; }
    var ready = !!(C && C.state === "done" && C.export_url);
    link.hidden = !ready;
    off.hidden = ready;
    if (ready) { link.href = C.export_url; }
  }

  function shorten(text, most) {
    text = String(text || "");
    if (text.length <= most) { return text; }
    var cut = text.lastIndexOf(" ", most);
    return text.slice(0, cut > most / 2 ? cut : most) + "...";
  }
  function quoted(text) { return escape(text).replace(/'/g, "&#39;"); }

  function drawComparison(box, urls, setTitle) {
    if (!box) { return; }
    var key = urls.comparison + "?" + urls.home + "=" + urls.homeId;
    var kept = comparisons[key] || { filter: "", timer: null };
    comparisons[key] = kept;
    box.dataset.key = key;
    if (setTitle) { setTitle("Comparison, " + (urls.title || "")); }

    function load() {
      return fetch(key).then(function (answer) { return answer.ok ? answer.json() : null; }).then(function (state) {
        if (!state) { box.innerHTML = "<p class='muted'>The comparison could not be read just now.</p>"; return; }
        kept.state = state;
        render();
        window.clearTimeout(kept.timer);
        if (state.busy) { kept.timer = window.setTimeout(load, 3000); }
      });
    }

    function render() {
      var C = kept.state;
      var counts = C.counts || {};
      setExportLink(C);
      var html = "<div class='row' style='gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px'>" +
        "<button type='button' class='small' data-run" + (C.possible && !C.busy ? "" : " disabled") + " title='" + escape(C.why || "The assistant reads the report in windows of pages against the record; every finding cites the paragraph and the moment, and you mark them") + "'>" +
        (C.state === "done" ? "Compare again" : "Compare with the report") + "</button>" +
        (C.state === "done" && C.export_url ? "<a class='btn small ghost' href='" + escape(C.export_url) + "'>Comparison to Word</a>" : "") +
        "<span class='muted small grow'>" + escape(C.words || (C.possible ? "" : C.why || "")) + (C.stale ? "; " + escape(C.stale) + ", Compare again to refresh" : "") + "</span></div>";
      if (C.state === "done") {
        html += "<div class='row search-kinds' style='margin-bottom: 8px'>" +
          "<button type='button' class='pill small" + (!kept.filter ? " on" : "") + "' data-filter=''>All (" + Object.keys(counts).reduce(function (n, k) { return n + counts[k]; }, 0) + ")</button>" +
          (C.marks || []).map(function (mark) {
            return "<button type='button' class='pill small " + mark.key + (kept.filter === mark.key ? " on" : "") + "' data-filter='" + mark.key + "'>" + escape(mark.words) + " (" + (counts[mark.key] || 0) + ")</button>";
          }).join("") + "</div>";
        var rows = (C.findings || []).filter(function (one) { return !kept.filter || one.mark === kept.filter; });
        if (!rows.length) {
          html += "<p class='muted'>" + (C.findings && C.findings.length ? "Nothing with that mark." : "No findings: the report and the record gave the assistant nothing to set beside each other.") + "</p>";
        } else {
          html += "<p class='muted small'>Every row cites the report's paragraph and the record's moment; read both before trusting a mark. A person marks the rows; nothing joins the chronology until you make it an event.</p>";
          html += "<table class='inc-events compare-rows'><tbody>";
          rows.forEach(function (one) {
            html += "<tr data-finding='" + escape(one.id) + "' class='" + (one.dismissed ? "dismissed" : "") + "'>" +
              "<td class='t'><span class='pill small mark " + escape(one.mark) + "'>" + escape(one.mark_words) + "</span>" +
              "<div>" + (one.clock ? "<a class='cite play' href='#' data-at='" + one.at + "'>" + escape(one.clock) + "</a>" : "<span class='muted small'>no moment</span>") + "</div>" +
              (one.event ? "<div class='muted small'>on the chronology</div>" : "") + "</td>" +
              "<td><div class='claim'>" + escape(one.claim) + "</div>" +
              (one.page ? "<div class='small rests'><a class='cite' href='" + escape(one.paragraph_url) + "' data-para-card='1' data-doc-url='" + escape(C.document_url || "") + "' data-page='" + one.page + "' data-para='" + one.n + "' data-title='" + escape(C.document || "") + "'>page " + one.page + ", para " + one.n + "</a>" + (one.paragraph ? " <span class='muted' title='" + quoted(one.paragraph) + "'>" + escape(shorten(one.paragraph, 220)) + "</span>" : "") + "</div>" : "<div class='muted small'>Not in the report</div>") +
              (one.why ? "<div class='small why'>" + escape(one.why) + "</div>" : "") +
              (one.note ? "<div class='small note'><b>Note:</b> " + escape(one.note) + "</div>" : "") +
              "<div class='acts'>" +
              (C.can_make_event && !one.event ? "<button type='button' class='tiny primary' data-make='" + escape(one.id) + "'>Make it an event</button> " : "") +
              "<button type='button' class='tiny ghost' data-note='" + escape(one.id) + "'>Note</button> " +
              (one.dismissed ? "<button type='button' class='tiny ghost' data-undismiss='" + escape(one.id) + "'>Undo</button>" : "<button type='button' class='tiny ghost' data-dismiss='" + escape(one.id) + "'>Dismiss</button>") +
              "</div></td></tr>";
          });
          html += "</tbody></table>";
        }
      } else if (!C.state) {
        html += "<p class='muted'>Nothing yet. Compare with the report reads the report in windows of pages against the record and the chronology; every finding cites both sides.</p>";
      }
      box.innerHTML = html;
    }

    function act(fields) {
      fields.home = urls.home;
      fields[urls.home] = urls.homeId;
      return post(urls.act || (urls.comparison + "/act"), fields).then(function (got) {
        if (!got.ok) { UI.alert({ title: "That did not go through", body: (got.said && got.said.error) || "Try again." }); return; }
        kept.state = got.said;
        render();
      });
    }

    function seekTo(at) {
      if (window.INCIDENT_PAGE && window.INCIDENT_PAGE.seek) { window.INCIDENT_PAGE.seek(at); }
      else if (window.VIEWER && window.VIEWER.seek) { window.VIEWER.seek(at); }
    }

    if (!box.dataset.bound) {
      box.dataset.bound = "yes";
      box.addEventListener("click", function (event) {
        var run = event.target.closest("[data-run]");
        if (run) {
          run.disabled = true;
          var fields = {};
          fields[urls.home] = urls.homeId;
          post(urls.compare, fields).then(function (got) {
            if (!got.ok) { UI.alert({ title: "The comparison did not start", body: (got.said && got.said.error) || "Try again." }); run.disabled = false; return; }
            kept.state = got.said;
            render();
            kept.timer = window.setTimeout(load, 3000);
          });
          return;
        }
        var filter = event.target.closest("[data-filter]");
        if (filter) { kept.filter = filter.dataset.filter; render(); return; }
        var play = event.target.closest(".cite.play[data-at]");
        if (play) { event.preventDefault(); seekTo(parseFloat(play.dataset.at)); return; }
        var make = event.target.closest("[data-make]");
        if (make) {
          var finding = (kept.state.findings || []).filter(function (one) { return one.id === make.dataset.make; })[0];
          if (finding && (finding.at === null || finding.at === undefined) && window.INCIDENT_PAGE) {
            // Not on camera: the report has no clock, so the event box asks the moment.
            window.INCIDENT_PAGE.addEvent(undefined, finding.claim, "[Report, page " + finding.page + ", paragraph " + finding.n + "] " + finding.paragraph);
            return;
          }
          act({ action: "make_event", finding: make.dataset.make }).then(function () {
            if (window.INCIDENT_PAGE && window.INCIDENT_PAGE.refresh) { window.INCIDENT_PAGE.refresh(); }
            UI.toast("On the chronology.");
          });
          return;
        }
        var note = event.target.closest("[data-note]");
        if (note) {
          var current = (kept.state.findings || []).filter(function (one) { return one.id === note.dataset.note; })[0];
          UI.prompt({ title: "A note on this finding", body: "The office's own words; printed with the comparison.", value: current ? current.note : "", ok: "Save" })
            .then(function (text) { if (text !== null) { act({ action: "note", finding: note.dataset.note, note: text }); } });
          return;
        }
        var dismiss = event.target.closest("[data-dismiss]");
        if (dismiss) { act({ action: "dismiss", finding: dismiss.dataset.dismiss }); return; }
        var undo = event.target.closest("[data-undismiss]");
        if (undo) { act({ action: "undismiss", finding: undo.dataset.undismiss }); }
      });
    }
    load();
  }

  // Draw every document named by the box's data-documents (JSON: [{id, url,
  // state}]) into it, once, when asked.
  function draw(box) {
    if (!box || box.dataset.drawn === "yes") { return; }
    box.dataset.drawn = "yes";
    var listed = [];
    try { listed = JSON.parse(box.dataset.documents || "[]"); } catch (ignored) { listed = []; }
    var home = box.dataset.home ? { kind: box.dataset.home, id: box.dataset.homeId } : null;
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
        return drawDocument(state, home);
      }).join("");
      // On the recording page the comparison sits under the document; on the
      // incident page it opens as a layer from its button.
      Array.prototype.forEach.call(box.querySelectorAll(".compare-box"), function (one) {
        var urls = { comparison: one.dataset.comparison, compare: one.dataset.compare, act: one.dataset.comparison + "/act", home: one.dataset.home, homeId: one.dataset.homeId, title: one.dataset.title };
        if (window.INCIDENT_PAGE) {
          // The button's line says where the comparison stands without opening it.
          fetch(urls.comparison + "?" + urls.home + "=" + urls.homeId).then(function (answer) { return answer.ok ? answer.json() : null; }).then(function (state) {
            var said = one.querySelector(".compare-said");
            if (said && state) { said.textContent = state.words || (state.possible ? "" : state.why || ""); }
            if (state) { setExportLink(state); }
            // The button says what pressing it does (v1.74.3): a comparison
            // that exists is opened, not run again.
            var opener = one.querySelector("[data-open-comparison]");
            if (opener && state) {
              var total = Object.keys(state.counts || {}).reduce(function (n, k) { return n + (state.counts[k] || 0); }, 0);
              if (state.state === "done") { opener.textContent = "Open the comparison, " + (total ? total + " finding" + (total === 1 ? "" : "s") : "no findings"); }
              else if (state.busy) { opener.textContent = "Comparison running, open it"; }
              else if (state.state) { opener.textContent = "Open the comparison"; }
            }
          });
        } else {
          drawComparison(one, urls, null);
        }
      });
    });
    box.addEventListener("click", function (event) {
      var open = event.target.closest("[data-open-comparison]");
      if (open && window.INCIDENT_PAGE && window.INCIDENT_PAGE.openComparison) {
        var holder = open.closest(".compare-box");
        var urls = { comparison: holder.dataset.comparison, compare: holder.dataset.compare, act: holder.dataset.comparison + "/act", home: holder.dataset.home, homeId: holder.dataset.homeId, title: holder.dataset.title };
        window.INCIDENT_PAGE.openComparison(function (layerBox, setTitle) { drawComparison(layerBox, urls, setTitle); });
        return;
      }
      var target = event.target.closest(".doc-box, .doc-para");
      if (!target) { return; }
      light(box, target.dataset.page, target.dataset.n);
    });
  }

  window.REPORT_PANEL = { draw: draw, drawComparison: drawComparison };
})();

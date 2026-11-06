// The comparison (Phase 8 chapter 4, part 3), drawn on the Comparison page
// (Phase 12 chapter 11, v1.213.0).
//
// Until v1.212.0 this script also drew the Report tab of the incident page
// and the recording page (the documents' pages stacked at the panel's
// width) and the comparison as a layer over it; both left with the shelf,
// and the drawing of a comparison is what stays: the state line with
// Compare again and Comparison to Word, the marks as pills that filter, the
// order (by time, by recording on a case comparison, by page), one row per
// finding with the paragraph and the moment as citations, and on each row
// Make it a note, a note and Dismiss. A moment plays in the Preview window.

(function () {
  "use strict";

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

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

  function shorten(text, most) {
    text = String(text || "");
    if (text.length <= most) { return text; }
    var cut = text.lastIndexOf(" ", most);
    return text.slice(0, cut > most / 2 ? cut : most) + "...";
  }
  function quoted(text) { return escape(text).replace(/'/g, "&#39;"); }

  function drawComparison(box, urls, setTitle, hooks) {
    if (!box) { return; }
    hooks = hooks || {};
    var key = urls.comparison + "?" + urls.home + "=" + urls.homeId;
    var kept = comparisons[key] || { filter: "", order: "time", timer: null };
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
        if (hooks.loaded) { hooks.loaded(state); }
      });
    }

    function ordered(rows) {
      var C = kept.state;
      if (kept.order === "recording" && C.home === "case") {
        return rows.slice().sort(function (a, b) { return (a.recording || "").localeCompare(b.recording || "") || ((a.at === null || a.at === undefined ? -1 : a.at) - (b.at === null || b.at === undefined ? -1 : b.at)); });
      }
      if (kept.order === "page") {
        // By page (v1.213.0): the report's own order; a Not in the report
        // finding has no page and comes last.
        return rows.slice().sort(function (a, b) { return ((a.page || 9999) - (b.page || 9999)) || ((a.n || 0) - (b.n || 0)); });
      }
      return rows;
    }

    function render() {
      var C = kept.state;
      var counts = C.counts || {};
      var html = "<div class='row cmp-state' style='gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px'>" +
        "<button type='button' class='small' data-run" + (C.possible && !C.busy ? "" : " disabled") + " title='" + escape(C.why || "The assistant reads the report in windows of pages against the record; every finding cites the paragraph and the moment, and you mark them") + "'>" +
        (C.state === "done" ? "Compare again" : (C.busy ? "Comparing..." : "Compare")) + "</button>" +
        (C.state === "done" && C.export_url ? "<a class='btn small ghost' href='" + escape(C.export_url) + "'>Comparison to Word</a>" : "") +
        "<div class='muted small grow'>" +
        (C.busy && C.expectation && C.expectation.words
          ? window.Expectation.html({ step: (C.words || "").replace(/\.\.\.$/, ""), state: C.state, expectation: C.expectation, inline: true, leaveable: true })
          : escape(C.words || (C.possible ? "" : C.why || "")) + (C.stale ? "; " + escape(C.stale) + ", Compare again to refresh" : "")) +
        "</div></div>";
      if (C.state === "done") {
        html += "<div class='row search-kinds' style='margin-bottom: 8px'>" +
          "<button type='button' class='pill small" + (!kept.filter ? " on" : "") + "' data-filter=''>All (" + Object.keys(counts).reduce(function (n, k) { return n + counts[k]; }, 0) + ")</button>" +
          (C.marks || []).map(function (mark) {
            return "<button type='button' class='pill small " + mark.key + (kept.filter === mark.key ? " on" : "") + "' data-filter='" + mark.key + "'>" + escape(mark.words) + " (" + (counts[mark.key] || 0) + ")</button>";
          }).join("") +
          "<span class='grow'></span>" +
          "<span class='toggle order' role='group' aria-label='The order'>" +
          "<button type='button' class='small" + (kept.order === "time" ? " on" : "") + "' data-order='time'>" + (C.home === "case" ? "By day and time" : "By time") + "</button>" +
          (C.home === "case" ? "<button type='button' class='small" + (kept.order === "recording" ? " on" : "") + "' data-order='recording'>By recording</button>" : "") +
          "<button type='button' class='small" + (kept.order === "page" ? " on" : "") + "' data-order='page' title='The findings in the report&#39;s own order'>By page</button>" +
          "</span></div>";
        var rows = ordered((C.findings || []).filter(function (one) { return !kept.filter || one.mark === kept.filter; }));
        if (!rows.length) {
          html += "<p class='muted'>" + (C.findings && C.findings.length ? "Nothing with that mark." : "No findings: the report and the record gave the assistant nothing to set beside each other.") + "</p>";
        } else {
          html += "<p class='muted small'>Every row cites the report's paragraph and the record's moment; read both before trusting a mark. A person marks the rows; nothing joins a recording until you make it a note.</p>";
          html += "<table class='inc-events compare-rows'><tbody>";
          rows.forEach(function (one) {
            html += "<tr data-finding='" + escape(one.id) + "'" + (one.page ? " data-page='" + one.page + "' data-n='" + one.n + "'" : "") + " class='" + (one.dismissed ? "dismissed" : "") + "'>" +
              "<td class='t'><span class='pill small mark " + escape(one.mark) + "'>" + escape(one.mark_words) + "</span>" +
              "<div>" + (one.clock ? "<a class='cite play' href='#' data-at='" + one.at + "'" + (one.recording_id ? " data-recording='" + escape(one.recording_id) + "'" : "") + " title='Play this moment here'>" + escape(one.clock) + "</a>" : "<span class='muted small'>no moment</span>") + "</div>" +
              (one.recording ? "<div class='muted small'>" + escape(one.recording) + "</div>" : "") +
              (one.note_id ? "<div class='muted small'>a note on " + escape(one.note_on || "the recording") + "</div>" : "") + "</td>" +
              "<td><div class='claim'>" + escape(one.claim) + "</div>" +
              (one.page ? "<div class='small rests'><a class='cite' href='" + escape(one.paragraph_url) + "' data-para-card='1' data-doc-url='" + escape(C.document_url || "") + "' data-page='" + one.page + "' data-para='" + one.n + "' data-title='" + escape(C.document || "") + "'>page " + one.page + ", para " + one.n + "</a>" + (one.paragraph ? " <span class='muted' title='" + quoted(one.paragraph) + "'>" + escape(shorten(one.paragraph, 220)) + "</span>" : "") + "</div>" : "<div class='muted small'>Not in the report</div>") +
              (one.why ? "<div class='small why'>" + escape(one.why) + "</div>" : "") +
              (one.note ? "<div class='small note'><b>Note:</b> " + escape(one.note) + "</div>" : "") +
              "<div class='acts'>" +
              (C.can_make_note && !one.note_id ? "<button type='button' class='tiny primary' data-make='" + escape(one.id) + "'>" + ((one.at === null || one.at === undefined) ? "Choose the moment" : "Make it a note") + "</button> " : "") +
              "<button type='button' class='tiny ghost' data-note='" + escape(one.id) + "'>Note</button> " +
              (one.dismissed ? "<button type='button' class='tiny ghost' data-undismiss='" + escape(one.id) + "'>Undo</button>" : "<button type='button' class='tiny ghost' data-dismiss='" + escape(one.id) + "'>Dismiss</button>") +
              "</div></td></tr>";
          });
          html += "</tbody></table>";
        }
      } else if (!C.state) {
        html += "<p class='muted'>Nothing yet. Compare reads the report in windows of pages against the record; every finding cites both sides.</p>";
      } else if (C.state === "failed") {
        html += "<p class='muted'>The comparison did not finish. Compare again tries once more.</p>";
      }
      box.innerHTML = html;
      if (hooks.rendered) { hooks.rendered(C); }
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

    // The moment of a finding on an incident's clock, as the Preview plays
    // it: the finding names no recording, so the Preview opens on the
    // incident's cameras at the time of day (all-cameras shape).
    function playAt(play) {
      if (play.dataset.recording && window.Preview && window.Preview.open) {
        window.Preview.open({ recording: play.dataset.recording, seconds: parseFloat(play.dataset.at), from: play });
        return;
      }
      if (hooks.playIncident) { hooks.playIncident(parseFloat(play.dataset.at), play); }
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
        var order = event.target.closest("[data-order]");
        if (order) { kept.order = order.dataset.order; render(); return; }
        var play = event.target.closest(".cite.play[data-at]");
        if (play) { event.preventDefault(); playAt(play); return; }
        var make = event.target.closest("[data-make]");
        if (make) {
          var finding = (kept.state.findings || []).filter(function (one) { return one.id === make.dataset.make; })[0];
          if (finding && (finding.at === null || finding.at === undefined) && finding.recording_id && window.Preview && window.Preview.open) {
            // Choose the moment (v1.170.0): the Preview's window on the finding's recording, Make it a note here in its foot.
            var fields = { action: "make_note", finding: finding.id, home: urls.home };
            fields[urls.home] = urls.homeId;
            window.Preview.open({ recording: finding.recording_id, seconds: 0, from: make, finding: { claim: finding.claim, where: finding.recording, act: urls.act || (urls.comparison + "/act"), fields: fields, done: load } });
            return;
          }
          if (finding && (finding.at === null || finding.at === undefined)) {
            // Not on camera against an incident or a camera (v1.213.0): the
            // report has no clock, so the moment is asked for in words; the
            // app reads it on the record's clock.
            UI.prompt({ title: "At what moment?", body: urls.home === "incident" ? "The time of day on the incident's clock, as hh:mm:ss." : "The time into the recording, as mm:ss or hh:mm:ss.", value: "", ok: "Make it a note" })
              .then(function (text) { if (text !== null && text.trim()) { act({ action: "make_note", finding: finding.id, at_words: text.trim() }).then(function () { UI.toast("Noted."); }); } });
            return;
          }
          act({ action: "make_note", finding: make.dataset.make }).then(function () { UI.toast("Noted on the recording."); });
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
    return { reload: load, state: function () { return kept.state; } };
  }

  window.REPORT_PANEL = { drawComparison: drawComparison };
})();

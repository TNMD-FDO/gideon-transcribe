// The comparison against the case (Phase 10 chapter 4, v1.170.0): on the
// Documents tab, Compare with the case on a document's row opens one layer
// under the table, drawn by report-panel.js as the incident's and the
// recording's comparisons are, with the case as the home.
(function () {
  "use strict";
  var layer = document.getElementById("case-compare");
  if (!layer || !window.REPORT_PANEL) { return; }
  var box = document.getElementById("case-compare-box");
  var title = document.getElementById("case-compare-title");
  function open(button) {
    var urls = { comparison: button.dataset.comparison, compare: button.dataset.compare, act: button.dataset.comparison + "/act", home: "case", homeId: layer.dataset.case, title: button.dataset.title };
    document.querySelectorAll("[data-case-compare]").forEach(function (b) { b.classList.toggle("on", b === button); });
    layer.hidden = false;
    box.dataset.key = "";
    window.REPORT_PANEL.drawComparison(box, urls, function (words) { title.textContent = words; });
    layer.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-case-compare]");
    if (button) { open(button); return; }
    if (event.target.closest("[data-case-compare-back]")) { layer.hidden = true; box.innerHTML = ""; }
  });
  // Opened from an address that names the document (?compare=<id>).
  var asked = new URLSearchParams(location.search).get("compare");
  if (asked) {
    var wanted = Array.prototype.filter.call(document.querySelectorAll("[data-case-compare]"), function (b) { return b.dataset.comparison.indexOf(asked) >= 0; })[0];
    if (wanted) { open(wanted); }
  }
})();

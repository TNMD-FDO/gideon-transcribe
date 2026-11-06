// The Documents tab as the shelf (Phase 12 chapter 11, v1.213.0).
//
// The chips narrow the shelf (all, reports, pictures, compared, not yet
// compared, stale); a PDF dropped on the drop zone adds itself through the
// add page's own form; Compare a report with this incident (from an
// incident's or a recording's Details) opens the Compare against menu on
// the first report that can be read against that record.

(function () {
  "use strict";

  var chips = document.getElementById("shelf-chips");
  var reports = document.getElementById("shelf-reports");
  var pictures = document.getElementById("shelf-pictures");

  function rows() { return Array.prototype.slice.call(document.querySelectorAll("#documents tr.document-row")); }
  function cards() { return Array.prototype.slice.call(document.querySelectorAll("#pictures .shelf-picture")); }

  function filter(kind) {
    var showReports = kind !== "pictures";
    var showPictures = kind === "all" || kind === "pictures";
    rows().forEach(function (row) {
      var on = showReports;
      if (kind === "compared") { on = row.dataset.compared === "yes"; }
      if (kind === "not-yet") { on = row.dataset.compared === "no"; }
      if (kind === "stale") { on = row.dataset.stale === "yes"; }
      row.hidden = !on;
    });
    if (reports) { reports.hidden = !showReports; }
    if (pictures) { pictures.hidden = !showPictures; }
    cards().forEach(function (card) { card.hidden = !showPictures; });
    if (chips) {
      Array.prototype.forEach.call(chips.querySelectorAll("[data-shelf-filter]"), function (chip) { chip.classList.toggle("on", chip.dataset.shelfFilter === kind); });
    }
  }

  if (chips) {
    chips.addEventListener("click", function (event) {
      var chip = event.target.closest("[data-shelf-filter]");
      if (chip) { filter(chip.dataset.shelfFilter); }
    });
  }

  // The drop zone: one PDF, added with the file's name as its title and no
  // about; the form posts as the add page's own does.
  var drop = document.getElementById("document-drop");
  if (drop) {
    var input = drop.querySelector("input[type=file]");
    function take(files) {
      if (!files || !files.length) { return; }
      var file = files[0];
      if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
        if (window.UI && window.UI.toast) { window.UI.toast("Only a PDF can be added; save the file as a PDF first.", "bad"); }
        return;
      }
      try {
        var list = new DataTransfer();
        list.items.add(file);
        input.files = list.files;
      } catch (e) {
        input.files = files;
      }
      drop.classList.add("busy");
      drop.querySelector("span").textContent = "Adding " + file.name + "...";
      drop.submit();
    }
    ["dragenter", "dragover"].forEach(function (name) {
      drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.add("over"); });
    });
    ["dragleave", "drop"].forEach(function (name) {
      drop.addEventListener(name, function (event) { event.preventDefault(); drop.classList.remove("over"); });
    });
    drop.addEventListener("drop", function (event) { take(event.dataTransfer && event.dataTransfer.files); });
    drop.addEventListener("click", function (event) {
      if (event.target.closest("input")) { return; }
      input.click();
    });
    input.addEventListener("change", function () { take(input.files); });
  }

  // Compare a report with this incident (or camera): ?against=incident:<id>
  // opens the menu on the first report that can be read against it.
  var against = new URLSearchParams(location.search).get("against");
  if (against) {
    var button = document.querySelector("[data-compare-against='" + against.replace(/'/g, "") + "']");
    if (button) {
      var menu = button.closest("details");
      if (menu) { menu.open = true; }
      button.scrollIntoView({ block: "center" });
      button.focus();
      if (window.UI && window.UI.toast) { window.UI.toast("Press the record under Compare against to read this report against it."); }
    } else if (window.UI && window.UI.toast) {
      window.UI.toast(rows().length ? "No report here can be read against that yet." : "Add a report first, then compare it.");
    }
  }
})();

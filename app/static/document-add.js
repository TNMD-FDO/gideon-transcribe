// Add a document (Phase 12 chapter 11, v1.213.0): the about's picker shows
// for the choice made, the compare choice "against what it is about" shows
// only with an incident or a camera chosen, and the drop zone names the
// file it holds.

(function () {
  "use strict";

  var form = document.getElementById("document-form");
  if (!form) { return; }
  var incidentPick = document.getElementById("pick-incident");
  var recordingPick = document.getElementById("pick-recording");
  var compareAbout = document.getElementById("compare-about-choice");
  var file = form.querySelector("input[type=file]");
  var name = document.getElementById("add-drop-name");
  var drop = document.getElementById("add-drop");

  function aboutChoice() {
    var picked = form.querySelector("[name=about]:checked");
    return picked ? picked.value : "nothing";
  }

  function drawAbout() {
    var choice = aboutChoice();
    if (incidentPick) { incidentPick.hidden = choice !== "incident"; }
    if (recordingPick) { recordingPick.hidden = choice !== "recording"; }
    if (compareAbout) {
      compareAbout.hidden = choice === "nothing";
      if (choice === "nothing" && compareAbout.querySelector("input").checked) {
        var none = form.querySelector("[name=compare][value=none]");
        if (none) { none.checked = true; }
      }
    }
    Array.prototype.forEach.call(form.querySelectorAll(".choice-btn"), function (label) {
      var input = label.querySelector("input");
      label.classList.toggle("on", !!(input && input.checked));
    });
  }

  form.addEventListener("change", function (event) {
    if (event.target.name === "about" || event.target.name === "compare") { drawAbout(); }
  });
  drawAbout();

  if (file && name) {
    file.addEventListener("change", function () {
      name.textContent = file.files && file.files.length ? file.files[0].name : "";
    });
  }
  if (drop && file) {
    ["dragenter", "dragover"].forEach(function (kind) { drop.addEventListener(kind, function (event) { event.preventDefault(); drop.classList.add("over"); }); });
    ["dragleave", "drop"].forEach(function (kind) { drop.addEventListener(kind, function (event) { event.preventDefault(); drop.classList.remove("over"); }); });
    drop.addEventListener("drop", function (event) {
      var files = event.dataTransfer && event.dataTransfer.files;
      if (!files || !files.length) { return; }
      try { var list = new DataTransfer(); list.items.add(files[0]); file.files = list.files; } catch (e) { file.files = files; }
      if (name) { name.textContent = files[0].name; }
    });
  }
})();

// The settings card (v1.174.0): read and written by the Upload page and by
// Bulk transcription alike, from templates/upload-settings.html, whose ids
// are this script's contract. The page's own script decides whose settings
// the card is showing (the batch's or one file's); this one only reads the
// controls into a plain object and writes one back.

(function () {
  "use strict";

  var hint = document.getElementById("hint");
  var diarizeBox = document.getElementById("diarize");
  if (!hint || !diarizeBox) { return; }
  var diarizeWarning = document.getElementById("diarize-warning");

  function by(id) { return document.getElementById(id); }

  function showHintBoxes() {
    by("hint-a").hidden = hint.value === "";
    by("hint-b").hidden = hint.value !== "between";
  }

  // The warning under the box is shown while speaker separation is on, for
  // the batch or for one file.
  function showDiarizeWarning() {
    if (diarizeWarning) { diarizeWarning.hidden = !diarizeBox.checked; }
  }

  function read() {
    var speakers = null;
    if (hint.value === "exactly") {
      speakers = { exactly: parseInt(by("hint-a").value, 10) };
    } else if (hint.value === "between") {
      speakers = { between: [parseInt(by("hint-a").value, 10), parseInt(by("hint-b").value, 10)] };
    }
    var intoCase = by("add-to-case");
    var whatKind = by("recording-type");
    var mailMe = by("email-when-done");
    var enrich = by("enrich-with-vision");
    var tick = by("vision-tick");
    var summaries = by("summaries-tonight");
    var summariesTick = by("summaries-tick");
    return {
      // Write each recording's summary tonight (Phase 9 chapter 5): only
      // while its tick is shown, which is only for a batch into a case.
      summaries: !!(summaries && summariesTick && !summariesTick.hidden && summaries.checked),
      // Absent while the Admin's switch is off or mail is not configured.
      email_when_done: !!(mailMe && !mailMe.disabled && mailMe.checked),
      // Enrich with vision (Phase 4 chapter 5): only while its tick is shown.
      enrich: !!(enrich && tick && !tick.hidden && enrich.checked),
      diarize: diarizeBox.checked,
      speakers: speakers,
      translate: by("translate").checked,
      language: by("language").value,
      vocabulary: by("vocabulary").value.split("\n"),
      context: by("context").value,
      // Absent from the card on Bulk transcription and while Folder
      // management is off.
      case: intoCase ? intoCase.value : "",
      case_name: intoCase && intoCase.value ? intoCase.options[intoCase.selectedIndex].textContent : "",
      recording_type: whatKind ? whatKind.value : ""
    };
  }

  function write(values) {
    var mailMe = by("email-when-done");
    if (mailMe && !mailMe.disabled) { mailMe.checked = !!values.email_when_done; }
    diarizeBox.checked = !!values.diarize;
    showDiarizeWarning();
    var translate = by("translate");
    // Greyed under the Qwen3-ASR recogniser (ADR 0025): never ticked then.
    translate.checked = !translate.disabled && !!values.translate;
    by("language").value = values.language || "";
    by("vocabulary").value = (values.vocabulary || []).join("\n");
    by("context").value = values.context || "";

    var intoCase = by("add-to-case");
    if (intoCase) {
      if (values.case) { intoCase.value = values.case; }
      by("recording-type").value = values.recording_type || "";
      // A recording type belongs to a case, so it is offered only once one
      // is chosen.
      by("type-field").hidden = !intoCase.value;
    }

    var speakers = values.speakers;
    if (speakers && speakers.exactly) {
      hint.value = "exactly";
      by("hint-a").value = speakers.exactly;
    } else if (speakers && speakers.between) {
      hint.value = "between";
      by("hint-a").value = speakers.between[0];
      by("hint-b").value = speakers.between[1];
    } else {
      hint.value = "";
    }
    showHintBoxes();
  }

  function enable(on) {
    Array.prototype.forEach.call(
      document.querySelectorAll("#the-settings input, #the-settings select, #the-settings textarea"),
      function (control) { control.disabled = !on; }
    );
    // The two controls greyed for a reason of their own stay greyed.
    var translate = by("translate");
    if (translate && translate.dataset.greyed === "yes") { translate.disabled = true; }
    if (hint.dataset.greyed === "yes") { hint.disabled = true; }
  }

  function onChange(fn) {
    Array.prototype.forEach.call(
      document.querySelectorAll("#the-settings input, #the-settings select, #the-settings textarea"),
      function (control) {
        control.addEventListener("change", fn);
        control.addEventListener("input", fn);
      }
    );
  }

  function copyOf(values) { return JSON.parse(JSON.stringify(values)); }

  // The controls greyed by the page for a reason (the hint under Nemotron,
  // Translate under Qwen3-ASR with no engine) are remembered, so enabling
  // the card for one file's own settings never ungreys them.
  if (hint.disabled) { hint.dataset.greyed = "yes"; }
  if (by("translate").disabled) { by("translate").dataset.greyed = "yes"; }

  diarizeBox.addEventListener("change", showDiarizeWarning);
  hint.addEventListener("change", showHintBoxes);

  window.UploadSettings = { read: read, write: write, enable: enable, onChange: onChange, copyOf: copyOf, showHintBoxes: showHintBoxes };
})();

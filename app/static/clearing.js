// Finishing with recordings: "Done with these" on a batch, and "Clear my
// recordings" on the recordings page.
//
// An office running batches works in a loop: upload, wait, download, clear,
// upload the next lot. Until this existed the clearing step meant signing
// out, because the only other way to remove twelve recordings was to delete
// them one at a time. That is not only untidy. Every recording counts
// against its owner's quota until it goes, so the loop stalled at the quota
// by the middle of the morning with no remedy that kept the person signed
// in.
//
// The counts are asked for before anything is confirmed, so the sentence
// says how much is going and what has been made from it. It is final, and it
// reads as final.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function many(count, word) {
    return count + " " + word + (count === 1 ? "" : "s");
  }

  function theSentence(told, batch) {
    var what = batch ? "Done with these removes " : "This removes ";
    what += many(told.recordings, "recording");
    if (told.transcripts) {
      what += " and " + many(told.transcripts, "transcript");
    }
    if (told.clips) {
      what += " and " + many(told.clips, "clip");
    }
    what += ", " + told.size + ".";
    return what;
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".clear-recordings");
    if (!button) { return; }

    var batch = button.dataset.batch || "";
    var asking = "/recordings/what-would-go" + (batch ? "?batch=" + batch : "");

    button.disabled = true;
    fetch(asking, { headers: { "Accept": "application/json" } })
      .then(function (answer) { return answer.json(); })
      .then(function (told) {
        button.disabled = false;
        if (!told.recordings) {
          UI.toast("There is nothing to clear.", { icon: "info" });
          return;
        }
        return UI.confirm({
          title: batch ? "Done with these recordings?" : "Clear your recordings?",
          body: [theSentence(told, batch), "Download anything you want to keep first. This cannot be undone."],
          ok: batch ? "Remove them" : "Clear my recordings",
          cancel: "Keep them",
          danger: true
        }).then(function (yes) {
          if (!yes) { return; }
          button.disabled = true;
          var form = new FormData();
          if (batch) { form.append("batch", batch); }
          return fetch("/recordings/clear", {
            method: "POST",
            headers: { "X-CSRFToken": cookie("csrftoken") },
            body: form
          }).then(function (answer) { return answer.json(); })
            .then(function (done) {
              window.location.href = done.where || "/";
            });
        });
      })
      .catch(function () {
        button.disabled = false;
        UI.alert({
          title: "Nothing was cleared",
          body: "The page could not reach the app. Try again, and if it keeps happening tell whoever looks after the server."
        });
      });
  });
})();

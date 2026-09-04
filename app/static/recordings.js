// Delete on a recording: one control that removes the recording and
// everything about it, behind a confirmation that says so.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".delete");
    if (!button) { return; }

    if (!window.confirm(
      "Delete " + button.dataset.title + "? This removes the recording, its " +
      "transcript, and everything else about it. It cannot be undone, and " +
      "anything you want to keep has to be exported first."
    )) { return; }

    fetch("/recording/" + button.dataset.recording + "/delete", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function (answer) {
      if (answer.ok) { window.location.reload(); }
    });
  });
})();

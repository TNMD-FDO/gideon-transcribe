// Trying again, and processing again.
//
// Both make a batch of one recording and take the person to its batch page,
// which is where everything about a running transcription already lives. The
// only difference is what they are told first.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function send(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (answer) {
      return answer.json().then(function (said) {
        return { ok: answer.ok, said: said };
      });
    });
  }

  function went(answer) {
    if (answer.ok && answer.said.batch) {
      window.location = "/batch/" + answer.said.batch;
      return;
    }
    // A refusal says why, and where the batch in the way is.
    var words = answer.said.error || "That could not be done.";
    if (answer.said.batch) {
      words += "\n\nOpen it to see how it is getting on?";
      if (window.confirm(words)) {
        window.location = "/batch/" + answer.said.batch;
      }
      return;
    }
    window.alert(words);
  }

  document.addEventListener("click", function (event) {
    var again = event.target.closest(".retry");
    if (again) {
      again.disabled = true;
      send("/recording/" + again.dataset.recording + "/retry")
        .then(went)
        .catch(function () { again.disabled = false; });
      return;
    }

    var over = event.target.closest(".process-again");
    if (!over) { return; }

    // What a person is giving up has to be said before they agree to it, not
    // after: the corrections and the speaker names are somebody's afternoon.
    if (!window.confirm(
      "Transcribe " + over.dataset.title + " again from the start?\n\n" +
      "Lost: this transcript, every correction made to it, and the speaker " +
      "names.\n" +
      "Kept: the recording itself, its clips and their spans, and the record " +
      "of both processings.\n\n" +
      "The old transcript stays readable, and locked, until the new one lands."
    )) { return; }

    over.disabled = true;
    send("/recording/" + over.dataset.recording + "/process-again", {})
      .then(went)
      .catch(function () { over.disabled = false; });
  });
})();

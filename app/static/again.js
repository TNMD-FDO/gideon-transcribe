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
      UI.confirm({ title: "Not yet", body: [words, "Open that batch to see how it is getting on?"], ok: "Open the batch", cancel: "Stay here" })
        .then(function (yes) { if (yes) { window.location = "/batch/" + answer.said.batch; } });
      return;
    }
    UI.alert({ title: "Not yet", body: words });
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

    // Tell the speakers apart, offered where the transcript says the speakers
    // were not told apart (v1.54.1): the same second transcription, with the
    // upload page's own warning about speaker separation first.
    var tell = event.target.closest(".tell-speakers");
    if (tell) {
      UI.confirm({
        title: "Tell the speakers apart in " + tell.dataset.title + "?",
        body: [
          "Speaker separation is not always right. It can run two people together or split one person in two, and the labels are guesses until somebody checks them against the audio.",
          "The recording is transcribed again with the speakers told apart. Lost: this transcript and every correction made to it. Kept: the recording, its clips and their spans, and the record of both processings.",
          "The old transcript stays readable, and locked, until the new one lands."
        ],
        ok: "Tell the speakers apart",
        cancel: "Keep this transcript",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        tell.disabled = true;
        send("/recording/" + tell.dataset.recording + "/process-again", { diarize: true })
          .then(went)
          .catch(function () { tell.disabled = false; });
      });
      return;
    }

    var over = event.target.closest(".process-again");
    if (!over) { return; }

    // What a person is giving up has to be said before they agree to it, not
    // after: the corrections and the speaker names are somebody's afternoon.
    // Tell the speakers apart may be changed here (v1.54.1): a recording
    // transcribed without it is sent back with it, or the other way round.
    UI.confirm({
      title: "Transcribe " + over.dataset.title + " again?",
      body: [
        "Lost: this transcript, every correction made to it, and the speaker names.",
        "Kept: the recording, its clips and their spans, and the record of both processings.",
        "The old transcript stays readable, and locked, until the new one lands."
      ],
      check: { label: "Tell the speakers apart", checked: over.dataset.diarize === "yes" },
      ok: "Transcribe again",
      cancel: "Keep this transcript",
      danger: true
    }).then(function (answer) {
      if (!answer || !answer.ok) { return; }
      over.disabled = true;
      send("/recording/" + over.dataset.recording + "/process-again", { diarize: !!answer.checked })
        .then(went)
        .catch(function () { over.disabled = false; });
    });
  });
})();

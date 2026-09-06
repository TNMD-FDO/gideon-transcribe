// The Dictations page: write the memo, send to a colleague, take it back,
// delete. Add to a case is the Move to case picker from cases.js.

(function () {
  "use strict";

  var page = document.getElementById("dictations");
  if (!page) { return; }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify(body || {})
    }).then(function (answer) {
      return answer.json().then(function (said) { return { ok: answer.ok, said: said }; });
    });
  }

  function escaped(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

  // Rows still on their way, or writing a memo, ask where they stand.
  function watch(recordingId, cell, until) {
    var tries = 0;
    var timer = window.setInterval(function () {
      tries += 1;
      fetch("/dictation/" + recordingId + "/state", { cache: "no-store" })
        .then(function (answer) { return answer.json(); })
        .then(function (said) {
          if (until(said)) { window.clearInterval(timer); window.location.reload(); return; }
          if (cell && said.says) { cell.textContent = said.says; }
          if (tries > 900) { window.clearInterval(timer); }
        })
        .catch(function () {});
    }, 4000);
  }

  document.querySelectorAll("tr[data-recording] .queue-line").forEach(function (line) {
    var row = line.closest("tr");
    watch(row.dataset.recording, line, function (said) { return said.state === "ready" || said.state === "failed"; });
  });
  document.querySelectorAll(".memo-cell .pill.warn").forEach(function (pill) {
    var row = pill.closest("tr");
    watch(row.dataset.recording, null, function (said) { return said.memo === "done" || said.memo === "failed"; });
  });

  page.addEventListener("click", function (event) {
    var write = event.target.closest(".write-memo");
    if (write) {
      write.disabled = true;
      post("/dictation/" + write.dataset.recording + "/memo").then(function (answer) {
        if (!answer.ok) {
          write.disabled = false;
          UI.toast(answer.said.why || "The memo could not be started.", { problem: true, icon: "warning" });
          return;
        }
        var cell = write.closest(".memo-cell");
        cell.innerHTML = "<span class='pill warn'>Writing</span>";
        watch(write.dataset.recording, null, function (said) { return said.memo === "done" || said.memo === "failed"; });
      });
      return;
    }

    var send = event.target.closest(".send-to");
    if (send) { sendTo(send.dataset.recording, send.dataset.title); return; }

    var back = event.target.closest(".take-back");
    if (back) {
      UI.confirm({
        title: "Take this dictation back from " + back.dataset.name + "?",
        body: "It leaves their Dictations page. Nothing is mailed.",
        ok: "Take back",
        cancel: "Keep it",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        post("/dictation/" + back.dataset.recording + "/take-back", { share: back.dataset.share }).then(function (answer) {
          if (answer.ok) { back.parentNode.remove(); }
          else { UI.toast("That could not be taken back.", { problem: true, icon: "warning" }); }
        });
      });
      return;
    }

    var remove = event.target.closest(".delete-dictation");
    if (remove) {
      UI.confirm({
        title: "Delete the dictation " + remove.dataset.title + "?",
        body: ["The recording, its transcript, and its memo go for good.", "Anyone you sent it to loses it too."],
        ok: "Delete",
        cancel: "Keep it",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        post("/recording/" + remove.dataset.recording + "/delete").then(function (answer) {
          if (answer.ok) { window.location.reload(); }
          else { UI.toast("That could not be deleted.", { problem: true, icon: "warning" }); }
        });
      });
    }
  });

  // Send to: one prompt over the colleagues who may be sent this, with the
  // fixed words above the field so the person reads what they are agreeing to.
  var list = document.createElement("datalist");
  list.id = "dictation-colleagues";
  document.body.appendChild(list);

  function sendTo(recordingId, title) {
    fetch("/dictation/" + recordingId + "/who")
      .then(function (answer) { return answer.json(); })
      .then(function (said) {
        var people = said.people || [];
        list.innerHTML = "";
        people.forEach(function (one) {
          var option = document.createElement("option");
          option.value = one.username;
          option.label = one.name === one.username ? one.name : one.name + " (" + one.username + ")";
          list.appendChild(option);
        });
        if (!people.length) {
          return UI.alert({ title: "Send " + title, body: "Nobody can be sent this yet. A colleague appears here once they have signed in to the app." });
        }
        return UI.prompt({
          title: "Send " + title + " to a colleague",
          body: page.dataset.sendWords.split(". ").map(function (line, i, all) { return i < all.length - 1 ? line + "." : line; }),
          placeholder: "A colleague's name or username",
          list: "dictation-colleagues",
          ok: "Send"
        }).then(function (who) {
          if (!who) { return; }
          post("/dictation/" + recordingId + "/send", { who: who }).then(function (answer) {
            if (!answer.ok) {
              UI.toast(answer.said.why || "That could not be sent.", { problem: true, icon: "warning" });
              return;
            }
            var cell = document.querySelector("tr[data-recording='" + recordingId + "'] .sent-cell");
            if (cell) {
              var nobody = cell.querySelector(".muted");
              if (nobody && nobody.textContent === "nobody yet") { nobody.remove(); }
              var line = document.createElement("div");
              line.className = "row";
              line.style.gap = "6px";
              line.innerHTML = "<span>" + escaped(answer.said.share.name) + (answer.said.share.attached ? " <span class='muted'>(memo attached)</span>" : "") + "</span>" +
                "<button type='button' class='ghost tiny take-back' data-recording='" + recordingId + "' data-share='" + answer.said.share.id + "' data-name='" + escaped(answer.said.share.name) + "'>Take back</button>";
              cell.appendChild(line);
            }
            UI.toast("Sent to " + answer.said.share.name + ".", { icon: "ok" });
          });
        });
      });
  }
})();

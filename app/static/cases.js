// Cases: making one, renaming it, deleting it, and moving a recording into it.
//
// The picker is built here rather than rendered into every page, because the
// same picker is offered from the recordings list, from a case page, and from
// the sign-out dialog, and one of them is a page this script does not own.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(url, fields) {
    var body = new URLSearchParams();
    Object.keys(fields || {}).forEach(function (key) {
      body.append(key, fields[key]);
    });
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") },
      body: body
    }).then(function (answer) {
      return answer.json().then(function (said) {
        return { ok: answer.ok, said: said };
      });
    });
  }

  function escaped(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

  function show(element, on) {
    if (element) { element.hidden = !on; }
  }

  // The Cases page's New case box -------------------------------------------

  var openNew = document.getElementById("open-new");
  if (openNew) {
    var newBox = document.getElementById("new-box");
    var newName = document.getElementById("new-name");
    var newWarning = document.getElementById("new-warning");

    function openTheBox() {
      show(newBox, true);
      newName.focus();
    }
    openNew.addEventListener("click", openTheBox);
    // The empty state's own New case, when there are no cases yet.
    var openNewEmpty = document.getElementById("open-new-empty");
    if (openNewEmpty) { openNewEmpty.addEventListener("click", openTheBox); }
    var neverMind = document.getElementById("never-mind");
    if (neverMind) {
      neverMind.addEventListener("click", function () { show(newBox, false); });
    }

    var makeIt = document.getElementById("make-it");
    function makeOne() {
      var name = newName.value.trim();
      if (!name) { return; }
      makeIt.disabled = true;
      post("/cases/new", { name: name }).then(function (answer) {
        makeIt.disabled = false;
        if (!answer.ok) {
          UI.toast(answer.said.why || "That case could not be made.", { problem: true, icon: "warning" });
          return;
        }
        // The duplicate name is a warning, so the case exists either way and
        // the person decides whether to rename it.
        if (answer.said.warning) {
          newWarning.textContent = answer.said.warning;
          show(newWarning, true);
          window.setTimeout(function () {
            window.location = answer.said.where;
          }, 1200);
          return;
        }
        window.location = answer.said.where;
      });
    }
    makeIt.addEventListener("click", makeOne);
    newName.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); makeOne(); }
    });
  }

  // One case's own controls --------------------------------------------------

  // Which case this page is already in, so the picker does not offer it. The
  // case page carries it on the page; the viewer carries it on its own
  // object, because the viewer belongs to a recording and not to a case.
  var holder = document.querySelector("[data-case]");
  var caseId = holder ? holder.dataset.case : "";
  if (!caseId && window.VIEWER && window.VIEWER.inCase) {
    caseId = window.VIEWER.inCase;
  }

  var rename = document.getElementById("rename");
  if (rename) {
    var renameBox = document.getElementById("rename-box");
    var wanted = document.getElementById("new-name");
    var renameWarning = document.getElementById("rename-warning");

    rename.addEventListener("click", function () {
      show(renameBox, true);
      wanted.focus();
      wanted.select();
    });
    document.getElementById("never-mind").addEventListener("click", function () {
      show(renameBox, false);
    });
    document.getElementById("save-name").addEventListener("click", function () {
      var name = wanted.value.trim();
      if (!name) { return; }
      post("/case/" + caseId + "/rename", { name: name }).then(function (answer) {
        if (!answer.ok) {
          UI.toast(answer.said.why || "That name could not be saved.", { problem: true, icon: "warning" });
          return;
        }
        document.getElementById("case-name").textContent = answer.said.name;
        document.title = answer.said.name;
        show(renameBox, false);
        if (answer.said.warning) {
          renameWarning.textContent = answer.said.warning;
          show(renameWarning, true);
        }
      });
    });
  }

  var remove = document.getElementById("delete-case");
  if (remove) {
    remove.addEventListener("click", function () {
      // What is being taken is named before anybody agrees to it, because
      // there is no recycle bin for a person's own delete.
      fetch("/case/" + caseId + "/what-would-go")
        .then(function (answer) { return answer.json(); })
        .then(function (counts) {
          var taking =
            "This removes " + plural(counts.recordings, "recording") + ", " +
            plural(counts.transcripts, "transcript") + ", " +
            (counts.chats ? "" : "and ") + plural(counts.clips, "clip") +
            (counts.chats ? ", and " + plural(counts.chats, "case chat") : "") +
            ", " + counts.size + " in all.";
          UI.confirm({
            title: "Delete the case " + counts.name + "?",
            body: [taking, "This is final. There is no way to get it back."],
            ok: "Delete case",
            cancel: "Keep it",
            danger: true
          }).then(function (yes) {
            if (!yes) { return; }
            remove.disabled = true;
            post("/case/" + caseId + "/delete").then(function (answer) {
              if (!answer.ok) {
                remove.disabled = false;
                UI.toast("That case could not be deleted.", { problem: true, icon: "warning" });
                return;
              }
              window.location = answer.said.where;
            });
          });
        });
    });
  }

  // Sharing: Share, Remove, Transfer, Leave ---------------------------------
  //
  // One dialog for Share and one for Transfer, each a prompt over the list of
  // colleagues the case may go to, with the fixed words above the field so
  // the person reads what they are agreeing to before they confirm.

  var sharedWith = document.getElementById("shared-with");
  if (sharedWith) {
    var colleagueList = document.createElement("datalist");
    colleagueList.id = "colleague-list";
    document.body.appendChild(colleagueList);

    function loadColleagues() {
      return fetch("/case/" + caseId + "/share/who")
        .then(function (answer) { return answer.json(); })
        .then(function (said) {
          colleagueList.innerHTML = "";
          (said.people || []).forEach(function (one) {
            var option = document.createElement("option");
            option.value = one.username;
            option.label = one.name === one.username ? one.name : one.name + " (" + one.username + ")";
            colleagueList.appendChild(option);
          });
          return said.people || [];
        });
    }

    function askWho(options) {
      return loadColleagues().then(function (people) {
        if (!people.length) {
          return UI.alert({
            title: options.title,
            body: "Nobody can be added yet. A colleague appears here once they have signed in to the app."
          }).then(function () { return null; });
        }
        return UI.prompt({
          title: options.title,
          body: options.body,
          placeholder: "A colleague's name or username",
          list: "colleague-list",
          ok: options.ok
        });
      });
    }

    function addShareRow(share) {
      var table = document.getElementById("shares");
      var row = document.createElement("tr");
      row.dataset.share = share.id;
      row.innerHTML =
        "<td>" + escaped(share.name) + "</td>" +
        "<td class='muted'>" + escaped(share.added_on) + "</td>" +
        "<td class='muted'>" + (share.last_opened ? escaped(share.last_opened) : "not yet") + "</td>" +
        "<td class='acts'><button type='button' class='small ghost unshare' data-share='" + share.id +
        "' data-name='" + escaped(share.name) + "'>Remove</button></td>";
      table.querySelector("tbody").appendChild(row);
      show(table, true);
      show(document.getElementById("nobody-yet"), false);
    }

    var share = document.getElementById("share");
    if (share) {
      share.addEventListener("click", function () {
        askWho({
          title: "Share this case",
          body: sharedWith.dataset.shareWords.split(". ").map(function (line, i, all) {
            return i < all.length - 1 ? line + "." : line;
          }),
          ok: "Share"
        }).then(function (who) {
          if (!who) { return; }
          post("/case/" + caseId + "/share", { who: who }).then(function (answer) {
            if (!answer.ok) {
              UI.toast(answer.said.why || "That person could not be added.", { problem: true, icon: "warning" });
              return;
            }
            addShareRow(answer.said.share);
            UI.toast("Shared with " + answer.said.share.name + ".", { icon: "ok" });
          });
        });
      });
    }

    var transfer = document.getElementById("transfer");
    if (transfer) {
      transfer.addEventListener("click", function () {
        askWho({
          title: "Hand this case to a colleague",
          body: sharedWith.dataset.transferWords.split(". ").map(function (line, i, all) {
            return i < all.length - 1 ? line + "." : line;
          }),
          ok: "Transfer"
        }).then(function (who) {
          if (!who) { return; }
          post("/case/" + caseId + "/transfer", { who: who }).then(function (answer) {
            if (!answer.ok) {
              UI.toast(answer.said.why || "That case could not be handed over.", { problem: true, icon: "warning" });
              return;
            }
            window.location.reload();
          });
        });
      });
    }

    sharedWith.addEventListener("click", function (event) {
      var remove = event.target.closest(".unshare");
      if (!remove) { return; }
      var leaving = !!remove.dataset.leave;
      UI.confirm({
        title: leaving ? "Leave this case?" : "Remove " + remove.dataset.name + "?",
        body: leaving
          ? "You will no longer see this case. Anything you added stays in it."
          : remove.dataset.name + " will no longer see this case. Anything they added stays in it.",
        ok: leaving ? "Leave" : "Remove",
        cancel: "Keep it",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        post("/case/" + caseId + "/unshare", { share: remove.dataset.share }).then(function (answer) {
          if (!answer.ok) {
            UI.toast("That could not be done.", { problem: true, icon: "warning" });
            return;
          }
          if (answer.said.left) { window.location = answer.said.where; return; }
          var row = sharedWith.querySelector("tr[data-share='" + remove.dataset.share + "']");
          if (row) { row.remove(); }
          var table = document.getElementById("shares");
          if (table && !table.querySelector("tbody tr")) {
            show(table, false);
            show(document.getElementById("nobody-yet"), true);
          }
        });
      });
    });
  }

  // The Retention policy: Keep on a warned row, and the Recycle bin's Restore,
  // Delete permanently, and Empty --------------------------------------------

  function plural(count, word) {
    return count + " " + word + (count === 1 ? "" : "s");
  }

  document.addEventListener("click", function (event) {
    var keep = event.target.closest(".keep");
    if (keep) {
      keep.disabled = true;
      post("/case/" + keep.dataset.case + "/keep").then(function (answer) {
        if (answer.ok) { window.location.reload(); return; }
        keep.disabled = false;
        UI.toast("That case could not be kept.", { problem: true, icon: "warning" });
      });
      return;
    }

    var restore = event.target.closest(".restore");
    if (restore) {
      restore.disabled = true;
      post("/case/" + restore.dataset.case + "/restore").then(function (answer) {
        if (answer.ok) { window.location = answer.said.where; return; }
        restore.disabled = false;
        UI.toast("That case could not be restored.", { problem: true, icon: "warning" });
      });
      return;
    }

    var wipe = event.target.closest(".wipe");
    if (wipe) {
      // Named before anybody agrees to it. There is nothing after this.
      fetch("/case/" + wipe.dataset.case + "/what-would-go")
        .then(function (answer) { return answer.json(); })
        .then(function (counts) {
          UI.confirm({
            title: "Delete the case " + counts.name + " permanently?",
            body: [
              "This removes " + plural(counts.recordings, "recording") + ", " +
              plural(counts.transcripts, "transcript") + ", and " +
              plural(counts.clips, "clip") + ", " + counts.size + " in all.",
              "Nothing can bring it back."
            ],
            ok: "Delete permanently",
            cancel: "Leave it in the bin",
            danger: true
          }).then(function (yes) {
            if (!yes) { return; }
            wipe.disabled = true;
            post("/case/" + wipe.dataset.case + "/wipe").then(function (answer) {
              if (answer.ok) { window.location.reload(); return; }
              wipe.disabled = false;
              UI.toast("That case could not be deleted.", { problem: true, icon: "warning" });
            });
          });
        });
    }
  });

  var emptyBin = document.getElementById("empty-bin");
  if (emptyBin) {
    emptyBin.addEventListener("click", function () {
      fetch("/cases/bin/what-would-go")
        .then(function (answer) { return answer.json(); })
        .then(function (counts) {
          if (!counts.cases) { UI.toast("The recycle bin is already empty.", { icon: "info" }); return; }
          UI.confirm({
            title: "Empty the recycle bin?",
            body: [
              "This permanently removes " + plural(counts.cases, "case") + " holding " +
              plural(counts.recordings, "recording") + ", " + counts.size + " in all.",
              "Nothing can bring them back."
            ],
            ok: "Empty the bin",
            cancel: "Leave it",
            danger: true
          }).then(function (yes) {
            if (!yes) { return; }
            emptyBin.disabled = true;
            post("/cases/bin/empty").then(function (answer) {
              if (answer.ok) { window.location.reload(); return; }
              emptyBin.disabled = false;
              UI.toast("The recycle bin could not be emptied.", { problem: true, icon: "warning" });
            });
          });
        });
    });
  }

  // The type and the description, on a case page's rows ----------------------

  document.addEventListener("click", function (event) {
    var save = event.target.closest(".save-details");
    if (!save) { return; }
    var row = save.closest("[data-recording]");
    save.disabled = true;
    post("/recording/" + row.dataset.recording + "/case-details", {
      recording_type: row.querySelector(".a-type").value,
      description: row.querySelector(".a-description").value
    }).then(function (answer) {
      save.disabled = false;
      save.textContent = answer.ok ? "Saved" : "Not saved";
      window.setTimeout(function () { save.textContent = "Save"; }, 1500);
    });
  });

  // The Move to case picker --------------------------------------------------

  function picker(recordingId, title, thisCase) {
    fetch("/cases/where")
      .then(function (answer) { return answer.json(); })
      .then(function (said) {
        var choices = said.cases.filter(function (one) {
          return one.id !== thisCase;
        }).map(function (one) {
          // A case shared with the person says whose it is.
          return one.shared_by ? Object.assign({}, one, { name: one.name + " (shared by " + one.shared_by + ")" }) : one;
        });
        draw(recordingId, title, choices, said.types);
      });
  }

  function draw(recordingId, title, choices, types) {
    var background = document.createElement("div");
    background.className = "modal-bg";
    background.innerHTML =
      '<div class="modal">' +
      '<div class="row"><h2 class="grow">Move to case</h2>' +
      '<button type="button" class="ghost" data-shut>Close</button></div>' +
      '<p class="muted small">' + escaped(title) + "</p>" +
      '<div class="field"><label for="pick-case">Case</label>' +
      '<select id="pick-case">' +
      choices.map(function (one) {
        return '<option value="' + escaped(one.id) + '">' + escaped(one.name) +
          "</option>";
      }).join("") +
      '<option value="">A new case&hellip;</option>' +
      "</select></div>" +
      '<div class="field" id="fresh-name-field" hidden>' +
      '<label for="fresh-name">New case name</label>' +
      '<input id="fresh-name" type="text" maxlength="200"></div>' +
      '<div class="field"><label for="pick-type">Recording type</label>' +
      '<select id="pick-type"><option value="">No type</option>' +
      types.map(function (one) {
        return '<option value="' + escaped(one) + '">' + escaped(one) + "</option>";
      }).join("") +
      "</select></div>" +
      '<div class="field"><label for="pick-description">Description, if you want one</label>' +
      '<input id="pick-description" type="text" maxlength="2000" ' +
      'placeholder="You can skip this"></div>' +
      '<p class="notice">Nothing ever moves back out of a case. The only way ' +
      "out is to delete it.</p>" +
      '<div class="row"><span class="grow"></span>' +
      '<button type="button" class="btn ghost" data-shut>Cancel</button>' +
      '<button type="button" class="btn primary" id="do-move">Move</button></div>' +
      "</div>";
    document.body.appendChild(background);

    var which = background.querySelector("#pick-case");
    var freshField = background.querySelector("#fresh-name-field");
    var fresh = background.querySelector("#fresh-name");

    // With no case to move into, the box opens ready to make one.
    if (!choices.length) {
      which.value = "";
      show(freshField, true);
    }
    which.addEventListener("change", function () {
      show(freshField, which.value === "");
      if (which.value === "") { fresh.focus(); }
    });

    function shut() { background.remove(); }
    Array.prototype.forEach.call(
      background.querySelectorAll("[data-shut]"),
      function (one) { one.addEventListener("click", shut); }
    );
    background.addEventListener("click", function (event) {
      if (event.target === background) { shut(); }
    });

    background.querySelector("#do-move").addEventListener("click", function () {
      var go = this;
      go.disabled = true;

      var chosen = which.value;
      var thenMove = chosen
        ? Promise.resolve(chosen)
        : post("/cases/new", { name: fresh.value.trim() }).then(function (made) {
            if (!made.ok) { throw new Error(made.said.why || "no case"); }
            return made.said.id;
          });

      thenMove
        .then(function (into) {
          return post("/recording/" + recordingId + "/move", {
            case: into,
            recording_type: background.querySelector("#pick-type").value,
            description: background.querySelector("#pick-description").value
          });
        })
        .then(function (answer) {
          if (!answer.ok) {
            go.disabled = false;
            UI.toast(answer.said.why || "That could not be moved.", { problem: true, icon: "warning" });
            return;
          }
          window.location = answer.said.where;
        })
        .catch(function (trouble) {
          go.disabled = false;
          UI.toast(trouble.message === "no case" ? "That case could not be made." : "That could not be moved.",
            { problem: true, icon: "warning" });
        });
    });
  }

  document.addEventListener("click", function (event) {
    var move = event.target.closest(".move");
    if (!move) { return; }
    picker(move.dataset.recording, move.dataset.title, caseId);
  });

  // The case rail in the viewer -----------------------------------------------

  var rail = document.getElementById("caserail");
  if (rail) {
    var body = rail.closest(".body");
    var hide = document.getElementById("hide-case");
    var reopen = document.getElementById("show-case");

    // Two classes rather than one, because the width alone decides what the
    // rail does by default and a person's choice has to be able to say either
    // thing: case-hidden closes it on a wide screen, case-shown opens it on a
    // narrow one, where it lies over the page rather than squeezing it.
    function draw(shut) {
      body.classList.toggle("case-hidden", shut);
      body.classList.toggle("case-shown", !shut);
      try {
        window.localStorage.setItem("case-rail", shut ? "hidden" : "shown");
      } catch (ignored) { /* a browser that forbids storage forgets it */ }
    }

    function open() {
      return !body.classList.contains("case-hidden")
        && window.getComputedStyle(rail).display !== "none";
    }

    // Both answers are applied, not just "hidden": a person who opened the
    // rail on a narrow screen, where it starts closed, would otherwise lose
    // it at the next page. With nothing stored the screen's width decides.
    var chosen = null;
    try {
      chosen = window.localStorage.getItem("case-rail");
    } catch (ignored) { /* the rail then follows the screen's width */ }
    if (chosen === "hidden") { draw(true); }
    else if (chosen === "shown") { draw(false); }

    hide.addEventListener("click", function () { draw(true); });
    // Shut it when it is open and open it when it is not: draw() takes
    // "shut", so the button hands it the state it is in now.
    reopen.addEventListener("click", function () { draw(open()); });
  }
}());

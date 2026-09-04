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

    openNew.addEventListener("click", function () {
      show(newBox, true);
      newName.focus();
    });
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
          window.alert(answer.said.why || "That case could not be made.");
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
          window.alert(answer.said.why || "That name could not be saved.");
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
          var words =
            "Delete the case “" + counts.name + "”?\n\n" +
            "This removes " + counts.recordings + " recording" +
            (counts.recordings === 1 ? "" : "s") + ", " +
            counts.transcripts + " transcript" +
            (counts.transcripts === 1 ? "" : "s") + ", and " +
            counts.clips + " clip" + (counts.clips === 1 ? "" : "s") +
            ", " + counts.size + " in all.\n\n" +
            "This is final. There is no way to get it back.";
          if (!window.confirm(words)) { return; }
          remove.disabled = true;
          post("/case/" + caseId + "/delete").then(function (answer) {
            if (!answer.ok) {
              remove.disabled = false;
              window.alert("That case could not be deleted.");
              return;
            }
            window.location = answer.said.where;
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
            window.alert(answer.said.why || "That could not be moved.");
            return;
          }
          window.location = answer.said.where;
        })
        .catch(function (trouble) {
          go.disabled = false;
          window.alert(trouble.message === "no case"
            ? "That case could not be made."
            : "That could not be moved.");
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

    try {
      if (window.localStorage.getItem("case-rail") === "hidden") { draw(true); }
    } catch (ignored) { /* the same, and the rail follows the screen's width */ }

    hide.addEventListener("click", function () { draw(true); });
    // Shut it when it is open and open it when it is not: draw() takes
    // "shut", so the button hands it the state it is in now.
    reopen.addEventListener("click", function () { draw(open()); });
  }
}());

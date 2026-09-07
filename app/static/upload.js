// The Upload page: choose files, choose settings, then send the bytes.
//
// Nothing is sent before the button is pressed. On Submit the app makes the
// Batch and one Recording per file, and the browser then uploads each file to
// the sidecar, three at a time, naming its Recording in the upload's metadata.

(function () {
  "use strict";

  // Three at a time, as the specification fixes: enough to use the network,
  // few enough that one large file does not starve the others.
  var AT_ONCE = 3;

  var chosen = [];
  var picker = document.getElementById("picker");
  var drop = document.getElementById("drop");
  var list = document.getElementById("chosen");
  if (!picker) { return; }

  // The stylesheet lays the three steps out two ways by the width of the
  // window: one at a time with Next and Back on a narrow one, all three at
  // once on a wide one. This is the same question asked from here.
  var WIDE = window.matchMedia("(min-width: 1280px)");
  function allAtOnce() { return WIDE.matches; }
  var step = 1;

  function bytes(size) {
    if (size >= 1073741824) { return (size / 1073741824).toFixed(1) + " GB"; }
    if (size >= 1048576) { return (size / 1048576).toFixed(0) + " MB"; }
    return (size / 1024).toFixed(0) + " KB";
  }

  function withoutExtension(name) {
    var dot = name.lastIndexOf(".");
    return dot > 0 ? name.slice(0, dot) : name;
  }

  function add(files) {
    Array.prototype.forEach.call(files, function (file) {
      // An archive is never sent: the person is told to choose the recordings
      // inside it instead.
      var refused = null;
      if (/\.(zip|rar|7z|tar|gz)$/i.test(file.name)) {
        refused = "Zip files are not accepted. Choose the recordings inside it instead.";
      } else if (file.size === 0) {
        refused = "The file is empty";
      }
      chosen.push({
        own: null,
        file: file,
        title: withoutExtension(file.name),
        refused: refused
      });
    });
    draw();
  }

  function draw() {
    list.innerHTML = "";
    chosen.forEach(function (one, index) {
      var card = document.createElement("li");
      card.className = one.refused ? "card refused" : "card";

      var title = document.createElement("input");
      title.type = "text";
      title.value = one.title;
      title.setAttribute("aria-label", "Title");
      title.addEventListener("input", function () { one.title = title.value; });

      var about = document.createElement("p");
      about.className = "quiet";
      about.textContent = one.file.name + " · " + bytes(one.file.size);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "plain";
      remove.textContent = "Remove";
      remove.addEventListener("click", function () {
        chosen.splice(index, 1);
        draw();
      });

      card.appendChild(title);
      card.appendChild(about);
      if (one.refused) {
        var why = document.createElement("p");
        why.className = "problem";
        why.textContent = one.refused;
        card.appendChild(why);
      }
      if (!one.refused) {
        // The same chip the exceptions table carries, so that on a wide
        // window, where that table is not repeated, a file's own settings
        // are one click from the file.
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "pill chip-for";
        chip.dataset.index = String(index);
        chip.title = "Give this file its own settings";
        chip.addEventListener("click", function () {
          showFile(index);
          if (!allAtOnce()) { show(2); }
        });
        card.appendChild(chip);
      }
      card.appendChild(remove);
      list.appendChild(card);
    });

    document.getElementById("to-settings").disabled = !usable().length;
    drawExceptions();
  }

  function usable() {
    return chosen.filter(function (one) { return !one.refused; });
  }

  picker.addEventListener("change", function () { add(picker.files); picker.value = ""; });
  drop.addEventListener("dragover", function (event) {
    event.preventDefault();
    drop.classList.add("over");
  });
  drop.addEventListener("dragleave", function () { drop.classList.remove("over"); });
  drop.addEventListener("drop", function (event) {
    event.preventDefault();
    drop.classList.remove("over");
    add(event.dataTransfer.files);
  });

  // Where do they go ---------------------------------------------------------------
  //
  // The one question above the steps, asked only when the office uses cases:
  // this session, or into a case. The cards drive the rail's Add to case box,
  // whose change listener does the rest, so each write here fires "change".

  function fire(control) {
    control.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function lightUp(group, value) {
    Array.prototype.forEach.call(group.querySelectorAll(".style"), function (card) {
      var radio = card.querySelector("input");
      radio.checked = radio.value === value;
      card.classList.toggle("on", radio.checked);
    });
  }

  var wheres = document.getElementById("wheres");
  var whichCase = document.getElementById("which-case");
  var hint = document.getElementById("hint");

  function applyWhere() {
    var intoCase = document.getElementById("add-to-case");
    if (!wheres || !intoCase) { return; }
    var chosenWhere = wheres.querySelector('input[name="where"]:checked');
    lightUp(wheres, chosenWhere ? chosenWhere.value : "");
    intoCase.value = chosenWhere && chosenWhere.value === "case" ? whichCase.value : "";
    fire(intoCase);
  }

  if (wheres) {
    wheres.addEventListener("change", function (event) {
      if (event.target.name === "where") { applyWhere(); }
    });
    whichCase.addEventListener("change", function () {
      lightUp(wheres, "case");
      applyWhere();
    });
    // Clicking into the select chooses Into a case, since that is what it is for.
    whichCase.addEventListener("focus", function () {
      wheres.querySelector('input[value="case"]').checked = true;
      applyWhere();
    });
  }

  // Speaker separation is off until the person turns it on, and the warning
  // under the box is shown while it is on, for the batch or for one file.
  var diarizeBox = document.getElementById("diarize");
  var diarizeWarning = document.getElementById("diarize-warning");
  function showDiarizeWarning() {
    if (diarizeWarning) { diarizeWarning.hidden = !diarizeBox.checked; }
  }
  diarizeBox.addEventListener("change", showDiarizeWarning);

  // The three steps -----------------------------------------------------------

  function show(number) {
    step = number;
    [1, 2, 3].forEach(function (each) {
      var element = document.getElementById("step-" + each);
      element.hidden = allAtOnce() ? false : each !== number;
      element.classList.toggle("here", each === number);
    });
  }

  document.getElementById("to-settings").addEventListener("click", function () {
    show(2);
  });
  document.getElementById("to-check").addEventListener("click", function () {
    review();
    show(3);
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-back]"), function (button) {
    button.addEventListener("click", function () {
      show(parseInt(button.getAttribute("data-back"), 10));
    });
  });

  // The rail shows one set of settings at a time: the batch's, or one file's
  // own. A file's own start as null, meaning "same as the batch", and a copy
  // is taken only when somebody unticks the box, so a file that follows the
  // batch keeps following it when the batch changes.
  var batchSettings = null;
  var railFor = null;

  var useBatch = document.getElementById("use-batch");
  var fileTitle = document.getElementById("file-title");

  function readRail() {
    var speakers = null;
    if (hint.value === "exactly") {
      speakers = { exactly: parseInt(document.getElementById("hint-a").value, 10) };
    } else if (hint.value === "between") {
      speakers = {
        between: [
          parseInt(document.getElementById("hint-a").value, 10),
          parseInt(document.getElementById("hint-b").value, 10)
        ]
      };
    }
    var intoCase = document.getElementById("add-to-case");
    var whatKind = document.getElementById("recording-type");
    var mailMe = document.getElementById("email-when-done");
    return {
      // Absent while the Admin's switch is off or mail is not configured.
      email_when_done: !!(mailMe && !mailMe.disabled && mailMe.checked),
      diarize: document.getElementById("diarize").checked,
      speakers: speakers,
      translate: document.getElementById("translate").checked,
      language: document.getElementById("language").value,
      vocabulary: document.getElementById("vocabulary").value.split("\n"),
      context: document.getElementById("context").value,
      // Absent from the page altogether while Folder management is off.
      case: intoCase ? intoCase.value : "",
      case_name: intoCase && intoCase.value
        ? intoCase.options[intoCase.selectedIndex].textContent
        : "",
      recording_type: whatKind ? whatKind.value : ""
    };
  }

  function writeRail(values) {
    var mailMe = document.getElementById("email-when-done");
    if (mailMe && !mailMe.disabled) { mailMe.checked = !!values.email_when_done; }
    document.getElementById("diarize").checked = !!values.diarize;
    showDiarizeWarning();
    document.getElementById("translate").checked = !!values.translate;
    document.getElementById("language").value = values.language || "";
    document.getElementById("vocabulary").value =
      (values.vocabulary || []).join("\n");
    document.getElementById("context").value = values.context || "";

    var intoCase = document.getElementById("add-to-case");
    if (intoCase) {
      intoCase.value = values.case || "";
      document.getElementById("recording-type").value =
        values.recording_type || "";
      // A recording type belongs to a case, so it is offered only once
      // one is chosen.
      document.getElementById("type-field").hidden = !intoCase.value;
    }

    var speakers = values.speakers;
    if (speakers && speakers.exactly) {
      hint.value = "exactly";
      document.getElementById("hint-a").value = speakers.exactly;
    } else if (speakers && speakers.between) {
      hint.value = "between";
      document.getElementById("hint-a").value = speakers.between[0];
      document.getElementById("hint-b").value = speakers.between[1];
    } else {
      hint.value = "";
    }
    showHintBoxes();
  }

  function showHintBoxes() {
    document.getElementById("hint-a").hidden = hint.value === "";
    document.getElementById("hint-b").hidden = hint.value !== "between";
  }

  function copyOf(values) {
    return JSON.parse(JSON.stringify(values));
  }

  // Whatever the rail is showing, keep it in the right place.
  function remember() {
    if (railFor === null) {
      batchSettings = readRail();
    } else if (chosen[railFor] && chosen[railFor].own) {
      chosen[railFor].own = readRail();
    }
    drawExceptions();
  }

  Array.prototype.forEach.call(
    document.querySelectorAll("#the-settings input, #the-settings select, " +
      "#the-settings textarea"),
    function (control) {
      control.addEventListener("change", remember);
      control.addEventListener("input", remember);
    }
  );
  hint.addEventListener("change", showHintBoxes);

  // A recording type belongs to a case, so the box appears only once one is
  // chosen. writeRail() does this when the rail is switched; this does it
  // when somebody picks a case without switching anything.
  var chooseCase = document.getElementById("add-to-case");
  if (chooseCase) {
    chooseCase.addEventListener("change", function () {
      document.getElementById("type-field").hidden = !this.value;
      // The where cards follow the batch's box, so the two never disagree.
      if (railFor === null && wheres) {
        lightUp(wheres, this.value ? "case" : "");
        if (this.value) { whichCase.value = this.value; }
      }
    });
  }

  // The page opens with the cards' answer already in the rail.
  if (wheres) { applyWhere(); }

  function settings() {
    // The batch's own, read from the rail when the rail is showing them.
    if (railFor === null) { batchSettings = readRail(); }
    return batchSettings || readRail();
  }

  function settingsFor(one) {
    return one.own || settings();
  }

  // Switching the rail --------------------------------------------------------

  function showBatch() {
    railFor = null;
    document.getElementById("rail-heading").textContent = "Batch settings";
    document.getElementById("back-to-batch").hidden = true;
    document.getElementById("use-batch-line").hidden = true;
    document.getElementById("file-title-line").hidden = true;
    // The batch's case is chosen on the where cards above the steps; the
    // rail's own box is for one file that goes somewhere else.
    var caseField = document.getElementById("case-field");
    if (caseField) { caseField.hidden = true; }
    enableSettings(true);
    writeRail(batchSettings || readRail());
    drawExceptions();
  }

  function showFile(index) {
    railFor = index;
    var one = chosen[index];
    document.getElementById("rail-heading").textContent = one.title;
    document.getElementById("back-to-batch").hidden = false;
    document.getElementById("use-batch-line").hidden = false;
    document.getElementById("file-title-line").hidden = false;
    var caseField = document.getElementById("case-field");
    if (caseField) { caseField.hidden = false; }
    fileTitle.value = one.title;
    useBatch.checked = !one.own;
    enableSettings(!!one.own);
    writeRail(one.own || settings());
    drawExceptions();
  }

  function enableSettings(on) {
    Array.prototype.forEach.call(
      document.querySelectorAll("#the-settings input, #the-settings select, " +
        "#the-settings textarea"),
      function (control) { control.disabled = !on; }
    );
  }

  document.getElementById("back-to-batch").addEventListener("click", showBatch);

  useBatch.addEventListener("change", function () {
    var one = chosen[railFor];
    if (!one) { return; }
    // Unticking takes a copy of the batch settings, which then edit on their
    // own; ticking gives the file back to the batch and drops the copy.
    one.own = this.checked ? null : copyOf(settings());
    enableSettings(!this.checked);
    writeRail(one.own || settings());
    drawExceptions();
  });

  fileTitle.addEventListener("input", function () {
    var one = chosen[railFor];
    if (!one) { return; }
    one.title = this.value;
    document.getElementById("rail-heading").textContent = this.value;
    draw();
    drawExceptions();
  });

  // The exceptions table ------------------------------------------------------

  function speakersInWords(values) {
    var speakers = values.speakers;
    if (!values.diarize) { return "not separated"; }
    if (speakers && speakers.exactly) { return "exactly " + speakers.exactly; }
    if (speakers && speakers.between) {
      return "between " + speakers.between[0] + " and " + speakers.between[1];
    }
    return "the app decides";
  }

  function drawExceptions() {
    var body = document.querySelector("#exceptions tbody");
    if (!body) { return; }
    body.innerHTML = "";

    usable().forEach(function (one) {
      var index = chosen.indexOf(one);
      var values = settingsFor(one);
      var row = document.createElement("tr");
      row.innerHTML =
        "<td><b>" + escape(one.title) + "</b></td>" +
        "<td class='muted'>" +
        escape(values.case_name || "this session only") + "</td>" +
        "<td class='muted'>" + escape(speakersInWords(values)) + "</td>" +
        "<td class='muted'>" + (values.translate ? "yes" : "no") + "</td>" +
        "<td class='muted'>" + escape(values.language || "automatic") + "</td>" +
        "<td><button type='button' class='pill chip-for" +
        (railFor === index ? " on" : "") +
        "'>" + (one.own ? "Custom" : "Same as batch") + "</button></td>";
      row.querySelector(".chip-for").addEventListener("click", function () {
        showFile(index);
      });
      body.appendChild(row);
    });
    markChips();
    review();
  }

  // The chips on the file cards say the same as the table's, and mark the
  // file whose settings the rail is showing.
  function markChips() {
    Array.prototype.forEach.call(list.querySelectorAll(".chip-for"), function (chip) {
      var index = parseInt(chip.dataset.index, 10);
      var one = chosen[index];
      if (!one) { return; }
      chip.textContent = one.own ? "Custom settings" : "Same as batch";
      chip.classList.toggle("on", railFor === index);
    });
  }

  function review() {
    var body = document.querySelector("#review tbody");
    body.innerHTML = "";
    usable().forEach(function (one) {
      var values = settingsFor(one);
      var row = document.createElement("tr");
      var marks = [];
      if (values.case_name) { marks.push("into " + values.case_name); }
      if (values.recording_type) { marks.push(values.recording_type); }
      if (values.diarize) { marks.push("diarize"); }
      if (values.translate) { marks.push("to English"); }
      if (values.language) { marks.push(values.language); }
      if (values.vocabulary && values.vocabulary.join("").trim()) {
        marks.push("vocabulary");
      }
      row.innerHTML =
        "<td>" + escape(one.title) +
        (one.own ? " <span class='pill'>custom</span>" : "") + "</td>" +
        "<td class='muted'>" + escape(one.file.name) + "</td>" +
        "<td class='muted'>" + bytes(one.file.size) + "</td>" +
        "<td class='muted'>" + (marks.join(", ") || "plain transcription") + "</td>";
      body.appendChild(row);
    });
    var start = document.getElementById("start");
    start.disabled = !usable().length;
    start.textContent = usable().length
      ? "Upload and transcribe " + usable().length +
        (usable().length === 1 ? " file" : " files")
      : "Upload and transcribe";
  }

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text;
    return holder.innerHTML;
  }

  // Submitting ----------------------------------------------------------------

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  document.getElementById("start").addEventListener("click", function () {
    var button = this;
    var problem = document.getElementById("submit-problem");
    var files = usable();
    button.disabled = true;
    problem.hidden = true;

    fetch("/upload/submit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: JSON.stringify({
        batch: settings(),
        files: files.map(function (one) {
          var sent = {
            name: one.file.name,
            title: one.title,
            size: one.file.size
          };
          // Only a file with its own settings sends any: the rest follow the
          // batch, and the app applies the batch's to them.
          if (one.own) { sent.settings = one.own; }
          return sent;
        })
      })
    }).then(function (answer) {
      return answer.json().then(function (body) {
        if (!answer.ok) { throw new Error(body.error || "That did not work."); }
        return body;
      });
    }).then(function (body) {
      startUploads(files, body.recordings, body.batch);
    }).catch(function (trouble) {
      problem.textContent = trouble.message;
      problem.hidden = false;
      button.disabled = false;
    });
  });

  // Uploading -----------------------------------------------------------------
  //
  // Each file gets a line saying where it has got to, because an upload that
  // fails silently is an upload nobody knows to try again. A failed one keeps
  // its own Try again, so one bad file does not mean starting the batch over.

  function why(error) {
    // The app refuses an upload with a plain message and a reason class. Any
    // other failure is the network, and saying so is more use than saying
    // nothing.
    var answer = error && error.originalResponse;
    if (answer) {
      try {
        var body = JSON.parse(answer.getBody());
        if (body && body.error) { return body.error; }
      } catch (ignored) { /* not the app's own answer */ }
    }
    return "The upload did not finish. Check the connection and try again.";
  }

  function startUploads(files, recordings, batch) {
    var byName = {};
    recordings.forEach(function (one) { byName[one.name] = one.id; });

    var progress = document.getElementById("progress");
    var start = document.getElementById("start");
    start.hidden = true;
    document.getElementById("review").hidden = true;
    progress.hidden = false;

    var lines = {};
    var waiting = files.slice();
    var running = 0;
    var done = 0;

    files.forEach(function (one) {
      var line = document.createElement("li");
      line.className = "card";
      line.innerHTML =
        "<strong>" + escape(one.title) + "</strong>" +
        "<p class='state quiet'>Waiting</p>";
      progress.appendChild(line);
      lines[one.file.name] = line;
    });

    function say(one, words, isProblem) {
      var line = lines[one.file.name].querySelector(".state");
      line.textContent = words;
      line.className = isProblem ? "state problem" : "state quiet";
    }

    function offerRetry(one) {
      var line = lines[one.file.name];
      if (line.querySelector("button")) { return; }
      var again = document.createElement("button");
      again.type = "button";
      again.className = "plain";
      again.textContent = "Try again";
      again.addEventListener("click", function () {
        again.remove();
        waiting.push(one);
        next();
      });
      line.appendChild(again);
    }

    function finishedIfDone() {
      if (waiting.length || running) { return; }
      if (done === files.length) {
        window.location = "/batch/" + batch;
        return;
      }
      document.getElementById("to-batch-link").setAttribute(
        "href", "/batch/" + batch
      );
      document.getElementById("to-batch").hidden = false;
    }

    function next() {
      if (!waiting.length || running >= AT_ONCE) {
        finishedIfDone();
        return;
      }

      var one = waiting.shift();
      running += 1;
      say(one, "Uploading");

      var upload = new tus.Upload(one.file, {
        endpoint: "/files/",
        retryDelays: [0, 1000, 3000, 5000],
        chunkSize: 50 * 1024 * 1024,
        metadata: { recording: byName[one.file.name], filename: one.file.name },
        onProgress: function (sent, total) {
          say(one, "Uploading " + Math.floor((sent / total) * 100) + "%");
        },
        onError: function (error) {
          running -= 1;
          say(one, why(error), true);
          offerRetry(one);
          next();
        },
        onSuccess: function () {
          running -= 1;
          done += 1;
          say(one, "Uploaded");
          next();
        }
      });
      upload.start();
      next();
    }

    // Leaving the page abandons what has not finished, so the browser is
    // asked to warn. It words the dialog itself; the page cannot.
    window.addEventListener("beforeunload", function (event) {
      if (done < files.length) { event.preventDefault(); event.returnValue = ""; }
    });

    next();
  }

  // The rail starts on the batch's settings, and the steps take their shape
  // from the width of the window. A window widened or narrowed keeps the
  // step it was on.
  batchSettings = readRail();
  showBatch();
  show(1);
  if (WIDE.addEventListener) {
    WIDE.addEventListener("change", function () { show(step); });
  }
  // A plain resize as well: not every browser fires the change above.
  window.addEventListener("resize", function () { show(step); });
})();

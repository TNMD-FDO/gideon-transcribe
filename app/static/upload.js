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
      card.appendChild(remove);
      list.appendChild(card);
    });

    document.getElementById("to-settings").disabled = !usable().length;
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

  // The three steps -----------------------------------------------------------

  function show(step) {
    [1, 2, 3].forEach(function (number) {
      var element = document.getElementById("step-" + number);
      element.hidden = number !== step;
      element.classList.toggle("here", number === step);
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

  var hint = document.getElementById("hint");
  hint.addEventListener("change", function () {
    document.getElementById("hint-a").hidden = hint.value === "";
    document.getElementById("hint-b").hidden = hint.value !== "between";
  });

  function settings() {
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
    return {
      diarize: document.getElementById("diarize").checked,
      speakers: speakers,
      translate: document.getElementById("translate").checked,
      language: document.getElementById("language").value,
      vocabulary: document.getElementById("vocabulary").value.split("\n"),
      context: document.getElementById("context").value
    };
  }

  function review() {
    var body = document.querySelector("#review tbody");
    var chosenSettings = settings();
    body.innerHTML = "";
    usable().forEach(function (one) {
      var row = document.createElement("tr");
      var marks = [];
      if (chosenSettings.diarize) { marks.push("diarize"); }
      if (chosenSettings.translate) { marks.push("to English"); }
      if (chosenSettings.language) { marks.push(chosenSettings.language); }
      row.innerHTML =
        "<td>" + escape(one.title) + "</td>" +
        "<td class='quiet'>" + escape(one.file.name) + "</td>" +
        "<td class='quiet'>" + bytes(one.file.size) + "</td>" +
        "<td class='quiet'>" + (marks.join(", ") || "plain transcription") + "</td>";
      body.appendChild(row);
    });
    document.getElementById("start").textContent =
      "Upload and transcribe " + usable().length +
      (usable().length === 1 ? " file" : " files");
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
          return { name: one.file.name, title: one.title, size: one.file.size };
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

  function startUploads(files, recordings, batch) {
    var waiting = files.slice();
    var byName = {};
    recordings.forEach(function (one) { byName[one.name] = one.id; });

    document.getElementById("start").textContent = "Uploading...";

    var running = 0;
    var done = 0;

    function next() {
      if (!waiting.length) {
        if (running === 0) { window.location = "/batch/" + batch; }
        return;
      }
      if (running >= AT_ONCE) { return; }

      var one = waiting.shift();
      running += 1;

      var upload = new tus.Upload(one.file, {
        endpoint: "/files/",
        retryDelays: [0, 1000, 3000, 5000],
        chunkSize: 50 * 1024 * 1024,
        metadata: { recording: byName[one.file.name], filename: one.file.name },
        onError: function () {
          running -= 1;
          next();
        },
        onSuccess: function () {
          running -= 1;
          done += 1;
          if (!waiting.length && running === 0) {
            window.location = "/batch/" + batch;
          }
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
})();

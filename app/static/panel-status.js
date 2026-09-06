// The Status page: everything read again every five seconds, like every
// other page in the app.

(function () {
  "use strict";

  var EVERY = 5000;

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function facts(into, rows) {
    var list = document.getElementById(into);
    list.innerHTML = rows.map(function (row) {
      return "<dt>" + escape(row[0]) + "</dt><dd>" + escape(row[1]) + "</dd>";
    }).join("");
  }

  function draw(state) {
    var services = document.getElementById("services");
    if (!state.services.length) {
      services.innerHTML =
        "<p class='muted small'>No service answered. Something is very wrong, " +
        "or this page could not reach the network.</p>";
    } else {
      services.innerHTML = "<dl class='kv'>" + state.services.map(function (one) {
        var mark = one.state === "healthy"
          ? "<span class='pill ok'>healthy</span>"
          : "<span class='pill danger'>" + escape(one.state) + "</span>";
        return "<dt>" + escape(one.name) + "</dt><dd>" + mark +
          " <span class='muted small'>" + escape(one.says) + "</span></dd>";
      }).join("") + "</dl>";
    }

    var service = state.service;
    if (!service.up) {
      facts("service", [["Reachable", "no: " + (service.says || "")]]);
    } else {
      var gpu = service.gpu || {};
      var line = service.queue || {};
      var loaded = service.model_loaded || {};
      var running = service.current_job;
      var versions = service.versions || {};
      var speeds = Object.keys(service.speed || {}).map(function (name) {
        var one = service.speed[name];
        return name + ": " + (one.with_diarization || "?") + "x with speakers, " +
          (one.without_diarization || "?") + "x without";
      });

      facts("service", [
        ["Model loaded", loaded.model
          ? loaded.model + " (" + String(loaded.revision).slice(0, 12) + ")"
          : "none"],
        ["GPU", (gpu.name || "") + " " + (gpu.uuid || "")],
        ["VRAM", gpu.vram_used_mb === undefined ? "" :
          gpu.vram_used_mb + " MB used, " + gpu.vram_free_mb + " MB free"],
        ["In line", (line.length === undefined ? "?" : line.length) + " job(s), " +
          (line.audio_minutes === undefined ? "?" : line.audio_minutes) +
          " audio minutes"],
        ["Running now", running
          ? (running.consumer || "another consumer") + ", " + running.stage
          : "nothing"],
        ["Measured speed", speeds.join("; ") || "not measured yet"],
        ["Version", (versions.service || "") + ", api " + (versions.api || "")],
        ["Uptime", service.uptime_seconds
          ? Math.round(service.uptime_seconds / 3600) + " h" : ""],
        ["Last failure", service.last_failure
          ? service.last_failure.reason_class + " at " + service.last_failure.time
          : "none"],
        ["Consumers", (service.tokens || []).join(", ")]
      ]);
    }

    var storage = document.getElementById("storage");
    storage.textContent = state.storage.free + " free (the floor is " +
      state.storage.floor + ")";
    storage.className = state.storage.colour === "plain"
      ? ""
      : "notice " + (state.storage.colour === "red" ? "danger" : "warn");

    document.getElementById("workspaces").textContent =
      "Workspaces: " + state.workspaces.open + " open, " +
      state.workspaces.busy + " busy, " + state.workspaces.gigabytes +
      " GB in scratch";

    // Kept while Folder management is off, with the date it went off, so IT
    // can see what is parked and for how long it has been out of reach.
    var cases = document.getElementById("cases");
    if (cases) {
      // The panel chapter's line: live cases, then the ones in their last
      // days, then what waits in the recycle bin and how much disk it holds.
      cases.textContent =
        "Cases: " + state.workspaces.cases + ", " +
        state.workspaces.cases_gigabytes + " GB; " +
        state.workspaces.expiring + " expiring; " +
        state.workspaces.binned + " in the recycle bin, " +
        state.workspaces.binned_gigabytes + " GB" +
        (state.workspaces.cases_off_since
          ? ". Folder management has been off since " +
            state.workspaces.cases_off_since
          : "");
    }

    document.getElementById("media").textContent =
      state.media.running + " media job(s) running, " +
      state.media.pieces + " upload piece(s) pending";

    var directory = document.getElementById("directory");
    if (directory) {
      var told = state.directory;
      directory.textContent = !told.on
        ? "The directory is switched off: local admins only."
        : (told.reachable
            ? "Reachable. Last check: " + told.last_check
            : "Unreachable: " + told.says);
      directory.className = told.on && !told.reachable ? "notice danger" : "";
    }

    // The AI assistant's line: what llm-worker's last check found. Green with
    // the model, red with "unreachable since", or plain while no engine is
    // configured. Under it, the last Test connection, if one has been run.
    // Names here are the assistant's own: `told` is already the directory
    // line's variable in this function, and `var` is function-scoped.
    var assistant = document.getElementById("assistant");
    if (assistant && state.assistant) {
      var engineTold = state.assistant;
      assistant.textContent = "AI assistant: " + engineTold.says;
      assistant.className = engineTold.state === "unreachable" ? "notice danger"
        : engineTold.state === "reachable" ? "notice" : "muted";
      var testLine = document.getElementById("assistant-test");
      var lastTest = engineTold.test || {};
      if (!lastTest.at) {
        testLine.textContent = "";
      } else if (lastTest.ok) {
        testLine.textContent = "Test connection at " + lastTest.at.slice(11, 16) +
          ": the engine lists " + (lastTest.models || []).join(", ") +
          " and answered “" + (lastTest.answered || "") + "” in " + lastTest.seconds +
          " s." + (lastTest.warning ? " " + lastTest.warning : "");
      } else {
        testLine.textContent = "Test connection at " + lastTest.at.slice(11, 16) +
          " failed: " + (lastTest.says || lastTest.reason || "") +
          (lastTest.models ? " (the engine lists " + lastTest.models.join(", ") + ")" : "");
      }
    }

    // The Backup line: red when off, failed or overdue; amber while the
    // first Snapshot is still to come or a drill is late; plain otherwise.
    var backup = document.getElementById("backup");
    if (backup && state.backup) {
      backup.textContent = "Backup: " + state.backup.says;
      backup.className = state.backup.colour === "red" ? "notice danger"
        : state.backup.colour === "amber" ? "notice warn" : "notice";
      var drillLine = document.getElementById("backup-drill");
      drillLine.textContent = state.backup.drill ? "Restore drill: " + state.backup.drill : "";
    }

    // The Email line: not configured, or last sent and last failure; red
    // while the most recent try failed.
    var email = document.getElementById("email");
    if (email && state.email) {
      email.textContent = "Email: " + state.email.says;
      email.className = state.email.colour === "red" ? "notice danger" : "notice";
      document.getElementById("email-without").textContent =
        "People without an email address: " + state.email.without_email;
    }

    facts("versions", [
      ["Release", state.versions.release],
      ["Database migration", state.versions.migration],
      ["WhisperX service", state.versions.service]
    ]);
  }

  function ask() {
    fetch("/panel/status/lines")
      .then(function (answer) { return answer.json(); })
      .then(function (state) { draw(state); })
      .catch(function () { /* the next ask will find it */ })
      .then(function () { window.setTimeout(ask, EVERY); });
  }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  // The integrity check walks the whole chain, so it is a button rather
  // than something the page does again every five seconds.
  var check = document.getElementById("integrity");
  var said = document.getElementById("integrity-said");
  check.addEventListener("click", function () {
    check.disabled = true;
    said.textContent = "Walking the chain...";
    fetch("/panel/audit/check", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    })
      .then(function (answer) { return answer.json(); })
      .then(function (result) {
        said.textContent = result.message + " (" + result.rows + " rows checked)";
      })
      .catch(function () { said.textContent = "The check could not be run."; })
      .then(function () { check.disabled = false; });
  });

  // Test connection is handed to llm-worker, the one container on the
  // engine's network; the answer lands on the status row and the next poll
  // shows it, so this only starts it and says so.
  var testEngine = document.getElementById("test-engine");
  if (testEngine) {
    testEngine.addEventListener("click", function () {
      testEngine.disabled = true;
      var saying = document.getElementById("assistant-test");
      saying.textContent = "Testing. The answer appears here in a moment.";
      fetch("/panel/assistant/test", {
        method: "POST",
        headers: { "X-CSRFToken": cookie("csrftoken") }
      })
        .catch(function () { saying.textContent = "The test could not be started."; })
        .then(function () { window.setTimeout(function () { testEngine.disabled = false; }, 8000); });
    });
  }

  ask();
})();

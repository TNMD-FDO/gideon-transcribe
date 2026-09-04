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

  ask();
})();

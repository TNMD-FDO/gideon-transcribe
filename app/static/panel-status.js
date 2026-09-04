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
        "<li class='card quiet'>The container states cannot be read from " +
        "inside the app on this server.</li>";
    } else {
      services.innerHTML = state.services.map(function (one) {
        return "<li class='card'><strong>" + escape(one.name) + "</strong> " +
          escape(one.state) + " <span class='quiet'>" + escape(one.says) +
          "</span></li>";
      }).join("");
    }

    var service = state.service;
    if (!service.up) {
      facts("service", [["Reachable", "no: " + (service.says || "")]]);
    } else {
      var gpu = service.gpu || {};
      var line = service.line || {};
      facts("service", [
        ["Model loaded", service.model_loaded || "none"],
        ["GPU", (gpu.name || "") + " " + (gpu.uuid || "")],
        ["VRAM", (gpu.vram_used_mb || "?") + " MB used, " +
          (gpu.vram_free_mb || "?") + " MB free"],
        ["In line", (line.queued === undefined ? "?" : line.queued) + " job(s), " +
          (line.audio_minutes === undefined ? "?" : line.audio_minutes) +
          " audio minutes"],
        ["Running now", (service.current && service.current.consumer
          ? service.current.consumer + ", " + service.current.stage : "nothing")],
        ["Version", service.version || ""],
        ["Uptime", service.uptime_seconds
          ? Math.round(service.uptime_seconds / 3600) + " h" : ""],
        ["Last failure", (service.last_failure && service.last_failure.reason_class)
          || "none"]
      ]);
    }

    var storage = document.getElementById("storage");
    storage.textContent = state.storage.free + " free (the floor is " +
      state.storage.floor + ")";
    storage.className = state.storage.colour === "plain"
      ? "" : "notice " + state.storage.colour;

    document.getElementById("workspaces").textContent =
      "Workspaces: " + state.workspaces.open + " open, " +
      state.workspaces.busy + " busy, " + state.workspaces.gigabytes +
      " GB in scratch";

    document.getElementById("media").textContent =
      state.media.running + " media job(s) running, " +
      state.media.pieces + " upload piece(s) pending";

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

  ask();
})();

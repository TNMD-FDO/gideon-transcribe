// Add path files from the case's head (Phase 12 chapter 6, v1.194.0): a
// folder's worth of .vtt files posted in batches; each finds its video by
// name and lands on it, the rest wait on the case for theirs, and what is
// flagged, already taken or refused comes back in a layer to settle. The
// Map tab's own script reloads when it is open. Nothing here reads a file.
(function () {
  "use strict";
  var label = document.getElementById("case-add-paths");
  if (!label) { return; }
  var input = label.querySelector("input");
  var BATCH = 20;   // files per post: two hundred at once would be one request too large

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
  function cookie(name) { var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  function toast(words, bad) { if (window.UI && window.UI.toast) { window.UI.toast(words, bad ? "bad" : ""); } }
  function postForm(url, form) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": cookie("csrftoken") }, body: form })
      .then(function (a) { return a.json().then(function (told) { if (!a.ok) { throw new Error(told.error || "That did not work."); } return told; }); });
  }

  input.addEventListener("change", function () {
    if (input.files.length) { add(Array.prototype.slice.call(input.files), {}, []); input.value = ""; }
  });

  // Several files, in batches; the answers are merged into one. The layer
  // opens at once with the count going up (v1.195.1: two hundred files took
  // a few seconds a batch and the page looked idle, and a press on a tab
  // threw the rest away), and the page says so if it is about to be left.
  var busy = null;
  window.addEventListener("beforeunload", function (e) { if (busy) { e.preventDefault(); e.returnValue = "Path files are still being added."; return e.returnValue; } });
  function add(files, chosen, replace) {
    var batches = [];
    for (var i = 0; i < files.length; i += BATCH) { batches.push(files.slice(i, i + BATCH)); }
    var merged = { landed: [], leftovers: [], waiting: [] }, done = 0, stopped = false;
    label.classList.add("busy");
    var layer = document.createElement("div");
    layer.className = "map-layer";
    layer.innerHTML = "<div class='map-layer-card'><div class='h'><b>Adding " + plural(files.length, "path file") + "</b><span class='muted small' id='paths-count'>0 of " + files.length + " read</span></div>" +
      "<div class='bar'><i id='paths-bar' style='width: 0%'></i></div>" +
      "<p class='small' style='margin: 0'>Keep this page open until it finishes: the files go up " + BATCH + " at a time, and each finds its video by name or waits on the case for it.</p>" +
      "<div class='acts'><button type='button' class='small ghost' data-act='stop'>Stop after this batch</button></div></div>";
    document.body.appendChild(layer);
    layer.addEventListener("click", function (e) { var b = e.target.closest("[data-act='stop']"); if (b) { stopped = true; b.disabled = true; b.textContent = "Stopping..."; } });
    busy = layer;
    function progress() {
      var count = layer.querySelector("#paths-count"), bar = layer.querySelector("#paths-bar");
      if (count) { count.textContent = done + " of " + files.length + " read"; }
      if (bar) { bar.style.width = Math.round((done / Math.max(1, files.length)) * 100) + "%"; }
    }
    function over(error) { busy = null; label.classList.remove("busy"); finish(files, merged, layer, error || (stopped && batches.length ? "Stopped: " + (files.length - done) + " of the files were not sent." : "")); }
    function next() {
      if (!batches.length || stopped) { over(""); return; }
      var batch = batches.shift(), form = new FormData();
      batch.forEach(function (f) { var at = files.indexOf(f); form.append("files", f, f.name); form.append("chosen", chosen[at] || ""); });
      replace.forEach(function (id) { form.append("replace", id); });
      postForm(label.dataset.add, form).then(function (told) {
        merged.landed = merged.landed.concat(told.landed || []);
        merged.leftovers = merged.leftovers.concat(told.leftovers || []);
        merged.waiting = merged.waiting.concat(told.waiting || []);
        done += batch.length; progress();
        next();
      }).catch(function (e) { over((e && e.message ? e.message : "That did not work.") + " " + (files.length - done) + " of the files were not sent."); });
    }
    next();
  }

  function finish(files, told, layer, error) {
    var landed = told.landed, left = told.leftovers, waiting = told.waiting;
    var flagged = left.filter(function (one) { return one.why === "flagged"; }).length;
    var hasOne = left.filter(function (one) { return one.why === "has_one"; }).length;
    var refused = left.filter(function (one) { return one.why === "refused"; }).length;
    var again = waiting.filter(function (one) { return one.again; }).length;
    if (!layer) { layer = document.createElement("div"); layer.className = "map-layer"; document.body.appendChild(layer); }
    var rows = (error ? "<tr><td colspan='3'><span class='pill danger small'>Not finished</span> " + esc(error) + " Choose the files again to send the rest; a file already waiting is not kept twice.</td></tr>" : "") +
      "<tr><td>Added to their videos</td><td class='mono'>" + landed.length + "</td><td class='muted'>" + (landed.length ? "on the map now" : "") + "</td></tr>" +
      "<tr><td>Waiting for their video</td><td class='mono'>" + (waiting.length - again) + "</td><td class='muted'>kept on the case; paired when the video arrives" + (again ? " · " + plural(again, "file") + " already waiting, not kept twice" : "") + "</td></tr>" +
      (flagged ? "<tr><td>Flagged</td><td class='mono'>" + flagged + "</td><td class='muted'>matched a video by name, but something disagrees; settle below</td></tr>" : "") +
      (hasOne ? "<tr><td>Already has one</td><td class='mono'>" + hasOne + "</td><td class='muted'>the video has a path file; Replace below</td></tr>" : "") +
      (refused ? "<tr><td>Refused</td><td class='mono'>" + refused + "</td><td class='muted'>not a path file, or too large</td></tr>" : "");
    var settle = left.map(function (one, i) {
      var what = esc(one.words) + (one.about ? "<br><span class='muted'>" + esc(one.about) + "</span>" : ""), act = "";
      if (one.why === "flagged") { what = "Matches <b>" + esc(one.title) + "</b> by name, but: " + what + " <span class='pill warn small'>Flagged</span>"; act = "<label><input type='checkbox' data-i='" + i + "' data-rec='" + one.recording + "'> Add anyway</label>"; }
      else if (one.why === "has_one") { what = "<b>" + esc(one.title) + "</b> already has a path file. <span class='pill small'>Has one</span>"; act = "<label><input type='checkbox' data-i='" + i + "' data-rec='" + one.recording + "' data-replace='1'> Replace</label>"; }
      else { what += " <span class='pill danger small'>Refused</span>"; }
      return "<tr><td class='mono'>" + esc(one.file) + "</td><td>" + what + "</td><td>" + act + "</td></tr>";
    }).join("");
    var sent = landed.length + left.length + waiting.length;
    layer.innerHTML = "<div class='map-layer-card'><div class='h'><b>" + plural(sent, "path file") + " taken in" + (sent < files.length ? " of " + files.length + " chosen" : "") + "</b><button type='button' class='tiny ghost' data-act='layer-close'>Close</button></div>" +
      "<table class='tbl small'><thead><tr><th>What</th><th>How many</th><th></th></tr></thead><tbody>" + rows + "</tbody></table>" +
      "<p class='muted small' style='margin: 0'>Nothing waiting is read by the map, the chat, the memo or the Speakers page until its video arrives.</p>" +
      (settle ? "<table class='tbl small'><thead><tr><th>File</th><th>What the app found</th><th></th></tr></thead><tbody>" + settle + "</tbody></table>" : "") +
      "<div class='acts'>" + (location.search.indexOf("tab=map") < 0 ? "<a class='btn small ghost' href='" + esc(label.dataset.map) + "'>On the Map tab</a>" : "") +
      (settle && (flagged || hasOne) ? "<button type='button' class='small primary' data-act='layer-go'>Add the settled files</button>" : "") +
      "<button type='button' class='small" + (settle && (flagged || hasOne) ? "" : " primary") + "' data-act='layer-close'>Done</button></div></div>";
    var byName = {}; files.forEach(function (f) { byName[f.name] = f; });
    layer.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]"); if (!b) { return; }
      if (b.dataset.act === "layer-close") { layer.remove(); reload(); return; }
      if (b.dataset.act === "layer-go") {
        var picked = [], chosen = {}, replace = [];
        layer.querySelectorAll("input[type=checkbox]:checked").forEach(function (c) { var one = left[parseInt(c.dataset.i, 10)]; if (byName[one.file]) { chosen[picked.length] = c.dataset.rec; if (c.dataset.replace) { replace.push(c.dataset.rec); } picked.push(byName[one.file]); } });
        layer.remove();
        if (picked.length) { add(picked, chosen, replace); } else { reload(); }
      }
    });
  }

  // The Map tab reads its paths again when it is open; elsewhere the counts
  // in the bar and the head catch up on the next load.
  function reload() { if (window.MapTab && window.MapTab.reload) { window.MapTab.reload(); } }

  window.PathFiles = { add: add };
})();

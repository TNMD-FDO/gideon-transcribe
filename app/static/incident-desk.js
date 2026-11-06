// The Incidents tab's wall (Phase 12 chapter 10, v1.212.0; the drawing
// docs/spec/mockups/phase-12-incident-builder-desk.html): every camera
// ticked on the strip plays its video here at the clock, in step with the
// others, up to the Cameras on the wall setting. One transport under the
// wall (Play, 10 s back and forward, the speed, the clock, a scrub across
// the span); one tile carries the sound; a press on a tile makes it the
// focus with the line being said beside it, a second press returns to the
// grid. The strip (chronology.js) tells the wall what is ticked, the span
// and the clock line by a "desk-cams" event; the wall answers with the clock
// while it plays ("desk-clock"), the clock let go ("desk-clock-set"), and a
// tile's untick or a faint tile's tick. Nothing is kept on the server: the
// layout is remembered for the person on this browser.
(function () {
  "use strict";
  var host = document.getElementById("desk-wall");
  if (!host) { return; }
  var CASE = host.dataset.case || "";
  var MOST = parseInt(host.dataset.most, 10) || 8;
  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function hms(seconds) { seconds = Math.max(0, Math.round(seconds)) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function hm(seconds) { return hms(seconds).slice(0, 5); }
  function elapsed(seconds) { seconds = Math.max(0, Math.round(seconds)); var m = Math.floor(seconds / 60), s = seconds % 60; return m ? m + " min " + s + " s" : s + " s"; }
  function recall(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function remember(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* no storage */ } }
  function tell(name, detail) { try { window.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (e) { /* an old browser */ } }

  var W = {
    cams: [], players: {}, order: [], near: [],
    at: null, span: null, playing: false, speed: 1, anchorAt: 0, anchorNow: 0,
    layout: recall("desk-layout:" + CASE) === "focus" ? "focus" : "grid",
    sound: null, focus: null, said: {}, saidKey: "", timer: null, told: 0, day: ""
  };
  var SPEEDS = [0.5, 1, 2, 4];

  // The clock ------------------------------------------------------------------
  function now() { return W.playing ? W.anchorAt + (performance.now() - W.anchorNow) / 1000 * W.speed : (W.at === null ? 0 : W.at); }
  function clamp(at) { if (!W.span) { return at; } return Math.max(W.span[0], Math.min(W.span[1], at)); }
  function play() {
    if (W.playing || W.at === null || !W.cams.length) { return; }
    if (W.span && W.at >= W.span[1] - 0.5) { W.at = W.span[0]; }
    W.anchorAt = W.at; W.anchorNow = performance.now(); W.playing = true;
    if (!W.timer) { W.timer = window.setInterval(tick, 200); }
    drawTransport(); tick();
  }
  function pause(quiet) {
    if (!W.playing) { return; }
    W.at = clamp(now()); W.playing = false;
    if (W.timer) { window.clearInterval(W.timer); W.timer = null; }
    drawTransport(); tick();
    if (!quiet) { tell("desk-clock-set", { at: W.at, from: "wall" }); }
  }
  // A seek while playing keeps playing from there; the strip hears the
  // clock as it moves and keeps it when it is let go.
  function seek(at, settle) {
    at = clamp(Math.round(at));
    W.at = at;
    if (W.playing) { W.anchorAt = at; W.anchorNow = performance.now(); }
    tick();
    if (settle) { tell("desk-clock-set", { at: at, from: "wall" }); } else { tell("desk-clock", { at: at, playing: W.playing }); }
  }
  function step(seconds) { if (W.at === null) { return; } seek(now() + seconds, true); }

  // The cameras ----------------------------------------------------------------
  window.addEventListener("desk-cams", function (e) {
    var told = e.detail || {};
    var dayChanged = told.day !== W.day; W.day = told.day || "";
    W.span = told.span || null; W.near = told.near || []; if (told.most) { MOST = told.most; }
    syncCams(told.cams || []);
    if (!W.cams.length || dayChanged) { pause(true); }
    if (!W.playing && typeof told.at === "number") { W.at = told.at; }
    if (W.at === null && W.span) { W.at = W.span[0]; }
    drawWall();
    tick();
  });
  window.addEventListener("desk-clock-set", function (e) {
    // The strip's clock line let go: the wall seeks there without answering.
    var told = e.detail || {};
    if (told.from !== "strip" || typeof told.at !== "number") { return; }
    W.at = clamp(told.at); if (W.playing) { W.anchorAt = W.at; W.anchorNow = performance.now(); } tick();
  });
  window.addEventListener("desk-focus", function (e) { var id = e.detail && e.detail.id; if (id && W.players[id]) { setFocus(id); } });
  function syncCams(cams) {
    var wanted = {};
    cams.forEach(function (c) { wanted[c.id] = c; });
    Object.keys(W.players).forEach(function (id) { if (!wanted[id]) { removeTile(id); } });
    cams.forEach(function (c) { if (W.players[c.id]) { W.players[c.id].cam = c; } else { W.players[c.id] = { cam: c, tile: tileFor(c), video: null }; W.players[c.id].video = W.players[c.id].tile.querySelector("video"); } });
    W.cams = cams; W.order = cams.map(function (c) { return c.id; });
    if (W.sound && !wanted[W.sound]) { W.sound = null; }
    if (W.focus && !wanted[W.focus]) { W.focus = null; }
    if (!W.sound && W.order.length) { W.sound = W.focus || W.order[0]; }
    if (!W.focus && W.order.length) { W.focus = W.order[0]; }
  }
  function removeTile(id) {
    var p = W.players[id]; if (!p) { return; }
    if (p.video) { try { p.video.pause(); p.video.removeAttribute("src"); p.video.load(); } catch (e) { /* nothing to let go */ } }
    if (p.tile.parentNode) { p.tile.remove(); }
    delete W.players[id];
  }
  function tileFor(cam) {
    var tile = document.createElement("div");
    tile.className = "wtile" + (cam.unclocked || !cam.media ? " blank" : "");
    tile.dataset.id = cam.id;
    tile.style.setProperty("--cam", cam.colour || "var(--muted)");
    var reason = cam.unclocked ? "Not on the clock: it joins the incident unplaced and is synced on the incident page." : (!cam.media ? "Its playback copy is not ready yet." : "");
    tile.innerHTML = "<div class='well'>" +
      (reason ? "<p class='muted small state'>" + esc(reason) + "</p>" : "<video muted playsinline preload='metadata' src='" + esc(cam.media) + "'></video><span class='state small' hidden></span><span class='prog' title='Where the clock is in this video; press to go there'><i></i></span>") +
      "</div>" +
      "<div class='wbar'><i class='dot'></i><b class='w' title='" + esc(cam.title) + "'>" + esc(cam.name) + "</b>" +
      (reason ? "" : "<button type='button' class='link tiny snd' title='Hear this camera; the others play silent'>sound</button><span class='into muted tiny'></span>") +
      "<button type='button' class='link tiny untick' title='Take this camera off the wall and out of your incident'>untick</button></div>";
    tile.querySelector(".untick").addEventListener("click", function (ev) { ev.stopPropagation(); tell("desk-untick", { id: cam.id }); });
    var snd = tile.querySelector(".snd");
    if (snd) { snd.addEventListener("click", function (ev) { ev.stopPropagation(); setSound(cam.id); }); }
    var prog = tile.querySelector(".prog");
    if (prog) { prog.addEventListener("click", function (ev) { ev.stopPropagation(); var r = prog.getBoundingClientRect(); var share = Math.max(0, Math.min(1, (ev.clientX - r.left) / (r.width || 1))); seek(cam.zero + share * (cam.to - cam.zero), true); }); }
    tile.querySelector(".well").addEventListener("click", function () {
      // A press makes the tile the focus; a press on the focus returns to the grid.
      if (W.layout === "focus" && W.focus === cam.id) { setLayout("grid"); return; }
      setFocus(cam.id); if (W.layout !== "focus") { setLayout("focus"); }
    });
    return tile;
  }
  function setSound(id) {
    W.sound = id;
    Object.keys(W.players).forEach(function (pid) { var p = W.players[pid]; if (p.video) { p.video.muted = pid !== id; } p.tile.classList.toggle("sound", pid === id); });
  }
  function setFocus(id) { W.focus = id; W.saidKey = ""; drawWall(); tick(); }
  function setLayout(layout) { W.layout = layout; remember("desk-layout:" + CASE, layout); W.saidKey = ""; drawWall(); tick(); }

  // Drawing ----------------------------------------------------------------------
  var el = {};
  function drawWall() {
    if (!el.grid) {
      host.innerHTML = "<div class='whead'><span class='eye' id='wall-words'></span><span class='muted tiny' id='wall-hint'></span></div><div class='wgrid' id='wall-grid'></div><div class='wsaid' id='wall-said' hidden></div><div class='wnear' id='wall-near' hidden></div><div class='wtransport' id='wall-transport'></div>";
      el.grid = host.querySelector("#wall-grid"); el.words = host.querySelector("#wall-words"); el.hint = host.querySelector("#wall-hint"); el.said = host.querySelector("#wall-said"); el.near = host.querySelector("#wall-near"); el.transport = host.querySelector("#wall-transport");
      el.said.addEventListener("click", function (ev) { var line = ev.target.closest("[data-at]"); if (line) { seek(parseFloat(line.dataset.at), true); } });
      el.near.addEventListener("click", function (ev) { var b = ev.target.closest("[data-near]"); if (b) { tell("desk-tick", { id: b.dataset.near }); } });
    }
    var n = W.order.length;
    host.dataset.layout = W.layout; host.dataset.n = String(n);
    host.classList.toggle("empty", !n);
    el.words.textContent = n ? "The wall · " + n + " of " + MOST + (W.playing ? " playing in step" : " at " + hms(now())) : "The wall";
    el.hint.textContent = n ? (W.layout === "focus" ? "Focus · press the large tile for the grid" : "Grid · press a tile to focus on it") : "Tick cameras on the lanes and they play here together.";
    // The tiles in the ticks' order, the focus first in Focus; faint tiles
    // for the near cameras while there is room, each a press to tick.
    var want = W.order.slice();
    if (W.layout === "focus" && W.focus && want.indexOf(W.focus) > 0) { want.splice(want.indexOf(W.focus), 1); want.unshift(W.focus); }
    var nodes = want.map(function (id) { return W.players[id].tile; });
    // The near cameras (the map's answer) offered under the tiles as faint
    // chips while there is room on the wall, each a press to tick.
    var nearRow = n && n < MOST ? W.near.slice(0, 4) : [];
    el.near.hidden = !nearRow.length;
    el.near.innerHTML = nearRow.length ? "<span class='muted tiny'>Near at the clock line:</span>" + nearRow.map(function (c) { return "<button type='button' class='pill small' data-near='" + esc(c.id) + "' title='Within 50 m of " + esc(c.by) + " at the clock line, by their paths; press to tick'>" + esc(c.name) + " · tick</button>"; }).join("") : "";
    nodes.forEach(function (node, i) { if (el.grid.children[i] !== node) { el.grid.insertBefore(node, el.grid.children[i] || null); } });
    Array.prototype.slice.call(el.grid.children).forEach(function (node) { if (nodes.indexOf(node) < 0) { node.remove(); } });
    Object.keys(W.players).forEach(function (id) { W.players[id].tile.classList.toggle("focus", W.layout === "focus" && id === W.focus); });
    if (W.sound) { setSound(W.sound); }
    el.said.hidden = !(W.layout === "focus" && W.focus && W.players[W.focus] && !W.players[W.focus].cam.unclocked);
    if (!el.said.hidden) { wantSaid(W.focus); }
    drawTransport();
  }
  function drawTransport() {
    if (!el.transport) { return; }
    var n = W.order.length;
    el.transport.hidden = !n;
    if (!n) { return; }
    if (!el.transport.firstChild) {
      el.transport.innerHTML = "<button type='button' class='small primary' data-act='play'>▶ Play</button><button type='button' class='small' data-act='back' title='Ten seconds back'>‹ 10 s</button><button type='button' class='small' data-act='fwd' title='Ten seconds on'>10 s ›</button>" +
        "<select class='small' data-act='speed' title='The speed'>" + SPEEDS.map(function (s) { return "<option value='" + s + "'>Speed " + s + "×</option>"; }).join("") + "</select>" +
        "<b class='wclock mono'></b><span class='wscrub'><span class='muted tiny' data-from></span><input type='range' min='0' max='1' step='1' value='0' aria-label='The clock across the span' title='Drag across the span; the wall and the map follow'><span class='muted tiny' data-to></span></span>";
      el.play = el.transport.querySelector("[data-act='play']"); el.clock = el.transport.querySelector(".wclock"); el.range = el.transport.querySelector("input[type=range]");
      el.from = el.transport.querySelector("[data-from]"); el.to = el.transport.querySelector("[data-to]"); el.speed = el.transport.querySelector("[data-act='speed']");
      el.play.addEventListener("click", function () { if (W.playing) { pause(); } else { play(); } });
      el.transport.querySelector("[data-act='back']").addEventListener("click", function () { step(-10); });
      el.transport.querySelector("[data-act='fwd']").addEventListener("click", function () { step(10); });
      el.speed.addEventListener("change", function () { var s = parseFloat(el.speed.value) || 1; if (W.playing) { W.anchorAt = now(); W.anchorNow = performance.now(); } W.speed = s; tick(); });
      var scrubbing = false;
      el.range.addEventListener("input", function () { scrubbing = true; seek(parseFloat(el.range.value), false); });
      el.range.addEventListener("change", function () { scrubbing = false; seek(parseFloat(el.range.value), true); });
      el.range.addEventListener("keydown", function (ev) { if (ev.key === " ") { ev.preventDefault(); el.play.click(); } });
    }
    el.play.textContent = W.playing ? "❚❚ Pause" : "▶ Play";
    el.play.title = W.playing ? "Pause every camera" : "Play every ticked camera in step from the clock";
    el.speed.value = String(W.speed);
    if (W.span) { el.range.min = String(Math.round(W.span[0])); el.range.max = String(Math.round(W.span[1])); el.from.textContent = hm(W.span[0]); el.to.textContent = hm(W.span[1]); }
  }

  // Keeping in step (the incident page's rule): a video that drifts under
  // half a second is nudged by its rate, one further off is seeked.
  function follow(p, m) {
    var cam = p.cam, video = p.video; if (!video) { return; }
    var local = m - cam.zero, length = cam.to - cam.zero;
    var state = p.tile.querySelector(".state"), into = p.tile.querySelector(".into"), prog = p.tile.querySelector(".prog i");
    if (local < 0 || local > length) {
      state.hidden = false; state.textContent = local < 0 ? "Starts in " + elapsed(-local) : "Ended at " + hm(cam.to);
      p.tile.classList.add("off");
      if (!video.paused) { video.pause(); }
      if (into) { into.textContent = ""; }
      if (prog) { prog.style.width = local < 0 ? "0%" : "100%"; }
      return;
    }
    state.hidden = true; p.tile.classList.remove("off");
    if (into) { into.textContent = elapsed(local) + " in"; }
    if (prog) { prog.style.width = (100 * local / (length || 1)) + "%"; }
    // A seek still in flight is left to land: seeking again every tick
    // would hold the video at its old frame for good.
    if (video.seeking) { return; }
    var drift = video.currentTime - local;
    if (W.playing) {
      if (video.paused && video.readyState >= 2) {
        video.currentTime = local; video.playbackRate = W.speed;
        var started = video.play();
        if (started && started.catch) { started.catch(function () { /* the browser asks for a gesture; the next press gives one */ }); }
        return;
      }
      if (video.paused) { return; }
      if (Math.abs(drift) > 0.5) { video.currentTime = local; video.playbackRate = W.speed; }
      else if (Math.abs(drift) > 0.08) { video.playbackRate = Math.max(0.5, Math.min(4, W.speed * (1 - Math.max(-0.1, Math.min(0.1, drift))))); }
      else { video.playbackRate = W.speed; }
    } else {
      if (!video.paused) { video.pause(); }
      if (Math.abs(drift) > 0.05 && video.readyState >= 1) { video.currentTime = local; }
    }
  }
  function tick() {
    if (!el.grid) { return; }
    var m = now();
    if (W.playing && W.span && m >= W.span[1]) { W.at = W.span[1]; pause(); return; }
    if (el.clock) { el.clock.textContent = hms(m); }
    if (el.range && document.activeElement !== el.range) { el.range.value = String(Math.round(m)); }
    if (el.words && W.order.length) { el.words.textContent = "The wall · " + W.order.length + " of " + MOST + (W.playing ? " playing in step at " + hms(m) : " at " + hms(m)); }
    Object.keys(W.players).forEach(function (id) { follow(W.players[id], m); });
    if (!el.said.hidden) { drawSaid(m); }
    if (W.playing) { var t = Date.now(); if (t - W.told > 250) { W.told = t; tell("desk-clock", { at: m, playing: true }); } }
  }
  document.addEventListener("visibilitychange", function () { if (document.hidden && W.playing) { pause(); } });

  // The said line (Focus): what is being said on the focus camera at the
  // clock, from its transcript, read once per camera.
  function wantSaid(id) {
    if (W.said[id]) { return; }
    W.said[id] = { lines: null };
    fetch("/recording/" + id + "/segments?words=0", { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      W.said[id].lines = (told.segments || []).map(function (s) { return { start: s.start, end: s.end, text: s.text, speaker: s.speaker || "" }; });
      W.saidKey = ""; tick();
    }).catch(function () { W.said[id].lines = []; });
  }
  function drawSaid(m) {
    var p = W.players[W.focus]; if (!p) { return; }
    var kept = W.said[W.focus], local = m - p.cam.zero;
    var head = "Said on " + esc(p.cam.name);
    if (!kept || !kept.lines) { if (W.saidKey !== "wait") { W.saidKey = "wait"; el.said.innerHTML = "<span class='eye'>" + head + "</span><span class='muted small'>reading the transcript...</span>"; } return; }
    if (!kept.lines.length) { if (W.saidKey !== "none") { W.saidKey = "none"; el.said.innerHTML = "<span class='eye'>" + head + "</span><span class='muted small'>no transcript yet</span>"; } return; }
    var i = -1;
    for (var k = 0; k < kept.lines.length; k++) { if (kept.lines[k].start <= local + 0.3) { i = k; } else { break; } }
    var key = W.focus + ":" + i;
    if (key === W.saidKey) { return; }
    W.saidKey = key;
    var html = "<span class='eye'>" + head + "</span>";
    if (i < 0) { el.said.innerHTML = html + "<span class='muted small'>nothing said yet</span>"; return; }
    [i - 1, i, i + 1].forEach(function (k) {
      var line = kept.lines[k]; if (!line) { return; }
      html += "<button type='button' class='wline" + (k === i ? " lit" : "") + "' data-at='" + (p.cam.zero + line.start) + "' title='Go to this line'><span class='mono muted'>" + hms(p.cam.zero + line.start) + "</span>" + (line.speaker ? "<span class='who'>" + esc(line.speaker) + "</span>" : "") + "<span class='txt'>" + esc(line.text) + "</span></button>";
    });
    el.said.innerHTML = html;
  }

  // Keys: space plays and pauses; the arrows step a second, ten with shift.
  document.addEventListener("keydown", function (ev) {
    var at = ev.target;
    if (!W.order.length || !at || !at.closest || at.closest("input, textarea, select, button, [contenteditable]")) { return; }
    if (ev.key === " ") { ev.preventDefault(); if (W.playing) { pause(); } else { play(); } return; }
    if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); step((ev.key === "ArrowRight" ? 1 : -1) * (ev.shiftKey ? 10 : 1)); }
  });
  drawWall();
})();

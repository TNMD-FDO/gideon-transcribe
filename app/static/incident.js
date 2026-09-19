// The Incident page (Phase 6 chapters 1 and 2): the cameras of one event in
// step, and its Chronology.
//
// One clock runs the page: the moment on the Incident clock, in seconds from
// the Incident's zero. While playing it advances by the wall clock at the
// chosen speed, and every camera on the Wall is kept at (moment minus its
// start): a camera that has not started waits, one that has ended stops,
// and one that drifts is nudged by its rate or seeked outright. The camera
// with the sound is the one that is heard; the rest are muted. An Event is
// made at the moment being watched, from a line under a tile, or from a
// citation's address, and drawn on the Events lane and the Chronology tab.
// Nothing here is stored except through the act endpoint, and every answer
// redraws the page from the state it carries.

(function () {
  "use strict";

  var C = window.INCIDENT;
  var stateNode = document.getElementById("incident-state");
  if (!C || !stateNode) { return; }
  var S = JSON.parse(stateNode.textContent);
  var eventWordsNode = document.getElementById("event-words");
  var eventWords = eventWordsNode ? JSON.parse(eventWordsNode.textContent) : "";

  var wallBox = document.getElementById("wall");
  var lanesBox = document.getElementById("lanes");
  var ticksBox = document.getElementById("ticks");
  var band = document.getElementById("clip-band");   // the dragged span on the ruler (Phase 6 chapter 5)
  var strip = document.getElementById("strip");
  var clockBig = document.getElementById("inc-clock");
  var dateBox = document.getElementById("inc-date");
  var facts = document.getElementById("inc-facts");
  var clockSmall = document.getElementById("clock");
  var playButton = document.getElementById("play");
  var speedBox = document.getElementById("speed");
  var soundSaid = document.getElementById("sound-said");
  var filmBox = document.getElementById("film");
  var deskBox = document.querySelector(".inc-desk");
  var workBox = document.querySelector(".inc-work");
  var followBox = document.getElementById("follow");
  var trouble = document.getElementById("player-trouble");
  var eventBox = document.getElementById("event-box");
  var clipBox = document.getElementById("clip-box");      // Clip this event (Phase 7 chapter 1)
  // The layers (Phase 8 chapter 1): one job opened over the tab in the work
  // panel; the wall and the strip never move. A stack, because a clip can
  // open from an event; Back pops one and returns exactly.
  var LAYERS = ["event", "clip", "sync", "proposals", "find"];
  var layerStack = [];
  var layerReturn = null;

  // The clock ------------------------------------------------------------------------

  var moment = C.at || 0;      // seconds on the Incident clock
  var playing = false;
  var speed = 1;
  var anchorMoment = 0;
  var anchorNow = 0;
  var soundCamera = null;      // the camera id with the sound
  var players = {};            // camera id -> { cam, video, tile }
  var lines = {};              // camera id -> { segments, moments }
  var zoom = 0;                // seconds shown; 0 is all
  var panFrom = null;          // a zoomed window's left edge once the person has moved it; null follows the playhead
  var dragging = null;
  var pollTimer = null;
  var currentEventId = null;
  var draggedTile = null;
  var layout = "focus";        // focus, side, grid2, grid3, grid4 (chapter 4)
  var focusCamera = null;      // the large camera in the Focus layout
  var soundPinned = false;     // the sound stays put rather than following the focus
  var LAYOUTS = ["focus", "side", "grid2", "grid3", "grid4"];
  // The tile's short pill (chapter 4); the full words are its hover title.
  var SHORT_PILL = { clock: "Clock", clock_unchecked: "Clock?", sound: "Sound", file: "File", hand: "Hand", guess: "Guess" };
  function shortPill(cam) { return SHORT_PILL[cam.placed] || cam.placed_words || ""; }

  function now() {
    if (!playing) { return moment; }
    return anchorMoment + ((performance.now() - anchorNow) / 1000) * speed;
  }

  function span() {
    var low = S.incident.span_low, high = S.incident.span_high;
    if (low === null || low === undefined) { return [0, 60]; }
    if (high - low < 1) { high = low + 1; }
    return [low, high];
  }

  function hms(seconds) {
    seconds = Math.round(seconds);
    seconds = ((seconds % 86400) + 86400) % 86400;
    var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function elapsed(seconds) {
    seconds = Math.max(0, Math.round(seconds));
    var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
    return (h ? h + ":" + (m < 10 ? "0" : "") : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function timeOfDay(at) {
    return S.incident.has_clock ? hms(S.incident.clock_zero + at) : elapsed(at);
  }

  // A typed time back to seconds on the Incident clock: hh:mm:ss of the day
  // when the Incident has a clock, else m:ss from the first camera.
  function parseWhen(text) {
    var parts = String(text || "").trim().split(":");
    if (!parts.length || parts.some(function (one) { return one === "" || isNaN(parseInt(one, 10)); })) { return null; }
    var seconds = parts.map(function (one) { return parseInt(one, 10); }).reduce(function (sum, one) { return sum * 60 + one; }, 0);
    if (!S.incident.has_clock) { return seconds; }
    var at = seconds - S.incident.clock_zero;
    while (at < -43200) { at += 86400; }
    while (at > 43200) { at -= 86400; }
    return at;
  }

  function escape(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

  function quoted(text) { return escape(text).replace(/'/g, "&#39;"); }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (key) {
      if (Array.isArray(fields[key])) { fields[key].forEach(function (one) { body.append(key, one); }); }
      else { body.append(key, fields[key]); }
    });
    return fetch(C.act, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") }, body: body })
      .then(function (answer) { return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }); })
      .then(function (got) {
        if (!got.ok) {
          window.UI.toast(got.said.error || "That did not work.", { problem: true });
          return got;
        }
        if (got.said.redirect) { window.location = got.said.redirect; return got; }
        if (got.said.said) { window.UI.toast(got.said.said); }
        if (got.said.state) { take(got.said.state); }
        return got;
      });
  }

  function cameraById(id) {
    for (var i = 0; i < S.cameras.length; i += 1) { if (S.cameras[i].id === id) { return S.cameras[i]; } }
    return null;
  }

  function eventById(id) {
    for (var i = 0; i < S.events.length; i += 1) { if (S.events[i].id === id) { return S.events[i]; } }
    return null;
  }

  function placedCameras() { return S.cameras.filter(function (one) { return one.starts_at !== null && one.placed; }); }
  function wallCameras() {
    var order = S.wall || [];
    return placedCameras().filter(function (one) { return one.on_wall; })
      .sort(function (a, b) { return order.indexOf(a.id) - order.indexOf(b.id); });
  }
  function parkedCameras() { return placedCameras().filter(function (one) { return !one.on_wall; }); }

  // Taking a state: redraw everything but keep the clock where it is.
  function take(state) {
    S = state;
    S.events = S.events || [];
    S.proposals = S.proposals || {};
    S.memo = S.memo || {};
    drawHead();
    drawWall();
    drawStrip();
    drawChronology();
    drawMemo();
    drawCameras();
    drawDetails();
    if (soundCamera && !cameraById(soundCamera)) { soundCamera = null; soundPinned = false; }
    if (!soundCamera && wallCameras().length) { soundCamera = (layout === "focus" && focusCamera) ? focusCamera : wallCameras()[0].id; }
    drawSoundChoice();
    tick();
    // A clip box left open follows the cameras as they stand now.
    if (clipBox && !clipBox.hidden) { refreshClipBox(); }
    // The assistant at work (chapter 3), or a clip rendering (v1.63.1): the
    // page asks again until it lands, so the row's words change by themselves.
    var rendering = S.events.some(function (one) { return one.clips_rendering; });
    var matching = S.cameras.some(function (cam) { return cam.match && (cam.match.state === "queued" || cam.match.state === "running"); });
    if (layerOf("sync") && !layerOf("sync").hidden) { drawSync(); }
    drawProposals();
    if (S.proposals.busy || S.memo.busy || rendering || matching) {
      window.clearTimeout(pollTimer);
      pollTimer = window.setTimeout(refresh, 3000);
    }
  }

  var STILL_PROPOSING = "The assistant is still proposing; accept or dismiss once it has finished";

  function keptEvents() { return S.events.filter(function (one) { return !one.proposed; }); }

  // The head ----------------------------------------------------------------------------

  function drawHead() {
    var count = S.incident.count;
    var events = keptEvents().length;
    facts.textContent = count + " camera" + (count === 1 ? "" : "s") + " · " + S.incident.span_words +
      " · " + events + " event" + (events === 1 ? "" : "s");
    dateBox.textContent = S.incident.has_clock ? S.incident.clock_date : "no camera clock; times are from the first camera";
  }

  // The Wall ----------------------------------------------------------------------------

  function tileFor(cam) {
    var tile = document.createElement("div");
    tile.className = "inc-tile";
    tile.dataset.camera = cam.id;
    tile.style.setProperty("--speaker", cam.colour);
    tile.draggable = true;
    tile.innerHTML =
      "<div class='inc-tile-head'><span class='dot'></span><b title='" + quoted(cam.title) + "'>" + escape(cam.camera_id) + "</b>" +
      "<span class='pill " + escape(cam.placed_tone) + " small' title='" + quoted(cam.placed_words) + "'>" + escape(shortPill(cam)) + "</span>" +
      "<button type='button' class='tiny ghost snd' data-tile='sound' title='Hear this camera'><svg class='i' aria-hidden='true'><use href='#i-muted'></use></svg></button>" +
      "<button type='button' class='tiny sync-open' data-tile='sync' title='Nudge this camera into step, or set its start'>Sync</button>" +
      "<details class='menu tile-menu'><summary class='tiny' title='Swap out, open, remove'>⋯</summary><ul>" +
      "<li><button type='button' data-tile='swap'>Swap out</button></li>" +
      "<li><a href='" + escape(cam.viewer_url) + "'>Open the recording</a></li>" +
      "<li class='sep'></li><li><button type='button' class='danger' data-tile='remove'>Remove from incident</button></li></ul></details></div>" +
      "<div class='inc-sync' hidden></div>" +
      "<div class='inc-well'>" + (cam.media_url ? "<video preload='metadata' playsinline muted></video>" : "<p class='preparing small'>Playback is being prepared.</p>") +
      "<div class='state' hidden></div></div>" +
      "<div class='inc-lines'>" +
      "<div class='said'><span class='who'></span> <span class='txt muted'>…</span> <button type='button' class='tiny ghost add-line' data-kind='words' title='Add this line as an event' hidden>+ event</button></div></div>";
    tile.querySelector(".inc-tile-head").addEventListener("click", function (event) {
      var button = event.target.closest("[data-tile]");
      if (!button) { return; }
      tile.querySelector(".tile-menu").removeAttribute("open");
      if (button.dataset.tile === "sync") { openSync(cam.id); }
      else if (button.dataset.tile === "sound") { pickSound(cam.id); }
      else if (button.dataset.tile === "swap") { swapOut(cam.id); }
      else if (button.dataset.tile === "remove") {
        window.UI.confirm({ title: "Remove " + cam.camera_id + " from this incident?", body: "The recording stays in the case; only its place here goes.", ok: "Remove" }).then(function (yes) { if (yes) { post({ action: "remove", camera: cam.id }); } });
      }
    });
    tile.addEventListener("dragstart", function (event) {
      if (event.target.closest("button, input, select, details, label, .inc-sync")) { event.preventDefault(); return; }
      draggedTile = cam.id;
      event.dataTransfer.effectAllowed = "move";
      try { event.dataTransfer.setData("text/plain", cam.id); } catch (ignored) { /* an older browser */ }
    });
    tile.addEventListener("dragover", function (event) { if (draggedTile && draggedTile !== cam.id) { event.preventDefault(); tile.classList.add("over"); } });
    tile.addEventListener("dragleave", function () { tile.classList.remove("over"); });
    tile.addEventListener("drop", function (event) {
      event.preventDefault();
      tile.classList.remove("over");
      if (!draggedTile || draggedTile === cam.id) { return; }
      var order = wallCameras().map(function (one) { return one.id; });
      var from = order.indexOf(draggedTile), to = order.indexOf(cam.id);
      if (from < 0 || to < 0) { return; }
      order.splice(from, 1);
      order.splice(to, 0, draggedTile);
      draggedTile = null;
      post({ action: "wall", cameras: order.join(",") });
    });
    tile.addEventListener("dragend", function () { draggedTile = null; });
    var video = tile.querySelector("video");
    if (video) {
      // The picture is where a person takes hold of the tile to drag it, so
      // the video must not start a drag of its own.
      video.setAttribute("draggable", "false");
      video.src = cam.media_url;
      video.addEventListener("error", function () { trouble.textContent = "One of the cameras could not be played: " + cam.camera_id + "."; trouble.hidden = false; });
    }
    tile.querySelector(".inc-well").addEventListener("click", function (event) {
      if (event.target.closest("label")) { return; }
      // A filmstrip tile's picture brings that camera to the front (chapter 4).
      if (tile.classList.contains("film")) { setFocus(cam.id); return; }
      if (playing) { pause(); } else { play(); }
    });
    Array.prototype.forEach.call(tile.querySelectorAll(".add-line"), function (button) {
      button.addEventListener("click", function () {
        var entry = players[cam.id];
        var got = lines[cam.id];
        if (!entry || !got) { return; }
        var local = now() - cam.starts_at;
        var found = button.dataset.kind === "words" ? lineAt(got.segments, local) : lineAt(got.moments, local);
        if (!found) { return; }
        openEventBox({
          at: cam.starts_at + found.start,
          text: found.text,
          source: button.dataset.kind,
          camera: cam.id,
          cameras: [cam.id]
        });
      });
    });
    return tile;
  }

  function drawWall() {
    var wanted = wallCameras();
    var keep = {};
    wanted.forEach(function (cam) { keep[cam.id] = true; });
    Object.keys(players).forEach(function (id) {
      if (!keep[id]) {
        if (players[id].video) { players[id].video.pause(); players[id].video.removeAttribute("src"); players[id].video.load(); }
        players[id].tile.remove();
        delete players[id];
      }
    });
    wanted.forEach(function (cam) {
      if (!players[cam.id]) {
        var tile = tileFor(cam);
        players[cam.id] = { cam: cam, video: tile.querySelector("video"), tile: tile };
        wallBox.appendChild(tile);
        loadLines(cam.id);
      } else {
        players[cam.id].cam = cam;
        var pill = players[cam.id].tile.querySelector(".pill");
        pill.className = "pill " + cam.placed_tone + " small";
        pill.textContent = shortPill(cam);
        pill.title = cam.placed_words;
      }
    });
    // The layout (chapter 4): in Focus one camera is large and the rest sit
    // in the filmstrip under it; otherwise every camera is on the wall.
    var focusId = null;
    if (layout === "focus" && wanted.length) {
      focusId = wanted.some(function (one) { return one.id === focusCamera; }) ? focusCamera : wanted[0].id;
      focusCamera = focusId;
    }
    wanted.forEach(function (cam) {
      var tile = players[cam.id].tile;
      var film = focusId !== null && cam.id !== focusId;
      tile.classList.toggle("film", film);
      (film ? filmBox : wallBox).appendChild(tile);
    });
    layWall(wanted.length);
    if (!wanted.length) {
      wallBox.innerHTML = "<p class='muted' style='padding: 20px'>No camera is placed yet. Place one on the Cameras tab, and it plays here.</p>";
    }
    drawFilmParked(focusId !== null);
    placeWork();
  }

  // The wall's columns by the layout: one in Focus, by the count Side by
  // side, the chosen count in a Grid.
  function layWall(count) {
    var columns;
    if (layout === "focus") { columns = 1; }
    else if (layout === "side") { columns = count <= 4 ? 2 : 3; }
    else { columns = parseInt(layout.slice(4), 10) || 3; }
    wallBox.className = "inc-wall";
    wallBox.style.gridTemplateColumns = "repeat(" + Math.min(columns, Math.max(1, count)) + ", minmax(0, 1fr))";
  }

  // The parked cameras (beyond the wall's size) in the filmstrip, in Focus:
  // the id and the pill, no picture; a press swaps one in and brings it to
  // the front. In the other layouts they are lanes in the strip alone.
  function drawFilmParked(inFocus) {
    Array.prototype.forEach.call(filmBox.querySelectorAll(".parked"), function (one) { one.remove(); });
    filmBox.hidden = !inFocus;
    if (!inFocus) { return; }
    parkedCameras().forEach(function (cam) {
      var tile = document.createElement("div");
      tile.className = "inc-tile film parked";
      tile.style.setProperty("--speaker", cam.colour);
      tile.title = "Swap " + cam.camera_id + " in and bring it to the front";
      tile.innerHTML = "<div class='inc-tile-head'><span class='dot'></span><b>" + escape(cam.camera_id) + "</b>" +
        "<span class='pill " + escape(cam.placed_tone) + " small' title='" + quoted(cam.placed_words) + "'>" + escape(shortPill(cam)) + "</span></div>" +
        "<div class='inc-well'><p class='preparing small'>Swap in</p></div>";
      tile.addEventListener("click", function () { swapIn(cam.id, true); });
      filmBox.appendChild(tile);
    });
  }

  // Where the work panel sits: beside the cameras, or under the strip in a Grid.
  function placeWork() {
    deskBox.dataset.layout = layout;
    var below = layout.indexOf("grid") === 0;
    workBox.classList.toggle("below", below);
    if (below) { if (strip.nextElementSibling !== workBox) { strip.after(workBox); } }
    else if (workBox.parentNode !== deskBox) { deskBox.appendChild(workBox); }
  }

  // The Layout menu: the person's choice, kept in the browser; the office's
  // setting until they choose.
  var layoutBox = document.getElementById("layout");
  (function () {
    var kept = "";
    try { kept = window.localStorage.getItem("incident-layout") || ""; } catch (ignored) { /* this page only */ }
    layout = LAYOUTS.indexOf(kept) !== -1 ? kept : (LAYOUTS.indexOf(S.incident.layout) !== -1 ? S.incident.layout : "focus");
    if (layoutBox) {
      layoutBox.value = layout;
      layoutBox.addEventListener("change", function () {
        layout = LAYOUTS.indexOf(layoutBox.value) !== -1 ? layoutBox.value : "focus";
        try { window.localStorage.setItem("incident-layout", layout); } catch (ignored) { /* this page only */ }
        drawWall();
        if (!soundPinned && layout === "focus" && focusCamera) { setSound(focusCamera); } else { sayWhoIsHeard(); }
        drawStrip();
      });
    }
    window.addEventListener("resize", function () { layWall(wallCameras().length); });
  })();

  function swapOut(id) {
    var order = wallCameras().map(function (one) { return one.id; }).filter(function (one) { return one !== id; });
    var next = parkedCameras()[0];
    if (next) { order.push(next.id); }
    if (soundCamera === id) { soundCamera = null; }
    if (focusCamera === id) { focusCamera = null; }
    post({ action: "wall", cameras: order.join(",") });
  }

  function swapIn(id, toFront) {
    if (toFront) { focusCamera = id; if (!soundPinned) { soundCamera = id; } }
    var order = wallCameras().map(function (one) { return one.id; });
    if (order.length >= S.incident.wall_size) {
      var out = order[order.length - 1];
      if (soundCamera === out) { soundCamera = null; }
      order.pop();
    }
    order.push(id);
    post({ action: "wall", cameras: order.join(",") });
  }

  // The lines under a tile: the words being said, and what the camera showed.
  function loadLines(id) {
    fetch(C.lines + id + "/lines").then(function (answer) { return answer.json(); })
      .then(function (body) { lines[id] = body; })
      .catch(function () { lines[id] = { segments: [], moments: [] }; });
  }

  function lineAt(list, at) {
    for (var i = 0; i < list.length; i += 1) {
      if (list[i].start <= at && at < list[i].end) { return list[i]; }
    }
    return null;
  }

  function sayLines(entry, local) {
    var box = entry.tile.querySelector(".inc-lines");
    var got = lines[entry.cam.id];
    if (!got) { return; }
    var said = lineAt(got.segments, local);
    var who = box.querySelector(".who"), txt = box.querySelector(".txt");
    var addSaid = box.querySelector(".said .add-line");
    if (said) {
      who.textContent = said.speaker ? said.speaker + ":" : "";
      who.style.color = said.colour || "";
      txt.textContent = said.text;
      txt.classList.remove("muted");
      addSaid.hidden = false;
    } else {
      who.textContent = "";
      txt.textContent = local < 0 || local > entry.cam.length ? "" : "…";
      txt.classList.add("muted");
      addSaid.hidden = true;
    }
  }

  // Keeping in step ---------------------------------------------------------------------

  function follow(entry, m) {
    var cam = entry.cam, video = entry.video;
    var local = m - cam.starts_at;
    var state = entry.tile.querySelector(".state");
    if (!video) { return; }
    if (local < 0) {
      state.hidden = false;
      state.textContent = "Starts in " + elapsed(-local);
      if (!video.paused) { video.pause(); }
      if (video.currentTime > 0.05) { video.currentTime = 0; }
      return;
    }
    if (local > cam.length) {
      state.hidden = false;
      state.textContent = "Ended at " + timeOfDay(cam.starts_at + cam.length);
      if (!video.paused) { video.pause(); }
      return;
    }
    state.hidden = true;
    var drift = video.currentTime - local;
    if (playing) {
      if (video.paused && video.readyState >= 2) {
        video.currentTime = local;
        var started = video.play();
        if (started && started.catch) { started.catch(function () { /* the browser asks for a gesture; the next press gives one */ }); }
        return;
      }
      if (Math.abs(drift) > 0.5) {
        video.currentTime = local;
        video.playbackRate = speed;
      } else if (Math.abs(drift) > 0.08) {
        video.playbackRate = Math.max(0.5, Math.min(4, speed * (1 - Math.max(-0.1, Math.min(0.1, drift)))));
      } else {
        video.playbackRate = speed;
      }
    } else {
      if (!video.paused) { video.pause(); }
      if (Math.abs(drift) > 0.05) { video.currentTime = local; }
    }
  }

  function tick() {
    var m = now();
    var high = span()[1];
    if (playing && m >= high) { m = high; pause(); }
    clockBig.textContent = timeOfDay(m);
    var low = span()[0];
    clockSmall.textContent = elapsed(m - low) + " / " + elapsed(high - low);
    Object.keys(players).forEach(function (id) {
      var entry = players[id];
      follow(entry, m);
      if (followBox.checked) { sayLines(entry, m - entry.cam.starts_at); }
    });
    movePlayheads(m);
    markCurrentEvent(m);
  }

  window.setInterval(tick, 200);

  function play() {
    anchorMoment = now();
    anchorNow = performance.now();
    playing = true;
    playButton.innerHTML = "<svg class='i' aria-hidden='true'><use href='#i-pause'></use></svg> Pause";
    tick();
  }

  function pause() {
    moment = now();
    playing = false;
    playButton.innerHTML = "<svg class='i' aria-hidden='true'><use href='#i-play'></use></svg> Play";
    Object.keys(players).forEach(function (id) { if (players[id].video && !players[id].video.paused) { players[id].video.pause(); } });
  }

  function seek(at) {
    var range = span();
    at = Math.max(range[0], Math.min(range[1], at));
    if (playing) { anchorMoment = at; anchorNow = performance.now(); } else { moment = at; }
    tick();
  }

  function setSound(id) {
    soundCamera = id;
    Object.keys(players).forEach(function (one) {
      var entry = players[one];
      if (entry.video) { entry.video.muted = one !== id; }
      entry.tile.classList.toggle("sound", one === id);
      var speaker = entry.tile.querySelector(".snd use");
      if (speaker) { speaker.setAttribute("href", one === id ? "#i-sound" : "#i-muted"); }
    });
    sayWhoIsHeard();
  }

  // The speaker on a tile (chapter 4): takes the sound and pins it there; on
  // the focus camera a second press lets the sound follow the focus again.
  function pickSound(id) {
    if (layout === "focus" && soundPinned && soundCamera === id && id === focusCamera) {
      soundPinned = false;
      setSound(focusCamera);
      return;
    }
    soundPinned = true;
    setSound(id);
  }

  function setFocus(id) {
    focusCamera = id;
    drawWall();
    if (!soundPinned) { setSound(id); }
  }

  function sayWhoIsHeard() {
    var cam = cameraById(soundCamera);
    soundSaid.textContent = cam ? "Sound: " + cam.camera_id + (layout === "focus" && !soundPinned ? " (follows the focus)" : "") : "";
  }

  function drawSoundChoice() {
    if (soundCamera) { setSound(soundCamera); } else { sayWhoIsHeard(); }
  }

  playButton.addEventListener("click", function () { if (playing) { pause(); } else { play(); } });
  Array.prototype.forEach.call(document.querySelectorAll("[data-seek]"), function (button) {
    button.addEventListener("click", function () {
      seek(now() + parseFloat(button.dataset.seek));
      if (button.dataset.seek === "-3" && !playing) { play(); }
    });
  });
  speedBox.addEventListener("change", function () {
    if (playing) { anchorMoment = now(); anchorNow = performance.now(); }
    speed = parseFloat(speedBox.value) || 1;
  });

  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) { return; }
    if (event.key === "Escape" && layerStack.length) { closeLayer(); return; }
    if (event.target.closest("input, textarea, select")) { return; }
    if (event.key === " ") { event.preventDefault(); if (playing) { pause(); } else { play(); } }
    else if (event.key === "ArrowLeft") { event.preventDefault(); seek(now() - 5); }
    else if (event.key === "ArrowRight") { event.preventDefault(); seek(now() + 5); }
    else if (event.key === "b" || event.key === "B") { seek(now() - 3); if (!playing) { play(); } }
    else if (event.key === "e" || event.key === "E") { event.preventDefault(); openEventBox({ at: now() }); }
  });

  // The strip ---------------------------------------------------------------------------

  function view() {
    var range = span();
    if (!zoom || zoom >= range[1] - range[0]) { return range; }
    var from = panFrom !== null ? panFrom : now() - zoom / 2;
    from = Math.max(range[0], Math.min(from, range[1] - zoom));
    return [from, from + zoom];
  }

  // Along a zoomed strip: the wheel over the lanes or the arrows by the zoom
  // buttons move the window; a seek inside it keeps it, and the playhead
  // leaving it while playing lets the window follow the playhead again.
  function pan(direction) {
    if (!zoom) { return; }
    panFrom = view()[0] + direction * zoom * 0.25;
    drawStrip();
  }

  function percent(at, shown) {
    return Math.max(0, Math.min(100, ((at - shown[0]) / (shown[1] - shown[0])) * 100)) + "%";
  }

  function shortLabel(text) {
    return text.length <= 26 ? text : text.slice(0, 24) + "…";
  }

  // The Events lane's labels: every Event has a mark; a label is drawn only
  // when it would not run into the one before it at this zoom.
  function eventMarks(shown) {
    var width = lanesBox.clientWidth ? lanesBox.clientWidth - 108 : 900;
    var html = "";
    var lastRight = -1;
    S.events.slice().sort(function (a, b) { return a.at - b.at; }).forEach(function (one) {
      if (one.at < shown[0] || one.at > shown[1]) { return; }
      var left = ((one.at - shown[0]) / (shown[1] - shown[0])) * width;
      var cls = one.proposed ? " proposed" : "";
      var wide = one.until && one.until > one.at ? ((Math.min(one.until, shown[1]) - one.at) / (shown[1] - shown[0])) * 100 : 0;
      html += "<span class='mk-ev" + cls + "' data-event='" + one.id + "' style='left: " + percent(one.at, shown) + (wide ? "; width: " + wide + "%" : "") + "' title='" + quoted(timeOfDay(one.at) + " " + one.text) + "'></span>";
      var label = shortLabel(one.text);
      var needs = label.length * 6.5 + 12;
      if (left >= lastRight) {
        html += "<span class='lbl" + cls + "' data-event='" + one.id + "' style='left: " + percent(one.at, shown) + "' title='" + quoted(timeOfDay(one.at) + " " + one.text) + "'>" + escape(label) + "</span>";
        lastRight = left + needs;
      }
    });
    return html;
  }

  function drawStrip() {
    var shown = view();
    var ticks = "";
    var count = 6;
    for (var i = 0; i <= count; i += 1) {
      ticks += "<span>" + timeOfDay(shown[0] + ((shown[1] - shown[0]) * i) / count) + "</span>";
    }
    ticksBox.innerHTML = ticks;
    // The band lives in the ticks and must outlive their redraw.
    if (band) { ticksBox.appendChild(band); }
    var html = "";
    S.cameras.forEach(function (cam) {
      var placed = cam.starts_at !== null && cam.placed;
      var start = placed ? cam.starts_at : (S.incident.span_low || 0);
      // Only the part of the bar inside the window is drawn (v1.63.2): a bar
      // wider than the track ran past its edge when zoomed in, and the marks
      // and playhead were left behind.
      var barFrom = Math.max(start, shown[0]);
      var barTo = Math.min(start + cam.length, shown[1]);
      var width = barTo > barFrom ? ((barTo - barFrom) / (shown[1] - shown[0])) * 100 : 0;
      html += "<div class='lane" + (placed ? "" : " unplaced") + "' data-camera='" + cam.id + "' style='--speaker: " + cam.colour + "'>" +
        "<div class='head' title='" + quoted(cam.title + ", " + cam.placed_words) + "'><span class='dot'></span><span class='name'>" + escape(cam.camera_id) + "</span>" +
        (placed && !cam.on_wall ? "<button type='button' class='tiny swap' data-swap='" + cam.id + "' title='Onto the wall, and to the front'>Swap in</button>" : "") + "</div>" +
        "<div class='track'><i class='" + (cam.on_wall ? "" : "thin") + (placed ? "" : " ghost") + "' draggable='false' style='left: " + percent(barFrom, shown) + "; width: " + (width ? Math.max(0.3, width) : 0) + "%" + (width ? "" : "; display: none") + "' title='" + timeOfDay(start) + " to " + timeOfDay(start + cam.length) + "'></i>" +
        "<span class='playhead'></span></div></div>";
    });
    html += "<div class='lane events'><div class='head'><span class='name muted'>Events</span></div><div class='track'>" + eventMarks(shown) + "<span class='playhead'></span></div></div>";
    lanesBox.innerHTML = html;
    Array.prototype.forEach.call(strip.querySelectorAll("[data-pan]"), function (one) { one.disabled = !zoom || zoom >= span()[1] - span()[0]; });
    movePlayheads(now());
  }

  function movePlayheads(m) {
    var shown = view();
    if (zoom && (m < shown[0] || m > shown[1])) {
      // The window was moved away and the cameras stand still: the playhead
      // is off the strip, not drawn at its edge. Playing, the window follows.
      if (panFrom !== null && !playing) { lanesBox.classList.add("away"); return; }
      panFrom = null;
      drawStrip();
      return;
    }
    lanesBox.classList.remove("away");
    var left = percent(m, shown);
    Array.prototype.forEach.call(lanesBox.querySelectorAll(".playhead"), function (head) { head.style.left = left; });
  }

  strip.addEventListener("click", function (event) {
    var zoomButton = event.target.closest("[data-zoom]");
    var panButton = event.target.closest("[data-pan]");
    if (panButton) { pan(parseInt(panButton.dataset.pan, 10) || 0); return; }
    if (zoomButton) {
      zoom = parseInt(zoomButton.dataset.zoom, 10) || 0;
      panFrom = null;
      Array.prototype.forEach.call(strip.querySelectorAll("[data-zoom]"), function (one) { one.classList.toggle("on", one === zoomButton); });
      drawStrip();
      return;
    }
    if (dragging && dragging.moved) { return; }
    var swap = event.target.closest("[data-swap]");
    if (swap) { swapIn(swap.dataset.swap, true); return; }
    var mark = event.target.closest("[data-event]");
    if (mark) {
      var found = eventById(mark.dataset.event);
      if (found) { seek(found.at); }
      return;
    }
    var track = event.target.closest(".track");
    if (!track) { return; }
    var shown = view();
    var box = track.getBoundingClientRect();
    var at = shown[0] + ((event.clientX - box.left) / box.width) * (shown[1] - shown[0]);
    var lane = track.closest(".lane");
    if (lane && lane.dataset.camera) {
      var cam = cameraById(lane.dataset.camera);
      if (cam && cam.starts_at !== null && cam.placed && !cam.on_wall) { swapIn(cam.id, true); }
    }
    seek(at);
  });

  // Drag a bar to place the camera by hand.
  lanesBox.addEventListener("wheel", function (event) {
    if (!zoom) { return; }
    var delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
    if (!delta) { return; }
    event.preventDefault();
    pan(delta > 0 ? 1 : -1);
  }, { passive: false });

  lanesBox.addEventListener("mousedown", function (event) {
    var bar = event.target.closest(".track i");
    if (!bar) { return; }
    var lane = bar.closest(".lane");
    var cam = cameraById(lane.dataset.camera);
    if (!cam) { return; }
    var shown = view();
    var track = bar.parentNode.getBoundingClientRect();
    dragging = {
      cam: cam, bar: bar, moved: false, startX: event.clientX,
      perPixel: (shown[1] - shown[0]) / track.width,
      from: cam.starts_at !== null && cam.placed ? cam.starts_at : (S.incident.span_low || 0),
      at: null
    };
    event.preventDefault();
  });

  document.addEventListener("mousemove", function (event) {
    if (!dragging) { return; }
    var moved = (event.clientX - dragging.startX) * dragging.perPixel;
    if (Math.abs(event.clientX - dragging.startX) > 3) { dragging.moved = true; }
    dragging.at = dragging.from + moved;
    dragging.bar.style.left = percent(dragging.at, view());
    dragging.bar.title = timeOfDay(dragging.at) + " (" + (moved >= 0 ? "+" : "") + moved.toFixed(1) + " s)";
  });

  document.addEventListener("mouseup", function () {
    if (!dragging) { return; }
    var done = dragging;
    window.setTimeout(function () { dragging = null; }, 0);
    if (!done.moved || done.at === null) { return; }
    var moved = done.at - done.from;
    window.UI.confirm({
      title: "Place " + done.cam.camera_id + " by hand?",
      body: "Moved " + (moved >= 0 ? "+" : "") + moved.toFixed(1) + " s, to start at " + timeOfDay(done.at) + ". From then on it reads Synced by hand.",
      ok: "Place it"
    }).then(function (yes) {
      if (yes) { post({ action: "place", camera: done.cam.id, how: "hand", starts_at: done.at.toFixed(2) }); }
      else { drawStrip(); }
    });
  });

  // The Chronology (chapter 2) ----------------------------------------------------------

  function currentEvent(m) {
    var best = null;
    S.events.forEach(function (one) {
      if (one.proposed || one.at > m + 0.5) { return; }
      if (!best || one.at > best.at) { best = one; }
    });
    return best;
  }

  function markCurrentEvent(m) {
    var here = currentEvent(m);
    var id = here ? here.id : null;
    if (id === currentEventId) { return; }
    currentEventId = id;
    var panel = document.getElementById("panel-chronology");
    Array.prototype.forEach.call(panel.querySelectorAll("tr[data-event]"), function (row) {
      var on = row.dataset.event === id;
      row.classList.toggle("here", on);
      if (on && followBox.checked && !panel.hidden) { row.scrollIntoView({ block: "nearest" }); }
    });
  }

  function drawChronology() {
    var box = document.getElementById("panel-chronology");
    var kept = keptEvents();
    var proposed = S.events.filter(function (one) { return one.proposed; });
    var P = S.proposals || {};
    var M = S.memo || {};
    var toCheck = kept.filter(function (one) { return one.to_check; }).length;
    var lead = kept.length ? kept.length + " event" + (kept.length === 1 ? "" : "s") + " on the chronology" + (toCheck ? ", " + toCheck + " to check" : "") + "." : "No events yet. Add one at the moment you are watching, or from a line under a camera.";
    if (M.state === "done" && kept.length) { lead += " The memo was written on " + M.events_count + " of them."; }
    var html = "<div class='row' style='gap: 8px; align-items: center; margin-bottom: 8px'>" +
      "<p class='lead grow' style='margin: 0'>" + escape(lead) + "</p>" +
      "<button type='button' class='small primary' id='add-event-here'>+ Event here</button>" +
      (P.on ? "<button type='button' class='small' id='open-proposals' title='The assistant reads each synced camera in stretches and proposes the moments that matter; nothing joins the chronology until you accept it'>Propose events" +
        (proposed.length ? " <span class='pill warn small'>" + proposed.length + " waiting</span>" : "") + "</button>" : "") + "</div>";
    // About this chronology (Phase 7 chapter 1): the office's paragraph
    // before the events, edited in place.
    var about = S.incident.about || "";
    html += "<div class='inc-about' id='about-line'><span class='small'><b>About this chronology:</b> " +
      (about ? escape(about.length > 160 ? about.slice(0, 158) + "\u2026" : about) : "<span class='muted'>none yet. What a reader should know before the events.</span>") +
      "</span> <button type='button' class='tiny ghost' id='about-edit'>" + (about ? "Edit" : "Write it") + "</button></div>" +
      "<form class='inc-about-box' id='about-box' hidden><textarea name='about' rows='4' maxlength='2000' aria-label='About this chronology'>" + escape(about) + "</textarea>" +
      "<div class='row' style='gap: 6px; margin-top: 6px'><button type='submit' class='small primary'>Save</button><button type='button' class='small ghost' id='about-cancel'>Cancel</button>" +
      "<span class='muted small'>Printed on the export's cover and told to the memo as the office's own words.</span></div></form>";
    if (kept.length) {
      html += "<table class='inc-events'><tbody>";
      kept.forEach(function (one) {
        // One line for what happened, one muted line for everything about it
        // (Phase 8 chapter 1); the controls behind the row's menu.
        var meta = [];
        meta.push(escape(one.source_words));
        if (one.seen_on) { meta.push("seen on " + escape(one.seen_on)); }
        if (one.note) { meta.push("<i>note: " + escape(one.note) + "</i>" + (one.note_by ? " (" + escape(one.note_by) + ")" : "")); }
        if (one.why) { meta.push("<i>" + escape(one.why) + "</i>"); }
        if (one.clips) { meta.push("<a class='clipmark' href='" + S.incident.clips_url + "' title='Open the case&#39;s Clips tab, where the clip is'>" + escape(one.clips_words) + "</a>"); }
        html += "<tr data-event='" + one.id + "'><td class='t'><a class='cite' href='#' data-at='" + one.at + "'>" + timeOfDay(one.at) + "</a>" +
          (one.until ? "<div class='muted small'>to " + timeOfDay(one.until) + "</div>" : "") + "</td>" +
          "<td><div class='what'>" + escape(one.text) +
          (one.to_check ? " <span class='pill warn small' title='The office has not settled this'>To check</span>" : "") + "</div>" +
          "<div class='meta muted small'>" + meta.join(" &middot; ") + "</div></td>" +
          "<td class='acts nowrap'><details class='row-menu'><summary class='tiny ghost' title='Edit, note, clip, remove'>&middot;&middot;&middot;</summary><div class='menu'>" +
          "<button type='button' data-edit='" + one.id + "'>Edit</button>" +
          "<button type='button' data-note='" + one.id + "'>" + (one.note ? "Edit the note" : "Add a note") + "</button>" +
          (mayClip(one) ? "<button type='button' data-clip='" + one.id + "'>Clip this event</button>" : (S.incident.clips ? "<button type='button' disabled title='Sync a camera first'>Clip this event</button>" : "")) +
          "<button type='button' class='danger' data-remove='" + one.id + "'>Remove</button></div></details></td></tr>";
      });
      html += "</tbody></table>";
    }
    html += "<p class='muted small' style='margin: 10px 0 0'>A time on this list plays every camera from there. E adds an event at the moment being watched.</p>";
    box.innerHTML = html;
    currentEventId = null;
    markCurrentEvent(now());
  }


  // The Proposed events layer (Phase 8 chapter 1): Propose again, the Look
  // for box, the state line, and the proposals with Accept and Dismiss.
  function drawProposals() {
    var box = document.getElementById("proposals-box");
    var acts = document.getElementById("proposals-head-acts");
    if (!box) { return; }
    var proposed = S.events.filter(function (one) { return one.proposed; });
    var P = S.proposals || {};
    var title = document.getElementById("proposals-title");
    if (title) { title.textContent = "Proposed events" + (proposed.length ? " (" + proposed.length + ")" : ""); }
    var html = "";
    if (P.on) {
      html += "<div class='row inc-propose' style='gap: 8px; align-items: center; margin-bottom: 8px'>" +
        "<button type='button' class='small' id='propose-events'" + (P.possible && !P.busy ? "" : " disabled") + " title='The assistant reads each synced camera in stretches, proposes the moments that matter and says why; the watch phrases are searched first. Nothing joins the chronology until you accept it'>Propose again</button>" +
        "<input type='text' id='look-for' class='small' maxlength='300' placeholder='Look for, this run only' aria-label='Look for, this run only' title='Something to look for on this run alone: anything about the gun and the ring camera'" + (P.possible && !P.busy ? "" : " disabled") + ">" +
        "<span class='small muted' id='propose-said'>" + escape(P.words || (P.possible ? "" : "Sync a camera that has a transcript first.")) + "</span></div>";
    }

    if (!proposed.length) {
      html += "<p class='muted'>Nothing waiting. Propose events reads each synced camera and proposes what it finds; nothing joins the chronology until you accept it.</p>";
    }
    if (proposed.length) {
      html += "<p class='muted small'>Nothing joins the chronology until you accept it. A time plays every camera from there.</p>";
      html += "<table class='inc-events'><tbody>";
      // While the run is going the proposals are still arriving, and one
      // accepted now is proposed again by the cameras read after it (v1.63.2).
      var held = P.busy ? " disabled title='" + STILL_PROPOSING + "'" : "";
      proposed.forEach(function (one) {
        html += "<tr data-event='" + one.id + "' class='proposed'><td class='t'><a class='cite' href='#' data-at='" + one.at + "'>" + timeOfDay(one.at) + "</a>" +
          (one.until ? "<div class='muted small'>to " + timeOfDay(one.until) + "</div>" : "") + "</td>" +
          "<td title='" + quoted(one.rests_on ? "Rests on: " + one.rests_on : "") + "'>" + escape(one.text) +
          (one.why ? "<div class='small why'>" + escape(one.why) + "</div>" : "") +
          (one.rests_on ? "<div class='muted small rests'>Rests on: " + escape(one.rests_on) + "</div>" : "") + "</td>" +
          "<td><span class='pill small " + (one.source === "watch" ? "watch" : "warn") + "'>" + escape(one.source_words) + "</span></td>" +
          "<td class='acts nowrap'><button type='button' class='tiny primary' data-accept='" + one.id + "'" + held + ">Accept</button> <button type='button' class='tiny ghost' data-dismiss='" + one.id + "'" + held + ">Dismiss</button></td></tr>";
      });
      html += "</tbody></table>";
    }

    box.innerHTML = html;
    if (acts) {
      acts.innerHTML = proposed.length > 1 ? "<button type='button' class='small primary' id='accept-all'" + (P.busy ? " disabled title='" + STILL_PROPOSING + "'" : "") + ">Accept all</button>" : "";
    }
  }

  // The Memo tab (chapter 3): the memo with its times as citations and its
  // event marks, or the way to write one.
  function memoHtml(text, citations, numbers) {
    return text.split(/\n+/).filter(function (line) { return line.trim(); }).map(function (line) {
      var stripped = line.replace(/^[#* ]+/, "").trim();
      if (/:$/.test(stripped) && stripped.length <= 60) { return "<h3>" + escape(stripped.slice(0, -1)) + "</h3>"; }
      var body = escape(stripped).replace(/\[(\d{1,2}):(\d{2}):(\d{2})\]/g, function (whole) {
        if (citations && Object.prototype.hasOwnProperty.call(citations, whole)) {
          return "<a href='#' class='cite' data-at='" + citations[whole] + "' title='Every camera at this moment'>" + whole + "</a>";
        }
        return whole;
      }).replace(/\(Event (\d+)\)/g, function (whole, n) {
        var id = numbers && numbers[n];
        if (!id) { return whole; }
        return "<a href='#' class='evmark' data-event='" + id + "' title='Event " + n + " on the chronology'>Event " + n + "</a>";
      });
      return "<p>" + body + "</p>";
    }).join("");
  }

  function drawMemo() {
    var box = document.getElementById("panel-memo");
    var exportMemo = document.getElementById("export-memo");
    if (!box) { return; }
    var M = S.memo || {};
    var html = "";
    if (exportMemo) { exportMemo.hidden = M.state !== "done"; }
    if (!M.state) {
      html = "<p class='lead'>" + escape(M.before || "") + "</p>" +
        (M.possible ? "<button type='button' class='small primary' id='memo-write'>Write the memo</button>" : "<p class='muted small'>" + escape(M.why_not || "") + "</p>") +
        "<p class='muted small' style='margin-top: 10px'>The memo is written by the assistant across every synced camera, on the chronology's events. Every time in it plays every camera from there.</p>";
    } else if (M.busy) {
      html = "<p class='lead'>" + escape(M.stage || "Waiting for the engine") + "...</p>" +
        "<p class='muted small'>The memo is being written; it will show here when it lands.</p>" +
        "<button type='button' class='small ghost' id='memo-cancel'>Cancel</button>";
    } else if (M.state === "failed") {
      html = "<p class='problem'>" + escape(M.reason_words || "The memo could not be written.") + "</p>" +
        "<button type='button' class='small primary' id='memo-write'>Try again</button>";
    } else {
      html = (M.notice ? "<p class='notice small' style='margin: 0 0 8px'>" + escape(M.notice) + "</p>" : "") +
        "<div class='row' style='align-items: center; gap: 8px; margin: 0 0 6px'><b class='grow'>Incident memo</b>" +
        "<button type='button' class='small' id='memo-export'>Memo to Word</button>" +
        "<button type='button' class='small ghost' id='memo-write'>Regenerate</button></div>" +
        "<p class='muted small' style='margin: 0 0 8px'>" + escape(M.written_words || "") + "</p>" +
        (M.stale_words ? "<p class='notice warn small' style='margin: 0 0 10px'>" + escape(M.stale_words) + "</p>" : "") +
        "<div class='inc-memo'>" + memoHtml(M.text || "", M.citations, M.event_numbers) + "</div>" +
        (M.cut_short ? "<p class='muted small'>The memo was cut short.</p>" : "");
    }
    box.innerHTML = html;
  }

  var memoPanel = document.getElementById("panel-memo");
  if (memoPanel) {
    memoPanel.addEventListener("click", function (event) {
      var cite = event.target.closest(".cite");
      if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.at)); return; }
      var mark = event.target.closest(".evmark");
      if (mark) {
        event.preventDefault();
        var found = eventById(mark.dataset.event);
        if (found) { seek(found.at); showTab("chronology"); flashRow(found.id); }
        return;
      }
      if (event.target.closest("#memo-write")) {
        var again = (S.memo || {}).state === "done";
        (again ? window.UI.confirm({ title: "Write the memo again?", body: "The memo you have is replaced. Export it first if you want to keep it.", ok: "Regenerate" }) : Promise.resolve(true))
          .then(function (yes) { if (yes) { post({ action: "memo" }); } });
        return;
      }
      if (event.target.closest("#memo-cancel")) { post({ action: "memo_cancel" }); return; }
      if (event.target.closest("#memo-export")) { drawPicture().then(function (blob) { return exportWith(C.exportMemo, blob); }); }
    });
  }
  var exportMemoButton = document.getElementById("export-memo");
  if (exportMemoButton) {
    exportMemoButton.addEventListener("click", function () {
      document.getElementById("export-menu").removeAttribute("open");
      drawPicture().then(function (blob) { return exportWith(C.exportMemo, blob); });
    });
  }

  function chronologyClick(event) {
    if (event.target.closest("#open-proposals")) { openLayer("proposals"); return; }
    var note = event.target.closest("[data-note]");
    if (note) {
      var noted = eventById(note.dataset.note);
      if (noted) {
        openEventBox(noted);
        var opener = document.getElementById("event-note-open");
        if (opener && eventBox.elements.note.hidden) { opener.click(); }
        eventBox.elements.note.focus();
      }
      return;
    }
    var remove = event.target.closest("[data-remove]");
    if (remove) {
      var gone = eventById(remove.dataset.remove);
      if (!gone) { return; }
      window.UI.confirm({ title: "Remove this event?", body: "Its note and its clips' marks go with it; a clip already made stays on the Clips tab.", ok: "Remove", danger: true })
        .then(function (yes) { if (yes) { post({ action: "event_remove", event: gone.id }); } });
      return;
    }
    chronologyActions(event);
  }
  document.getElementById("panel-chronology").addEventListener("click", chronologyClick);
  document.getElementById("layer-proposals").addEventListener("click", chronologyClick);
  function chronologyActions(event) {
    var cite = event.target.closest(".cite");
    if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.at)); return; }
    var edit = event.target.closest("[data-edit]");
    if (edit) { var found = eventById(edit.dataset.edit); if (found) { openEventBox(found); } return; }
    var clip = event.target.closest("[data-clip]");
    if (clip) { var clipped = eventById(clip.dataset.clip); if (clipped) { openClipBox(clipped); } return; }
    if (event.target.closest("#add-event-here")) { openEventBox({ at: now() }); return; }
    // About this chronology (Phase 7 chapter 1).
    if (event.target.closest("#about-edit")) {
      document.getElementById("about-line").hidden = true;
      var box = document.getElementById("about-box");
      box.hidden = false;
      box.elements.about.focus();
      return;
    }
    if (event.target.closest("#about-cancel")) { drawChronology(); return; }
    // The assistant's proposals (chapter 3).
    var accept = event.target.closest("[data-accept]");
    if (accept) { post({ action: "event_accept", event: accept.dataset.accept }); return; }
    var dismiss = event.target.closest("[data-dismiss]");
    if (dismiss) { post({ action: "event_dismiss", event: dismiss.dataset.dismiss }); return; }
    if (event.target.closest("#accept-all")) { post({ action: "event_accept_all" }); return; }
    if (event.target.closest("#propose-events")) {
      var button = event.target.closest("#propose-events");
      button.disabled = true;
      document.getElementById("propose-said").textContent = "Reading the cameras...";
      var lookFor = document.getElementById("look-for");
      post({ action: "propose", look_for: lookFor ? lookFor.value : "" });
    }
  }

  document.getElementById("panel-chronology").addEventListener("submit", function (event) {
    var form = event.target.closest("#about-box");
    if (!form) { return; }
    event.preventDefault();
    post({ action: "about", about: form.elements.about.value });
  });

  document.getElementById("add-event").addEventListener("click", function () { openEventBox({ at: now() }); });

  // The event box: one form for a new Event and for Edit.
  function openEventBox(given) {
    var at = given.at !== undefined ? given.at : now();
    openLayer("event");
    eventBox.elements.event.value = given.id || "";
    // Clip this event, on Edit, while clips are on and a camera can be cut.
    document.getElementById("event-clip").hidden = !mayClip(given);
    eventBox.elements.source.value = given.source || "person";
    eventBox.elements.camera.value = given.camera || "";
    eventBox.elements.when.value = timeOfDay(at);
    eventBox.elements.until_when.value = given.until ? timeOfDay(given.until) : "";
    eventBox.elements.text.value = given.text || "";
    eventBox.elements.note.value = given.note || "";
    eventBox.elements.to_check.checked = !!given.to_check;
    // The note folds closed until pressed, or open when the event has one.
    eventBox.elements.note.hidden = !given.note;
    document.getElementById("event-title").textContent = given.id ? "Edit event" : "New event";
    document.getElementById("event-save").textContent = given.id ? "Save" : "Add";
    document.getElementById("event-remove").hidden = !given.id;
    document.getElementById("event-said").textContent = given.source === "words" ? "Quoted from the words as they stand." : (given.source === "camera" ? "What the camera showed, as described." : "");
    var chosen = given.cameras || placedCameras().filter(function (cam) { return cam.starts_at <= at && at <= cam.starts_at + cam.length; }).map(function (cam) { return cam.id; });
    var cams = document.getElementById("event-cams");
    cams.innerHTML = placedCameras().map(function (cam) {
      return "<label class='small' style='--speaker: " + cam.colour + "'><input type='checkbox' name='cameras' value='" + cam.id + "'" + (chosen.indexOf(cam.id) !== -1 ? " checked" : "") + "> " + escape(cam.camera_id) + "</label>";
    }).join("");
    eventBox.elements.text.focus();
    if (!given.text) { eventBox.elements.text.select(); }
  }

  function closeEventBox() {
    if (layerStack.indexOf("event") !== -1) { while (layerStack.length && layerStack[layerStack.length - 1] !== "event") { closeLayer(); } closeLayer(); }
  }

  var syncBox = document.getElementById("sync-box");
  var panelsBox = document.querySelector(".inc-work .panels");
  function layerOf(name) { return document.getElementById("layer-" + name); }
  function currentTab() {
    var on = document.querySelector(".inc-work .tab.on");
    return on ? on.dataset.panel : "chronology";
  }
  function tabName(name) {
    var tab = document.querySelector(".inc-work .tab[data-panel='" + name + "']");
    return tab ? tab.textContent.trim() : "Chronology";
  }
  function openLayer(name) {
    var layer = layerOf(name);
    if (!layer) { return; }
    if (!layerStack.length) {
      layerReturn = { tab: currentTab(), scroll: panelsBox ? panelsBox.scrollTop : 0, row: currentEventId };
    }
    layerStack = layerStack.filter(function (one) { return one !== name; });
    layerStack.push(name);
    LAYERS.forEach(function (one) { var other = layerOf(one); if (other) { other.hidden = one !== name; } });
    var back = layer.querySelector(".back-tab");
    if (back) { back.textContent = layerStack.length > 1 ? layerName(layerStack[layerStack.length - 2]) : tabName(layerReturn.tab); }
    if (panelsBox) { panelsBox.hidden = true; }
    layer.scrollTop = 0;
  }
  function layerName(name) {
    return { event: "Event", clip: "Clip", sync: "Sync", proposals: "Proposed events", find: "Find" }[name] || name;
  }
  function closeLayer() {
    var name = layerStack.pop();
    var layer = name ? layerOf(name) : null;
    if (layer) { layer.hidden = true; }
    if (name === "event") { eventBox.reset(); }
    if (name === "clip") { clipBox.reset(); hideBand(); }
    if (name === "find" && findBox) { findBox.value = ""; findList = []; }
    if (layerStack.length) {
      var below = layerOf(layerStack[layerStack.length - 1]);
      if (below) { below.hidden = false; }
      return;
    }
    if (panelsBox) { panelsBox.hidden = false; }
    if (layerReturn) {
      showTab(layerReturn.tab);
      if (panelsBox) { panelsBox.scrollTop = layerReturn.scroll; }
      if (layerReturn.row) { flashRow(layerReturn.row); }
      layerReturn = null;
    }
  }
  function closeLayers() { while (layerStack.length) { closeLayer(); } }
  window.INCIDENT_LAYERS = { open: openLayer, close: closeLayer, stack: function () { return layerStack.slice(); } };
  document.querySelector(".inc-work").addEventListener("click", function (event) {
    if (event.target.closest("[data-back]")) { closeLayer(); }
  });

  eventBox.addEventListener("submit", function (event) {
    event.preventDefault();
    var at = parseWhen(eventBox.elements.when.value);
    if (at === null) { window.UI.toast("When did it happen? " + (S.incident.has_clock ? "A time of day, hh:mm:ss." : "Minutes and seconds, m:ss."), { problem: true }); return; }
    var until = eventBox.elements.until_when.value.trim() ? parseWhen(eventBox.elements.until_when.value) : null;
    var fields = {
      action: eventBox.elements.event.value ? "event_change" : "event_add",
      event: eventBox.elements.event.value,
      at: at.toFixed(2),
      until: until === null ? "" : until.toFixed(2),
      text: eventBox.elements.text.value,
      source: eventBox.elements.source.value,
      camera: eventBox.elements.camera.value,
      note: eventBox.elements.note.value,
      to_check: eventBox.elements.to_check.checked ? "yes" : "",
      cameras_given: "yes",
      cameras: Array.prototype.map.call(eventBox.querySelectorAll("input[name=cameras]:checked"), function (one) { return one.value; })
    };
    post(fields).then(function (got) { if (got.ok) { closeEventBox(); showTab("chronology"); } });
  });
  document.getElementById("event-cancel").addEventListener("click", closeEventBox);
  document.getElementById("event-note-open").addEventListener("click", function () {
    var note = eventBox.elements.note;
    note.hidden = !note.hidden;
    if (!note.hidden) { note.focus(); }
  });
  // The Note field: Enter adds or saves as everywhere on the box; Shift+Enter
  // starts a new line (Phase 7 chapter 1).
  eventBox.elements.note.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.shiftKey) { return; }
    event.preventDefault();
    if (eventBox.requestSubmit) { eventBox.requestSubmit(); } else { eventBox.dispatchEvent(new Event("submit", { cancelable: true })); }
  });
  document.getElementById("event-remove").addEventListener("click", function () {
    var id = eventBox.elements.event.value;
    if (!id) { return; }
    window.UI.confirm({ title: "Remove this event?", body: "It leaves the chronology and the exports.", ok: "Remove", danger: true }).then(function (yes) {
      if (yes) { post({ action: "event_remove", event: id }).then(closeEventBox); }
    });
  });
  document.getElementById("event-clip").addEventListener("click", function () {
    var found = eventById(eventBox.elements.event.value);
    if (found) { openClipBox(found); }
  });

  // The clip box (Phase 7 chapter 1): one file from the event's cameras over
  // its span. The cameras are tiles in the picture's order, the first the
  // large one in Focus; a camera the span falls outside is greyed.

  function clipCameras() {
    // Synced, with a playback copy: the ones ffmpeg can cut.
    return placedCameras().filter(function (cam) { return cam.synced && cam.media_url; });
  }

  function mayClip(ev) {
    // While clips are on and at least one of the event's own cameras (its
    // Seen on list) is synced with a playback copy, as the chapter says.
    if (!S.incident.clips || !ev || !ev.id) { return false; }
    var cuttable = clipCameras().map(function (cam) { return cam.id; });
    return (ev.cameras || []).some(function (id) { return cuttable.indexOf(id) !== -1; });
  }

  function clipSpan() {
    var from = parseWhen(clipBox.elements.from.value), until = parseWhen(clipBox.elements.until.value);
    if (from === null || until === null) { return null; }
    return [from, until];
  }

  function isRunning(cam, span) {
    return cam.starts_at < span[1] && cam.starts_at + cam.length > span[0];
  }

  function clipTiles() { return Array.prototype.slice.call(clipBox.querySelectorAll(".clip-cam")); }

  function tickedCameras() {
    return clipTiles().filter(function (tile) { var box = tile.querySelector("input"); return box.checked && !box.disabled; })
      .map(function (tile) { return tile.dataset.camera; });
  }

  function openClipBox(ev) {
    // From an event: ten seconds either side of it. From the strip (Phase 6
    // chapter 5): the dragged span as it is, no event, every camera that
    // runs inside it, synced or not.
    var strip = !ev.id;
    var from = strip ? ev.at : Math.floor(ev.at) - 10;
    var until = strip ? ev.until : Math.ceil(ev.until || ev.at) + 10;
    if (!S.incident.has_clock && from < 0) { from = 0; }
    openLayer("clip");
    document.getElementById("clip-eyebrow-head").textContent = strip ? "Clip from the strip" : "Clip this event";
    clipBox.elements.event.value = ev.id || "";
    document.getElementById("clip-eyebrow").textContent = strip ? "Clip from the strip" : "Clip this event";
    document.getElementById("clip-event-text").textContent = strip ? timeOfDay(from) + " to " + timeOfDay(until) : timeOfDay(ev.at) + "  " + ev.text;
    clipBox.elements.from.value = timeOfDay(from);
    clipBox.elements.until.value = timeOfDay(until);
    clipBox.elements.title.value = strip ? timeOfDay(from) + " to " + timeOfDay(until) : (ev.text || "").slice(0, 120);
    clipBox.elements.layout.value = layout === "focus" ? "focus" : "grid";
    clipBox.elements.burn_ids.checked = true;
    // The clock is burned only from an Incident clock: elapsed time would
    // read as a time of day just after midnight.
    var clockLabel = document.getElementById("clip-clock-label");
    clipBox.elements.burn_clock.checked = !!S.incident.has_clock;
    clipBox.elements.burn_clock.disabled = !S.incident.has_clock;
    clockLabel.title = S.incident.has_clock ? "The time of day on the incident clock, top right, running" : "No camera clock on this incident";
    clockLabel.classList.toggle("muted", !S.incident.has_clock);
    // The Wall's order, then the parked cameras; ticked from Seen on, or,
    // from the strip, every camera running inside the span.
    var order = wallCameras().concat(parkedCameras()).filter(function (cam) { return cam.media_url && (strip || cam.synced); });
    var ticked = strip ? order.filter(function (cam) { return isRunning(cam, [from, until]); }).map(function (cam) { return cam.id; }) : (ev.cameras || []);
    var cams = document.getElementById("clip-cams");
    cams.innerHTML = order.map(function (cam) {
      return "<label class='clip-cam" + (cam.synced ? "" : " unsynced") + "' draggable='true' data-camera='" + cam.id + "' style='--speaker: " + cam.colour + "'>" +
        "<input type='checkbox' name='cameras' value='" + cam.id + "'" + (ticked.indexOf(cam.id) !== -1 ? " checked" : "") + "> " +
        "<span class='name'>" + escape(cam.camera_id) + "</span>" + (cam.synced ? "" : "<span class='pill warn small'>Not synced yet</span>") + "<span class='muted small why' hidden> not running then</span>" +
        "<button type='button' class='tiny ghost large' title='Make this the large tile'>Large</button></label>";
    }).join("");
    // The sound: the camera the page hears, when it is in the clip. The
    // choices are built afresh, so the last box's first camera cannot win.
    clipBox.elements.sound.innerHTML = "";
    clipBox.elements.sound.dataset.wanted = soundCamera || "";
    refreshClipBox();
    clipBox.elements.title.focus();
  }

  function closeClipBox() {
    if (layerStack[layerStack.length - 1] === "clip") { closeLayer(); }
  }

  function refreshClipBox() {
    var span = clipSpan();
    var lengthBox = document.getElementById("clip-length");
    // The warning (Phase 6 chapter 5): a ticked camera not synced is cut at
    // its guessed place.
    var warn = document.getElementById("clip-unsynced");
    if (warn) {
      warn.hidden = !clipTiles().some(function (tile) {
        var box = tile.querySelector("input");
        return box.checked && tile.classList.contains("unsynced");
      });
    }
    var make = document.getElementById("clip-make");
    var wrong = "";
    if (span === null) {
      wrong = S.incident.has_clock ? "Times of day, hh:mm:ss." : "Minutes and seconds, m:ss.";
    } else if (span[1] - span[0] < 1) {
      wrong = "A clip is at least one second long.";
    } else if (span[1] - span[0] > S.incident.clip_longest) {
      wrong = "A clip may be up to " + Math.floor(S.incident.clip_longest / 60) + " minutes long.";
    }
    lengthBox.textContent = wrong || (spell(span[1] - span[0]));
    lengthBox.classList.toggle("danger", !!wrong);
    // Grey a camera the span falls outside; the first ticked is the large one.
    // A camera gone from the incident while the box was open says so.
    var first = true;
    clipTiles().forEach(function (tile) {
      var cam = cameraById(tile.dataset.camera), box = tile.querySelector("input");
      var running = !!(span && cam && isRunning(cam, span));
      tile.classList.toggle("off", !running);
      tile.querySelector(".why").hidden = running;
      tile.querySelector(".why").textContent = cam ? " not running then" : " removed from the incident";
      box.disabled = !running;
      var on = running && box.checked;
      tile.classList.toggle("first", on && first && clipBox.elements.layout.value === "focus");
      tile.querySelector(".large").hidden = !(on && !first && clipBox.elements.layout.value === "focus");
      if (on) { first = false; }
    });
    var ticked = tickedCameras();
    // Focus holds up to five cameras; past that the box starts from Grid.
    var focusOption = clipBox.elements.layout.options[0];
    focusOption.disabled = ticked.length > S.incident.clip_focus_most;
    focusOption.title = focusOption.disabled ? "Focus holds up to five cameras" : "";
    if (focusOption.disabled && clipBox.elements.layout.value === "focus") { clipBox.elements.layout.value = "grid"; }
    if (ticked.length > S.incident.clip_most) { wrong = "Up to nine cameras in one clip."; }
    // The sound: from one of the ticked cameras, the page's when it is one.
    var sound = clipBox.elements.sound;
    var wanted = sound.value || sound.dataset.wanted || "";
    sound.innerHTML = ticked.map(function (id) {
      var cam = cameraById(id);
      return "<option value='" + id + "'>" + escape(cam ? cam.camera_id : id) + "</option>";
    }).join("");
    if (ticked.indexOf(wanted) !== -1) { sound.value = wanted; }
    var said = document.getElementById("clip-sound-said");
    var heard = cameraById(sound.value);
    said.textContent = (heard && span && heard.starts_at > span[0]) ? "silent until " + timeOfDay(heard.starts_at) : "";
    if (!ticked.length) { wrong = wrong || "Tick at least one camera."; }
    make.disabled = !!wrong;
    if (wrong && !lengthBox.textContent) { lengthBox.textContent = wrong; }
    var says = document.getElementById("clip-said");
    says.textContent = wrong || (ticked.length + " camera" + (ticked.length === 1 ? "" : "s") + ", " + (clipBox.elements.layout.value === "focus" ? "Focus" : "Grid") + ": one file, 1280 wide, each camera cut from its own moment. It renders on the media worker and lands on the case's Clips tab.");
  }

  function spell(seconds) {
    var whole = Math.round(seconds), h = Math.floor(whole / 3600), m = Math.floor((whole % 3600) / 60), s = whole % 60;
    if (h) { return h + " h" + (m ? " " + m + " min" : ""); }
    if (m) { return m + " min" + (s ? " " + s + " s" : ""); }
    return s + " s";
  }

  clipBox.addEventListener("input", function () { refreshClipBox(); });
  clipBox.addEventListener("change", function () { refreshClipBox(); });
  document.getElementById("clip-cancel").addEventListener("click", closeClipBox);

  // The tiles: dragged to reorder, or Large to bring one to the front.
  var draggedClip = null;
  var clipCams = document.getElementById("clip-cams");
  clipCams.addEventListener("click", function (event) {
    var large = event.target.closest(".large");
    if (!large) { return; }
    event.preventDefault();
    var tile = large.closest(".clip-cam");
    clipCams.insertBefore(tile, clipCams.firstChild);
    refreshClipBox();
  });
  clipCams.addEventListener("dragstart", function (event) {
    var tile = event.target.closest(".clip-cam");
    if (!tile) { return; }
    draggedClip = tile;
    event.dataTransfer.effectAllowed = "move";
    try { event.dataTransfer.setData("text/plain", tile.dataset.camera); } catch (ignored) { /* an old browser */ }
  });
  clipCams.addEventListener("dragover", function (event) {
    var tile = event.target.closest(".clip-cam");
    if (draggedClip && tile && tile !== draggedClip) { event.preventDefault(); tile.classList.add("over"); }
  });
  clipCams.addEventListener("dragleave", function (event) {
    var tile = event.target.closest(".clip-cam");
    if (tile) { tile.classList.remove("over"); }
  });
  clipCams.addEventListener("drop", function (event) {
    var tile = event.target.closest(".clip-cam");
    if (!draggedClip || !tile || tile === draggedClip) { return; }
    event.preventDefault();
    tile.classList.remove("over");
    var after = Array.prototype.indexOf.call(clipCams.children, draggedClip) < Array.prototype.indexOf.call(clipCams.children, tile);
    clipCams.insertBefore(draggedClip, after ? tile.nextSibling : tile);
    draggedClip = null;
    refreshClipBox();
  });
  clipCams.addEventListener("dragend", function () { draggedClip = null; });

  clipBox.addEventListener("submit", function (event) {
    event.preventDefault();
    var span = clipSpan();
    if (span === null) { window.UI.toast(S.incident.has_clock ? "Times of day, hh:mm:ss." : "Minutes and seconds, m:ss.", { problem: true }); return; }
    var body = {
      from: span[0].toFixed(2),
      until: span[1].toFixed(2),
      cameras: tickedCameras(),
      sound: clipBox.elements.sound.value,
      layout: clipBox.elements.layout.value,
      burn_clock: clipBox.elements.burn_clock.checked,
      burn_ids: clipBox.elements.burn_ids.checked,
      title: clipBox.elements.title.value
    };
    var make = document.getElementById("clip-make");
    make.disabled = true;
    fetch(clipBox.elements.event.value ? C.eventClip + clipBox.elements.event.value + "/clip" : C.spanClip, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken"), "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (answer) { return answer.json().then(function (said) { return { ok: answer.ok, said: said }; }); })
      .then(function (got) {
        make.disabled = false;
        if (!got.ok) { window.UI.toast(got.said.error || "That did not work.", { problem: true }); return; }
        closeClipBox();
        hideBand();
        if (got.said.said) { window.UI.toast(got.said.said); }
        if (got.said.state) { take(got.said.state); }
        showTab("chronology");
      })
      .catch(function () { make.disabled = false; window.UI.toast("That did not work.", { problem: true }); });
  });

  // The picture: the strip drawn on a canvas from the same rows, in the light
  // palette whatever the theme, at twice the screen's resolution.
  var LIGHT = ["#1f6fb2", "#c2410c", "#2e7d32", "#8e24aa", "#00838f", "#ad1457", "#6d4c41", "#546e7a"];

  function drawPicture() {
    var scale = 2;
    var width = 1000, left = 130, right = 20, laneHeight = 22, top = 34;
    var cameras = S.cameras.slice();
    var events = S.events.filter(function (one) { return !one.proposed; }).sort(function (a, b) { return a.at - b.at; });
    var height = top + cameras.length * laneHeight + 16 + 44 + 16;
    var canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;
    var ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    var shown = span();
    function x(at) { return left + ((at - shown[0]) / (shown[1] - shown[0])) * (width - left - right); }
    ctx.font = "11px 'IBM Plex Mono', Consolas, monospace";
    ctx.fillStyle = "#5b6673";
    ctx.textBaseline = "middle";
    for (var i = 0; i <= 6; i += 1) {
      var at = shown[0] + ((shown[1] - shown[0]) * i) / 6;
      var tx = x(at);
      ctx.textAlign = i === 0 ? "left" : (i === 6 ? "right" : "center");
      ctx.fillText(timeOfDay(at), tx, 14);
      ctx.fillStyle = "#d3d9e0";
      ctx.fillRect(tx, 24, 1, height - 24 - 16);
      ctx.fillStyle = "#5b6673";
    }
    ctx.font = "12px 'IBM Plex Sans', system-ui, sans-serif";
    cameras.forEach(function (cam, index) {
      var y = top + index * laneHeight;
      var placed = cam.starts_at !== null && cam.placed;
      var start = placed ? cam.starts_at : shown[0];
      ctx.textAlign = "left";
      ctx.fillStyle = "#171b21";
      ctx.fillText(cam.camera_id.length > 16 ? cam.camera_id.slice(0, 15) + "…" : cam.camera_id, 8, y + laneHeight / 2);
      ctx.fillStyle = "#e9edf1";
      ctx.fillRect(left, y + 4, width - left - right, laneHeight - 8);
      ctx.fillStyle = LIGHT[index % LIGHT.length];
      ctx.globalAlpha = placed ? 0.9 : 0.3;
      ctx.fillRect(x(start), y + 6, Math.max(2, x(start + cam.length) - x(start)), laneHeight - 12);
      ctx.globalAlpha = 1;
    });
    var ey = top + cameras.length * laneHeight + 16;
    ctx.fillStyle = "#171b21";
    ctx.textAlign = "left";
    ctx.fillText("Events", 8, ey + 10);
    ctx.fillStyle = "#d3d9e0";
    ctx.fillRect(left, ey + 20, width - left - right, 1);
    var lastRight = -1;
    events.forEach(function (one, index) {
      var ex = x(one.at);
      ctx.fillStyle = "#0f5e86";
      ctx.fillRect(ex - 1, ey, 2, 22);
      if (one.until) { ctx.globalAlpha = 0.25; ctx.fillRect(ex, ey + 4, Math.max(2, x(one.until) - ex), 14); ctx.globalAlpha = 1; }
      ctx.font = "11px 'IBM Plex Sans', system-ui, sans-serif";
      var label = String(index + 1) + " " + shortLabel(one.text);
      var needs = ctx.measureText(label).width + 8;
      if (ex >= lastRight) {
        ctx.fillStyle = "#171b21";
        ctx.fillText(label, ex + 4, ey + 32);
        lastRight = ex + needs;
      } else {
        ctx.fillStyle = "#5b6673";
        ctx.fillText(String(index + 1), ex + 3, ey + 32);
      }
    });
    ctx.font = "10px 'IBM Plex Sans', system-ui, sans-serif";
    ctx.fillStyle = "#5b6673";
    ctx.fillText("Each bar is one camera's recording on the clock; a line on the Events lane is an event, numbered as in the table.", 8, height - 8);
    return new Promise(function (resolve) { canvas.toBlob(function (blob) { resolve(blob); }, "image/png"); });
  }

  function download(blob, name) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
  }

  function exportWith(url, blob) {
    var form = new FormData();
    if (blob) { form.append("picture", blob, "strip.png"); }
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") }, body: form })
      .then(function (answer) {
        if (!answer.ok) { window.UI.toast("The export did not work.", { problem: true }); return null; }
        var name = (answer.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)"?/);
        return answer.blob().then(function (got) { download(got, name ? name[1] : "chronology"); });
      });
  }

  document.getElementById("export-word").addEventListener("click", function () {
    document.getElementById("export-menu").removeAttribute("open");
    drawPicture().then(function (blob) { return exportWith(C.exportWord, blob); });
  });
  document.getElementById("export-picture").addEventListener("click", function () {
    document.getElementById("export-menu").removeAttribute("open");
    drawPicture().then(function (blob) { return exportWith(C.exportPicture, blob); });
  });

  // The Cameras tab ----------------------------------------------------------------------

  function placeControls(cam) {
    var html = "";
    if (cam.has_clock) { html += "<button type='button' class='tiny' data-act='place' data-how='clock' data-camera='" + cam.id + "'>From its clock</button> "; }
    if (cam.file_time && S.incident.has_clock) { html += "<button type='button' class='tiny' data-act='place' data-how='file' data-camera='" + cam.id + "' title='The file says " + quoted(cam.file_time) + "'>From its file</button> "; }
    if (S.incident.sound_match) {
      var others = placedCameras().filter(function (one) { return one.id !== cam.id && one.synced; });
      if (others.length) {
        html += "<span class='inc-match'><select data-against='" + cam.id + "' class='small'>";
        others.forEach(function (one) { html += "<option value='" + one.id + "'>" + escape(one.camera_id) + "</option>"; });
        html += "</select> <button type='button' class='tiny' data-act='match' data-camera='" + cam.id + "'>Match the sound</button></span> ";
      }
    }
    html += "<span class='inc-nudge'><button type='button' class='tiny' data-act='nudge' data-by='-1' data-camera='" + cam.id + "'>−1 s</button>" +
      "<button type='button' class='tiny' data-act='nudge' data-by='-0.1' data-camera='" + cam.id + "'>−0.1</button>" +
      "<button type='button' class='tiny' data-act='nudge' data-by='0.1' data-camera='" + cam.id + "'>+0.1</button>" +
      "<button type='button' class='tiny' data-act='nudge' data-by='1' data-camera='" + cam.id + "'>+1 s</button></span> ";
    html += "<button type='button' class='tiny' data-act='type' data-camera='" + cam.id + "'>Type a time</button>";
    return html;
  }

  function matchLine(cam) {
    var m = cam.match;
    if (!m || !m.state) { return ""; }
    var against = cameraById(m.against);
    var name = against ? against.camera_id : "another camera";
    if (m.state === "queued" || m.state === "running") { return "<div class='small muted'>Matching the sound against " + escape(name) + "; about a minute.</div>"; }
    if (m.state === "failed") { return "<div class='small muted'>No match: " + escape(m.reason || "the sounds did not line up") + ".</div>"; }
    if (m.state === "done") {
      var words = "The sound lines up " + (m.lag >= 0 ? "" : "−") + Math.abs(m.lag).toFixed(1) + " s " + (m.lag >= 0 ? "after" : "before") + " " + escape(name) + " starts";
      if (cam.placed === "sound") { return "<div class='small muted'>" + words + "; placed by it.</div>"; }
      return "<div class='small'><span class='pill warn small'>Weak match</span> " + words + ", but not clearly. <button type='button' class='tiny' data-act='place' data-how='match' data-camera='" + cam.id + "'>Use it anyway</button></div>";
    }
    return "";
  }

  function drawCameras() {
    var box = document.getElementById("panel-cameras");
    var html = "<p class='lead' style='margin: 0 0 8px'>" + S.incident.count + " camera" + (S.incident.count === 1 ? "" : "s") + ". " + escape(S.incident.placed_words) + ".</p>";
    html += "<table class='tbl inc-cameras'><thead><tr><th>Camera</th><th>Starts at</th><th>Placed</th><th></th></tr></thead><tbody>";
    S.cameras.forEach(function (cam) {
      var placed = cam.starts_at !== null && cam.placed;
      html += "<tr data-row='" + cam.id + "'" + (cam.synced ? "" : " class='unsynced'") + "><td><b style='color: " + cam.colour + "'>" + escape(cam.camera_id) + "</b><div class='muted small'>" + escape(cam.title) + "</div>" +
        (cam.clock ? "<div class='small'><span class='pill " + escape(cam.clock_tone) + " small'>" + escape(cam.clock) + "</span></div>" : "") +
        (cam.file_time ? "<div class='muted small'>the file says " + escape(cam.file_time) + "</div>" : "") + "</td>" +
        "<td class='mono'>" + (placed ? timeOfDay(cam.starts_at) : "") + "</td>" +
        "<td><span class='pill " + escape(cam.placed_tone) + " small'>" + escape(cam.placed_words) + "</span>" +
        (cam.placed_by && cam.synced ? "<div class='muted small'>by " + escape(cam.placed_by) + "</div>" : "") + matchLine(cam) + "</td>" +
        "<td class='acts'><button type='button' class='tiny' data-act='sync-open' data-camera='" + cam.id + "' title='This camera on the Sync sheet'>Sync</button> " +
        (placed && !cam.on_wall ? "<button type='button' class='tiny' data-swap='" + cam.id + "'>Swap in</button> " : "") +
        "<a class='tiny btn ghost' href='" + escape(cam.viewer_url) + "'>Open</a> " +
        "<button type='button' class='tiny ghost danger' data-act='remove' data-camera='" + cam.id + "'>Remove</button></td></tr>";
    });
    html += "</tbody></table>";
    html += "<div class='row actions' style='margin-top: 10px; gap: 6px'><button type='button' class='small' id='add-cameras'>Add cameras</button>" +
      "<button type='button' class='small ghost' id='rename-incident'>Rename incident</button><span class='grow'></span>" +
      "<button type='button' class='small ghost danger' id='delete-incident'>Delete incident</button></div>";
    box.innerHTML = html;
    var pending = S.cameras.some(function (cam) { return cam.match && (cam.match.state === "queued" || cam.match.state === "running"); });
    window.clearTimeout(pollTimer);
    if (pending) { pollTimer = window.setTimeout(refresh, 3000); }
  }

  function refresh() {
    fetch(C.state).then(function (answer) { return answer.json(); }).then(take).catch(function () { pollTimer = window.setTimeout(refresh, 6000); });
  }

  function flashRow(id) {
    var row = document.querySelector("[data-row='" + id + "']");
    if (row) { row.classList.add("match-here"); row.scrollIntoView({ block: "nearest" }); window.setTimeout(function () { row.classList.remove("match-here"); }, 2000); }
  }

  document.getElementById("panel-cameras").addEventListener("click", function (event) {
    var swap = event.target.closest("[data-swap]");
    if (swap) { swapIn(swap.dataset.swap); return; }
    var button = event.target.closest("[data-act]");
    if (button) {
      var cam = cameraById(button.dataset.camera);
      var act = button.dataset.act;
      if (act === "sync-open") { openSync(cam.id); }
      else if (act === "place") { post({ action: "place", camera: cam.id, how: button.dataset.how }); }
      else if (act === "listen") { listen(cam); }
      else if (act === "nudge") {
        var from = cam.starts_at !== null && cam.placed ? cam.starts_at : (S.incident.span_low || 0);
        post({ action: "place", camera: cam.id, how: "hand", starts_at: (from + parseFloat(button.dataset.by)).toFixed(2) });
      } else if (act === "type") {
        window.UI.prompt({ title: "When does " + cam.camera_id + " start?", body: S.incident.has_clock ? "A time of day, hh:mm:ss, by the cameras' clocks." : "Minutes and seconds from the first camera, m:ss.", ok: "Sync" }).then(function (text) {
          if (!text) { return; }
          var at = parseWhen(text);
          if (at === null) { window.UI.toast("That is not a time.", { problem: true }); return; }
          post({ action: "place", camera: cam.id, how: "hand", starts_at: at.toFixed(2) });
        });
      } else if (act === "match") {
        var pick = document.querySelector("select[data-against='" + cam.id + "']");
        post({ action: "match", camera: cam.id, against: pick ? pick.value : "" });
      } else if (act === "remove") {
        window.UI.confirm({ title: "Remove " + cam.camera_id + " from this incident?", body: "The recording stays in the case; only its place here goes.", ok: "Remove" }).then(function (yes) { if (yes) { post({ action: "remove", camera: cam.id }); } });
      }
      return;
    }
    if (event.target.closest("#add-cameras")) { openAddBox(); return; }
    if (event.target.closest("#rename-incident")) {
      window.UI.prompt({ title: "Rename this incident", body: "", ok: "Rename", value: S.incident.name }).then(function (name) {
        if (name) { post({ action: "rename", name: name }).then(function () { document.getElementById("inc-title").firstChild.textContent = S.incident.name + " "; }); }
      });
      return;
    }
    if (event.target.closest("#delete-incident")) {
      window.UI.confirm({ title: "Delete this incident?", body: "Its placements and events go; no recording is deleted.", ok: "Delete incident", danger: true }).then(function (yes) { if (yes) { post({ action: "delete" }); } });
    }
  });

  var addBox = document.getElementById("add-box");
  function openAddBox() {
    var list = document.getElementById("add-list");
    var others = S.others || [];
    list.innerHTML = others.map(function (one) {
      return "<label class='inc-check'><input type='checkbox' name='recordings' value='" + one.recording + "'>" +
        "<span><b>" + escape(one.title) + "</b>" + (one.elsewhere ? " <span class='muted'>in " + escape(one.elsewhere) + "</span>" : "") + "</span>" +
        (one.clock ? "<span class='pill " + escape(one.tone) + " small'>" + escape(one.clock) + "</span>" : "<span></span>") + "</label>";
    }).join("");
    document.getElementById("add-none").hidden = others.length > 0;
    document.getElementById("add-go").disabled = !others.length;
    addBox.hidden = false;
  }
  document.getElementById("add-cancel").addEventListener("click", function () { addBox.hidden = true; });
  document.getElementById("add-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var chosen = Array.prototype.map.call(addBox.querySelectorAll("input:checked"), function (one) { return one.value; });
    addBox.hidden = true;
    if (chosen.length) { post({ action: "add", recordings: chosen }); }
  });

  // The Details tab ----------------------------------------------------------------------

  function drawDetails() {
    var box = document.getElementById("panel-details");
    var I = S.incident;
    var html = "<dl class='kv'>";
    html += "<dt>Incident</dt><dd>" + escape(I.name) + "</dd>";
    html += "<dt>Made</dt><dd>" + (I.created_by ? "by " + escape(I.created_by) + ", " : "") + new Date(I.created).toLocaleString() + (I.how === "offer" ? ", from the case page's offer" : ", with New incident") + "</dd>";
    html += "<dt>Clock</dt><dd>" + (I.has_clock ? "the time of day on " + escape(I.clock_date) + ", from the first camera placed from a checked clock" : "no camera clock; times count from the first camera") + "</dd>";
    html += "<dt>Span</dt><dd>" + escape(I.span_words) + "</dd>";
    html += "<dt>Cameras</dt><dd>" + I.count + ", " + escape(I.placed_words) + "</dd>";
    html += "<dt>Events</dt><dd>" + keptEvents().length + "</dd>";
    if (C.role === "admin" && S.memo && S.memo.state === "done") {
      html += "<dt>Memo</dt><dd>written on " + S.memo.events_count + " events from an incident record of " + S.memo.record_lines + " lines (" + escape((S.memo.cameras_used || []).concat(S.memo.cameras_transcript_only || []).join(", ") || "no camera") + ")</dd>";
    }
    html += "</dl><h3 style='font-size: var(--t-body); margin: 14px 0 6px'>Each camera's stamp</h3><dl class='kv'>";
    S.cameras.forEach(function (cam) {
      html += "<dt>" + escape(cam.camera_id) + "</dt><dd>" + (cam.clock ? escape(cam.clock) : "no stamp read") + (cam.file_time ? "; the file says " + escape(cam.file_time) : "") + "</dd>";
    });
    html += "</dl>";
    box.innerHTML = html;
  }

  // Tabs ------------------------------------------------------------------------------------

  var twoPanels = false;
  function showTab(name) {
    if (layerStack.length) { closeLayers(); }
    Array.prototype.forEach.call(document.querySelectorAll(".inc-work .tab"), function (tab) { tab.classList.toggle("on", tab.dataset.panel === name); });
    ["chronology", "memo", "cameras", "details"].forEach(function (one) { var panel = document.getElementById("panel-" + one); if (panel) { panel.hidden = one !== name && !(twoPanels && one === "memo"); } });
    if (name === "chronology") { currentEventId = null; markCurrentEvent(now()); }
  }
  Array.prototype.forEach.call(document.querySelectorAll(".inc-work .tab"), function (tab) {
    tab.addEventListener("click", function () { showTab(tab.dataset.panel); });
  });

  // What Gideon's drawer calls (Phase 7 chapter 5): a citation seeks every
  // camera; + event opens the event box at the moment with the line filled.
  window.INCIDENT_PAGE = {
    seek: function (at) { seek(at); if (!playing) { play(); } },
    addEvent: function (at, line) { openEventBox({ at: at, text: line || "", source: "person" }); }
  };

  // Go ---------------------------------------------------------------------------------------

  // Two panels (Phase 8 chapter 1): from a very wide window, the Memo beside
  // the Chronology; the choice is the browser's, per person.
  var twoButton = document.getElementById("two-panels");
  var veryWide = window.matchMedia ? window.matchMedia("(min-width: 3840px)") : null;
  function drawTwo() {
    if (!twoButton) { return; }
    var wide = !!(veryWide && veryWide.matches);
    twoButton.hidden = !wide;
    twoPanels = wide && (function () { try { return window.localStorage.getItem("inc-two") === "yes"; } catch (ignored) { return false; } }());
    document.querySelector(".inc-work").classList.toggle("two", twoPanels);
    twoButton.classList.toggle("on", twoPanels);
    showTab(currentTab());
  }
  if (twoButton) {
    twoButton.addEventListener("click", function () {
      try { window.localStorage.setItem("inc-two", twoPanels ? "no" : "yes"); } catch (ignored) { /* forgotten */ }
      drawTwo();
    });
    if (veryWide && veryWide.addEventListener) { veryWide.addEventListener("change", drawTwo); }
  }

  take(S);
  showTab(C.openTab || (placedCameras().length ? "chronology" : "cameras"));
  drawTwo();
  seek(moment);
  if (eventWords) { openEventBox({ at: moment, text: eventWords, source: "words" }); }
  // A search hit opens the memo at a paragraph (Phase 7 chapter 3).
  if (C.openTab === "memo" && C.para !== "") { lightParagraph(document.getElementById("panel-memo"), parseInt(C.para, 10)); }

  // Sync, one control (Phase 6 chapter 5) --------------------------------------------------
  //
  // One sheet with every camera: its clock as read from the picture, its
  // place, who synced it, a tick and its controls. Sync all has the app do
  // the rounds on every camera not yet synced; Sync ticked on the ticked
  // ones. A camera the app could not sync says why and shows what to do.
  var syncOpenRow = null;
  var syncSaid = "";
  function openSync(cameraId) {
    syncOpenRow = cameraId || null;
    syncSaid = "";
    drawSync();
    openLayer("sync");
    if (cameraId) {
      var row = syncBox.querySelector("[data-sync-row='" + cameraId + "']");
      if (row) { row.scrollIntoView({ block: "nearest" }); }
    }
  }
  function closeSync() { if (layerStack[layerStack.length - 1] === "sync") { closeLayer(); } }
  function tickedSync() {
    return Array.prototype.map.call(syncBox.querySelectorAll("input[name='sync-tick']:checked"), function (box) { return box.value; });
  }
  function drawSync() {
    if (!syncBox) { return; }
    var ticked = tickedSync();
    var cams = wallCameras().concat(parkedCameras());
    var synced = cams.filter(function (cam) { return cam.synced; }).length;
    var html = "<div class='row' style='gap: 8px; align-items: center; flex-wrap: wrap'>" +
      "<span class='eyebrow'>Sync</span>" +
      "<span class='small grow'>" + synced + " of " + cams.length + " synced. " + escape(syncSaid) + "</span>" +
      "<button type='button' class='small primary' id='sync-all' title='The app tries each camera not yet synced: its clock, then the sound against a camera in step, then asks for a hand'>Sync all</button>" +
      "<button type='button' class='small' id='sync-ticked' title='The rounds on the ticked cameras, synced or not'" + (ticked.length ? "" : " disabled") + ">Sync ticked</button>" +
      "<button type='button' class='small ghost' id='sync-close'>Done</button></div>";
    html += "<table class='inc-sync'><tbody>";
    cams.forEach(function (cam) {
      var open = !cam.synced || cam.id === syncOpenRow;
      html += "<tr data-sync-row='" + cam.id + "'" + (cam.synced ? "" : " class='unsynced'") + ">" +
        "<td><input type='checkbox' name='sync-tick' value='" + cam.id + "'" + (ticked.indexOf(cam.id) !== -1 ? " checked" : "") + " aria-label='Tick " + quoted(cam.camera_id) + "'></td>" +
        "<td><b style='color: " + cam.colour + "'>" + escape(cam.camera_id) + "</b><div class='muted small'>" + escape(cam.title) + "</div></td>" +
        "<td>" + (cam.clock ? "<span class='pill " + escape(cam.clock_tone) + " small'>" + escape(cam.clock) + "</span>" : "<span class='muted small'>" + (cam.has_clock ? "" : "no clock in the picture") + "</span>") + "</td>" +
        "<td><span class='pill " + escape(cam.placed_tone) + " small'>" + escape(cam.placed_words) + "</span>" +
        (cam.placed_by && cam.synced ? "<div class='muted small'>by " + escape(cam.placed_by) + "</div>" : "") +
        (cam.needs_hand ? "<div class='small problem'>Needs a hand: " + escape(cam.needs_hand) + ".</div>" : "") +
        (cam.placed === "clock_unchecked" ? "<div class='small'>Read once: listen to a moment two cameras hear. <button type='button' class='tiny' data-act='listen' data-camera='" + cam.id + "'>Listen</button></div>" : "") +
        matchLine(cam) + "</td>" +
        "<td class='acts'>" + (open ? "<div class='inc-place-box'>" + placeControls(cam) + "</div>" : "<button type='button' class='tiny ghost' data-act='sync-open' data-camera='" + cam.id + "'>More</button>") + "</td></tr>";
    });
    html += "</tbody></table>";
    syncBox.innerHTML = html;
  }
  // Listen: the first moment this camera and a synced camera run together,
  // played with the sound from the other one.
  function listen(cam) {
    var partner = null;
    placedCameras().forEach(function (one) {
      if (one.id === cam.id || !one.synced) { return; }
      if (one.starts_at < cam.starts_at + cam.length && one.ends_at > cam.starts_at && (!partner || one.starts_at < partner.starts_at)) { partner = one; }
    });
    if (!partner) { window.UI.toast("No synced camera runs at the same time.", { problem: true }); return; }
    if (!cam.on_wall) { swapIn(cam.id, false); }
    seek(Math.max(cam.starts_at, partner.starts_at));
    setSound(partner.id);
    play();
  }
  document.getElementById("sync-open").addEventListener("click", function () { if (syncBox.hidden) { openSync(null); } else { closeSync(); } });
  syncBox.addEventListener("click", function (event) {
    if (event.target.closest("#sync-close")) { closeSync(); return; }
    if (event.target.closest("#sync-all") || event.target.closest("#sync-ticked")) {
      var fields = { action: "sync_all" };
      if (event.target.closest("#sync-ticked")) { fields.cameras = tickedSync(); }
      syncSaid = "Syncing...";
      drawSync();
      post(fields).then(function (got) { if (got.ok) { syncSaid = got.said.said || ""; drawSync(); } });
      return;
    }
    if (event.target.closest("input[name='sync-tick']")) { drawSync(); return; }
    var button = event.target.closest("[data-act]");
    if (!button) { return; }
    var cam = cameraById(button.dataset.camera);
    if (!cam) { return; }
    var act = button.dataset.act;
    if (act === "sync-open") { syncOpenRow = cam.id; drawSync(); }
    else if (act === "place") { post({ action: "place", camera: cam.id, how: button.dataset.how }); }
    else if (act === "listen") { listen(cam); }
    else if (act === "nudge") {
      var from = cam.starts_at !== null && cam.placed ? cam.starts_at : (S.incident.span_low || 0);
      post({ action: "place", camera: cam.id, how: "hand", starts_at: (from + parseFloat(button.dataset.by)).toFixed(2) });
    } else if (act === "type") {
      window.UI.prompt({ title: "When does " + cam.camera_id + " start?", body: S.incident.has_clock ? "A time of day, hh:mm:ss, by the cameras' clocks." : "Minutes and seconds from the first camera, m:ss.", ok: "Sync" }).then(function (text) {
        if (!text) { return; }
        var at = parseWhen(text);
        if (at === null) { window.UI.toast("That is not a time.", { problem: true }); return; }
        post({ action: "place", camera: cam.id, how: "hand", starts_at: at.toFixed(2) });
      });
    } else if (act === "match") {
      var pick = syncBox.querySelector("select[data-against='" + cam.id + "']");
      post({ action: "match", camera: cam.id, against: pick ? pick.value : "" });
    }
  });

  // The clip from the strip (Phase 6 chapter 5): drag across the ruler and
  // the clip box opens with that span.
  var banding = null;
  function hideBand() { if (band) { band.hidden = true; } }
  function showBand(a, b) {
    var shown = view();
    var low = Math.min(a, b), high = Math.max(a, b);
    band.style.left = percent(low, shown);
    band.style.width = (Math.max(0, Math.min(100, ((high - shown[0]) / (shown[1] - shown[0])) * 100)) - parseFloat(band.style.left)) + "%";
    band.hidden = false;
  }
  if (ticksBox && band) {
    ticksBox.addEventListener("mousedown", function (event) {
      if (event.button !== 0 || !S.incident.clips) { return; }
      var box = ticksBox.getBoundingClientRect();
      var shown = view();
      banding = { startX: event.clientX, box: box, shown: shown, from: shown[0] + ((event.clientX - box.left) / box.width) * (shown[1] - shown[0]), to: null };
      event.preventDefault();
    });
    document.addEventListener("mousemove", function (event) {
      if (!banding) { return; }
      var shown = banding.shown;
      banding.to = shown[0] + ((event.clientX - banding.box.left) / banding.box.width) * (shown[1] - shown[0]);
      if (Math.abs(event.clientX - banding.startX) > 3) { showBand(banding.from, banding.to); }
    });
    document.addEventListener("mouseup", function () {
      if (!banding) { return; }
      var done = banding;
      banding = null;
      if (done.to === null || Math.abs(done.to - done.from) < 1) { hideBand(); return; }
      var range = span();
      var low = Math.max(range[0], Math.min(done.from, done.to)), high = Math.min(range[1], Math.max(done.from, done.to));
      showBand(low, high);
      openClipBox({ id: "", at: low, until: high, text: "" });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && banding) { banding = null; hideBand(); }
    });
  }

  // Find (Phase 7 chapter 3) ------------------------------------------------------------------
  //
  // The box in the panel's head: the synced cameras' words, the events and
  // the memo, asked for as the person types; every hit a moment, and a press
  // seeks every camera there and brings the camera it was heard on to the
  // front with the sound. Never logged, never stored.
  var findBox = document.getElementById("find");
  var findHits = document.getElementById("find-hits");
  var findTimer = null;
  var findList = [];
  var findCurrent = -1;
  function lightParagraph(panel, index) {
    if (!panel || isNaN(index)) { return; }
    var blocks = panel.querySelectorAll("p, h3");
    var block = blocks[index];
    if (!block) { return; }
    block.classList.add("lit");
    block.scrollIntoView({ block: "center" });
    window.setTimeout(function () { block.classList.remove("lit"); }, 3000);
  }
  function drawFind(got) {
    findList = got.hits || [];
    findCurrent = -1;
    if (!findBox.value.trim()) { findHits.innerHTML = ""; if (layerStack[layerStack.length - 1] === "find") { closeLayer(); } return; }
    var head = findList.length + " moment" + (findList.length === 1 ? "" : "s") + " for \u201c" + escape(findBox.value.trim()) + "\u201d" +
      (got.skipped ? " <span class='muted'>(" + got.skipped + " camera" + (got.skipped === 1 ? "" : "s") + " not synced " + (got.skipped === 1 ? "is" : "are") + " not searched)</span>" : "");
    var html = "<p class='small muted find-head'>" + head + "</p>";
    findList.forEach(function (one, n) {
      var cam = one.camera ? cameraById(one.camera) : null;
      var who = one.kind === "words" ? "<span class='dot' style='--speaker: " + (cam ? cam.colour : "var(--muted)") + "'></span>" + escape(one.camera_id) : escape(one.who);
      html += "<div class='inc-find-hit' data-n='" + n + "'>" +
        "<span class='t mono'>" + (one.at === null ? "" : timeOfDay(one.at)) + "</span>" +
        "<span class='who small'>" + who + (one.kind === "words" && one.who ? " <span class='muted'>" + escape(one.who) + "</span>" : "") + "</span>" +
        "<span class='grow'>" + one.html + "<div class='muted small'>" + (one.kind === "words" ? "Said on " + escape(one.camera_id) + (one.who ? ", " + escape(one.who) : "") : (one.kind === "event" ? "An event on the chronology" : (one.kind === "note" ? "The office's note on a line of " + escape(one.camera_id) : "The memo"))) + "</div></span>" +
        (one.kind === "words" ? "<button type='button' class='tiny ghost' data-find-event='" + n + "' title='An event at this moment, with the line filled'>E</button>" : "") +
        "</div>";
    });
    findHits.innerHTML = html;
    var title = document.getElementById("find-title");
    if (title) { title.textContent = findList.length + " moment" + (findList.length === 1 ? "" : "s") + " for \u201c" + findBox.value.trim() + "\u201d"; }
    if (layerStack[layerStack.length - 1] !== "find") { openLayer("find"); }
  }
  function goToHit(n) {
    var one = findList[n];
    if (!one) { return; }
    findCurrent = n;
    Array.prototype.forEach.call(findHits.querySelectorAll(".inc-find-hit"), function (row) { row.classList.toggle("on", parseInt(row.dataset.n, 10) === n); });
    if (one.at !== null && one.at !== undefined) { seek(one.at); }
    if ((one.kind === "words" || one.kind === "note") && one.camera && cameraById(one.camera)) {
      if (layout === "focus") { setFocus(one.camera); }
      else {
        var entry = players[one.camera];
        if (entry && entry.tile && entry.tile.scrollIntoView) { entry.tile.scrollIntoView({ block: "nearest" }); }
        setSound(one.camera);
      }
    } else if (one.kind === "event") {
      showTab("chronology");
      if (one.event) { flashRow(one.event); }
    } else if (one.kind === "memo") {
      showTab("memo");
      lightParagraph(document.getElementById("panel-memo"), one.para);
    }
  }
  if (findBox && findHits) {
    findBox.addEventListener("input", function () {
      window.clearTimeout(findTimer);
      var asked = findBox.value.trim();
      if (asked.length < 2) { findHits.innerHTML = ""; findList = []; if (layerStack[layerStack.length - 1] === "find") { closeLayer(); } return; }
      findTimer = window.setTimeout(function () {
        fetch(C.find + "?q=" + encodeURIComponent(asked), { credentials: "same-origin" })
          .then(function (answer) { return answer.ok ? answer.json() : { hits: [] }; })
          .then(drawFind)
          .catch(function () { /* the next keystroke asks again */ });
      }, 300);
    });
    findBox.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { findBox.blur(); if (layerStack[layerStack.length - 1] === "find") { closeLayer(); } else { findBox.value = ""; findHits.innerHTML = ""; findList = []; } return; }
      if (event.key === "Enter") {
        event.preventDefault();
        if (!findList.length) { return; }
        var next = event.shiftKey ? (findCurrent <= 0 ? findList.length - 1 : findCurrent - 1) : (findCurrent + 1) % findList.length;
        goToHit(next);
        var row = findHits.querySelector(".inc-find-hit.on");
        if (row) { row.scrollIntoView({ block: "nearest" }); }
      }
    });
    findHits.addEventListener("click", function (event) {
      var add = event.target.closest("[data-find-event]");
      if (add) {
        var one = findList[parseInt(add.dataset.findEvent, 10)];
        if (one) { seek(one.at); openEventBox({ at: one.at, text: one.text, source: "words", camera: one.camera }); }
        return;
      }
      var row = event.target.closest(".inc-find-hit");
      if (row) { goToHit(parseInt(row.dataset.n, 10)); }
    });
  }
})();

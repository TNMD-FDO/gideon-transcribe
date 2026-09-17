// The Incident page (Phase 6 chapter 1): the cameras of one event in step.
//
// One clock runs the page: the moment on the Incident clock, in seconds from
// the Incident's zero. While playing it advances by the wall clock at the
// chosen speed, and every camera on the Wall is kept at (moment minus its
// start): a camera that has not started waits, one that has ended stops,
// and one that drifts is nudged by its rate or seeked outright. The camera
// with the sound is the one that is heard; the rest are muted. Nothing here
// is stored except through the act endpoint, and every answer redraws the
// page from the state it carries.

(function () {
  "use strict";

  var C = window.INCIDENT;
  var stateNode = document.getElementById("incident-state");
  if (!C || !stateNode) { return; }
  var S = JSON.parse(stateNode.textContent);

  var wallBox = document.getElementById("wall");
  var parkedBox = document.getElementById("parked");
  var lanesBox = document.getElementById("lanes");
  var ticksBox = document.getElementById("ticks");
  var strip = document.getElementById("strip");
  var clockBig = document.getElementById("inc-clock");
  var dateBox = document.getElementById("inc-date");
  var facts = document.getElementById("inc-facts");
  var clockSmall = document.getElementById("clock");
  var playButton = document.getElementById("play");
  var speedBox = document.getElementById("speed");
  var soundBox = document.getElementById("sound");
  var followBox = document.getElementById("follow");
  var trouble = document.getElementById("player-trouble");

  // The clock ------------------------------------------------------------------------

  var moment = C.at || 0;      // seconds on the Incident clock
  var playing = false;
  var speed = 1;
  var anchorMoment = 0;
  var anchorNow = 0;
  var soundCamera = null;      // the camera id with the sound
  var players = {};            // camera id -> { cam, video, tile, lines, loaded }
  var lines = {};              // camera id -> { segments, moments }
  var zoom = 0;                // seconds shown; 0 is all
  var dragging = null;

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

  function escape(text) {
    var box = document.createElement("div");
    box.textContent = text === null || text === undefined ? "" : text;
    return box.innerHTML;
  }

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
          if (window.UI) { window.UI.toast(got.said.error || "That did not work.", { problem: true }); }
          return got;
        }
        if (got.said.redirect) { window.location = got.said.redirect; return got; }
        if (got.said.said && window.UI) { window.UI.toast(got.said.said); }
        if (got.said.state) { take(got.said.state); }
        return got;
      });
  }

  function cameraById(id) {
    for (var i = 0; i < S.cameras.length; i += 1) { if (S.cameras[i].id === id) { return S.cameras[i]; } }
    return null;
  }

  function placedCameras() { return S.cameras.filter(function (one) { return one.starts_at !== null && one.placed; }); }
  function wallCameras() { return placedCameras().filter(function (one) { return one.on_wall; }); }
  function parkedCameras() { return placedCameras().filter(function (one) { return !one.on_wall; }); }

  // Taking a state: redraw everything but keep the clock where it is.
  function take(state) {
    S = state;
    drawHead();
    drawWall();
    drawStrip();
    drawCameras();
    drawDetails();
    if (soundCamera && !cameraById(soundCamera)) { soundCamera = null; }
    if (!soundCamera && wallCameras().length) { soundCamera = wallCameras()[0].id; }
    drawSoundChoice();
    tick();
  }

  // The head ----------------------------------------------------------------------------

  function drawHead() {
    var count = S.incident.count;
    facts.textContent = count + " camera" + (count === 1 ? "" : "s") + " · " + S.incident.span_words;
    dateBox.textContent = S.incident.has_clock ? S.incident.clock_date : "no camera clock; times are from the first camera";
  }

  // The Wall ----------------------------------------------------------------------------

  function tileFor(cam) {
    var tile = document.createElement("div");
    tile.className = "inc-tile";
    tile.dataset.camera = cam.id;
    tile.style.setProperty("--speaker", cam.colour);
    tile.innerHTML =
      "<div class='inc-tile-head'><span class='dot'></span><b title='" + escape(cam.title).replace(/'/g, "&#39;") + "'>" + escape(cam.camera_id) + "</b>" +
      "<span class='pill " + escape(cam.placed_tone) + " small' title='" + escape(cam.placed_words) + "'>" + escape(cam.placed_words) + "</span>" +
      "<label class='small sound-pick'><input type='radio' name='sound-tile' value='" + cam.id + "'> Sound</label></div>" +
      "<div class='inc-well'>" + (cam.media_url ? "<video preload='metadata' playsinline muted></video>" : "<p class='preparing small'>Playback is being prepared.</p>") +
      "<div class='state' hidden></div></div>" +
      "<div class='inc-lines'><div class='said'><span class='who'></span> <span class='txt muted'>…</span></div><div class='cam muted' hidden></div></div>";
    var video = tile.querySelector("video");
    if (video) {
      video.src = cam.media_url;
      video.addEventListener("error", function () { trouble.textContent = "One of the cameras could not be played: " + cam.camera_id + "."; trouble.hidden = false; });
    }
    tile.querySelector("input[type=radio]").addEventListener("change", function () { setSound(cam.id); });
    tile.querySelector(".inc-well").addEventListener("click", function (event) {
      if (event.target.closest("label")) { return; }
      if (playing) { pause(); } else { play(); }
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
        pill.textContent = cam.placed_words;
      }
    });
    // In the Wall's order.
    wanted.forEach(function (cam) { wallBox.appendChild(players[cam.id].tile); });
    wallBox.className = "inc-wall count-" + Math.min(9, wanted.length);
    if (!wanted.length) {
      wallBox.innerHTML = "<p class='muted' style='padding: 20px'>No camera is placed yet. Place one on the Cameras tab, and it plays here.</p>";
    }
    drawParked();
  }

  function drawParked() {
    var rest = parkedCameras();
    var unplaced = S.cameras.filter(function (one) { return !(one.starts_at !== null && one.placed); });
    var html = "";
    if (rest.length) {
      html += "<span class='muted'>" + rest.length + " more camera" + (rest.length === 1 ? "" : "s") + " on the strip, not on the wall:</span>";
      rest.forEach(function (cam) {
        html += "<span class='tile' style='--speaker: " + cam.colour + "'><span class='dot'></span>" + escape(cam.camera_id) +
          " <button type='button' class='tiny' data-swap='" + cam.id + "'>Swap in</button></span>";
      });
    }
    if (unplaced.length) {
      html += "<span class='muted'>" + unplaced.length + " not placed:</span>";
      unplaced.forEach(function (cam) {
        html += "<span class='tile' style='--speaker: " + cam.colour + "'><span class='dot'></span>" + escape(cam.camera_id) +
          " <button type='button' class='tiny' data-place='" + cam.id + "'>Place</button></span>";
      });
    }
    if (rest.length || unplaced.length) {
      html += "<span class='muted'>" + S.incident.wall_size + " play at once; the office sets how many.</span>";
    }
    parkedBox.innerHTML = html;
  }

  parkedBox.addEventListener("click", function (event) {
    var swap = event.target.closest("[data-swap]");
    if (swap) { swapIn(swap.dataset.swap); return; }
    var place = event.target.closest("[data-place]");
    if (place) { showTab("cameras"); flashRow(place.dataset.place); }
  });

  function swapIn(id) {
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
    if (said) {
      who.textContent = said.speaker ? said.speaker + ":" : "";
      who.style.color = said.colour || "";
      txt.textContent = said.text;
      txt.classList.remove("muted");
    } else {
      who.textContent = "";
      txt.textContent = local < 0 || local > entry.cam.length ? "" : "…";
      txt.classList.add("muted");
    }
    var seen = lineAt(got.moments, local);
    var cam = box.querySelector(".cam");
    cam.hidden = !seen;
    if (seen) { cam.textContent = seen.text; }
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
        // Nudge: a little slower when ahead, a little faster when behind.
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
      var radio = entry.tile.querySelector("input[type=radio]");
      if (radio) { radio.checked = one === id; }
    });
    if (soundBox.value !== id) { soundBox.value = id; }
  }

  function drawSoundChoice() {
    soundBox.innerHTML = "";
    wallCameras().forEach(function (cam) {
      var option = document.createElement("option");
      option.value = cam.id;
      option.textContent = cam.camera_id;
      soundBox.appendChild(option);
    });
    if (soundCamera) { setSound(soundCamera); }
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
  soundBox.addEventListener("change", function () { setSound(soundBox.value); });

  document.addEventListener("keydown", function (event) {
    if (event.target.closest("input, textarea, select") || event.altKey || event.ctrlKey || event.metaKey) { return; }
    if (event.key === " ") { event.preventDefault(); if (playing) { pause(); } else { play(); } }
    else if (event.key === "ArrowLeft") { event.preventDefault(); seek(now() - 5); }
    else if (event.key === "ArrowRight") { event.preventDefault(); seek(now() + 5); }
    else if (event.key === "b" || event.key === "B") { seek(now() - 3); if (!playing) { play(); } }
  });

  // The strip ---------------------------------------------------------------------------

  function view() {
    var range = span();
    if (!zoom || zoom >= range[1] - range[0]) { return range; }
    var m = now();
    var from = Math.max(range[0], Math.min(m - zoom / 2, range[1] - zoom));
    return [from, from + zoom];
  }

  function percent(at, shown) {
    return Math.max(0, Math.min(100, ((at - shown[0]) / (shown[1] - shown[0])) * 100)) + "%";
  }

  function drawStrip() {
    var shown = view();
    var ticks = "";
    var count = 6;
    for (var i = 0; i <= count; i += 1) {
      ticks += "<span>" + timeOfDay(shown[0] + ((shown[1] - shown[0]) * i) / count) + "</span>";
    }
    ticksBox.innerHTML = ticks;
    var html = "";
    S.cameras.forEach(function (cam) {
      var placed = cam.starts_at !== null && cam.placed;
      var start = placed ? cam.starts_at : (S.incident.span_low || 0);
      var width = ((cam.length) / (shown[1] - shown[0])) * 100;
      html += "<div class='lane" + (placed ? "" : " unplaced") + "' data-camera='" + cam.id + "' style='--speaker: " + cam.colour + "'>" +
        "<div class='head' title='" + escape(cam.title).replace(/'/g, "&#39;") + ", " + escape(cam.placed_words) + "'><span class='dot'></span><span class='name'>" + escape(cam.camera_id) + "</span></div>" +
        "<div class='track'><i class='" + (cam.on_wall ? "" : "thin") + (placed ? "" : " ghost") + "' draggable='false' style='left: " + percent(start, shown) + "; width: " + Math.max(0.3, width) + "%' title='" + timeOfDay(start) + " to " + timeOfDay(start + cam.length) + "'></i>" +
        "<span class='playhead'></span></div></div>";
    });
    html += "<div class='lane events'><div class='head'><span class='name muted'>Events</span></div><div class='track'><span class='playhead'></span></div></div>";
    lanesBox.innerHTML = html;
    movePlayheads(now());
  }

  function movePlayheads(m) {
    var shown = view();
    if (zoom && (m < shown[0] || m > shown[1])) { drawStrip(); return; }
    var left = percent(m, shown);
    Array.prototype.forEach.call(lanesBox.querySelectorAll(".playhead"), function (head) { head.style.left = left; });
  }

  strip.addEventListener("click", function (event) {
    var zoomButton = event.target.closest("[data-zoom]");
    if (zoomButton) {
      zoom = parseInt(zoomButton.dataset.zoom, 10) || 0;
      Array.prototype.forEach.call(strip.querySelectorAll("[data-zoom]"), function (one) { one.classList.toggle("on", one === zoomButton); });
      drawStrip();
      return;
    }
    if (dragging && dragging.moved) { return; }
    var track = event.target.closest(".track");
    if (!track) { return; }
    var shown = view();
    var box = track.getBoundingClientRect();
    var at = shown[0] + ((event.clientX - box.left) / box.width) * (shown[1] - shown[0]);
    var lane = track.closest(".lane");
    if (lane && lane.dataset.camera) {
      var cam = cameraById(lane.dataset.camera);
      if (cam && cam.starts_at !== null && cam.placed && !cam.on_wall) { swapIn(cam.id); }
    }
    seek(at);
  });

  // Drag a bar to place the camera by hand.
  lanesBox.addEventListener("mousedown", function (event) {
    var bar = event.target.closest(".track i");
    if (!bar || C.role === "admin" && false) { return; }
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
    var ask = window.UI.confirm({
      title: "Place " + done.cam.camera_id + " by hand?",
      body: "Moved " + (moved >= 0 ? "+" : "") + moved.toFixed(1) + " s, to start at " + timeOfDay(done.at) + ". From then on it reads Placed by hand.",
      ok: "Place it"
    });
    ask.then(function (yes) {
      if (yes) { post({ action: "place", camera: done.cam.id, how: "hand", starts_at: done.at.toFixed(2) }); }
      else { drawStrip(); }
    });
  });

  // The Cameras tab ----------------------------------------------------------------------

  function placeControls(cam) {
    var html = "";
    if (cam.has_clock) { html += "<button type='button' class='tiny' data-act='place' data-how='clock' data-camera='" + cam.id + "'>From its clock</button> "; }
    if (cam.file_time && S.incident.has_clock) { html += "<button type='button' class='tiny' data-act='place' data-how='file' data-camera='" + cam.id + "' title='The file says " + escape(cam.file_time) + "'>From its file</button> "; }
    if (S.incident.sound_match) {
      var others = placedCameras().filter(function (one) { return one.id !== cam.id; });
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
      html += "<tr data-row='" + cam.id + "'><td><b style='color: " + cam.colour + "'>" + escape(cam.camera_id) + "</b><div class='muted small'>" + escape(cam.title) + "</div>" +
        (cam.clock ? "<div class='small'><span class='pill " + escape(cam.clock_tone) + " small'>" + escape(cam.clock) + "</span></div>" : "") +
        (cam.file_time ? "<div class='muted small'>the file says " + escape(cam.file_time) + "</div>" : "") + "</td>" +
        "<td class='mono'>" + (placed ? timeOfDay(cam.starts_at) : "—") + "</td>" +
        "<td><span class='pill " + escape(cam.placed_tone) + " small'>" + escape(cam.placed_words) + "</span>" +
        (cam.placed_by ? "<div class='muted small'>by " + escape(cam.placed_by) + "</div>" : "") + matchLine(cam) + "</td>" +
        "<td class='acts'><details class='inc-place'><summary class='small'>" + (placed ? "Adjust" : "Place") + "</summary><div class='inc-place-box'>" + placeControls(cam) + "</div></details>" +
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

  var pollTimer = null;
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
      if (act === "place") { post({ action: "place", camera: cam.id, how: button.dataset.how }); }
      else if (act === "nudge") {
        var from = cam.starts_at !== null && cam.placed ? cam.starts_at : (S.incident.span_low || 0);
        post({ action: "place", camera: cam.id, how: "hand", starts_at: (from + parseFloat(button.dataset.by)).toFixed(2) });
      } else if (act === "type") {
        var asked = window.UI.prompt({ title: "When does " + cam.camera_id + " start?", body: S.incident.has_clock ? "A time of day, hh:mm:ss, by the cameras' clocks." : "Minutes and seconds from the first camera, m:ss.", ok: "Place it" });
        asked.then(function (text) {
          if (!text) { return; }
          var parts = String(text).trim().split(":").map(function (one) { return parseInt(one, 10) || 0; });
          var seconds = parts.reduce(function (sum, one) { return sum * 60 + one; }, 0);
          var at = S.incident.has_clock ? seconds - S.incident.clock_zero : seconds;
          if (S.incident.has_clock) { while (at < -43200) { at += 86400; } while (at > 43200) { at -= 86400; } }
          post({ action: "place", camera: cam.id, how: "hand", starts_at: at.toFixed(2) });
        });
      } else if (act === "match") {
        var pick = document.querySelector("select[data-against='" + cam.id + "']");
        post({ action: "match", camera: cam.id, against: pick ? pick.value : "" });
      } else if (act === "remove") {
        var ask = window.UI.confirm({ title: "Remove " + cam.camera_id + " from this incident?", body: "The recording stays in the case; only its place here goes.", ok: "Remove" });
        ask.then(function (yes) { if (yes) { post({ action: "remove", camera: cam.id }); } });
      }
      return;
    }
    if (event.target.closest("#add-cameras")) { document.getElementById("add-box").hidden = false; return; }
    if (event.target.closest("#rename-incident")) {
      var renamed = window.UI.prompt({ title: "Rename this incident", body: "", ok: "Rename", value: S.incident.name });
      renamed.then(function (name) { if (name) { post({ action: "rename", name: name }).then(function () { document.getElementById("inc-title").firstChild.textContent = S.incident.name + " "; }); } });
      return;
    }
    if (event.target.closest("#delete-incident")) {
      var sure = window.UI.confirm({ title: "Delete this incident?", body: "Its placements go; no recording is deleted.", ok: "Delete incident", danger: true });
      sure.then(function (yes) { if (yes) { post({ action: "delete" }); } });
    }
  });

  var addBox = document.getElementById("add-box");
  document.getElementById("add-cancel").addEventListener("click", function () { addBox.hidden = true; });
  document.getElementById("add-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var chosen = Array.prototype.map.call(addBox.querySelectorAll("input:checked"), function (one) { return one.value; });
    addBox.hidden = true;
    if (chosen.length) { post({ action: "add", recordings: chosen }).then(function () { window.location.reload(); }); }
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
    html += "</dl><h3 style='font-size: var(--t-body); margin: 14px 0 6px'>Each camera's stamp</h3><dl class='kv'>";
    S.cameras.forEach(function (cam) {
      html += "<dt>" + escape(cam.camera_id) + "</dt><dd>" + (cam.clock ? escape(cam.clock) : "no stamp read") + (cam.file_time ? "; the file says " + escape(cam.file_time) : "") + "</dd>";
    });
    html += "</dl>";
    box.innerHTML = html;
  }

  // Tabs ------------------------------------------------------------------------------------

  function showTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".inc-work .tab"), function (tab) { tab.classList.toggle("on", tab.dataset.panel === name); });
    document.getElementById("panel-cameras").hidden = name !== "cameras";
    document.getElementById("panel-details").hidden = name !== "details";
  }
  Array.prototype.forEach.call(document.querySelectorAll(".inc-work .tab"), function (tab) {
    tab.addEventListener("click", function () { showTab(tab.dataset.panel); });
  });

  // Go ---------------------------------------------------------------------------------------

  take(S);
  seek(moment);
})();

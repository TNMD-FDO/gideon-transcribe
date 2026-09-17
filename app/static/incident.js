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
  var eventBox = document.getElementById("event-box");

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
  var dragging = null;
  var pollTimer = null;
  var currentEventId = null;

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
  function wallCameras() { return placedCameras().filter(function (one) { return one.on_wall; }); }
  function parkedCameras() { return placedCameras().filter(function (one) { return !one.on_wall; }); }

  // Taking a state: redraw everything but keep the clock where it is.
  function take(state) {
    S = state;
    S.events = S.events || [];
    drawHead();
    drawWall();
    drawStrip();
    drawChronology();
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
    var events = S.events.length;
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
    tile.innerHTML =
      "<div class='inc-tile-head'><span class='dot'></span><b title='" + quoted(cam.title) + "'>" + escape(cam.camera_id) + "</b>" +
      "<span class='pill " + escape(cam.placed_tone) + " small' title='" + quoted(cam.placed_words) + "'>" + escape(cam.placed_words) + "</span>" +
      "<label class='small sound-pick'><input type='radio' name='sound-tile' value='" + cam.id + "'> Sound</label></div>" +
      "<div class='inc-well'>" + (cam.media_url ? "<video preload='metadata' playsinline muted></video>" : "<p class='preparing small'>Playback is being prepared.</p>") +
      "<div class='state' hidden></div></div>" +
      "<div class='inc-lines'>" +
      "<div class='said'><span class='who'></span> <span class='txt muted'>…</span> <button type='button' class='tiny ghost add-line' data-kind='words' title='Add this line as an event' hidden>+ event</button></div>" +
      "<div class='cam-line' hidden><span class='cam muted'></span> <button type='button' class='tiny ghost add-line' data-kind='camera' title='Add what the camera showed as an event'>+ event</button></div></div>";
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
        pill.textContent = cam.placed_words;
      }
    });
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
    var seen = lineAt(got.moments, local);
    var camLine = box.querySelector(".cam-line");
    camLine.hidden = !seen;
    if (seen) { camLine.querySelector(".cam").textContent = seen.text; }
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
    if (event.altKey || event.ctrlKey || event.metaKey) { return; }
    if (event.key === "Escape" && !eventBox.hidden) { closeEventBox(); return; }
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
    var m = now();
    var from = Math.max(range[0], Math.min(m - zoom / 2, range[1] - zoom));
    return [from, from + zoom];
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
    var html = "";
    S.cameras.forEach(function (cam) {
      var placed = cam.starts_at !== null && cam.placed;
      var start = placed ? cam.starts_at : (S.incident.span_low || 0);
      var width = ((cam.length) / (shown[1] - shown[0])) * 100;
      html += "<div class='lane" + (placed ? "" : " unplaced") + "' data-camera='" + cam.id + "' style='--speaker: " + cam.colour + "'>" +
        "<div class='head' title='" + quoted(cam.title + ", " + cam.placed_words) + "'><span class='dot'></span><span class='name'>" + escape(cam.camera_id) + "</span></div>" +
        "<div class='track'><i class='" + (cam.on_wall ? "" : "thin") + (placed ? "" : " ghost") + "' draggable='false' style='left: " + percent(start, shown) + "; width: " + Math.max(0.3, width) + "%' title='" + timeOfDay(start) + " to " + timeOfDay(start + cam.length) + "'></i>" +
        "<span class='playhead'></span></div></div>";
    });
    html += "<div class='lane events'><div class='head'><span class='name muted'>Events</span></div><div class='track'>" + eventMarks(shown) + "<span class='playhead'></span></div></div>";
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
      if (cam && cam.starts_at !== null && cam.placed && !cam.on_wall) { swapIn(cam.id); }
    }
    seek(at);
  });

  // Drag a bar to place the camera by hand.
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
      body: "Moved " + (moved >= 0 ? "+" : "") + moved.toFixed(1) + " s, to start at " + timeOfDay(done.at) + ". From then on it reads Placed by hand.",
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
    var kept = S.events.filter(function (one) { return !one.proposed; });
    var proposed = S.events.filter(function (one) { return one.proposed; });
    var html = "<div class='row' style='gap: 8px; align-items: center; margin-bottom: 8px'>" +
      "<p class='lead grow' style='margin: 0'>" + (kept.length ? kept.length + " event" + (kept.length === 1 ? "" : "s") + " on the chronology." : "No events yet. Add one at the moment you are watching, or from a line under a camera.") + "</p>" +
      "<button type='button' class='small primary' id='add-event-here'>Add event here</button></div>";
    if (kept.length) {
      html += "<table class='inc-events'><tbody>";
      kept.forEach(function (one) {
        html += "<tr data-event='" + one.id + "'><td class='t'><a class='cite' href='#' data-at='" + one.at + "'>" + timeOfDay(one.at) + "</a>" +
          (one.until ? "<div class='muted small'>to " + timeOfDay(one.until) + "</div>" : "") + "</td>" +
          "<td>" + escape(one.text) + (one.seen_on ? "<div class='muted small'>Seen on " + escape(one.seen_on) + "</div>" : "") + "</td>" +
          "<td><span class='pill small" + (one.source === "person" ? " person" : "") + "'>" + escape(one.source_words) + "</span></td>" +
          "<td class='acts'><button type='button' class='tiny ghost' data-edit='" + one.id + "'>Edit</button></td></tr>";
      });
      html += "</tbody></table>";
    }
    if (proposed.length) {
      html += "<h3 style='font-size: var(--t-heading); margin: 18px 0 6px'>Proposed by the assistant <span class='muted small' style='font-weight: 400'>nothing joins the chronology until you accept it</span></h3>";
      html += "<table class='inc-events'><tbody>";
      proposed.forEach(function (one) {
        html += "<tr data-event='" + one.id + "' class='proposed'><td class='t'><a class='cite' href='#' data-at='" + one.at + "'>" + timeOfDay(one.at) + "</a></td>" +
          "<td>" + escape(one.text) + "</td><td><span class='pill warn small'>Proposed</span></td><td class='acts'></td></tr>";
      });
      html += "</tbody></table>";
    }
    html += "<p class='muted small' style='margin: 10px 0 0'>A time on this list plays every camera from there. E adds an event at the moment being watched.</p>";
    box.innerHTML = html;
    currentEventId = null;
    markCurrentEvent(now());
  }

  document.getElementById("panel-chronology").addEventListener("click", function (event) {
    var cite = event.target.closest(".cite");
    if (cite) { event.preventDefault(); seek(parseFloat(cite.dataset.at)); return; }
    var edit = event.target.closest("[data-edit]");
    if (edit) { var found = eventById(edit.dataset.edit); if (found) { openEventBox(found); } return; }
    if (event.target.closest("#add-event-here")) { openEventBox({ at: now() }); }
  });

  document.getElementById("add-event").addEventListener("click", function () { openEventBox({ at: now() }); });

  // The event box: one form for a new Event and for Edit.
  function openEventBox(given) {
    var at = given.at !== undefined ? given.at : now();
    eventBox.hidden = false;
    eventBox.elements.event.value = given.id || "";
    eventBox.elements.source.value = given.source || "person";
    eventBox.elements.camera.value = given.camera || "";
    eventBox.elements.when.value = timeOfDay(at);
    eventBox.elements.until_when.value = given.until ? timeOfDay(given.until) : "";
    eventBox.elements.text.value = given.text || "";
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
    eventBox.hidden = true;
    eventBox.reset();
  }

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
      cameras_given: "yes",
      cameras: Array.prototype.map.call(eventBox.querySelectorAll("input[name=cameras]:checked"), function (one) { return one.value; })
    };
    post(fields).then(function (got) { if (got.ok) { closeEventBox(); showTab("chronology"); } });
  });
  document.getElementById("event-cancel").addEventListener("click", closeEventBox);
  document.getElementById("event-remove").addEventListener("click", function () {
    var id = eventBox.elements.event.value;
    if (!id) { return; }
    window.UI.confirm({ title: "Remove this event?", body: "It leaves the chronology and the exports.", ok: "Remove", danger: true }).then(function (yes) {
      if (yes) { post({ action: "event_remove", event: id }).then(closeEventBox); }
    });
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
        window.UI.prompt({ title: "When does " + cam.camera_id + " start?", body: S.incident.has_clock ? "A time of day, hh:mm:ss, by the cameras' clocks." : "Minutes and seconds from the first camera, m:ss.", ok: "Place it" }).then(function (text) {
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
    if (event.target.closest("#add-cameras")) { document.getElementById("add-box").hidden = false; return; }
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
    html += "<dt>Events</dt><dd>" + S.events.length + "</dd>";
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
    ["chronology", "cameras", "details"].forEach(function (one) { document.getElementById("panel-" + one).hidden = one !== name; });
    if (name === "chronology") { currentEventId = null; markCurrentEvent(now()); }
  }
  Array.prototype.forEach.call(document.querySelectorAll(".inc-work .tab"), function (tab) {
    tab.addEventListener("click", function () { showTab(tab.dataset.panel); });
  });

  // Go ---------------------------------------------------------------------------------------

  take(S);
  showTab(placedCameras().length ? "chronology" : "cameras");
  seek(moment);
  if (eventWords) { openEventBox({ at: moment, text: eventWords, source: "words" }); }
})();

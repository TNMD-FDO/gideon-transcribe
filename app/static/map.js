// The Map tab (Phase 12 chapter 1; the drawing docs/spec/mockups/phase-12-map.html):
// every camera's path from the file beside its video, on one clock, with the
// video a press away. One reading of map.json; the street map from the file
// the Admin placed, drawn by the vendored library, or plain ground without it;
// the clock as the incident page runs it; the Preview as the player.
(function () {
  "use strict";
  var host = document.getElementById("case-map");
  if (!host || !window.maplibregl) { return; }
  // The incident page's map pane (Phase 12 chapter 5): the same script on a
  // second host, following that page's clock (window.IncidentClock) instead
  // of running its own transport, list and strip. A press on the map seeks
  // the incident's clock and brings the camera to the front of the wall.
  var INC = host.dataset.clock === "incident";
  function incClock() { return INC && window.IncidentClock ? window.IncidentClock : null; }

  function esc(text) { return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function hms(seconds) { seconds = Math.round(seconds); seconds = ((seconds % 86400) + 86400) % 86400; var h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s; }
  function hm(seconds) { return hms(seconds).slice(0, 5); }
  function elapsed(seconds) { seconds = Math.max(0, Math.round(seconds)); var m = Math.floor(seconds / 60), s = seconds % 60; return m + ":" + (s < 10 ? "0" : "") + s; }
  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
  function cookie(name) { var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)")); return m ? decodeURIComponent(m[1]) : ""; }
  // A camera's colour (v1.179.0): the server names the light palette's hex,
  // the page paints its own token so dark reads.
  var PAINT = { "#1f6fb2": 1, "#c2410c": 2, "#2e7d32": 3, "#8e24aa": 4, "#00838f": 5, "#ad1457": 6, "#6d4c41": 7, "#546e7a": 8 };
  function paint(hex) { var n = PAINT[String(hex || "").toLowerCase()]; return n ? "var(--sp" + n + ")" : "var(--muted)"; }
  function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888888"; }
  function colourOf(cam) { var n = PAINT[String(cam.colour || "").toLowerCase()]; return token(n ? "--sp" + n : "--muted"); }
  function dayWords(date) { if (!date) { return ""; } var p = date.split("-"); var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]; return parseInt(p[2], 10) + " " + months[parseInt(p[1], 10) - 1] + " " + p[0]; }
  function remember(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* no storage */ } }
  function recall(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function postForm(url, form) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": cookie("csrftoken") }, body: form })
      .then(function (a) { return a.json().then(function (told) { if (!a.ok) { throw new Error(told.error || "That did not work."); } return told; }); });
  }
  function postJson(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") }, body: JSON.stringify(body || {}) })
      .then(function (a) { return a.json().then(function (told) { if (!a.ok) { throw new Error(told.error || "That did not work."); } return told; }); });
  }
  function toast(words, bad) { if (window.UI && window.UI.toast) { window.UI.toast(words, bad ? "bad" : ""); } }

  var GAP = 15;          // seconds between fixes that reads as "no fix"
  var STEP = 200;        // the tick, as the incident page's
  var EVENT_KINDS = ["camera", "lights", "siren", "mic", "bookmark", "notes"];
  var S = {
    told: null, cams: [], byId: {}, day: "", loaded: false,
    moment: 0, playing: false, speed: 4, anchorMoment: 0, anchorNow: 0,
    following: null, selected: null, lit: null, inView: {},
    show: recall("map-show") || "trails", faint: recall("map-faint") !== "0", large: recall("map-large") === "1",
    events: {}, incident: host.dataset.incident || "", scope: null,
    readingsOpen: {}, asking: false,
    // Chapter 6: the cameras a person has unticked (hidden from the map, the
    // strip and the events; still listed), the one row opened, the circle.
    hidden: {}, open: null, circle: null, hits: null
  };
  var NEAR = 50;         // metres: the circle's first radius, as the server's together() counts "near"
  var CASE = host.dataset.case || "";
  try { (JSON.parse(recall("map-hidden-" + CASE) || "[]") || []).forEach(function (id) { S.hidden[id] = true; }); } catch (e) { /* nothing hidden */ }
  function rememberHidden() { remember("map-hidden-" + CASE, JSON.stringify(Object.keys(S.hidden))); }
  // Ticked means drawn. The incident page's pane has no list to untick from,
  // so it draws every camera of its incident.
  function shown(cam) { return INC || !S.hidden[cam.id]; }
  function shownCams() { return dayCams().filter(shown); }
  // The name first (chapter 6): the wearer as the file gives it, else the unit.
  function nameOf(cam) { return cam.wearer || cam.unit || cam.title; }
  function nameHtml(cam) { return esc(nameOf(cam)) + (cam.source === "car" && cam.wearer ? " <small class='muted'>vehicle</small>" : ""); }
  var circleMarkers = null;
  EVENT_KINDS.forEach(function (k) { S.events[k] = recall("map-ev-" + k) !== "0" || k === "notes"; });
  if (recall("map-ev-bookmark") === null) { S.events.bookmark = false; }
  if (INC) { S.large = recall("map-inc-large") === "1"; }

  var map = null, mapReady = false, markers = {}, trailIndex = {}, el = {};

  // The reading ------------------------------------------------------------------
  function load(quiet) {
    var url = host.dataset.json + (S.day ? "?day=" + encodeURIComponent(S.day) : "");
    if (!quiet) { host.innerHTML = "<p class='muted small'>Reading the paths...</p><div class='skeleton' aria-hidden='true'><i></i><i></i><i></i></div>"; }
    return fetch(url, { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      S.told = told; S.day = told.day || ""; S.loaded = true;
      prepare();
      // The address may name a camera or an incident on another day than
      // the one the server chose: decided once, before the first drawing.
      if (!S.dayChosen) { S.dayChosen = true; var wanted = wantedDay(); if (wanted) { S.day = wanted; } }
      if (!quiet || !map) { layout(); } else { drawList(); drawStrip(); tick(); refreshLayers(); }
    }).catch(function () { host.innerHTML = "<p class='muted small'>The paths could not be read. Reload the page.</p>"; });
  }

  function prepare() {
    S.cams = []; S.byId = {};
    var twinsOf = {};
    (S.told.cameras || []).forEach(function (cam) {
      cam.fixes = (cam.fixes || []).slice().sort(function (a, b) { return a[0] - b[0]; });
      cam.segments = [];
      var run = [];
      for (var i = 0; i < cam.fixes.length; i++) {
        var f = cam.fixes[i];
        if (run.length && (f[0] - run[run.length - 1][0] > GAP || inGap(cam, run[run.length - 1][0], f[0]))) { cam.segments.push(run); run = []; }
        run.push(f);
      }
      if (run.length) { cam.segments.push(run); }
      cam.onClock = !!(cam.zero && cam.zero.second !== null && cam.zero.second !== undefined);
      cam.date = cam.zero ? cam.zero.date : (cam.day_only || "");
      cam.streams = [];
      if (cam.twin_of) { (twinsOf[cam.twin_of] = twinsOf[cam.twin_of] || []).push(cam); return; }
      S.cams.push(cam); S.byId[cam.id] = cam;
    });
    Object.keys(twinsOf).forEach(function (id) { if (S.byId[id]) { S.byId[id].streams = twinsOf[id]; } });
    S.scope = null;
    if (S.incident) {
      (S.told.incidents || []).forEach(function (inc) { if (inc.id === S.incident) { S.scope = inc; } });
    }
  }
  function inGap(cam, a, b) { return (cam.gaps || []).some(function (g) { return g[0] >= a && g[1] <= b && g[1] - g[0] > GAP / 2; }); }
  function scoped(cam) { return !S.scope || S.scope.cameras.indexOf(cam.id) >= 0; }
  function ofDay(cam) { return cam.onClock && cam.date === S.day; }
  function dayCams() { return S.cams.filter(function (c) { return ofDay(c) && scoped(c); }); }

  // The clock --------------------------------------------------------------------
  function now() {
    var ic = incClock();
    if (ic) { var t = ic.now(); if (t !== null && t !== undefined && !isNaN(t)) { return t; } }
    if (!S.playing) { return S.moment; }
    return S.anchorMoment + ((performance.now() - S.anchorNow) / 1000) * S.speed;
  }
  function span() {
    var cams = dayCams();
    if (!cams.length) { return [0, 60]; }
    var low = Infinity, high = -Infinity;
    cams.forEach(function (c) { low = Math.min(low, c.zero.second); high = Math.max(high, c.zero.second + (c.length || 0)); });
    if (S.scope && S.scope.cameras.length) { /* the incident's own span is its cameras' */ }
    return [Math.max(0, low - 60), high + 60];
  }
  var tickedAt = null, tickedKey = "";
  function tickKey() { return [S.playing ? 1 : 0, S.speed, S.show, S.following || "", S.selected ? S.selected.key : "", S.lit || ""].join("|"); }
  function tickIfMoved() {
    if (document.hidden || !S.loaded) { return; }
    followPreview();
    var key = tickKey();
    if (!S.playing && now() === tickedAt && key === tickedKey) { return; }
    tickedKey = key; tick();
  }
  window.setInterval(tickIfMoved, STEP);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) { tick(); } });
  function play() { var ic = incClock(); if (ic) { ic.play(); tick(); return; } S.anchorMoment = now(); S.anchorNow = performance.now(); S.playing = true; drawTransport(); tick(); }
  function pause() { var ic = incClock(); if (ic) { ic.pause(); tick(); return; } S.moment = now(); S.playing = false; drawTransport(); tick(); }
  function seek(at, fromPreview) {
    var ic = incClock();
    if (ic) { ic.seek(at); tick(); return; }
    var range = span();
    at = Math.max(range[0], Math.min(range[1], at));
    if (S.playing) { S.anchorMoment = at; S.anchorNow = performance.now(); } else { S.moment = at; }
    if (!fromPreview && S.following && window.Preview && window.Preview.seek) {
      var cam = S.byId[S.following];
      if (cam && cam.onClock) { window.Preview.seek(Math.max(0, at - cam.zero.second)); }
    }
    tick();
  }

  // Where a camera was ------------------------------------------------------------
  function positionAt(cam, local) {
    var fx = cam.fixes;
    if (!fx.length || local < fx[0][0]) { return null; }
    if (local > (cam.length || fx[fx.length - 1][0])) { return { lat: fx[fx.length - 1][1], lon: fx[fx.length - 1][2], ended: true }; }
    var lo = 0, hi = fx.length - 1;
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (fx[mid][0] <= local) { lo = mid; } else { hi = mid - 1; } }
    var a = fx[lo], b = fx[lo + 1];
    for (var i = 0; i < (cam.gaps || []).length; i++) { var g = cam.gaps[i]; if (local >= g[0] && local < g[1]) { return { lat: a[1], lon: a[2], nofix: true }; } }
    if (!b || b[0] - a[0] > GAP) { return { lat: a[1], lon: a[2], nofix: !!b && b[0] - a[0] > GAP }; }
    var k = (local - a[0]) / (b[0] - a[0]);
    return { lat: a[1] + (b[1] - a[1]) * k, lon: a[2] + (b[2] - a[2]) * k, index: lo };
  }
  function flagsAt(cam, local) {
    var out = {};
    (cam.marks || []).forEach(function (m) { if (m[0] <= local) { out[m[1]] = m[2]; } });
    return out;
  }
  function lastIndex(cam, local) {
    var fx = cam.fixes, lo = 0, hi = fx.length - 1;
    if (!fx.length || local < fx[0][0]) { return -1; }
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (fx[mid][0] <= local) { lo = mid; } else { hi = mid - 1; } }
    return lo;
  }

  // The page ---------------------------------------------------------------------
  function layout() {
    if (INC) { layoutPane(); return; }
    host.classList.toggle("large", S.large);
    host.innerHTML =
      "<div class='map-lead'>" +
        "<div class='map-lead-left'>" + dayChips() +
          "<div class='map-show'><span class='muted small'>Show</span><span class='seg' id='map-show'>" +
            seg("markers", "Markers only") + seg("trails", "Trails") + seg("whole", "Whole paths") + "</span>" +
          "<span class='map-ev'><label title='The whole path drawn faint under the markers and trails'><input type='checkbox' id='map-faint'" + (S.faint ? " checked" : "") + "> faint paths under</label></span>" +
          "<span class='muted small'>Events</span><span class='map-ev' id='map-events'>" + EVENT_KINDS.map(evTick).join("") + "</span></div>" +
        "</div>" +
        "<div class='transport' id='map-transport'></div>" +
      "</div>" +
      "<div class='map-wrap' id='map-wrap'><div class='map-pane' id='map-pane'></div>" +
        "<div class='map-list' id='map-list'></div>" +
        "<div class='map-bar' id='map-bar'></div></div>" +
      "<div class='map-strip inc-strip' id='map-strip'></div>";
    el.transport = host.querySelector("#map-transport"); el.pane = host.querySelector("#map-pane");
    el.list = host.querySelector("#map-list"); el.strip = host.querySelector("#map-strip"); el.bar = host.querySelector("#map-bar"); el.wrap = host.querySelector("#map-wrap");
    host.querySelector("#map-show").addEventListener("click", function (e) { var b = e.target.closest("[data-show]"); if (!b) { return; } S.show = b.dataset.show; remember("map-show", S.show); drawShow(); refreshLayers(); tick(); });
    host.querySelector("#map-events").addEventListener("change", function (e) { var t = e.target; if (!t.dataset.ev) { return; } S.events[t.dataset.ev] = t.checked; remember("map-ev-" + t.dataset.ev, t.checked ? "1" : "0"); refreshLayers(); drawStrip(); });
    host.querySelector("#map-faint").addEventListener("change", function (e) { S.faint = e.target.checked; remember("map-faint", S.faint ? "1" : "0"); refreshLayers(); });
    host.addEventListener("click", onPress);
    host.addEventListener("change", onChange);
    var asked = askedMoment();
    S.moment = asked !== null ? asked : span()[0] + 60;
    drawTransport(); drawShow(); drawMap(); drawList(); drawStrip(); drawBar();
    wireAdd();
  }
  // The incident page's pane: the map and a foot row, nothing of its own
  // to play with; the page's transport is the clock.
  function layoutPane() {
    host.innerHTML =
      "<div class='map-wrap' id='map-wrap'><div class='map-pane' id='map-pane'></div></div>" +
      "<div class='map-foot' id='map-transport'></div>";
    el.transport = host.querySelector("#map-transport"); el.pane = host.querySelector("#map-pane"); el.wrap = host.querySelector("#map-wrap");
    el.list = null; el.strip = null; el.bar = null;
    if (!layoutPane.wired) {
      layoutPane.wired = true;
      host.addEventListener("click", onPress);
      host.addEventListener("change", function (e) { var t = e.target; if (!t.dataset || !t.dataset.ev) { return; } S.events[t.dataset.ev] = t.checked; remember("map-ev-" + t.dataset.ev, t.checked ? "1" : "0"); refreshLayers(); });
      var back = document.getElementById("map-away-back");
      if (back) { back.addEventListener("click", function () { S.large = false; remember("map-inc-large", "0"); applyLarge(); }); }
      // The panel is hidden until its tab is pressed, and the person sizes
      // the work panel by hand: the map takes its new size each time.
      if (window.ResizeObserver) { new ResizeObserver(function () { if (map) { map.resize(); } }).observe(host); }
    }
    drawTransport(); drawMap(); applyLarge();
  }
  // Larger map on the incident page: the host moves onto the stage in the
  // wall's place and back; the panel says where it went.
  function applyLarge() {
    if (!INC) { return; }
    var stage = document.querySelector(".inc-stage"), wall = document.getElementById("wall"), slot = document.getElementById("panel-map"), away = document.getElementById("map-away"), desk = document.querySelector(".inc-desk");
    if (!stage || !wall || !slot) { return; }
    if (S.large && host.parentNode !== stage) { stage.insertBefore(host, wall); }
    if (!S.large && host.parentNode !== slot) { slot.appendChild(host); }
    if (desk) { desk.classList.toggle("inc-map-large", S.large); }
    host.classList.toggle("large", S.large);
    if (away) { away.hidden = !S.large; }
    drawTransport();
    window.setTimeout(function () { if (map) { map.resize(); } }, 50);
  }
  function seg(key, words) { return "<button type='button' data-show='" + key + "' class='" + (S.show === key ? "on" : "") + "'>" + words + "</button>"; }
  function evTick(kind) {
    var words = { camera: "camera on and off", lights: "lights", siren: "siren", mic: "mic", bookmark: "bookmarks", notes: "notes" }[kind];
    return "<label><input type='checkbox' data-ev='" + kind + "'" + (S.events[kind] ? " checked" : "") + "><i class='k " + kind + "'></i> " + words + "</label>";
  }
  function dayChips() {
    var days = S.told.days || [];
    if (!days.length) { return ""; }
    var html = "<div class='days map-days'><span class='lbl'>Days</span>";
    var incidentDays = {};
    (S.told.incidents || []).forEach(function (inc) { if (inc.date) { incidentDays[inc.date] = (incidentDays[inc.date] || 0) + 1; } });
    days.forEach(function (d) {
      var words = esc(d.words) + " · " + plural(d.cameras, "camera") + (incidentDays[d.date] ? " · " + plural(incidentDays[d.date], "incident") : "");
      html += "<button type='button' data-day='" + d.date + "' class='" + (d.date === S.day ? "on" : "") + "'>" + words + (d.cameras > 1 ? "<i class='together' aria-hidden='true'></i>" : "") + "</button>";
    });
    if (S.told.off_clock && S.told.off_clock.length) { html += "<span class='muted small'>" + plural(S.told.off_clock.length, "camera") + " not on the clock</span>"; }
    return html + "</div>";
  }
  function drawShow() { host.querySelectorAll("#map-show [data-show]").forEach(function (b) { b.classList.toggle("on", b.dataset.show === S.show); }); }
  function drawTransport() {
    var m = now();
    if (INC) {
      var cams = dayCams(), ic = incClock();
      el.transport.innerHTML =
        "<span class='muted small' id='map-count'>" + (cams.length ? cams.filter(inView).length + " of " + cams.length + " in view" : "no camera on this day") + "</span>" +
        (ic && ic.now() === null ? "<span class='muted small'>This incident has no clock yet, so the map stands at the cameras' start.</span>" : "") +
        "<span class='seg' id='map-show'>" + seg("markers", "Markers") + seg("trails", "Trails") + seg("whole", "Paths") + "</span>" +
        "<span class='map-ev' id='map-events'>" + EVENT_KINDS.map(evTick).join("") + "</span>" +
        "<span class='grow'></span>" +
        "<button type='button' class='tiny' data-act='fit'>Fit all</button>" +
        (host.dataset.edit ? "<button type='button' class='tiny' data-act='picture' title='Keep this view of the map as a Document on the incident'>Save a picture</button>" : "") +
        "<button type='button' class='tiny " + (S.large ? "on" : "") + "' data-act='large'>" + (S.large ? "Smaller map" : "Larger map") + "</button>";
      return;
    }
    var scope = S.scope ? "<span class='pill small acc' title='" + esc(S.scope.name) + "'>" + esc(S.scope.name) + "</span> <button type='button' class='tiny ghost' data-act='whole-day'>whole day</button>" : "";
    el.transport.innerHTML =
      scope +
      "<button type='button' class='small primary' data-act='play'>" + (S.playing ? "<svg class='i' aria-hidden='true'><use href='#i-pause'></use></svg> Pause" : "<svg class='i' aria-hidden='true'><use href='#i-play'></use></svg> Play") + "</button>" +
      "<button type='button' class='small' data-act='back'>−10 s</button><button type='button' class='small' data-act='forward'>+10 s</button>" +
      "<button type='button' class='small' data-act='prev-event' title='The previous event'>‹ event</button><button type='button' class='small' data-act='next-event' title='The next event'>event ›</button>" +
      "<select class='small' id='map-speed' title='Speed'>" + [1, 4, 16, 60].map(function (v) { return "<option value='" + v + "'" + (v === S.speed ? " selected" : "") + ">Speed " + v + "×</option>"; }).join("") + "</select>" +
      "<span class='map-clock-wrap'><span class='map-clock mono' id='map-clock'>" + hms(m) + "</span><span class='map-zone'>" + esc(host.dataset.tz || "") + (S.day ? " · " + esc(dayWords(S.day)) : "") + "</span></span>" +
      (S.following ? "<span class='pill small acc'>following " + esc((S.byId[S.following] || {}).unit || (S.byId[S.following] || {}).title || "") + "</span>" : "") +
      "<button type='button' class='small' data-act='fit'>Fit shown</button>" +
      "<button type='button' class='small' data-act='note' title='A note on the selected camera at this moment'>Note here</button>" +
      "<button type='button' class='small " + (S.asking || S.circle ? "on" : "") + "' data-act='circle' title='Press, then press a place on the map: a circle you can widen, and the cameras that passed inside it'>Within a circle</button>" +
      (S.circle ? "<span class='pill small acc' id='map-radius'>" + Math.round(S.circle.radius) + " m</span><button type='button' class='tiny ghost' data-act='clear-circle'>clear the circle</button>" : "") +
      (host.dataset.edit ? "<button type='button' class='small' data-act='picture' title='Keep this view of the map as a Document on the incident shown, or on the camera pressed'>Save a picture</button>" : "") +
      "<button type='button' class='small " + (S.large ? "on" : "") + "' data-act='large'>" + (S.large ? "Smaller map" : "Larger map") + "</button>";
    el.transport.querySelector("#map-speed").addEventListener("change", function (e) { S.speed = parseInt(e.target.value, 10) || 1; if (S.playing) { S.anchorMoment = now(); S.anchorNow = performance.now(); } tick(); });
  }
  function drawBar() {
    if (!el.bar) { return; }
    var m = now();
    el.bar.innerHTML = "<button type='button' class='tiny primary' data-act='play'>" + (S.playing ? "Pause" : "Play") + "</button><span class='map-clock mono'>" + hms(m) + "</span><span class='muted small'>" + S.speed + "×</span><button type='button' class='tiny ghost' data-act='leave-full'>Leave full screen</button>";
  }

  // The map -----------------------------------------------------------------------
  function theme() { var t = document.documentElement.dataset.theme; if (t) { return t; } return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  function plainGround() { return { version: 8, sources: {}, layers: [{ id: "ground", type: "background", paint: { "background-color": token("--surface-2") } }] }; }
  function groundStyle() {
    if (!host.dataset.basemap) { return Promise.resolve(plainGround()); }
    var url = theme() === "dark" ? host.dataset.styleDark : host.dataset.styleLight;
    return fetch(url, { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (style) {
      style.sources = style.sources || {};
      style.sources.protomaps = { type: "vector", url: "pmtiles://" + location.origin + host.dataset.basemap, attribution: host.dataset.attribution };
      style.glyphs = host.dataset.glyphs + "/{fontstack}/{range}.pbf";
      style.sprite = location.origin + host.dataset.sprite + "/" + theme();
      return style;
    }).catch(function () { return plainGround(); });
  }
  function drawMap() {
    mapReady = false;
    // A map drawn before (a day chip, a reload) goes with its pane.
    if (map) { try { map.remove(); } catch (e) { /* gone with its pane */ } map = null; markers = {}; trailIndex = {}; }
    if (host.dataset.basemap && window.pmtiles && !drawMap.protocol) {
      try { maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile); drawMap.protocol = true; } catch (e) { /* the reader is missing; plain ground */ }
    }
    groundStyle().then(function (style) {
      try {
        map = new maplibregl.Map({ container: el.pane, style: style, attributionControl: false, dragRotate: false, pitchWithRotate: false, maxPitch: 0, minZoom: 2 });
      } catch (e) {
        el.pane.innerHTML = "<div class='map-nomap'><b>This browser cannot draw the map.</b> The list and the strip still work.</div>";
        return;
      }
      map.touchZoomRotate.disableRotation();
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "imperial" }), "bottom-left");
      map.addControl(new maplibregl.FullscreenControl({ container: el.wrap }), "top-right");
      if (host.dataset.basemap) { map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: host.dataset.attribution }), "bottom-right"); }
      else { var note = document.createElement("div"); note.className = "map-nomap"; note.innerHTML = "No street map installed: the paths are drawn on plain ground. <span class='muted'>The Admin can install one (admin guide, Maps).</span>"; el.pane.appendChild(note); }
      var north = document.createElement("div"); north.className = "map-north"; north.textContent = "N"; el.pane.appendChild(north);
      var mine = map;
      map.on("load", function () { if (map !== mine) { return; } mapReady = true; addLayers(); fitAll(); drawList(); tick(); if (S.circle) { drawCircle(); } });
      map.on("moveend", function () { drawList(); });
      map.on("move", function () { drawLeaders(); });
      map.on("click", "map-events", function (e) { if (S.asking) { return; } var f = e.features && e.features[0]; if (f) { selectKey(f.properties.key); } });
      map.on("click", function (e) { if (S.asking) { placeCircle(e.lngLat); } });
      map.on("mouseenter", "map-events", function () { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "map-events", function () { map.getCanvas().style.cursor = ""; });
      document.addEventListener("fullscreenchange", function () { host.classList.toggle("full", document.fullscreenElement === el.wrap); drawBar(); window.setTimeout(function () { map.resize(); }, 50); });
    });
    if (!drawMap.observing) {
      drawMap.observing = true;
      var observer = new MutationObserver(function () { if (map) { groundStyle().then(function (style) { map.setStyle(style); map.once("style.load", function () { addLayers(); refreshLayers(); }); recolourMarkers(); }); } });
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
  }
  function featureOf(cam, segments) {
    return { type: "Feature", id: cam.n, properties: { id: cam.id, colour: colourOf(cam) }, geometry: { type: "MultiLineString", coordinates: segments.map(function (seg) { return seg.map(function (f) { return [f[2], f[1]]; }); }) } };
  }
  function pathsCollection() {
    var features = [];
    S.cams.forEach(function (cam, i) { cam.n = i + 1; if (!cam.fixes.length) { return; } features.push(featureOf(cam, cam.segments)); });
    return { type: "FeatureCollection", features: features };
  }
  function eventsCollection() {
    var features = [];
    S.cams.forEach(function (cam) {
      if (!cam.fixes.length || !shown(cam)) { return; }
      (cam.events || []).forEach(function (ev, i) {
        var kind = ev.kind === "mic" ? "mic" : ev.kind;
        if (!S.events[kind === "camera" ? "camera" : kind]) { return; }
        if (["camera", "lights", "siren", "mic", "bookmark"].indexOf(kind) < 0) { return; }
        var p = positionAt(cam, ev.t);
        if (!p) { return; }
        features.push({ type: "Feature", properties: { key: "ev:" + cam.id + ":" + i, kind: kind, on: ev.value ? 1 : 0, cam: cam.id }, geometry: { type: "Point", coordinates: [p.lon, p.lat] } });
      });
      if (S.events.notes) {
        (cam.notes || []).forEach(function (n, i) {
          var p = positionAt(cam, n.t);
          if (!p) { return; }
          features.push({ type: "Feature", properties: { key: "note:" + cam.id + ":" + i, kind: "note", on: 1, cam: cam.id }, geometry: { type: "Point", coordinates: [p.lon, p.lat] } });
        });
      }
    });
    return { type: "FeatureCollection", features: features };
  }
  function addLayers() {
    if (!map) { return; }
    map.addSource("map-paths", { type: "geojson", data: pathsCollection() });
    var pathsLayer = { id: "map-paths", type: "line", source: "map-paths", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "colour"], "line-width": ["case", ["boolean", ["feature-state", "lit"], false], 5, 2.5], "line-opacity": pathsOpacity() } };
    // addLayer refuses a null filter where setFilter takes one as "none".
    if (hiddenFilter()) { pathsLayer.filter = hiddenFilter(); }
    map.addLayer(pathsLayer);
    S.cams.forEach(function (cam) {
      if (!cam.fixes.length) { return; }
      map.addSource("map-trail-" + cam.n, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "map-trail-" + cam.n, type: "line", source: "map-trail-" + cam.n, layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": colourOf(cam), "line-width": 3.5, "line-opacity": 1 } });
      trailIndex[cam.id] = -2;
    });
    map.addSource("map-events", { type: "geojson", data: eventsCollection() });
    map.addLayer({ id: "map-events", type: "circle", source: "map-events", paint: {
      "circle-radius": ["case", ["==", ["get", "key"], S.selected ? S.selected.key : ""], 8, ["==", ["get", "kind"], "camera"], 5, 5],
      "circle-color": ["match", ["get", "kind"], "lights", token("--warn"), "siren", token("--danger"), "mic", token("--muted"), "bookmark", token("--accent"), "note", token("--accent"), "camera", token("--text"), token("--muted")],
      "circle-stroke-color": ["case", ["==", ["get", "key"], S.selected ? S.selected.key : ""], token("--accent"), token("--surface")],
      "circle-stroke-width": ["case", ["==", ["get", "key"], S.selected ? S.selected.key : ""], 3, 1.5],
      "circle-opacity": ["case", ["all", ["==", ["get", "kind"], "camera"], ["==", ["get", "on"], 1]], 0, 1],
      "circle-stroke-opacity": 1
    } });
    drawMarkers();
  }
  function refreshLayers() {
    if (!map || !mapReady) { return; }
    var src = map.getSource("map-events"); if (src) { src.setData(eventsCollection()); }
    var sel = S.selected ? S.selected.key : "";
    if (map.getLayer("map-events")) {
      map.setPaintProperty("map-events", "circle-radius", ["case", ["==", ["get", "key"], sel], 8, 5]);
      map.setPaintProperty("map-events", "circle-stroke-color", ["case", ["==", ["get", "key"], sel], token("--accent"), token("--surface")]);
      map.setPaintProperty("map-events", "circle-stroke-width", ["case", ["==", ["get", "key"], sel], 3, 1.5]);
    }
    if (map.getLayer("map-paths")) { map.setPaintProperty("map-paths", "line-opacity", pathsOpacity()); map.setFilter("map-paths", hiddenFilter()); }
    Object.keys(trailIndex).forEach(function (id) { trailIndex[id] = -2; });
  }
  // Whole paths read strong; under markers or trails the whole path lies
  // faint, or not at all when "faint paths under" is unticked (chapter 6).
  function pathsOpacity() { return S.show === "whole" ? 0.9 : (S.faint ? 0.35 : 0); }
  function hiddenFilter() { var ids = Object.keys(S.hidden); if (INC || !ids.length) { return null; } return ["!", ["in", ["get", "id"], ["literal", ids]]]; }
  function drawMarkers() {
    Object.keys(markers).forEach(function (id) { markers[id].remove(); });
    markers = {};
    S.cams.forEach(function (cam) {
      if (!cam.fixes.length) { return; }
      var node = document.createElement("div");
      node.className = "map-head " + (cam.source === "car" ? "car" : "body");
      node.style.setProperty("--cam", colourOf(cam));
      node.innerHTML = "<b>" + esc(cam.unit || cam.title) + "</b><i class='badge' aria-hidden='true'></i>" + (cam.source === "car" ? "<span class='spd mono' hidden></span>" : "");
      node.title = nameOf(cam) + (cam.wearer ? " · " + cam.title : "");
      node.addEventListener("click", function (e) { e.stopPropagation(); select(cam); openPreview(cam); });
      var marker = new maplibregl.Marker({ element: node, anchor: "center" }).setLngLat([cam.fixes[0][2], cam.fixes[0][1]]).addTo(map);
      markers[cam.id] = marker;
    });
  }
  function recolourMarkers() { S.cams.forEach(function (cam) { var m = markers[cam.id]; if (m) { m.getElement().style.setProperty("--cam", colourOf(cam)); } }); }
  function fitAll() {
    if (!map) { return; }
    var cams = shownCams().filter(function (c) { return c.bounds; });
    if (!cams.length) { cams = dayCams().filter(function (c) { return c.bounds; }); }
    if (!cams.length) { cams = S.cams.filter(function (c) { return c.bounds; }); }
    if (!cams.length) { return; }
    var s = Infinity, w = Infinity, n = -Infinity, e = -Infinity;
    cams.forEach(function (c) { s = Math.min(s, c.bounds[0]); w = Math.min(w, c.bounds[1]); n = Math.max(n, c.bounds[2]); e = Math.max(e, c.bounds[3]); });
    map.fitBounds([[w, s], [e, n]], { padding: 48, maxZoom: 17, duration: 0 });
  }
  function flyTo(cam) { if (map && cam.bounds) { map.fitBounds([[cam.bounds[1], cam.bounds[0]], [cam.bounds[3], cam.bounds[2]]], { padding: 48, maxZoom: 17, duration: 600 }); } }
  function light(cam) {
    if (!map || !mapReady) { return; }
    S.cams.forEach(function (c) { if (c.fixes.length) { map.setFeatureState({ source: "map-paths", id: c.n }, { lit: !!cam && c.id === cam.id }); } });
    S.lit = cam ? cam.id : null;
    host.querySelectorAll(".map-row").forEach(function (r) { r.classList.toggle("lit", !!cam && r.dataset.cam === cam.id); });
  }
  function inView(cam) {
    if (!map || !cam.bounds) { return false; }
    var b = map.getBounds();
    if (cam.bounds[2] < b.getSouth() || cam.bounds[0] > b.getNorth() || cam.bounds[3] < b.getWest() || cam.bounds[1] > b.getEast()) { return false; }
    return cam.fixes.some(function (f) { return b.contains([f[2], f[1]]); });
  }

  // The tick ---------------------------------------------------------------------
  function tick() {
    if (!S.loaded) { return; }
    var m = now();
    var range = span();
    if (S.playing && m >= range[1]) { S.moment = range[1]; S.playing = false; drawTransport(); m = range[1]; }
    var clock = host.querySelector("#map-clock"); if (clock) { clock.textContent = hms(m); }
    var barClock = el.bar && el.bar.querySelector(".map-clock"); if (barClock) { barClock.textContent = hms(m); }
    S.cams.forEach(function (cam) {
      var marker = markers[cam.id];
      if (!marker) { return; }
      var node = marker.getElement();
      var local = cam.onClock ? m - cam.zero.second : (cam.own !== undefined ? cam.own : null);
      if (!shown(cam)) {
        // Unticked (chapter 6): no marker, no trail; the whole path is filtered off the paths layer.
        node.classList.add("before");
        if (map && mapReady && trailIndex[cam.id] !== -4) { trailIndex[cam.id] = -4; var s4 = map.getSource("map-trail-" + cam.n); if (s4) { s4.setData({ type: "FeatureCollection", features: [] }); } }
        return;
      }
      if (local === null || (!ofDay(cam) && cam.onClock) || !scoped(cam)) { node.classList.add("before"); return; }
      var p = positionAt(cam, local);
      if (!p) { node.classList.add("before"); return; }
      node.classList.remove("before");
      node.classList.toggle("nofix", !!p.nofix);
      node.classList.toggle("ended", !!p.ended);
      marker.setLngLat([p.lon, p.lat]);
      var flags = flagsAt(cam, local);
      node.classList.toggle("lights", !!flags.lights);
      node.classList.toggle("siren", !!flags.siren);
      node.classList.toggle("muted-mic", cam.source === "body" && flags.mic === 0);
      // A vehicle's speed (chapter 6): beside its marker while it moves, in
      // the lane's head and at the end of its row.
      var speedWords = flags.speed !== undefined ? Math.round(flags.speed) + " " + (cam.speed_unit || "mph").toLowerCase() : "";
      var moving = cam.source === "car" && flags.speed !== undefined && flags.speed > 3 && !p.ended;
      var tag = node.querySelector(".spd"); if (tag) { tag.hidden = !moving; if (moving) { tag.textContent = speedWords; } }
      var head = host.querySelector(".map-lane[data-cam='" + cam.id + "'] .spd");
      if (head) { head.textContent = speedWords; }
      var rowSpeed = host.querySelector(".map-row[data-cam='" + cam.id + "'] .spd");
      if (rowSpeed) { rowSpeed.textContent = moving ? speedWords : ""; }
      if (S.open === cam.id) { var where = host.querySelector(".map-where[data-cam='" + cam.id + "']"); if (where) { where.innerHTML = whereWords(cam, local, p); } }
      if (S.show === "trails" && map && mapReady) {
        var index = lastIndex(cam, local);
        if (trailIndex[cam.id] !== index) {
          trailIndex[cam.id] = index;
          var src = map.getSource("map-trail-" + cam.n);
          if (src) { src.setData({ type: "FeatureCollection", features: index < 0 ? [] : [featureOf(cam, trailSegments(cam, index, p))] }); }
        }
      } else if (map && mapReady && trailIndex[cam.id] !== -3) {
        trailIndex[cam.id] = -3;
        var s2 = map.getSource("map-trail-" + cam.n);
        if (s2) { s2.setData({ type: "FeatureCollection", features: S.show === "whole" ? [featureOf(cam, cam.segments)] : [] }); }
      }
    });
    movePlayhead(m);
    drawLeaders();
  }
  // Where a camera is now (chapter 6), for its opened row: the street under
  // it when a basemap is drawn, and the nearest other camera shown, by
  // distance. Never a coordinate.
  function whereWords(cam, local, p) {
    if (!p) { return "<span class='muted'>not started yet</span>"; }
    if (p.nofix) { return "<span class='muted'>no fix now</span>"; }
    if (p.ended) { return "<span class='muted'>ended here</span>"; }
    var m = now(), street = streetAt(cam, local), nearest = null, best = Infinity;
    shownCams().forEach(function (other) {
      if (other.id === cam.id || !other.onClock) { return; }
      var q = positionAt(other, m - other.zero.second); if (!q || q.nofix || q.ended) { return; }
      var d = metres(p, q); if (d < best) { best = d; nearest = other; }
    });
    var parts = [];
    if (street) { parts.push("on " + esc(street)); }
    if (nearest) { parts.push((best < 1000 ? Math.round(best) + " m" : (best / 1000).toFixed(1) + " km") + " from " + esc(nameOf(nearest))); }
    return parts.length ? parts.join(" · ") : "<span class='muted'>here at " + hms(m) + "</span>";
  }
  // The leaders (chapter 6): when markers would overlap at this zoom, each
  // gets a thin line out to a tag with its name, fanned round the knot so no
  // tag covers another. A lone marker keeps its own small label.
  var LEADER_NEAR = 30;  // px between marker centres that reads as a knot
  function drawLeaders() {
    if (!map || !mapReady || !el.pane) { return; }
    var layer = el.pane.querySelector(".map-leaders");
    if (!layer) { layer = document.createElement("div"); layer.className = "map-leaders"; layer.innerHTML = "<svg aria-hidden='true'></svg><div class='tags'></div>"; el.pane.appendChild(layer); }
    var w = el.pane.clientWidth, h = el.pane.clientHeight, pts = [];
    S.cams.forEach(function (cam) {
      var mk = markers[cam.id]; if (!mk) { return; }
      var node = mk.getElement(); if (node.classList.contains("before")) { return; }
      var p = map.project(mk.getLngLat());
      if (p.x < -20 || p.y < -20 || p.x > w + 20 || p.y > h + 20) { return; }
      pts.push({ cam: cam, x: p.x, y: p.y, group: -1 });
    });
    var groups = [];
    pts.forEach(function (a, i) {
      if (a.group >= 0) { return; }
      var g = [a]; a.group = groups.length;
      for (var j = i + 1; j < pts.length; j++) {
        var b = pts[j];
        if (b.group < 0 && g.some(function (k) { return Math.hypot(k.x - b.x, k.y - b.y) < LEADER_NEAR; })) { b.group = a.group; g.push(b); }
      }
      groups.push(g);
    });
    var lines = "", tags = "", lit = S.following || S.pressed || S.lit;
    groups.forEach(function (g) {
      if (g.length < 2) { return; }
      var cx = 0, cy = 0; g.forEach(function (k) { cx += k.x; cy += k.y; }); cx /= g.length; cy /= g.length;
      // Each marker takes the tag nearest its own bearing from the knot's centre, so the lines do not cross.
      g.forEach(function (k) { k.ang = Math.atan2(k.y - cy, k.x - cx); });
      g.sort(function (p1, p2) { return p1.ang - p2.ang; });
      var r = 46 + 7 * g.length, start = -Math.PI / 2 - Math.PI / g.length;
      g.forEach(function (k, i) {
        var ang = start + (i / g.length) * 2 * Math.PI;
        var tx = Math.max(52, Math.min(w - 52, cx + Math.cos(ang) * r)), ty = Math.max(12, Math.min(h - 12, cy + Math.sin(ang) * r));
        lines += "<line x1='" + k.x.toFixed(1) + "' y1='" + k.y.toFixed(1) + "' x2='" + tx.toFixed(1) + "' y2='" + ty.toFixed(1) + "'></line>";
        tags += "<button type='button' class='map-tag" + (lit === k.cam.id ? " on" : "") + "' data-act='tag' data-cam='" + k.cam.id + "' style='left: " + tx.toFixed(1) + "px; top: " + ty.toFixed(1) + "px'><i class='" + (k.cam.source === "car" ? "sq" : "") + "' style='background: " + colourOf(k.cam) + "'></i>" + nameHtml(k.cam) + "</button>";
      });
    });
    var svg = layer.querySelector("svg"), box = layer.querySelector(".tags");
    if (svg.innerHTML !== lines) { svg.innerHTML = lines; }
    if (box.innerHTML !== tags) { box.innerHTML = tags; }
  }
  function trailSegments(cam, index, p) {
    var out = [], run = [];
    for (var i = 0; i <= index; i++) {
      var f = cam.fixes[i];
      if (run.length && (f[0] - run[run.length - 1][0] > GAP)) { out.push(run); run = []; }
      run.push(f);
    }
    if (p && !p.nofix && !p.ended && run.length) { run.push([0, p.lat, p.lon]); }
    if (run.length) { out.push(run); }
    return out;
  }

  // The list ----------------------------------------------------------------------
  function suretyPill(cam) { var s = cam.surety; if (!s || !s.word) { return ""; } return "<span class='pill " + esc(s.tone || "") + " small surety' title='" + esc(s.why || "") + "'>" + esc(s.word) + "</span>"; }
  // A row (chapter 6): the tick, the colour, the name, and the rest behind
  // its disclosure. A vehicle's speed sits at the row's end while it moves.
  function rowOf(cam, dim) {
    var open = S.open === cam.id, inside = S.hits && S.hits[cam.id];
    var insideWords = inside ? " <small class='muted mono'>" + hm(cam.zero.second + inside[0][0]) + " to " + hm(cam.zero.second + inside[inside.length - 1][1]) + "</small>" : "";
    var noFix = !cam.fixes.length ? " <small class='muted'>no position</small>" : "";
    return "<div class='map-row " + (dim ? "dim " : "") + (S.lit === cam.id ? "lit " : "") + (open ? "open" : "") + "' data-cam='" + cam.id + "'>" +
      "<input type='checkbox' class='tk' data-tick='" + cam.id + "'" + (shown(cam) ? " checked" : "") + " title='Ticked: drawn on the map and the strip'>" +
      "<span class='dot " + (cam.source === "car" ? "sq" : "") + "' style='background: " + paint(cam.colour) + "'></span>" +
      "<span class='nm' title='Press: show this camera alone. Shift: add it.'>" + nameHtml(cam) + insideWords + noFix + "</span>" +
      "<span class='tail'><span class='spd mono small muted'></span><button type='button' class='tiny ghost more' data-act='open' data-cam='" + cam.id + "' title='" + (open ? "Fold" : "The camera, its clock and its actions") + "'>" + (open ? "▾" : "▸") + "</button></span>" +
      "</div>" + (open ? openOf(cam) : "");
  }
  function openOf(cam) {
    var spanWords = cam.onClock ? hm(cam.zero.second) + " to " + hm(cam.zero.second + (cam.length || 0)) : elapsed(cam.length || 0) + " long";
    var streams = cam.streams.length ? "<span class='streams'><span>stream 1</span>" + cam.streams.map(function (s, i) { return "<span>stream " + (i + 2) + "</span>"; }).join("") + "</span>" : "";
    var facts = "<div class='facts'><b>" + esc(cam.unit || cam.title) + "</b><span>" + (cam.source === "car" ? "in-car" : "body camera") + "</span>" + suretyPill(cam) + "<span class='mono'>" + spanWords + "</span>" + streams +
      (!cam.onClock ? "<button type='button' class='tiny' data-act='own' data-cam='" + cam.id + "'>" + (cam.own !== undefined ? "Hide it" : "Show on its own") + "</button>" : "") + "</div>" +
      (cam.own !== undefined ? "<input type='range' class='own-bar' data-cam='" + cam.id + "' min='0' max='" + Math.round(cam.length || 0) + "' value='" + Math.round(cam.own) + "'>" : "");
    var where = cam.onClock && cam.fixes.length ? "<div class='facts map-where' data-cam='" + cam.id + "'>" + whereWords(cam, now() - cam.zero.second, positionAt(cam, now() - cam.zero.second)) + "</div>" : "";
    var acts = "<div class='acts'>" +
      "<button type='button' class='tiny primary' data-act='play-here' data-cam='" + cam.id + "'>Play here</button>" +
      (cam.bounds ? "<button type='button' class='tiny' data-act='fly' data-cam='" + cam.id + "'>Fly to</button>" : "") +
      "<button type='button' class='tiny " + (S.readingsOpen[cam.id] ? "on" : "") + "' data-act='readings' data-cam='" + cam.id + "' title='Every reading of its file, with its time'>Readings</button>" +
      "<a class='btn tiny ghost' href='" + esc(cam.viewer_url) + "'>Open the recording</a>" +
      (host.dataset.edit ? "<label class='btn tiny ghost'>Replace file<input type='file' accept='.vtt,text/vtt' hidden data-replace-one='" + cam.id + "'></label><button type='button' class='tiny ghost danger' data-act='remove' data-cam='" + cam.id + "'>Remove</button>" : "") +
      "</div>";
    return "<div class='map-open' data-cam='" + cam.id + "'>" + facts + where + acts + (S.readingsOpen[cam.id] ? readingsOf(cam) : "") + "</div>";
  }
  // The Readings list (chapter 3): every moment the file records, with its
  // time of day, a press to go there, and Offer to the chronology.
  function readingsOf(cam) {
    var z = cam.onClock ? cam.zero.second : null;
    var when = function (t) { return z === null ? elapsed(t) + " in" : hms(z + t); };
    var items = (cam.events || []).map(function (ev, i) { return { ev: ev, i: i }; }).sort(function (a, b) { return a.ev.t - b.ev.t; });
    var html = "<ul class='map-readings' data-cam='" + cam.id + "'>";
    items.forEach(function (one) {
      var ev = one.ev, span = (ev.until !== null && ev.until !== undefined && ev.until > ev.t) ? " to " + when(ev.until) : "";
      html += "<li data-key='ev:" + cam.id + ":" + one.i + "' data-t='" + ev.t + "'><span class='mono'>" + when(ev.t) + span + "</span><span class='w'>" + esc(ev.words) + "</span>" + offerButton(cam, ev) + "</li>";
    });
    if (!items.length) { html += "<li class='muted'>No readings in its file.</li>"; }
    return html + "</ul>";
  }
  function offerButton(cam, ev) {
    if (ev.kind === "camera") { return ""; }
    var until = (ev.until === null || ev.until === undefined) ? "" : ev.until;
    if (!S.told.may_offer) { return "<span class='muted small' title='" + esc(S.told.offer_why || "") + "'>offer withheld</span>"; }
    return "<button type='button' class='tiny ghost' data-act='offer' data-cam='" + cam.id + "' data-t='" + ev.t + "' data-until='" + until + "' data-words='" + esc(ev.words) + "' title='A proposed event on the recording at this moment; it waits on the Proposed events tab for Accept or Dismiss'>Offer to the chronology</button>";
  }
  function offer(cam, t, until, words, button) {
    postJson("/recording/" + cam.id + "/path/offer", { t: t, until: until === "" ? null : until, words: words }).then(function (told) {
      toast(told.words);
      if (button) { button.textContent = "Offered"; button.disabled = true; }
    }).catch(function (e) { toast(e.message, true); });
  }
  // Within a circle (chapter 6; Who was near here of chapter 3 grown a
  // handle): answered from the fixes the page holds; nothing is asked of the
  // server, nothing is kept, and no position leaves the browser.
  function metres(a, b) {
    var r = 6371000, p1 = a.lat * Math.PI / 180, p2 = b.lat * Math.PI / 180, dp = (b.lat - a.lat) * Math.PI / 180, dl = (b.lon - a.lon) * Math.PI / 180;
    var h = Math.sin(dp / 2) * Math.sin(dp / 2) + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * r * Math.asin(Math.sqrt(h));
  }
  function eastOf(c, metresAway) { return { lat: c.lat, lon: c.lon + metresAway / (111320 * Math.cos(c.lat * Math.PI / 180)) }; }
  function circlePolygon(c) {
    var ring = [], dLat = c.radius / 111320, dLon = c.radius / (111320 * Math.cos(c.lat * Math.PI / 180));
    for (var i = 0; i <= 64; i++) { var a = (i / 64) * 2 * Math.PI; ring.push([c.lon + Math.cos(a) * dLon, c.lat + Math.sin(a) * dLat]); }
    return { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } }] };
  }
  function placeCircle(lngLat) {
    S.asking = false; if (map) { map.getCanvas().style.cursor = ""; }
    S.circle = { lat: lngLat.lat, lon: lngLat.lng, radius: NEAR };
    drawCircle(); circleHits(); drawTransport(); drawList(); drawStrip();
  }
  function drawCircle() {
    if (!map || !mapReady || !S.circle) { return; }
    var data = circlePolygon(S.circle);
    if (!map.getSource("map-circle")) {
      map.addSource("map-circle", { type: "geojson", data: data });
      map.addLayer({ id: "map-circle-fill", type: "fill", source: "map-circle", paint: { "fill-color": token("--accent"), "fill-opacity": 0.08 } });
      map.addLayer({ id: "map-circle-line", type: "line", source: "map-circle", paint: { "line-color": token("--accent"), "line-width": 1.5, "line-dasharray": [3, 2] } });
    } else { map.getSource("map-circle").setData(data); }
    if (!circleMarkers) {
      var centre = document.createElement("div"); centre.className = "map-circle-centre"; centre.title = "Drag to move the circle";
      var handle = document.createElement("div"); handle.className = "map-circle-handle"; handle.title = "Drag to widen or narrow the circle";
      handle.innerHTML = "<b></b>";
      circleMarkers = {
        centre: new maplibregl.Marker({ element: centre, anchor: "center", draggable: true }).setLngLat([S.circle.lon, S.circle.lat]).addTo(map),
        handle: new maplibregl.Marker({ element: handle, anchor: "center", draggable: true }).setLngLat([eastOf(S.circle, S.circle.radius).lon, S.circle.lat]).addTo(map)
      };
      circleMarkers.handle.on("drag", function () { var h = circleMarkers.handle.getLngLat(); S.circle.radius = Math.max(10, Math.min(5000, metres(S.circle, { lat: h.lat, lon: h.lng }))); map.getSource("map-circle").setData(circlePolygon(S.circle)); radiusWords(); });
      circleMarkers.centre.on("drag", function () { var c = circleMarkers.centre.getLngLat(); S.circle.lat = c.lat; S.circle.lon = c.lng; circleMarkers.handle.setLngLat([eastOf(S.circle, S.circle.radius).lon, S.circle.lat]); map.getSource("map-circle").setData(circlePolygon(S.circle)); });
      var settle = function () { circleHits(); drawTransport(); drawList(); drawStrip(); };
      circleMarkers.handle.on("dragend", settle); circleMarkers.centre.on("dragend", settle);
    }
    radiusWords();
  }
  function radiusWords() {
    var words = Math.round(S.circle.radius) + " m";
    if (circleMarkers) { circleMarkers.handle.getElement().querySelector("b").textContent = words; }
    var pill = host.querySelector("#map-radius"); if (pill) { pill.textContent = words; }
  }
  // Each camera's spells inside the circle, by its fixes: an entry and an
  // exit, a break of over a minute starting a new spell.
  function circleHits() {
    S.hits = {};
    if (!S.circle) { S.hits = null; return; }
    dayCams().forEach(function (cam) {
      var spells = [], start = null, last = null;
      cam.fixes.forEach(function (f) {
        if (metres(S.circle, { lat: f[1], lon: f[2] }) > S.circle.radius) { return; }
        if (start === null || f[0] - last > 60) { if (start !== null) { spells.push([start, last]); } start = f[0]; }
        last = f[0];
      });
      if (start !== null) { spells.push([start, last]); }
      if (spells.length) { S.hits[cam.id] = spells; }
    });
  }
  function clearCircle() {
    S.circle = null; S.hits = null; S.asking = false;
    if (circleMarkers) { circleMarkers.centre.remove(); circleMarkers.handle.remove(); circleMarkers = null; }
    if (map && mapReady) { ["map-circle-line", "map-circle-fill"].forEach(function (id) { if (map.getLayer(id)) { map.removeLayer(id); } }); if (map.getSource("map-circle")) { map.removeSource("map-circle"); } map.getCanvas().style.cursor = ""; }
    drawTransport(); drawList(); drawStrip();
  }
  function drawList() {
    if (INC) { var count = host.querySelector("#map-count"); var dc = dayCams(); if (count) { count.textContent = dc.length ? dc.filter(inView).length + " of " + dc.length + " in view" : "no camera on this day"; } return; }
    if (!el.list) { return; }
    var cams = S.cams.filter(scoped);
    var today = cams.filter(ofDay), other = cams.filter(function (c) { return c.onClock && !ofDay(c); }), off = cams.filter(function (c) { return !c.onClock; });
    var ticked = today.filter(shown), seen = ticked.filter(inView);
    var fold = host.classList.contains("large") ? "<button type='button' class='tiny ghost' data-act='fold'>" + (host.classList.contains("folded") ? "‹ show" : "fold ›") + "</button>" : "";
    var html;
    if (S.circle && S.hits) {
      // The circle's answer (chapter 6): who passed inside, with their spans, then the rest.
      var inside = today.filter(function (c) { return S.hits[c.id]; }), never = today.filter(function (c) { return !S.hits[c.id]; });
      inside.sort(function (a, b) { return (a.zero.second + S.hits[a.id][0][0]) - (b.zero.second + S.hits[b.id][0][0]); });
      html = "<div class='h'><span><b class='acc'>" + plural(inside.length, "camera") + "</b> passed inside the circle</span><span class='acts'>" + (inside.length ? "<button type='button' class='tiny' data-act='tick-inside' title='Tick these cameras alone'>Tick these</button>" : "") + fold + "</span></div>";
      inside.forEach(function (c) { html += rowOf(c, !shown(c)); });
      if (never.length) { html += "<details class='map-fold' open><summary>Never inside: " + plural(never.length, "camera") + "</summary>" + never.map(function (c) { return rowOf(c, true); }).join("") + "</details>"; }
    } else {
      var all = ticked.length === today.length;
      html = "<div class='h'><label title='Tick or untick every camera of the day'><input type='checkbox' id='map-tick-all'" + (all ? " checked" : "") + (ticked.length && !all ? " data-half='1'" : "") + "> " + (today.length ? ticked.length + " of " + today.length + " shown" + (ticked.length ? " · " + seen.length + " in view" : "") : "no camera on this day") + "</label>" +
        "<span class='acts'><button type='button' class='tiny ghost' data-act='tick-all'>all</button><button type='button' class='tiny ghost' data-act='tick-none'>none</button>" + fold + "</span></div>";
      today.forEach(function (c) { html += rowOf(c, !shown(c)); });
    }
    if (off.length) { html += "<details class='map-fold' open><summary>Not on the clock: " + plural(off.length, "camera") + "</summary>" + off.map(function (c) { return rowOf(c, true); }).join("") + "</details>"; }
    if (other.length) { html += "<details class='map-fold'><summary>Other days: " + plural(other.length, "camera") + "</summary>" + other.map(function (c) { return rowOf(c, true); }).join("") + "</details>"; }
    var without = S.told.videos_without_path || [];
    if (without.length) {
      html += "<details class='map-fold' " + (today.length ? "" : "open") + "><summary>No path file: " + plural(without.length, "video") + "</summary>" +
        without.map(function (v) { return "<div class='map-row dim' data-video='" + v.id + "'><span class='dot' style='background: var(--muted)'></span><div><b>" + esc(v.title) + "</b><div class='facts'>no path file</div></div><div class='acts'>" + (host.dataset.edit ? "<label class='tiny btn'>Add a path file<input type='file' accept='.vtt,text/vtt' hidden data-add-one='" + v.id + "'></label>" : "") + "</div></div>"; }).join("") + "</details>";
    }
    // The forming offer from the map (join 1): the Incidents tab's own Make it.
    (S.told.offer || []).forEach(function (one) {
      html += "<div class='map-offer'><span class='pill small offer'>Offer</span> <span class='small'>" + esc(one.line) + "</span><div class='acts'><button type='button' class='tiny primary' data-act='make-incident' data-recordings='" + esc(one.recordings.join(" ")) + "'>Make an incident</button><a class='btn tiny ghost' href='?tab=incidents'>On the Incidents tab</a></div></div>";
    });
    el.list.innerHTML = html;
    var half = el.list.querySelector("#map-tick-all[data-half]"); if (half) { half.indeterminate = true; }
    el.list.querySelectorAll("details.map-fold").forEach(function (d) { d.addEventListener("toggle", function () { S.foldOpen = d.open; }); });
    el.list.querySelectorAll(".map-row[data-cam]").forEach(function (r) {
      r.addEventListener("mouseenter", function () { light(S.byId[r.dataset.cam]); });
      r.addEventListener("mouseleave", function () { if (!S.selected) { light(null); } });
    });
    el.list.querySelectorAll(".own-bar").forEach(function (bar) { bar.addEventListener("input", function () { var cam = S.byId[bar.dataset.cam]; cam.own = parseFloat(bar.value); tick(); }); });
  }
  // The list's inputs (chapter 6): a tick, the tick-all box, a file chosen
  // for a row. The rows are redrawn often, so the host listens once.
  function onChange(e) {
    var t = e.target;
    if (t.dataset && t.dataset.tick) { setHidden(S.byId[t.dataset.tick], !t.checked); return; }
    if (t.id === "map-tick-all") { tickAll(t.checked); return; }
    if (t.dataset && t.dataset.addOne) { if (t.files[0]) { addOne(t.dataset.addOne, t.files[0], false); } return; }
    if (t.dataset && t.dataset.replaceOne) { if (t.files[0]) { addOne(t.dataset.replaceOne, t.files[0], true); } return; }
  }
  function setHidden(cam, hide) { if (!cam) { return; } if (hide) { S.hidden[cam.id] = true; } else { delete S.hidden[cam.id]; } afterTicks(); }
  function tickAll(on) { S.hidden = {}; if (!on) { dayCams().forEach(function (c) { S.hidden[c.id] = true; }); } afterTicks(); }
  function only(cam, add) { if (!add) { dayCams().forEach(function (c) { if (c.id !== cam.id) { S.hidden[c.id] = true; } }); } delete S.hidden[cam.id]; afterTicks(); }
  function afterTicks() { rememberHidden(); drawList(); drawStrip(); refreshLayers(); tick(); }

  // The strip ---------------------------------------------------------------------
  function drawStrip() {
    if (!el.strip) { return; }
    var range = span(), cams = shownCams();
    function x(sec) { return Math.max(0, Math.min(100, ((sec - range[0]) / (range[1] - range[0])) * 100)); }
    var html = "<div class='ruler'><div class='head'></div><div class='ticks'>";
    var step = (range[1] - range[0]) > 3 * 3600 ? 1800 : (range[1] - range[0]) > 3600 ? 900 : 300;
    for (var t = Math.ceil(range[0] / step) * step; t <= range[1]; t += step) { html += "<span style='left: " + x(t) + "%'>" + hm(t) + "</span>"; }
    html += "</div></div>";
    cams.forEach(function (cam) {
      var z = cam.zero.second;
      html += "<div class='map-lane lane' data-cam='" + cam.id + "'><div class='head'><i class='" + (cam.source === "car" ? "sq" : "") + "' style='background: " + paint(cam.colour) + "'></i><span class='nm' title='" + esc(cam.unit || cam.title) + "'>" + nameHtml(cam) + "</span><span class='spd mono'></span></div><div class='track'>";
      if (S.hits && S.hits[cam.id]) { S.hits[cam.id].forEach(function (s) { html += "<i class='in' style='left: " + x(z + s[0]) + "%; width: " + Math.max(0.3, x(z + s[1]) - x(z + s[0])) + "%' title='inside the circle " + hms(z + s[0]) + " to " + hms(z + s[1]) + "'></i>"; }); }
      if (cam.fixes.length) {
        cam.segments.forEach(function (seg) { var a = z + seg[0][0], b = z + seg[seg.length - 1][0]; html += "<i style='left: " + x(a) + "%; width: " + Math.max(0.3, x(b) - x(a)) + "%; background: " + paint(cam.colour) + "'></i>"; });
        (cam.gaps || []).forEach(function (g) { html += "<i class='gp' style='left: " + x(z + g[0]) + "%; width: " + Math.max(0.3, x(z + g[1]) - x(z + g[0])) + "%; background: " + paint(cam.colour) + "' title='no fix " + hm(z + g[0]) + " to " + hm(z + g[1]) + "'></i>"; });
      } else {
        html += "<i class='gp' style='left: " + x(z) + "%; width: " + Math.max(0.3, x(z + cam.length) - x(z)) + "%; background: " + paint(cam.colour) + "' title='no position in its file'></i>";
      }
      // The speed trace (chapter 3): an in-car unit's speed along its lane.
      var speeds = (cam.marks || []).filter(function (m) { return m[1] === "speed"; });
      if (speeds.length > 1) {
        var top = Math.max.apply(null, speeds.map(function (m) { return m[2]; })) || 1;
        var pts = speeds.map(function (m) { return x(z + m[0]).toFixed(2) + "," + (17 - (m[2] / top) * 15).toFixed(1); }).join(" ");
        html += "<svg class='spd' viewBox='0 0 100 18' preserveAspectRatio='none' aria-hidden='true'><title>speed, up to " + Math.round(top) + " " + esc((cam.speed_unit || "mph").toLowerCase()) + "</title><polyline points='" + pts + "'></polyline></svg>";
      }
      (cam.clips || []).forEach(function (c) { html += "<i class='clip' style='left: " + x(z + c.start) + "%; width: " + Math.max(0.3, x(z + c.end) - x(z + c.start)) + "%' title='" + esc(c.title) + "' data-preview-recording='" + cam.id + "' data-preview-at='" + c.start + "'></i>"; });
      (cam.events || []).forEach(function (ev, i) {
        var kind = ev.kind; if (["camera", "lights", "siren", "mic", "bookmark"].indexOf(kind) < 0 || !S.events[kind]) { return; }
        var key = "ev:" + cam.id + ":" + i;
        if (kind === "lights" && ev.value && ev.until) { html += "<em class='on' style='left: " + x(z + ev.t) + "%; width: " + Math.max(0.2, x(z + ev.until) - x(z + ev.t)) + "%'></em>"; }
        if (kind === "mic" && !ev.value && ev.until) { html += "<em class='off' style='left: " + x(z + ev.t) + "%; width: " + Math.max(0.2, x(z + ev.until) - x(z + ev.t)) + "%' title='muted " + hms(z + ev.t) + " to " + hms(z + ev.until) + "'></em>"; }
        html += "<em class='mk " + kind + (ev.value ? " is-on" : "") + (S.selected && S.selected.key === key ? " sel" : "") + "' style='left: " + x(z + ev.t) + "%' data-key='" + key + "' title='" + esc(ev.words) + " " + hms(z + ev.t) + "'></em>";
      });
      if (S.events.notes) { (cam.notes || []).forEach(function (n, i) { var key = "note:" + cam.id + ":" + i; html += "<em class='mk note" + (S.selected && S.selected.key === key ? " sel" : "") + "' style='left: " + x(z + n.t) + "%' data-key='" + key + "' title='" + esc(n.words).slice(0, 80) + "'></em>"; }); }
      html += "</div></div>";
    });
    if (!cams.length) { html += "<p class='muted small' style='grid-column: 1 / -1; margin: 6px 0 0'>" + (dayCams().length ? "No camera is ticked: tick one in the list." : "No camera on the clock on this day.") + "</p>"; }
    html += "<div class='playhead' id='map-playhead'><b>" + hm(now()) + "</b></div>";
    el.strip.innerHTML = html;
    el.strip.style.setProperty("--head", host.classList.contains("large") ? "110px" : "");
    wireStrip(range);
    movePlayhead(now());
  }
  function movePlayhead(m) {
    var ph = host.querySelector("#map-playhead"); if (!ph) { return; }
    var range = span(), track = el.strip.querySelector(".ruler .ticks");
    if (!track) { return; }
    var left = track.offsetLeft + ((m - range[0]) / (range[1] - range[0])) * track.offsetWidth;
    ph.style.left = Math.max(track.offsetLeft, Math.min(track.offsetLeft + track.offsetWidth, left)) + "px";
    ph.querySelector("b").textContent = hm(m);
  }
  function wireStrip(range) {
    var dragging = false;
    function at(e) {
      var track = el.strip.querySelector(".ruler .ticks"); var r = track.getBoundingClientRect();
      var px = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
      return range[0] + Math.max(0, Math.min(1, px / r.width)) * (range[1] - range[0]);
    }
    el.strip.addEventListener("mousedown", function (e) { if (e.target.closest("em.mk, i.clip, .head")) { return; } dragging = true; seek(at(e)); e.preventDefault(); });
    document.addEventListener("mousemove", function (e) { if (dragging) { seek(at(e)); } });
    document.addEventListener("mouseup", function () { dragging = false; });
    el.strip.addEventListener("touchstart", function (e) { if (e.target.closest("em.mk, i.clip, .head")) { return; } dragging = true; seek(at(e)); }, { passive: true });
    el.strip.addEventListener("touchmove", function (e) { if (dragging) { seek(at(e)); } }, { passive: true });
    el.strip.addEventListener("touchend", function () { dragging = false; });
    el.strip.addEventListener("click", function (e) { var mk = e.target.closest("em.mk"); if (mk) { selectKey(mk.dataset.key); } });
  }

  // Events and notes ----------------------------------------------------------------
  function allShown() {
    var out = [];
    shownCams().forEach(function (cam) {
      (cam.events || []).forEach(function (ev, i) { if (["camera", "lights", "siren", "mic", "bookmark"].indexOf(ev.kind) >= 0 && S.events[ev.kind]) { out.push({ key: "ev:" + cam.id + ":" + i, cam: cam, t: ev.t, moment: cam.zero.second + ev.t, words: ev.words, until: ev.until, kind: ev.kind }); } });
      if (S.events.notes) { (cam.notes || []).forEach(function (n, i) { out.push({ key: "note:" + cam.id + ":" + i, cam: cam, t: n.t, moment: cam.zero.second + n.t, words: n.words, note: n, kind: "note" }); }); }
    });
    out.sort(function (a, b) { return a.moment - b.moment; });
    return out;
  }
  function selectKey(key) { var found = null; allShown().forEach(function (one) { if (one.key === key) { found = one; } }); if (found) { selectEvent(found); } }
  function selectEvent(one) {
    S.selected = one;
    light(one.cam);
    seek(one.moment);
    refreshLayers(); drawStrip(); drawCard(one);
  }
  function clearSelection() {
    S.selected = null; light(null); closeCard(); refreshLayers(); drawStrip();
    if (S.asking) { S.asking = false; drawTransport(); if (map) { map.getCanvas().style.cursor = ""; } }
  }
  function stepEvent(dir) {
    var m = now(), list = allShown(), pick = null;
    for (var i = 0; i < list.length; i++) { if (dir > 0 && list[i].moment > m + 0.5) { pick = list[i]; break; } if (dir < 0 && list[i].moment < m - 0.5) { pick = list[i]; } }
    if (pick) { selectEvent(pick); }
  }
  function streetAt(cam, t) {
    if (!map || !mapReady || !host.dataset.basemap) { return ""; }
    var p = positionAt(cam, t); if (!p) { return ""; }
    try {
      var pt = map.project([p.lon, p.lat]);
      var hits = map.queryRenderedFeatures([[pt.x - 12, pt.y - 12], [pt.x + 12, pt.y + 12]]);
      for (var i = 0; i < hits.length; i++) { var f = hits[i]; if (f.properties && f.properties.name && /road|street|path/i.test(f.layer.id)) { return f.properties.name; } }
    } catch (e) { /* no street */ }
    return "";
  }
  function closeCard() { var c = host.querySelector(".map-evcard"); if (c) { c.remove(); } }
  function drawCard(one) {
    closeCard();
    var cam = one.cam, z = cam.zero.second;
    var street = streetAt(cam, one.t);
    var card = document.createElement("div");
    card.className = "map-evcard";
    var list = allShown().filter(function (e) { return e.cam.id === cam.id; });
    var index = list.map(function (e) { return e.key; }).indexOf(one.key);
    var prev = index > 0 ? list[index - 1] : null, next = index >= 0 && index < list.length - 1 ? list[index + 1] : null;
    var head = one.kind === "note" ? "Note · " + esc(nameOf(cam)) : esc(one.words) + " · " + esc(nameOf(cam));
    var body = one.kind === "note" ? "<div class='words'>" + esc(one.words) + "</div><span class='muted small'>" + esc(one.note.by) + (one.note.on ? " · " + esc(one.note.on) : "") + (one.note.from ? " · " + esc(one.note.from) : "") + "</span>" :
      "<span class='mono'>" + hms(one.moment) + "</span>" + (street ? " on " + esc(street) : "") + (one.until ? ", until " + hms(z + one.until) : "");
    card.innerHTML = "<b>" + head + "</b>" + body +
      "<div class='acts'><button type='button' class='tiny primary' data-act='play-here' data-cam='" + cam.id + "'>Play here</button>" +
      (one.kind !== "note" && host.dataset.edit ? "<button type='button' class='tiny' data-act='note-event'>Add a note</button>" : "") +
      (one.kind === "note" ? "<a class='btn tiny' href='" + esc(cam.viewer_url) + "?t=" + one.t.toFixed(1) + "&note=1'>Edit</a><a class='btn tiny ghost' href='?tab=notes'>On the Notes tab</a>" : "") +
      (one.kind !== "note" && host.dataset.edit ? "<button type='button' class='tiny' data-act='clip-here' data-cam='" + cam.id + "'>Clip from here</button>" : "") +
      (one.kind !== "note" && one.kind !== "camera" ? offerButton(cam, { kind: one.kind, t: one.t, until: one.until, words: one.words }) : "") +
      (prev ? "<button type='button' class='tiny ghost' data-act='select' data-key='" + prev.key + "'>‹ " + hm(prev.moment) + " " + esc(prev.words).slice(0, 18) + "</button>" : "") +
      (next ? "<button type='button' class='tiny ghost' data-act='select' data-key='" + next.key + "'>" + hm(next.moment) + " " + esc(next.words).slice(0, 18) + " ›</button>" : "") +
      "<button type='button' class='tiny ghost' data-act='clear'>Close</button></div>";
    el.pane.appendChild(card);
    if (map && mapReady) { var p = positionAt(cam, one.t); if (p) { var pt = map.project([p.lon, p.lat]); card.style.left = Math.max(8, Math.min(el.pane.clientWidth - card.offsetWidth - 8, pt.x + 14)) + "px"; card.style.top = Math.max(8, Math.min(el.pane.clientHeight - card.offsetHeight - 8, pt.y - 10)) + "px"; } }
  }
  function noteOn(cam, at, origin) {
    if (!window.UI || !window.UI.prompt) { return; }
    window.UI.prompt({ title: "Note on " + nameOf(cam) + " at " + (cam.onClock ? hms(cam.zero.second + at) : elapsed(at)), body: origin ? "From the map, at " + origin + ". Kept on the recording at this moment, shown on the Notes tab." : "Kept on the recording at this moment, shown on the Notes tab.", ok: "Save the note", placeholder: "The note" }).then(function (words) {
      if (!words) { return; }
      return postJson(host.dataset.noteUrl ? host.dataset.noteUrl : "/recording/" + cam.id + "/note-at", { at: at, note: words }).then(function () { toast("Note kept on " + nameOf(cam) + "."); load(true); });
    }).catch(function (e) { toast(e.message, true); });
  }

  // The Preview -------------------------------------------------------------------
  function openPreview(cam) {
    var ic = incClock();
    if (ic) {
      // On the incident page the wall is the player: the camera comes to the
      // front and the incident's clock runs from here.
      if (!cam.onClock) { toast("That camera is not on the clock.", true); return; }
      ic.focus(cam.id); ic.play(); tick(); return;
    }
    if (!window.Preview || !window.Preview.open) { return; }
    var seconds = cam.onClock ? Math.max(0, now() - cam.zero.second) : (cam.own || 0);
    S.following = cam.onClock ? cam.id : null;
    window.Preview.open({ recording: cam.id, seconds: seconds, from: host, exact: true });
    drawTransport();
  }
  function followPreview() {
    if (INC || !S.following || !window.Preview) { return; }
    if (!window.Preview.isOpen()) { S.following = null; if (S.playing) { pause(); } drawTransport(); return; }
    var asked = window.Preview.asked ? window.Preview.asked() : null;
    if (asked && asked.recording && asked.recording !== S.following) { S.following = S.byId[asked.recording] && S.byId[asked.recording].onClock ? asked.recording : null; drawTransport(); if (!S.following) { return; } }
    var video = window.Preview.media ? window.Preview.media() : null;
    var cam = S.byId[S.following];
    if (!video || !cam) { return; }
    if (!video.paused && !isNaN(video.currentTime)) {
      S.moment = cam.zero.second + video.currentTime; S.playing = false;
      var btn = el.transport.querySelector("[data-act='play']"); if (btn && /Pause/.test(btn.textContent)) { drawTransport(); }
    }
  }

  // The files ----------------------------------------------------------------------
  function wireAdd() {
    var label = document.getElementById("map-add-files");
    if (!label) { return; }
    var input = label.querySelector("input");
    input.addEventListener("change", function () { if (input.files.length) { addMany(Array.prototype.slice.call(input.files), {}, []); input.value = ""; } });
  }
  function addMany(files, chosen, replace) {
    var form = new FormData();
    files.forEach(function (f, i) { form.append("files", f, f.name); form.append("chosen", chosen[i] || ""); });
    replace.forEach(function (id) { form.append("replace", id); });
    toast("Adding " + plural(files.length, "path file") + "...");
    postForm(host.dataset.add, form).then(function (told) {
      var landed = told.landed || [], left = told.leftovers || [];
      if (landed.length) { toast(plural(landed.length, "file") + " added to " + (landed.length === 1 ? "its video" : "their videos") + (left.length ? " · " + left.length + " to settle" : "")); }
      if (left.length) { settle(files, left); } else if (!landed.length) { toast("Nothing was added.", true); }
      load(true);
    }).catch(function (e) { toast(e.message, true); });
  }
  function settle(files, left) {
    var byName = {}; files.forEach(function (f) { byName[f.name] = f; });
    var without = (S.told.videos_without_path || []).concat(S.cams.map(function (c) { return { id: c.id, title: c.title }; }));
    var layer = document.createElement("div");
    layer.className = "map-layer";
    layer.innerHTML = "<div class='map-layer-card'><div class='h'><b>" + plural(left.length, "file") + " to settle</b><button type='button' class='tiny ghost' data-act='layer-close'>Close</button></div>" +
      "<table class='tbl small'><thead><tr><th>File</th><th>What the app found</th><th></th></tr></thead><tbody>" +
      left.map(function (one, i) {
        var what = esc(one.words) + (one.about ? "<br><span class='muted'>" + esc(one.about) + "</span>" : "");
        var act = "";
        if (one.why === "flagged") { what = "Matches <b>" + esc(one.title) + "</b> by name, but: " + what + " <span class='pill warn small'>Flagged</span>"; act = "<label><input type='checkbox' data-i='" + i + "' data-rec='" + one.recording + "'> Add anyway</label>"; }
        else if (one.why === "has_one") { what = "<b>" + esc(one.title) + "</b> already has a path file. <span class='pill small'>Has one</span>"; act = "<label><input type='checkbox' data-i='" + i + "' data-rec='" + one.recording + "' data-replace='1'> Replace</label>"; }
        else if (one.why === "unmatched") { what += " <span class='pill small'>Unmatched</span>"; act = "<select data-i='" + i + "'><option value=''>Choose its video…</option>" + without.map(function (v) { return "<option value='" + v.id + "'>" + esc(v.title) + "</option>"; }).join("") + "</select>"; }
        else { what += " <span class='pill danger small'>Refused</span>"; }
        return "<tr><td class='mono'>" + esc(one.file) + "</td><td>" + what + "</td><td>" + act + "</td></tr>";
      }).join("") + "</tbody></table>" +
      "<div class='acts'><button type='button' class='small' data-act='layer-close'>Close</button><button type='button' class='small primary' data-act='layer-go'>Add the settled files</button></div></div>";
    document.body.appendChild(layer);
    layer.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]"); if (!b) { return; }
      if (b.dataset.act === "layer-close") { layer.remove(); return; }
      if (b.dataset.act === "layer-go") {
        var picked = [], chosen = {}, replace = [];
        layer.querySelectorAll("input[type=checkbox]:checked").forEach(function (c) { var one = left[parseInt(c.dataset.i, 10)]; if (byName[one.file]) { chosen[picked.length] = c.dataset.rec; if (c.dataset.replace) { replace.push(c.dataset.rec); } picked.push(byName[one.file]); } });
        layer.querySelectorAll("select").forEach(function (s) { if (s.value) { var one = left[parseInt(s.dataset.i, 10)]; if (byName[one.file]) { chosen[picked.length] = s.value; picked.push(byName[one.file]); } } });
        layer.remove();
        if (picked.length) { addMany(picked, chosen, replace); }
      }
    });
  }
  function addOne(recordingId, file, replace) {
    var form = new FormData(); form.append("file", file, file.name); if (replace) { form.append("replace", "1"); }
    postForm("/recording/" + recordingId + "/path", form).then(function (told) {
      toast("Path file added: " + told.words + (told.warnings && told.warnings.length ? ". " + told.warnings.join(" ") : ""));
      load(true);
    }).catch(function (e) { toast(e.message, true); });
  }
  function removeOne(cam) {
    if (!window.UI) { return; }
    window.UI.confirm({ title: "Remove the path file from " + nameOf(cam) + "?", body: "The video stays; only its path goes.", ok: "Remove" }).then(function (yes) {
      if (!yes) { return; }
      return postJson("/recording/" + cam.id + "/path/remove", {}).then(function () { toast("Path file removed."); load(true); });
    }).catch(function (e) { toast(e.message, true); });
  }

  // Presses -----------------------------------------------------------------------
  function onPress(e) {
    var chip = e.target.closest(".map-days [data-day]");
    if (chip) { S.day = chip.dataset.day; setAddress(); S.selected = null; S.following = null; load(false); return; }
    if (INC) { var sh = e.target.closest("#map-show [data-show]"); if (sh) { S.show = sh.dataset.show; remember("map-show", S.show); drawShow(); refreshLayers(); tick(); return; } }
    var b = e.target.closest("[data-act]");
    if (b) {
      var cam = b.dataset.cam ? S.byId[b.dataset.cam] : null;
      switch (b.dataset.act) {
        case "play": if (S.playing) { pause(); } else { play(); } drawBar(); return;
        case "back": seek(now() - 10); return;
        case "forward": seek(now() + 10); return;
        case "prev-event": stepEvent(-1); return;
        case "next-event": stepEvent(1); return;
        case "fit": fitAll(); return;
        case "fly": if (cam) { flyTo(cam); } return;
        case "open": if (cam) { S.open = S.open === cam.id ? null : cam.id; drawList(); } return;
        case "tag": if (cam) { select(cam); openPreview(cam); } return;
        case "tick-all": tickAll(true); return;
        case "tick-none": tickAll(false); return;
        case "tick-inside": if (S.hits) { S.hidden = {}; dayCams().forEach(function (c) { if (!S.hits[c.id]) { S.hidden[c.id] = true; } }); afterTicks(); } return;
        case "remove": if (cam) { removeOne(cam); } return;
        case "circle": if (S.circle) { clearCircle(); return; } S.asking = !S.asking; drawTransport(); if (map) { map.getCanvas().style.cursor = S.asking ? "crosshair" : ""; } if (S.asking) { toast("Press a place on the map: a circle appears there, with a handle to widen it."); } return;
        case "clear-circle": clearCircle(); return;
        case "whole-day": S.scope = null; S.incident = ""; setAddress(); drawTransport(); drawList(); drawStrip(); refreshLayers(); fitAll(); return;
        case "large": S.large = !S.large; if (INC) { remember("map-inc-large", S.large ? "1" : "0"); applyLarge(); return; } remember("map-large", S.large ? "1" : "0"); host.classList.toggle("large", S.large); drawTransport(); drawList(); drawStrip(); window.setTimeout(function () { if (map) { map.resize(); } }, 50); return;
        case "picture": savePicture(); return;
        case "leave-full": if (document.exitFullscreen) { document.exitFullscreen(); } return;
        case "fold": host.classList.toggle("folded"); drawList(); return;
        case "play-here": if (cam) { select(cam); openPreview(cam); } return;
        case "own": if (cam) { if (cam.own !== undefined) { delete cam.own; var mk = markers[cam.id]; if (mk) { mk.getElement().classList.add("before"); } } else { cam.own = 0; } drawList(); tick(); if (cam.own !== undefined) { flyTo(cam); } } return;
        case "select": selectKey(b.dataset.key); return;
        case "clear": clearSelection(); return;
        case "note": { var target = S.selected ? S.selected.cam : (S.lit ? S.byId[S.lit] : null); if (!target) { toast("Choose a camera first: press its row or its marker.", true); return; } if (!target.onClock) { toast("That camera is not on the clock.", true); return; } noteOn(target, Math.max(0, now() - target.zero.second), ""); return; }
        case "note-event": if (S.selected) { noteOn(S.selected.cam, S.selected.t, S.selected.words.toLowerCase() + " event"); } return;
        case "clip-here": if (cam) { location.href = cam.viewer_url + "?t=" + Math.max(0, now() - cam.zero.second).toFixed(1) + "&clip=1"; } return;
        case "make-incident": makeIncident(b.dataset.recordings.split(" ")); return;
        case "readings": if (cam) { S.readingsOpen[cam.id] = !S.readingsOpen[cam.id]; drawList(); } return;
        case "offer": if (cam) { offer(cam, parseFloat(b.dataset.t), b.dataset.until === "" ? "" : parseFloat(b.dataset.until), b.dataset.words, b); } return;
        case "go": if (cam) { select(cam); seek(cam.zero.second + parseFloat(b.dataset.t)); flyTo(cam); } return;
      }
    }
    var reading = e.target.closest(".map-readings li[data-key]");
    if (reading && !e.target.closest("button")) {
      var rc = S.byId[reading.closest(".map-readings").dataset.cam];
      var shown = allShown().some(function (one) { return one.key === reading.dataset.key; });
      if (shown) { selectKey(reading.dataset.key); } else if (rc && rc.onClock) { select(rc); seek(rc.zero.second + parseFloat(reading.dataset.t)); } else if (rc) { rc.own = parseFloat(reading.dataset.t); drawList(); tick(); }
      return;
    }
    // A press on the name shows that camera alone (Shift adds it), as a press
    // on one row of a list does; the row's own buttons do the rest.
    var row = e.target.closest(".map-row[data-cam]");
    if (row && !e.target.closest("button, label, input, a")) { var c = S.byId[row.dataset.cam]; select(c); if (ofDay(c)) { only(c, e.shiftKey); } }
  }
  function select(cam) { S.selected = null; S.pressed = cam ? cam.id : null; closeCard(); light(cam); refreshLayers(); }
  // The Incidents tab's own form, posted from here: the incident is made
  // there and the page lands on it.
  function makeIncident(ids) {
    var form = document.createElement("form");
    form.method = "post"; form.action = S.told.new_incident_url;
    var fields = [["csrfmiddlewaretoken", cookie("csrftoken")], ["how", "offer"]].concat(ids.map(function (id) { return ["recordings", id]; }));
    fields.forEach(function (f) { var i = document.createElement("input"); i.type = "hidden"; i.name = f[0]; i.value = f[1]; form.appendChild(i); });
    document.body.appendChild(form); form.submit();
  }
  document.addEventListener("keydown", function (e) {
    if ((e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) || e.ctrlKey || e.metaKey || e.altKey) { return; }
    // On the incident page the keys are that page's; only Escape clears a selection here.
    if (INC && e.key !== "Escape") { return; }
    if (e.key === " ") { e.preventDefault(); if (S.playing) { pause(); } else { play(); } }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seek(now() - (e.shiftKey ? 10 : 1)); }
    else if (e.key === "ArrowRight") { e.preventDefault(); seek(now() + (e.shiftKey ? 10 : 1)); }
    else if (e.key === "Escape") { if (S.selected || S.asking) { clearSelection(); } else if (S.circle) { clearCircle(); } }
  });

  // Save a picture (Phase 12 chapter 5) --------------------------------------------
  // The map's canvas as drawn, the markers drawn onto a copy (they are page
  // elements, not part of the canvas), a band under it with the title, the
  // scale and the map's attribution, then one PNG kept as a Document on the
  // incident shown, or on the camera pressed.
  function pictureHome() {
    if (S.scope) { return { incident: S.scope.id, words: S.scope.name }; }
    var cam = S.selected ? S.selected.cam : (S.pressed ? S.byId[S.pressed] : (S.lit ? S.byId[S.lit] : null));
    if (cam) { return { recording: cam.id, words: cam.title }; }
    return null;
  }
  function pictureTitle(m) { return "Map at " + hms(m) + (S.day ? ", " + dayWords(S.day) : ""); }
  function savePicture() {
    if (!map || !mapReady) { toast("The map is not drawn yet.", true); return; }
    var home = pictureHome();
    if (!home) { toast("Press a camera's row or marker first: the picture is kept as a Document on it, or on the incident when the map is opened from one.", true); return; }
    var m = now();
    map.once("render", function () {
      try {
        var src = map.getCanvas();
        var ratio = src.width / Math.max(1, src.clientWidth);
        var band = Math.round(34 * ratio);
        var out = document.createElement("canvas"); out.width = src.width; out.height = src.height + band;
        var ctx = out.getContext("2d");
        var font = getComputedStyle(document.body).fontFamily || "sans-serif";
        ctx.fillStyle = token("--surface"); ctx.fillRect(0, 0, out.width, out.height);
        ctx.drawImage(src, 0, 0);
        S.cams.forEach(function (cam) {
          var marker = markers[cam.id]; if (!marker) { return; }
          var node = marker.getElement(); if (node.classList.contains("before")) { return; }
          var pt = map.project(marker.getLngLat());
          var x = pt.x * ratio, y = pt.y * ratio, r = 11 * ratio, ended = node.classList.contains("ended");
          ctx.globalAlpha = node.classList.contains("nofix") ? 0.45 : 1;
          ctx.fillStyle = ended ? token("--surface") : colourOf(cam); ctx.strokeStyle = ended ? colourOf(cam) : token("--surface"); ctx.lineWidth = 2 * ratio;
          ctx.beginPath();
          if (cam.source === "car") { ctx.rect(x - r, y - r, 2 * r, 2 * r); } else { ctx.arc(x, y, r, 0, Math.PI * 2); }
          ctx.fill(); ctx.stroke();
          // The camera's name beside its marker, with a halo so it reads on any ground.
          var label = String(nameOf(cam)).slice(0, 28);
          ctx.font = "700 " + Math.round(11 * ratio) + "px " + font; ctx.textAlign = "left"; ctx.textBaseline = "middle";
          ctx.lineWidth = 3 * ratio; ctx.strokeStyle = token("--surface"); ctx.strokeText(label, x + r + 4 * ratio, y);
          ctx.fillStyle = token("--text"); ctx.fillText(label, x + r + 4 * ratio, y);
          ctx.globalAlpha = 1;
        });
        var y0 = src.height, mid = y0 + band / 2;
        ctx.fillStyle = token("--surface"); ctx.fillRect(0, y0, out.width, band);
        ctx.strokeStyle = token("--line"); ctx.lineWidth = ratio; ctx.beginPath(); ctx.moveTo(0, y0 + 0.5); ctx.lineTo(out.width, y0 + 0.5); ctx.stroke();
        ctx.fillStyle = token("--text"); ctx.font = "600 " + Math.round(12 * ratio) + "px " + font; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        ctx.fillText(pictureTitle(m) + " · " + home.words, 10 * ratio, mid);
        var sc = el.pane.querySelector(".maplibregl-ctrl-scale");
        if (sc && sc.offsetWidth) {
          var w = sc.offsetWidth * ratio, sx = out.width / 2 - w / 2;
          ctx.strokeStyle = token("--text"); ctx.lineWidth = 2 * ratio; ctx.beginPath(); ctx.moveTo(sx, mid - 4 * ratio); ctx.lineTo(sx, mid + 4 * ratio); ctx.lineTo(sx + w, mid + 4 * ratio); ctx.lineTo(sx + w, mid - 4 * ratio); ctx.stroke();
          ctx.font = Math.round(10 * ratio) + "px " + font; ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.fillText(sc.textContent, sx + w / 2, mid - 5 * ratio);
        }
        if (host.dataset.basemap) { ctx.fillStyle = token("--muted"); ctx.font = Math.round(10 * ratio) + "px " + font; ctx.textAlign = "right"; ctx.textBaseline = "middle"; ctx.fillText(host.dataset.attribution || "", out.width - 10 * ratio, mid); }
        out.toBlob(function (blob) {
          if (!blob) { toast("The picture could not be drawn.", true); return; }
          var form = new FormData();
          form.append("file", blob, "map.png"); form.append("title", pictureTitle(m) + ", " + home.words);
          if (home.incident) { form.append("incident", home.incident); }
          if (home.recording) { form.append("recording", home.recording); }
          postForm(host.dataset.picture, form).then(function (told) { toast(told.words || "Saved."); }).catch(function (err) { toast(err.message, true); });
        }, "image/png");
      } catch (e) { toast("The picture could not be drawn.", true); }
    });
    map.triggerRepaint();
  }

  // The address --------------------------------------------------------------------
  function askedMoment() {
    if (INC) { return null; }
    var rec = host.dataset.recording, at = parseFloat(host.dataset.at);
    if (rec && S.byId[rec] && S.byId[rec].onClock && !isNaN(at)) { var cam = S.byId[rec]; if (cam.date === S.day) { window.setTimeout(function () { select(cam); flyTo(cam); }, 300); return cam.zero.second + at; } }
    if (S.scope) { var low = Infinity; S.scope.cameras.forEach(function (id) { var c = S.byId[id]; if (c && c.onClock) { low = Math.min(low, c.zero.second); } }); if (low < Infinity) { return low; } }
    return null;
  }
  function setAddress() {
    if (INC) { return; }
    var p = new URLSearchParams(location.search);
    p.set("tab", "map");
    if (S.day) { p.set("day", S.day); } else { p.delete("day"); }
    if (S.incident) { p.set("incident", S.incident); } else { p.delete("incident"); }
    p.delete("recording"); p.delete("at");
    history.replaceState(null, "", location.pathname + "?" + p.toString());
  }

  function wantedDay() {
    if (host.dataset.day) { return ""; }
    var rec = host.dataset.recording;
    if (rec && S.byId[rec] && S.byId[rec].onClock) { return S.byId[rec].date; }
    if (S.scope && S.scope.date) { return S.scope.date; }
    return "";
  }
  if (host.dataset.day) { S.day = host.dataset.day; }
  load(false);
})();

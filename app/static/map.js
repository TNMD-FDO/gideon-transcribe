// The Map tab (Phase 12 chapter 1; the drawing docs/spec/mockups/phase-12-map.html):
// every camera's path from the file beside its video, on one clock, with the
// video a press away. One reading of map.json; the street map from the file
// the Admin placed, drawn by the vendored library, or plain ground without it;
// the clock as the incident page runs it; the Preview as the player.
(function () {
  "use strict";
  var host = document.getElementById("case-map");
  if (!host || !window.maplibregl) { return; }

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
    show: recall("map-show") || "trails", large: recall("map-large") === "1",
    events: {}, incident: host.dataset.incident || "", scope: null
  };
  EVENT_KINDS.forEach(function (k) { S.events[k] = recall("map-ev-" + k) !== "0" || k === "notes"; });
  if (recall("map-ev-bookmark") === null) { S.events.bookmark = false; }

  var map = null, mapReady = false, markers = {}, trailIndex = {}, el = {};

  // The reading ------------------------------------------------------------------
  function load(quiet) {
    var url = host.dataset.json + (S.day ? "?day=" + encodeURIComponent(S.day) : "");
    if (!quiet) { host.innerHTML = "<p class='muted small'>Reading the paths...</p><div class='skeleton' aria-hidden='true'><i></i><i></i><i></i></div>"; }
    return fetch(url, { credentials: "same-origin" }).then(function (a) { return a.json(); }).then(function (told) {
      S.told = told; S.day = told.day || ""; S.loaded = true;
      prepare();
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
  function now() { if (!S.playing) { return S.moment; } return S.anchorMoment + ((performance.now() - S.anchorNow) / 1000) * S.speed; }
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
  function play() { S.anchorMoment = now(); S.anchorNow = performance.now(); S.playing = true; drawTransport(); tick(); }
  function pause() { S.moment = now(); S.playing = false; drawTransport(); tick(); }
  function seek(at, fromPreview) {
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
    host.classList.toggle("large", S.large);
    host.innerHTML =
      "<div class='map-lead'>" +
        "<div class='map-lead-left'>" + dayChips() +
          "<div class='map-show'><span class='muted small'>Show</span><span class='seg' id='map-show'>" +
            seg("markers", "Markers only") + seg("trails", "Trails") + seg("whole", "Whole paths") + "</span>" +
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
    host.addEventListener("click", onPress);
    var asked = askedMoment();
    S.moment = asked !== null ? asked : span()[0] + 60;
    drawTransport(); drawShow(); drawMap(); drawList(); drawStrip(); drawBar();
    wireAdd();
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
    var scope = S.scope ? "<span class='pill small acc' title='" + esc(S.scope.name) + "'>" + esc(S.scope.name) + "</span> <button type='button' class='tiny ghost' data-act='whole-day'>whole day</button>" : "";
    el.transport.innerHTML =
      scope +
      "<button type='button' class='small primary' data-act='play'>" + (S.playing ? "<svg class='i' aria-hidden='true'><use href='#i-pause'></use></svg> Pause" : "<svg class='i' aria-hidden='true'><use href='#i-play'></use></svg> Play") + "</button>" +
      "<button type='button' class='small' data-act='back'>−10 s</button><button type='button' class='small' data-act='forward'>+10 s</button>" +
      "<button type='button' class='small' data-act='prev-event' title='The previous event'>‹ event</button><button type='button' class='small' data-act='next-event' title='The next event'>event ›</button>" +
      "<select class='small' id='map-speed' title='Speed'>" + [1, 4, 16, 60].map(function (v) { return "<option value='" + v + "'" + (v === S.speed ? " selected" : "") + ">Speed " + v + "×</option>"; }).join("") + "</select>" +
      "<span class='map-clock-wrap'><span class='map-clock mono' id='map-clock'>" + hms(m) + "</span><span class='map-zone'>" + esc(host.dataset.tz || "") + (S.day ? " · " + esc(dayWords(S.day)) : "") + "</span></span>" +
      (S.following ? "<span class='pill small acc'>following " + esc((S.byId[S.following] || {}).unit || (S.byId[S.following] || {}).title || "") + "</span>" : "") +
      "<button type='button' class='small' data-act='fit'>Fit all</button>" +
      "<button type='button' class='small' data-act='note' title='A note on the selected camera at this moment'>Note here</button>" +
      "<button type='button' class='small " + (S.large ? "on" : "") + "' data-act='large'>" + (S.large ? "Smaller map" : "Larger map") + "</button>";
    el.transport.querySelector("#map-speed").addEventListener("change", function (e) { S.speed = parseInt(e.target.value, 10) || 1; if (S.playing) { S.anchorMoment = now(); S.anchorNow = performance.now(); } tick(); });
  }
  function drawBar() {
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
      map.on("load", function () { mapReady = true; addLayers(); fitAll(); drawList(); tick(); });
      map.on("moveend", function () { drawList(); });
      map.on("click", "map-events", function (e) { var f = e.features && e.features[0]; if (f) { selectKey(f.properties.key); } });
      map.on("mouseenter", "map-events", function () { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "map-events", function () { map.getCanvas().style.cursor = ""; });
      document.addEventListener("fullscreenchange", function () { host.classList.toggle("full", document.fullscreenElement === el.wrap); drawBar(); window.setTimeout(function () { map.resize(); }, 50); });
    });
    var observer = new MutationObserver(function () { if (map) { groundStyle().then(function (style) { map.setStyle(style); map.once("style.load", function () { addLayers(); refreshLayers(); }); recolourMarkers(); }); } });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
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
      if (!cam.fixes.length) { return; }
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
    map.addLayer({ id: "map-paths", type: "line", source: "map-paths", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "colour"], "line-width": ["case", ["boolean", ["feature-state", "lit"], false], 5, 2.5], "line-opacity": S.show === "whole" ? 0.9 : 0.35 } });
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
    if (map.getLayer("map-paths")) { map.setPaintProperty("map-paths", "line-opacity", S.show === "whole" ? 0.9 : S.show === "markers" && recall("map-faint") === "0" ? 0 : 0.35); }
    Object.keys(trailIndex).forEach(function (id) { trailIndex[id] = -2; });
  }
  function drawMarkers() {
    Object.keys(markers).forEach(function (id) { markers[id].remove(); });
    markers = {};
    S.cams.forEach(function (cam) {
      if (!cam.fixes.length) { return; }
      var node = document.createElement("div");
      node.className = "map-head " + (cam.source === "car" ? "car" : "body");
      node.style.setProperty("--cam", colourOf(cam));
      node.innerHTML = "<b>" + esc(cam.unit || cam.title) + "</b><i class='badge' aria-hidden='true'></i>";
      node.title = cam.title + (cam.wearer ? " · " + cam.wearer : "");
      node.addEventListener("click", function (e) { e.stopPropagation(); select(cam); openPreview(cam); });
      var marker = new maplibregl.Marker({ element: node, anchor: "center" }).setLngLat([cam.fixes[0][2], cam.fixes[0][1]]).addTo(map);
      markers[cam.id] = marker;
    });
  }
  function recolourMarkers() { S.cams.forEach(function (cam) { var m = markers[cam.id]; if (m) { m.getElement().style.setProperty("--cam", colourOf(cam)); } }); }
  function fitAll() {
    if (!map) { return; }
    var cams = dayCams().filter(function (c) { return c.bounds; });
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
      var head = host.querySelector(".map-lane[data-cam='" + cam.id + "'] .spd");
      if (head) { head.textContent = flags.speed !== undefined ? Math.round(flags.speed) + " " + (cam.speed_unit || "mph").toLowerCase() : ""; }
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
  function rowOf(cam, dim) {
    var spanWords = cam.onClock ? hm(cam.zero.second) + " to " + hm(cam.zero.second + (cam.length || 0)) : elapsed(cam.length || 0) + " long";
    var streams = cam.streams.length ? "<div class='streams'><span>stream 1</span>" + cam.streams.map(function (s, i) { return "<span>stream " + (i + 2) + "</span>"; }).join("") + "</div>" : "";
    var noFix = !cam.fixes.length ? "<span class='pill small'>no position</span>" : "";
    var acts = "<button type='button' class='tiny' data-act='play-here' data-cam='" + cam.id + "'>Play here</button>" +
      (host.dataset.edit ? "<button type='button' class='tiny ghost' data-act='more' data-cam='" + cam.id + "' title='Replace or remove the path file'>⋯</button>" : "");
    return "<div class='map-row " + (dim ? "dim " : "") + (S.lit === cam.id ? "lit" : "") + "' data-cam='" + cam.id + "' tabindex='0'>" +
      "<span class='dot " + (cam.source === "car" ? "sq" : "") + "' style='background: " + paint(cam.colour) + "'></span>" +
      "<div><b>" + esc(cam.unit || cam.title) + "</b> <span class='muted small'>" + esc(cam.wearer || cam.title) + "</span>" +
      "<div class='facts'>" + suretyPill(cam) + "<span class='mono'>" + spanWords + "</span><span>" + (cam.source === "car" ? "in-car" : "body") + "</span>" + noFix +
      (!cam.onClock ? "<button type='button' class='tiny' data-act='own' data-cam='" + cam.id + "'>" + (cam.own !== undefined ? "Hide it" : "Show on its own") + "</button>" : "") + "</div>" + streams +
      (cam.own !== undefined ? "<input type='range' class='own-bar' data-cam='" + cam.id + "' min='0' max='" + Math.round(cam.length || 0) + "' value='" + Math.round(cam.own) + "'>" : "") +
      "</div><div class='acts'>" + acts + "</div></div>";
  }
  function drawList() {
    if (!el.list) { return; }
    var cams = S.cams.filter(scoped);
    var today = cams.filter(ofDay), other = cams.filter(function (c) { return c.onClock && !ofDay(c); }), off = cams.filter(function (c) { return !c.onClock; });
    var seen = today.filter(inView), unseen = today.filter(function (c) { return !inView(c); });
    var html = "<div class='h'><span>" + (today.length ? seen.length + " of " + today.length + " in view" : "no camera on this day") + "</span>" + (host.classList.contains("large") ? "<button type='button' class='tiny ghost' data-act='fold'>" + (host.classList.contains("folded") ? "‹ show" : "fold ›") + "</button>" : "") + "</div>";
    seen.forEach(function (c) { html += rowOf(c, false); });
    if (unseen.length) { html += "<details class='map-fold' " + (S.foldOpen ? "open" : "") + "><summary>" + plural(unseen.length, "more camera") + " out of view</summary>" + unseen.map(function (c) { return rowOf(c, true); }).join("") + "</details>"; }
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
    el.list.querySelectorAll("details.map-fold").forEach(function (d) { d.addEventListener("toggle", function () { S.foldOpen = d.open; }); });
    el.list.querySelectorAll(".map-row[data-cam]").forEach(function (r) {
      r.addEventListener("mouseenter", function () { light(S.byId[r.dataset.cam]); });
      r.addEventListener("mouseleave", function () { if (!S.selected) { light(null); } });
    });
    el.list.querySelectorAll(".own-bar").forEach(function (bar) { bar.addEventListener("input", function () { var cam = S.byId[bar.dataset.cam]; cam.own = parseFloat(bar.value); tick(); }); });
    el.list.querySelectorAll("[data-add-one]").forEach(function (input) { input.addEventListener("change", function () { if (input.files[0]) { addOne(input.dataset.addOne, input.files[0], false); } }); });
  }

  // The strip ---------------------------------------------------------------------
  function drawStrip() {
    if (!el.strip) { return; }
    var range = span(), cams = dayCams();
    function x(sec) { return Math.max(0, Math.min(100, ((sec - range[0]) / (range[1] - range[0])) * 100)); }
    var html = "<div class='ruler'><div class='head'></div><div class='ticks'>";
    var step = (range[1] - range[0]) > 3 * 3600 ? 1800 : (range[1] - range[0]) > 3600 ? 900 : 300;
    for (var t = Math.ceil(range[0] / step) * step; t <= range[1]; t += step) { html += "<span style='left: " + x(t) + "%'>" + hm(t) + "</span>"; }
    html += "</div></div>";
    cams.forEach(function (cam) {
      var z = cam.zero.second;
      html += "<div class='map-lane lane' data-cam='" + cam.id + "'><div class='head'><i class='" + (cam.source === "car" ? "sq" : "") + "' style='background: " + paint(cam.colour) + "'></i><span class='nm'>" + esc(cam.unit || cam.title) + "</span><span class='spd mono'></span></div><div class='track'>";
      if (cam.fixes.length) {
        cam.segments.forEach(function (seg) { var a = z + seg[0][0], b = z + seg[seg.length - 1][0]; html += "<i style='left: " + x(a) + "%; width: " + Math.max(0.3, x(b) - x(a)) + "%; background: " + paint(cam.colour) + "'></i>"; });
        (cam.gaps || []).forEach(function (g) { html += "<i class='gp' style='left: " + x(z + g[0]) + "%; width: " + Math.max(0.3, x(z + g[1]) - x(z + g[0])) + "%; background: " + paint(cam.colour) + "' title='no fix " + hm(z + g[0]) + " to " + hm(z + g[1]) + "'></i>"; });
      } else {
        html += "<i class='gp' style='left: " + x(z) + "%; width: " + Math.max(0.3, x(z + cam.length) - x(z)) + "%; background: " + paint(cam.colour) + "' title='no position in its file'></i>";
      }
      (cam.clips || []).forEach(function (c) { html += "<i class='clip' style='left: " + x(z + c.start) + "%; width: " + Math.max(0.3, x(z + c.end) - x(z + c.start)) + "%' title='" + esc(c.title) + "' data-preview-recording='" + cam.id + "' data-preview-at='" + c.start + "'></i>"; });
      (cam.events || []).forEach(function (ev, i) {
        var kind = ev.kind; if (["camera", "lights", "siren", "mic", "bookmark"].indexOf(kind) < 0 || !S.events[kind]) { return; }
        var key = "ev:" + cam.id + ":" + i;
        if (kind === "lights" && ev.value && ev.until) { html += "<em class='on' style='left: " + x(z + ev.t) + "%; width: " + Math.max(0.2, x(z + ev.until) - x(z + ev.t)) + "%'></em>"; }
        html += "<em class='mk " + kind + (ev.value ? " is-on" : "") + (S.selected && S.selected.key === key ? " sel" : "") + "' style='left: " + x(z + ev.t) + "%' data-key='" + key + "' title='" + esc(ev.words) + " " + hms(z + ev.t) + "'></em>";
      });
      if (S.events.notes) { (cam.notes || []).forEach(function (n, i) { var key = "note:" + cam.id + ":" + i; html += "<em class='mk note" + (S.selected && S.selected.key === key ? " sel" : "") + "' style='left: " + x(z + n.t) + "%' data-key='" + key + "' title='" + esc(n.words).slice(0, 80) + "'></em>"; }); }
      html += "</div></div>";
    });
    if (!cams.length) { html += "<p class='muted small' style='grid-column: 1 / -1; margin: 6px 0 0'>No camera on the clock on this day.</p>"; }
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
    dayCams().forEach(function (cam) {
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
  function clearSelection() { S.selected = null; light(null); closeCard(); refreshLayers(); drawStrip(); }
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
    var head = one.kind === "note" ? "Note · " + esc(cam.unit || cam.title) : esc(one.words) + " · " + esc(cam.unit || cam.title);
    var body = one.kind === "note" ? "<div class='words'>" + esc(one.words) + "</div><span class='muted small'>" + esc(one.note.by) + (one.note.on ? " · " + esc(one.note.on) : "") + (one.note.from ? " · " + esc(one.note.from) : "") + "</span>" :
      "<span class='mono'>" + hms(one.moment) + "</span>" + (street ? " on " + esc(street) : "") + (one.until ? ", until " + hms(z + one.until) : "");
    card.innerHTML = "<b>" + head + "</b>" + body +
      "<div class='acts'><button type='button' class='tiny primary' data-act='play-here' data-cam='" + cam.id + "'>Play here</button>" +
      (one.kind !== "note" && host.dataset.edit ? "<button type='button' class='tiny' data-act='note-event'>Add a note</button>" : "") +
      (one.kind === "note" ? "<a class='btn tiny' href='" + esc(cam.viewer_url) + "?t=" + one.t.toFixed(1) + "&note=1'>Edit</a><a class='btn tiny ghost' href='?tab=notes'>On the Notes tab</a>" : "") +
      (one.kind !== "note" && host.dataset.edit ? "<button type='button' class='tiny' data-act='clip-here' data-cam='" + cam.id + "'>Clip from here</button>" : "") +
      (prev ? "<button type='button' class='tiny ghost' data-act='select' data-key='" + prev.key + "'>‹ " + hm(prev.moment) + " " + esc(prev.words).slice(0, 18) + "</button>" : "") +
      (next ? "<button type='button' class='tiny ghost' data-act='select' data-key='" + next.key + "'>" + hm(next.moment) + " " + esc(next.words).slice(0, 18) + " ›</button>" : "") +
      "<button type='button' class='tiny ghost' data-act='clear'>Close</button></div>";
    el.pane.appendChild(card);
    if (map && mapReady) { var p = positionAt(cam, one.t); if (p) { var pt = map.project([p.lon, p.lat]); card.style.left = Math.max(8, Math.min(el.pane.clientWidth - card.offsetWidth - 8, pt.x + 14)) + "px"; card.style.top = Math.max(8, Math.min(el.pane.clientHeight - card.offsetHeight - 8, pt.y - 10)) + "px"; } }
  }
  function noteOn(cam, at, origin) {
    if (!window.UI || !window.UI.prompt) { return; }
    window.UI.prompt({ title: "Note on " + (cam.unit || cam.title) + " at " + (cam.onClock ? hms(cam.zero.second + at) : elapsed(at)), body: origin ? "From the map, at " + origin + ". Kept on the recording at this moment, shown on the Notes tab." : "Kept on the recording at this moment, shown on the Notes tab.", ok: "Save the note", placeholder: "The note" }).then(function (words) {
      if (!words) { return; }
      return postJson(host.dataset.noteUrl ? host.dataset.noteUrl : "/recording/" + cam.id + "/note-at", { at: at, note: words }).then(function () { toast("Note kept on " + (cam.unit || cam.title) + "."); load(true); });
    }).catch(function (e) { toast(e.message, true); });
  }

  // The Preview -------------------------------------------------------------------
  function openPreview(cam) {
    if (!window.Preview || !window.Preview.open) { return; }
    var seconds = cam.onClock ? Math.max(0, now() - cam.zero.second) : (cam.own || 0);
    S.following = cam.onClock ? cam.id : null;
    window.Preview.open({ recording: cam.id, seconds: seconds, from: host, exact: true });
    drawTransport();
  }
  function followPreview() {
    if (!S.following || !window.Preview) { return; }
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
    window.UI.confirm({ title: "Remove the path file from " + (cam.unit || cam.title) + "?", body: "The video stays; only its path goes.", ok: "Remove" }).then(function (yes) {
      if (!yes) { return; }
      return postJson("/recording/" + cam.id + "/path/remove", {}).then(function () { toast("Path file removed."); load(true); });
    }).catch(function (e) { toast(e.message, true); });
  }
  function more(cam, from) {
    var menu = document.createElement("div");
    menu.className = "map-menu";
    menu.innerHTML = "<label class='btn tiny'>Replace the path file<input type='file' accept='.vtt,text/vtt' hidden></label><button type='button' class='tiny danger' data-act='remove-path'>Remove the path file</button><a class='btn tiny ghost' href='" + esc(cam.viewer_url) + "'>Open the recording</a>";
    from.parentNode.appendChild(menu);
    menu.querySelector("input").addEventListener("change", function (e) { if (e.target.files[0]) { addOne(cam.id, e.target.files[0], true); } menu.remove(); });
    menu.querySelector("[data-act='remove-path']").addEventListener("click", function () { menu.remove(); removeOne(cam); });
    window.setTimeout(function () { document.addEventListener("click", function once() { menu.remove(); document.removeEventListener("click", once); }); }, 0);
  }

  // Presses -----------------------------------------------------------------------
  function onPress(e) {
    var chip = e.target.closest(".map-days [data-day]");
    if (chip) { S.day = chip.dataset.day; setAddress(); S.selected = null; S.following = null; load(false); return; }
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
        case "whole-day": S.scope = null; S.incident = ""; setAddress(); drawTransport(); drawList(); drawStrip(); refreshLayers(); fitAll(); return;
        case "large": S.large = !S.large; remember("map-large", S.large ? "1" : "0"); host.classList.toggle("large", S.large); drawTransport(); drawList(); drawStrip(); window.setTimeout(function () { if (map) { map.resize(); } }, 50); return;
        case "leave-full": if (document.exitFullscreen) { document.exitFullscreen(); } return;
        case "fold": host.classList.toggle("folded"); drawList(); return;
        case "play-here": if (cam) { select(cam); openPreview(cam); } return;
        case "own": if (cam) { if (cam.own !== undefined) { delete cam.own; var mk = markers[cam.id]; if (mk) { mk.getElement().classList.add("before"); } } else { cam.own = 0; } drawList(); tick(); if (cam.own !== undefined) { flyTo(cam); } } return;
        case "more": if (cam) { e.stopPropagation(); more(cam, b); } return;
        case "select": selectKey(b.dataset.key); return;
        case "clear": clearSelection(); return;
        case "note": { var target = S.selected ? S.selected.cam : (S.lit ? S.byId[S.lit] : null); if (!target) { toast("Choose a camera first: press its row or its marker.", true); return; } if (!target.onClock) { toast("That camera is not on the clock.", true); return; } noteOn(target, Math.max(0, now() - target.zero.second), ""); return; }
        case "note-event": if (S.selected) { noteOn(S.selected.cam, S.selected.t, S.selected.words.toLowerCase() + " event"); } return;
        case "clip-here": if (cam) { location.href = cam.viewer_url + "?t=" + Math.max(0, now() - cam.zero.second).toFixed(1) + "&clip=1"; } return;
        case "make-incident": makeIncident(b.dataset.recordings.split(" ")); return;
      }
    }
    var row = e.target.closest(".map-row[data-cam]");
    if (row && !e.target.closest("button, label, input, a")) { var c = S.byId[row.dataset.cam]; select(c); flyTo(c); }
  }
  function select(cam) { S.selected = null; closeCard(); light(cam); refreshLayers(); }
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
    if (e.key === " ") { e.preventDefault(); if (S.playing) { pause(); } else { play(); } }
    else if (e.key === "ArrowLeft") { e.preventDefault(); seek(now() - (e.shiftKey ? 10 : 1)); }
    else if (e.key === "ArrowRight") { e.preventDefault(); seek(now() + (e.shiftKey ? 10 : 1)); }
    else if (e.key === "Escape" && S.selected) { clearSelection(); }
  });

  // The address --------------------------------------------------------------------
  function askedMoment() {
    var rec = host.dataset.recording, at = parseFloat(host.dataset.at);
    if (rec && S.byId[rec] && S.byId[rec].onClock && !isNaN(at)) { var cam = S.byId[rec]; if (cam.date === S.day) { window.setTimeout(function () { select(cam); flyTo(cam); }, 300); return cam.zero.second + at; } }
    if (S.scope) { var low = Infinity; S.scope.cameras.forEach(function (id) { var c = S.byId[id]; if (c && c.onClock) { low = Math.min(low, c.zero.second); } }); if (low < Infinity) { return low; } }
    return null;
  }
  function setAddress() {
    var p = new URLSearchParams(location.search);
    p.set("tab", "map");
    if (S.day) { p.set("day", S.day); } else { p.delete("day"); }
    if (S.incident) { p.set("incident", S.incident); } else { p.delete("incident"); }
    p.delete("recording"); p.delete("at");
    history.replaceState(null, "", location.pathname + "?" + p.toString());
  }

  if (host.dataset.day) { S.day = host.dataset.day; }
  if (host.dataset.recording && S.day === "") { /* the day comes from the camera asked for */ }
  load(false).then(function () {
    var rec = host.dataset.recording;
    if (rec && S.byId[rec] && S.byId[rec].onClock && S.byId[rec].date !== S.day && !host.dataset.day) { S.day = S.byId[rec].date; load(false); }
    if (S.scope && S.scope.date && S.scope.date !== S.day && !host.dataset.day) { S.day = S.scope.date; load(false); }
  });
})();

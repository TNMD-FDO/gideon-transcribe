// The waveform (Phase 9 chapter 4): a recording's peaks drawn on a canvas,
// the played part in the accent, with a mark for each note and the playhead.
// The reading of the peaks file is the recording page's (viewer.js): a few
// pairs per pixel, the lowest low and the highest high of the pairs a pixel
// covers, worked out once per width.

(function () {
  "use strict";

  function ink(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  }

  function reduce(peaks, width) {
    if (!peaks || !peaks.data) { return null; }
    var channels = peaks.channels || 1;
    var pairs = Math.floor(peaks.data.length / (2 * channels));
    var scale = Math.pow(2, (peaks.bits || 8) - 1);
    var lows = new Float32Array(width * channels);
    var highs = new Float32Array(width * channels);
    for (var x = 0; x < width; x += 1) {
      var first = Math.floor((x / width) * pairs);
      var last = Math.max(first + 1, Math.floor(((x + 1) / width) * pairs));
      for (var channel = 0; channel < channels; channel += 1) {
        var low = 0, high = 0;
        for (var index = first; index < last && index < pairs; index += 1) {
          var here = (index * channels + channel) * 2;
          if (peaks.data[here] < low) { low = peaks.data[here]; }
          if (peaks.data[here + 1] > high) { high = peaks.data[here + 1]; }
        }
        lows[x * channels + channel] = low / scale;
        highs[x * channels + channel] = high / scale;
      }
    }
    return { width: width, channels: channels, lows: lows, highs: highs };
  }

  // One strip per canvas, remembered by width and by the peaks it came from.
  var kept = new WeakMap();

  function draw(canvas, given) {
    var width = canvas.clientWidth;
    if (!width) { return; }
    var height = given.height || 44;
    var ratio = window.devicePixelRatio || 1;
    if (canvas.width !== Math.floor(width * ratio)) {
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      canvas.style.height = height + "px";
    }
    var pen = canvas.getContext("2d");
    pen.setTransform(ratio, 0, 0, ratio, 0, 0);
    pen.clearRect(0, 0, width, height);
    pen.fillStyle = ink("--surface-2");
    pen.fillRect(0, 0, width, height);
    var duration = given.duration || 0;
    var time = given.time || 0;
    var strip = kept.get(canvas);
    if (!strip || strip.width !== width || strip.from !== given.peaks) {
      strip = reduce(given.peaks, width);
      if (strip) { strip.from = given.peaks; kept.set(canvas, strip); }
    }
    if (strip) {
      var played = ink("--accent"), unplayed = ink("--muted");
      var lane = strip.channels === 2 ? height / 2 : height;
      for (var x = 0; x < width; x += 1) {
        pen.fillStyle = duration && (x / width) * duration <= time ? played : unplayed;
        for (var channel = 0; channel < strip.channels; channel += 1) {
          var at = x * strip.channels + channel;
          var middle = strip.channels === 2 ? lane * channel + lane / 2 : height / 2;
          var top = middle - Math.max(1, strip.highs[at] * (lane / 2 - 1));
          pen.fillRect(x, top, 1, Math.max(1, (strip.highs[at] - strip.lows[at]) * (lane / 2 - 1)));
        }
      }
    }
    // The notes' marks and the playhead.
    if (duration) {
      pen.fillStyle = ink("--warn");
      (given.ticks || []).forEach(function (seconds) {
        pen.fillRect(Math.round((seconds / duration) * width) - 1, 0, 2, height);
      });
      pen.fillStyle = ink("--danger");
      pen.fillRect(Math.round((time / duration) * width) - 1, 0, 2, height);
    }
  }

  window.Waveform = { draw: draw };
})();

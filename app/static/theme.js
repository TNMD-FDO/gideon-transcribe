// Light or dark, chosen once and remembered.
//
// The choice is written before the page paints (in base.html), so this only
// has to handle somebody pressing the button. Three states in turn: dark,
// light, and whatever the browser itself is set to.

(function () {
  "use strict";

  var button = document.getElementById("theme");
  if (!button) { return; }

  function show() {
    var now = document.documentElement.getAttribute("data-theme");
    button.textContent = now === "dark" ? "☀" : "☽";
    button.title = now
      ? "Now " + now + ". Click for " + (now === "dark" ? "light" : "the browser's own")
      : "Following the browser. Click for dark";
  }

  button.addEventListener("click", function () {
    var root = document.documentElement;
    var now = root.getAttribute("data-theme");
    var next = now === "dark" ? "light" : (now === "light" ? "" : "dark");

    if (next) { root.setAttribute("data-theme", next); }
    else { root.removeAttribute("data-theme"); }
    try { window.localStorage.setItem("theme", next); } catch (ignored) { /* fine */ }

    show();
    // The waveform is drawn with the theme's own colours, so it is redrawn.
    if (window.VIEWER && window.VIEWER.redraw) { window.VIEWER.redraw(); }
  });

  show();
})();

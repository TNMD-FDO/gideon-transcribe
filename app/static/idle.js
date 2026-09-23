// The idle warning: a countdown in the browser, because the server can only
// tell a page the time left at the moment it loads.
//
// Every request a person makes moves their idle clock on, so the countdown
// starts at the whole timeout on every page load. Fifteen minutes before the
// end the banner appears, and Stay signed in is a request like any other,
// which is what moves the clock.
//
// At nought the page does not guess (Phase 8 chapter 7): it asks the server
// once whether the session is still open, with a question that does not move
// the clock. A second tab that kept the clock moving makes the server say
// so, and the countdown starts again from the time left; a session that has
// ended is answered with the 401 that session.js turns into the ended line.

(function () {
  "use strict";

  var WARN_AT = 15 * 60;

  var banner = document.getElementById("idle-warning");
  var words = document.getElementById("idle-words");
  var stay = document.getElementById("stay");
  if (!banner || !window.IDLE_SECONDS) { return; }

  var left = window.IDLE_SECONDS;

  function warn() {
    var minutes = Math.ceil(left / 60);
    words.textContent =
      "You will be signed out in " + minutes +
      (minutes === 1 ? " minute" : " minutes") +
      " and your recordings and transcripts removed.";
    banner.hidden = false;
  }

  function ask() {
    fetch("/session", { cache: "no-store" })
      .then(function (answer) { return answer.ok ? answer.json() : null; })
      .then(function (body) {
        if (!body || !body.signed_in) { return; }
        left = Math.max(30, body.left || 0);
        if (left > WARN_AT) { banner.hidden = true; } else { warn(); }
        window.setTimeout(tick, 30000);
      })
      .catch(function () { /* session.js has said what there is to say */ });
  }

  function tick() {
    left -= 30;
    if (left <= 0) { ask(); return; }
    if (left <= WARN_AT) { warn(); }
    window.setTimeout(tick, 30000);
  }

  stay.addEventListener("click", function () {
    // Any request moves the clock; this one asks for the smallest page there
    // is and throws the answer away.
    fetch(window.location.pathname, { method: "GET", cache: "no-store" })
      .then(function () {
        left = window.IDLE_SECONDS;
        banner.hidden = true;
      })
      .catch(function () { /* the ended line has taken the banner */ });
  });

  window.setTimeout(tick, 30000);
})();

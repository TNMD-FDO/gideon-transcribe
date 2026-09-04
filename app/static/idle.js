// The idle warning: a countdown in the browser, because the server can only
// tell a page the time left at the moment it loads.
//
// Every request a person makes moves their idle clock on, so the countdown
// starts at the whole timeout on every page load. Fifteen minutes before the
// end the banner appears, and Stay signed in is a request like any other,
// which is what moves the clock.

(function () {
  "use strict";

  var WARN_AT = 15 * 60;

  var banner = document.getElementById("idle-warning");
  var words = document.getElementById("idle-words");
  var stay = document.getElementById("stay");
  if (!banner || !window.IDLE_SECONDS) { return; }

  var left = window.IDLE_SECONDS;

  function tick() {
    left -= 30;
    if (left <= 0) {
      // The next request will be turned away by the app itself; saying so
      // here is kinder than letting somebody type into a page that is gone.
      words.textContent =
        "You have been signed out and your recordings and transcripts removed.";
      banner.hidden = false;
      return;
    }
    if (left <= WARN_AT) {
      var minutes = Math.ceil(left / 60);
      words.textContent =
        "You will be signed out in " + minutes +
        (minutes === 1 ? " minute" : " minutes") +
        " and your recordings and transcripts removed.";
      banner.hidden = false;
    }
    window.setTimeout(tick, 30000);
  }

  stay.addEventListener("click", function () {
    // Any request moves the clock; this one asks for the smallest page there
    // is and throws the answer away.
    fetch(window.location.pathname, { method: "GET", cache: "no-store" })
      .then(function () {
        left = window.IDLE_SECONDS;
        banner.hidden = true;
      });
  });

  window.setTimeout(tick, 30000);
})();

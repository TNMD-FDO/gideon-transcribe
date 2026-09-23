// A session that ends under an open page (Phase 8 chapter 7).
//
// Loaded before every other script on a signed-in page. It marks every
// request a page's script makes, so the app answers a script plainly when
// the session has ended (a small JSON body and the status 401) rather than
// with the sign-in page; and when that answer comes, once, it stops the
// page: every timer and poll is cleared, nothing is asked of the server
// again, the videos pause, the controls are greyed, and one line with one
// button says what happened and offers Sign in again, which returns the
// person to this page.

(function () {
  "use strict";

  var ended = false;
  var top = 0;

  var realFetch = window.fetch;
  var realTimeout = window.setTimeout;
  var realInterval = window.setInterval;

  function ours(input) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) { return true; }
    return url.indexOf(window.location.origin + "/") === 0;
  }

  window.fetch = function (input, init) {
    if (ended) { return Promise.reject(new Error("The session has ended.")); }
    init = init || {};
    if (ours(input)) {
      var headers = new Headers(init.headers || (input && input.headers) || undefined);
      headers.set("X-Requested-With", "transcribe");
      init.headers = headers;
    }
    return realFetch.call(window, input, init).then(function (answer) {
      if (answer.status !== 401 || ended) { return answer; }
      return answer.clone().json().then(function (body) {
        if (body && body.signed_in === false) { end(body); }
        return answer;
      }, function () { return answer; });
    });
  };

  // Timer ids count up; remembering the highest is enough to clear them all.
  window.setTimeout = function () {
    if (ended) { return 0; }
    var id = realTimeout.apply(window, arguments);
    if (id > top) { top = id; }
    return id;
  };
  window.setInterval = function () {
    if (ended) { return 0; }
    var id = realInterval.apply(window, arguments);
    if (id > top) { top = id; }
    return id;
  };

  function line(body) {
    var first = {
      idle: "Your session ended after a long wait.",
      elsewhere: "You signed in from another place, so this session ended.",
      ended: "An Admin ended your session.",
      blocked: "This account cannot sign in. Contact IT.",
      deactivated: "This account cannot sign in. Contact IT."
    }[body.why] || "Your session ended.";
    if (body.why === "blocked" || body.why === "deactivated") { return first; }
    return first + (body.kept
      ? " Your cases, clips and documents are kept."
      : " Your recordings and transcripts have been removed.");
  }

  function end(body) {
    if (ended) { return; }
    ended = true;
    for (var id = 1; id <= top; id += 1) { window.clearTimeout(id); window.clearInterval(id); }
    Array.prototype.forEach.call(document.querySelectorAll("video, audio"), function (one) {
      try { one.pause(); } catch (ignored) { /* a player that is not ready */ }
    });
    document.body.classList.add("session-ended");

    var banner = document.getElementById("idle-warning");
    var words = document.getElementById("idle-words");
    var stay = document.getElementById("stay");
    var again = document.getElementById("sign-in-again");
    if (words) { words.textContent = line(body); }
    if (stay) { stay.hidden = true; }
    if (again) {
      var canSignIn = body.why !== "blocked" && body.why !== "deactivated";
      again.hidden = !canSignIn;
      again.href = "/sign-in?next=" + encodeURIComponent(window.location.pathname + window.location.search);
    }
    if (banner) { banner.hidden = false; }
  }

  window.SESSION = {
    ended: function () { return ended; },
    end: end
  };
})();

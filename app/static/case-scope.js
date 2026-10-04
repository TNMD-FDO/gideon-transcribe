// The Scope (Phase 9 chapter 6): the recordings a question to Gideon is put
// to. The whole case until the page narrows: the case page's filter box and
// pills, a Search's hits, the Notes page's pills and filters each set it as
// the person narrows, and clear it when they clear. The drawer reads it for
// its head line and posts it with every question; the server keeps only the
// recordings in the case and names the rest as skipped. Nothing typed is
// ever in it: kinds and ids alone.

(function () {
  "use strict";

  var scope = { kind: "all", recordings: [] };

  function same(a, b) {
    if (a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i += 1) { if (a[i] !== b[i]) { return false; } }
    return true;
  }

  function tell() {
    try { document.dispatchEvent(new CustomEvent("case-scope", { detail: window.CaseScope.get() })); }
    catch (ignored) { /* an old browser: the drawer reads the scope when asked */ }
  }

  window.CaseScope = {
    // "filter", "search" or "notes", with the recordings' ids in page order.
    set: function (kind, ids) {
      var clean = [];
      (ids || []).forEach(function (one) { if (one && clean.indexOf(one) === -1) { clean.push(one); } });
      if (!clean.length) { this.clear(); return; }
      if (scope.kind === kind && same(scope.recordings, clean)) { return; }
      scope = { kind: kind, recordings: clean };
      tell();
    },
    clear: function () {
      if (scope.kind === "all") { return; }
      scope = { kind: "all", recordings: [] };
      tell();
    },
    get: function () { return { kind: scope.kind, recordings: scope.recordings.slice() }; },
    narrowed: function () { return scope.kind !== "all" && scope.recordings.length > 0; },
    // The head's words before a question: the narrowing, or the page's own
    // line for the whole case (the server's, by the hours and the summaries).
    words: function (wholeCase) {
      if (this.narrowed()) {
        return "Reads the " + scope.recordings.length + " recording" + (scope.recordings.length === 1 ? "" : "s") + " you have narrowed to";
      }
      return wholeCase || "This case";
    }
  };
})();

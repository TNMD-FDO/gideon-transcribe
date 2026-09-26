// Find in the guide (v1.89.0, from the walk): a box that lights every match
// in the guide's text and brings the first into view, on the guide's own page
// and in the pane beside a page. Plain text only: the marks are wrapped
// around text nodes and unwrapped again, so the guide's markup is untouched.

(function () {
  "use strict";

  function unmark(container) {
    Array.prototype.forEach.call(container.querySelectorAll("mark.found"), function (mark) {
      var parent = mark.parentNode;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    });
  }

  function markAll(container, wanted) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var tag = node.parentNode && node.parentNode.tagName;
        if (!tag || tag === "SCRIPT" || tag === "STYLE") { return NodeFilter.FILTER_REJECT; }
        return node.nodeValue.toLowerCase().indexOf(wanted) >= 0
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
    });
    var nodes = [];
    while (walker.nextNode()) { nodes.push(walker.currentNode); }
    var first = null;
    nodes.forEach(function (node) {
      var text = node.nodeValue;
      var low = text.toLowerCase();
      var at = 0;
      var piece = document.createDocumentFragment();
      var found;
      while ((found = low.indexOf(wanted, at)) >= 0) {
        piece.appendChild(document.createTextNode(text.slice(at, found)));
        var mark = document.createElement("mark");
        mark.className = "found";
        mark.textContent = text.slice(found, found + wanted.length);
        piece.appendChild(mark);
        if (!first) { first = mark; }
        at = found + wanted.length;
      }
      piece.appendChild(document.createTextNode(text.slice(at)));
      node.parentNode.replaceChild(piece, node);
    });
    return { count: nodes.length ? container.querySelectorAll("mark.found").length : 0, first: first };
  }

  function attach(input, container, count) {
    var pending = null;
    input.addEventListener("input", function () {
      if (pending) { window.clearTimeout(pending); }
      pending = window.setTimeout(function () {
        unmark(container);
        var wanted = input.value.trim().toLowerCase();
        if (count) { count.textContent = ""; }
        if (wanted.length < 2) { return; }
        var got = markAll(container, wanted);
        if (count) { count.textContent = got.count ? got.count + " found" : "nothing found"; }
        if (got.first && got.first.scrollIntoView) { got.first.scrollIntoView({ block: "center" }); }
      }, 150);
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { input.value = ""; unmark(container); if (count) { count.textContent = ""; } }
    });
  }

  window.GuideFind = { attach: attach, unmark: unmark };
})();

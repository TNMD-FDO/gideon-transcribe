// The guide's contents list marks the section being read, so that on a wide
// window, where the list is a rail beside the text, a reader always knows
// where they are. Without IntersectionObserver the list is simply a list.

(function () {
  "use strict";

  var contents = document.querySelector(".guide .contents");
  var body = document.querySelector(".guide-body");
  if (!contents || !body || !window.IntersectionObserver) { return; }

  var links = {};
  Array.prototype.forEach.call(contents.querySelectorAll("a[href^='#']"), function (link) {
    links[decodeURIComponent(link.getAttribute("href").slice(1))] = link;
  });
  var headings = Array.prototype.filter.call(
    body.querySelectorAll("h2[id], h3[id]"),
    function (heading) { return links[heading.id]; }
  );
  if (!headings.length) { return; }

  var current = null;
  function mark(id) {
    if (id === current) { return; }
    current = id;
    Object.keys(links).forEach(function (key) {
      links[key].classList.toggle("on", key === id);
    });
  }

  // The section being read is the last heading above the top third of the
  // window: the observer says which headings crossed, and this looks up.
  function settle() {
    var line = window.innerHeight / 3;
    var seen = null;
    for (var i = 0; i < headings.length; i += 1) {
      if (headings[i].getBoundingClientRect().top <= line) { seen = headings[i].id; }
    }
    mark(seen || headings[0].id);
  }
  var watcher = new IntersectionObserver(settle, { rootMargin: "0px 0px -66% 0px" });
  headings.forEach(function (heading) { watcher.observe(heading); });
  window.addEventListener("scroll", settle, { passive: true });
  settle();
})();

// The document page (Phase 8 chapter 4, part 1).
//
// The page pictures scroll down the middle; the words of the page in view
// sit beside them. A press on a paragraph's box on the picture lights its
// words, and a press on the words lights the box. A citation arriving as
// ?page=4&para=2 opens that page with the paragraph lit on both sides.
// Find lights every paragraph that carries the words, page by page.

(function () {
  "use strict";

  var root = document.getElementById("document");
  if (!root) { return; }
  var pictures = document.getElementById("doc-pictures");
  var words = document.getElementById("doc-words");
  var pageBox = document.getElementById("doc-page-box");
  var findBox = document.getElementById("doc-find");
  var pages = parseInt(root.dataset.pages, 10) || 0;
  var current = 0;

  function sheet(n) { return document.getElementById("sheet-" + n); }
  function text(n) { return document.getElementById("text-" + n); }

  function showWords(n) {
    if (n === current) { return; }
    current = n;
    Array.prototype.forEach.call(words.querySelectorAll(".doc-text"), function (one) {
      one.hidden = parseInt(one.dataset.number, 10) !== n;
    });
    if (pageBox && parseInt(pageBox.value, 10) !== n) { pageBox.value = n; }
  }

  function goTo(n, para) {
    n = Math.max(1, Math.min(pages, n || 1));
    var target = sheet(n);
    if (target) { target.scrollIntoView({ block: "start", behavior: "smooth" }); }
    showWords(n);
    if (para) { light(n, para); }
  }

  function light(n, para) {
    Array.prototype.forEach.call(root.querySelectorAll(".lit"), function (one) { one.classList.remove("lit"); });
    var box = root.querySelector(".doc-box[data-page='" + n + "'][data-n='" + para + "']");
    var line = root.querySelector(".doc-para[data-page='" + n + "'][data-n='" + para + "']");
    if (box) { box.classList.add("lit"); }
    if (line) { line.classList.add("lit"); line.scrollIntoView({ block: "center" }); }
  }

  // The page in view decides which words show.
  if ("IntersectionObserver" in window) {
    var seen = new IntersectionObserver(function (entries) {
      var best = null;
      entries.forEach(function (entry) {
        if (entry.isIntersecting && (!best || entry.intersectionRatio > best.intersectionRatio)) { best = entry; }
      });
      if (best) { showWords(parseInt(best.target.dataset.number, 10)); }
    }, { threshold: [0.25, 0.5, 0.75] });
    Array.prototype.forEach.call(pictures.querySelectorAll(".doc-sheet"), function (one) { seen.observe(one); });
  }

  pictures.addEventListener("click", function (event) {
    var box = event.target.closest(".doc-box");
    if (!box) { return; }
    showWords(parseInt(box.dataset.page, 10));
    light(parseInt(box.dataset.page, 10), parseInt(box.dataset.n, 10));
  });
  words.addEventListener("click", function (event) {
    var line = event.target.closest(".doc-para");
    if (!line) { return; }
    var n = parseInt(line.dataset.page, 10);
    var box = root.querySelector(".doc-box[data-page='" + n + "'][data-n='" + line.dataset.n + "']");
    Array.prototype.forEach.call(root.querySelectorAll(".lit"), function (one) { one.classList.remove("lit"); });
    line.classList.add("lit");
    if (box) { box.classList.add("lit"); box.scrollIntoView({ block: "center", behavior: "smooth" }); }
  });

  if (pageBox) {
    pageBox.addEventListener("change", function () { goTo(parseInt(pageBox.value, 10), 0); });
  }

  // Find within the document: every paragraph carrying all the words is
  // marked, and the first is brought into view.
  function find() {
    var asked = (findBox.value || "").trim().toLowerCase();
    var terms = asked.length >= 2 ? asked.split(/\s+/) : [];
    var first = null;
    Array.prototype.forEach.call(root.querySelectorAll(".doc-para"), function (line) {
      var hit = terms.length > 0 && terms.every(function (term) { return line.textContent.toLowerCase().indexOf(term) !== -1; });
      line.classList.toggle("hit", hit);
      var box = root.querySelector(".doc-box[data-page='" + line.dataset.page + "'][data-n='" + line.dataset.n + "']");
      if (box) { box.classList.toggle("hit", hit); }
      if (hit && !first) { first = line; }
    });
    if (first) { goTo(parseInt(first.dataset.page, 10), parseInt(first.dataset.n, 10)); }
  }
  if (findBox) {
    var timer = null;
    findBox.addEventListener("input", function () { window.clearTimeout(timer); timer = window.setTimeout(find, 250); });
    findBox.addEventListener("keydown", function (event) { if (event.key === "Escape") { findBox.value = ""; find(); } });
  }

  // Where the link asked to open.
  var open = parseInt(root.dataset.open, 10) || 1;
  var lit = parseInt(root.dataset.lit, 10) || 0;
  showWords(open);
  if (open > 1 || lit) { window.setTimeout(function () { goTo(open, lit); }, 50); }
  if (findBox && findBox.value) { find(); }
})();

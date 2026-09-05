// The guide beside the page. The "?" in the top bar opens the user guide (or
// the admin guide, from the Panel) in a pane on the right of the page, at the
// section about the page, and the page makes room for it rather than being
// covered. It stays open from page to page, each time at that page's section,
// until it is closed. On a window too narrow to give a pane room, the "?" is
// simply the Help link, and the stylesheet does not show it at all.

(function () {
  "use strict";

  var toggle = document.getElementById("help-beside");
  var pane = document.getElementById("help-pane");
  if (!toggle || !pane) { return; }

  var ROOM = window.matchMedia("(min-width: 1500px)");
  var body = pane.querySelector(".help-body");
  var asPage = pane.querySelector(".help-full");
  var loadedFrom = null;

  function guideAddress() {
    var href = toggle.getAttribute("href");
    var hash = href.indexOf("#");
    return hash >= 0 ? href.slice(0, hash) : href;
  }

  function sectionWanted() {
    var href = toggle.getAttribute("href");
    var hash = href.indexOf("#");
    return hash >= 0 ? decodeURIComponent(href.slice(hash + 1)) : "";
  }

  // The guide's headings keep their ids inside the pane, prefixed, so that a
  // page whose own elements share a name (the viewer has a #speakers) is not
  // confused with the guide, and the guide's own links still land inside it.
  function adopt(article) {
    Array.prototype.forEach.call(article.querySelectorAll("[id]"), function (one) {
      one.id = "help-" + one.id;
    });
    Array.prototype.forEach.call(article.querySelectorAll("a[href^='#']"), function (link) {
      link.setAttribute("href", "#help-" + link.getAttribute("href").slice(1));
      link.addEventListener("click", function (event) {
        event.preventDefault();
        jumpTo(link.getAttribute("href").slice(1));
      });
    });
  }

  function jumpTo(id) {
    var target = id ? body.querySelector("#" + window.CSS.escape(id)) : null;
    body.scrollTop = target ? Math.max(0, target.offsetTop - 8) : 0;
  }

  function jump() {
    var wanted = sectionWanted();
    jumpTo(wanted ? "help-" + wanted : "");
  }

  function remember(open) {
    try {
      if (open) { window.sessionStorage.setItem("help-beside", "1"); }
      else { window.sessionStorage.removeItem("help-beside"); }
    } catch (ignored) { /* then the pane lasts this page only */ }
  }

  function open() {
    pane.hidden = false;
    document.body.classList.add("help-open");
    toggle.classList.add("on");
    toggle.setAttribute("aria-expanded", "true");
    remember(true);
    var address = guideAddress();
    asPage.setAttribute("href", toggle.getAttribute("href"));
    if (loadedFrom === address) { jump(); return; }
    body.innerHTML = "<p class='muted small'>Loading the guide...</p>";
    fetch(address)
      .then(function (answer) { return answer.text(); })
      .then(function (html) {
        var page = new DOMParser().parseFromString(html, "text/html");
        var article = page.querySelector(".guide-body");
        if (!article) { throw new Error("no guide in the page"); }
        adopt(article);
        body.innerHTML = article.innerHTML;
        loadedFrom = address;
        jump();
      })
      .catch(function () {
        body.innerHTML =
          "<p class='muted'>The guide could not be loaded here. " +
          "<a href='" + address + "'>Open it as a page.</a></p>";
      });
  }

  function close() {
    pane.hidden = true;
    document.body.classList.remove("help-open");
    toggle.classList.remove("on");
    toggle.setAttribute("aria-expanded", "false");
    remember(false);
  }

  toggle.addEventListener("click", function (event) {
    if (!ROOM.matches) { return; }
    event.preventDefault();
    if (pane.hidden) { open(); } else { close(); }
  });
  pane.querySelector(".help-close").addEventListener("click", close);

  // Open from page to page until closed; a window narrowed below the room
  // for a pane closes it, and the "?" goes back to being a link.
  var wasOpen = null;
  try { wasOpen = window.sessionStorage.getItem("help-beside"); } catch (ignored) { /* closed then */ }
  if (wasOpen === "1" && ROOM.matches) { open(); }
  window.addEventListener("resize", function () {
    if (!ROOM.matches && !pane.hidden) { close(); }
  });
})();

// The people as cards (v1.151.0): the Case's Speakers tab and the Voices
// place. The filter chips show the cards of one kind (all, voice known, no
// voice yet, kept for the unit, something waiting, well taught, medium at
// best, forgotten) and nothing else moves: a card's actions sit in its own
// menu (a details element), and one menu closes when another opens.

(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    var chip = event.target.closest(".chips[data-filter-for] .chip[data-filter]");
    if (!chip) { return; }
    var chips = chip.closest(".chips");
    var grid = document.getElementById(chips.dataset.filterFor);
    if (!grid) { return; }
    var wanted = chip.dataset.filter;
    Array.prototype.forEach.call(chips.querySelectorAll(".chip"), function (one) { one.classList.toggle("on", one === chip); });
    Array.prototype.forEach.call(grid.querySelectorAll(".person-card"), function (card) {
      var kinds = (card.dataset.kinds || "").split(" ");
      card.hidden = wanted !== "all" && kinds.indexOf(wanted) === -1;
    });
  });

  // One menu open at a time, and Escape or a click elsewhere closes it.
  document.addEventListener("toggle", function (event) {
    var menu = event.target;
    if (!menu.matches || !menu.matches("details.menu") || !menu.open) { return; }
    Array.prototype.forEach.call(document.querySelectorAll("details.menu[open]"), function (other) {
      if (other !== menu) { other.open = false; }
    });
  }, true);
  document.addEventListener("click", function (event) {
    if (event.target.closest("details.menu")) { return; }
    Array.prototype.forEach.call(document.querySelectorAll("details.menu[open]"), function (menu) { menu.open = false; });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") { return; }
    Array.prototype.forEach.call(document.querySelectorAll("details.menu[open]"), function (menu) { menu.open = false; });
  });
})();

// The Usage page's one button (Phase 13 chapter 3): the figures as plain
// words on the clipboard, for the Admin to paste where they choose. Nothing
// is sent anywhere; where the browser gives no clipboard, the words are
// opened on the page to be selected by hand.
(function () {
  "use strict";
  var button = document.getElementById("usage-copy");
  if (!button) { return; }
  var said = document.getElementById("usage-copied");
  var plain = document.querySelector(".usage-plain");
  function open() {
    if (plain) { plain.open = true; }
    if (said) { said.textContent = "Select the words below to copy them"; }
  }
  button.addEventListener("click", function () {
    var words = button.dataset.words || "";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(words).then(function () {
        if (said) { said.textContent = "Copied"; }
      }, open);
    } else { open(); }
  });
}());

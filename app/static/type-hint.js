// The no-type line (v1.147.1): on a recording in a case with no type, while
// the voice listens on some types, the recording page and the Speakers page
// carry one quiet line saying so, with the type picker in it. The pick saves
// at once through the case page's own endpoint (the description is sent
// along, since that endpoint saves both), and the line then says what to
// do next: check the speakers again, and whether the voice listens on the
// type chosen.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function toast(words, options) {
    if (window.UI && window.UI.toast) { window.UI.toast(words, options); }
  }

  document.addEventListener("change", function (event) {
    var select = event.target.closest(".type-hint select");
    if (!select) { return; }
    var box = select.closest(".type-hint");
    var typed = select.value;
    if (!typed) { return; }
    select.disabled = true;
    fetch("/recording/" + box.dataset.recording + "/case-details", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken"), "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ recording_type: typed, description: box.dataset.description || "" })
    }).then(function (answer) { return answer.json(); }).then(function (said) {
      if (!said.ok) {
        select.disabled = false;
        toast((said && said.why) || "That could not be saved.", { problem: true, icon: "warning" });
        return;
      }
      var listed = (box.dataset.listed || "").split("|").filter(Boolean);
      var listens = listed.some(function (one) { return one.toLowerCase() === typed.toLowerCase(); });
      box.innerHTML = "<span>Type set to <b>" + escape(typed) + "</b>. " +
        (listens
          ? "The voice listens on this type: press Check the speakers again to hear the voices."
          : "The voice does not listen on this type, so the check reads the words alone.") +
        "</span>";
      toast("Saved.", { icon: "ok" });
    }).catch(function () {
      select.disabled = false;
      toast("That could not be saved.", { problem: true, icon: "warning" });
    });
  });
})();

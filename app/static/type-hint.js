// The no-type line (v1.147.1): on a recording in a case with no type, while
// the voice listens on some types, the recording page and the Speakers page
// carry one quiet line saying so, with the type picker in it. The pick saves
// at once through the case page's own endpoint (the description is sent
// along, since that endpoint saves both), and the line then says what to
// do next: check the speakers again, and whether the voice listens on the
// type chosen. Since v1.149.0 the line may carry one button that sets the
// jail-call type in a press, when the Call system's announcements were heard
// on the recording; it saves the same way.

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

  function save(box, typed, controls) {
    controls.forEach(function (one) { one.disabled = true; });
    fetch("/recording/" + box.dataset.recording + "/case-details", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken"), "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ recording_type: typed, description: box.dataset.description || "" })
    }).then(function (answer) { return answer.json(); }).then(function (said) {
      if (!said.ok) {
        controls.forEach(function (one) { one.disabled = false; });
        toast((said && said.why) || "That could not be saved.", { problem: true, icon: "warning" });
        return;
      }
      var listed = (box.dataset.listed || "").split("|").filter(Boolean);
      var listens = listed.some(function (one) { return one.toLowerCase() === typed.toLowerCase(); });
      box.innerHTML = "<span>Type set to <b>" + escape(typed) + "</b>. " +
        (said.call_system ? said.call_system + (said.call_system === 1 ? " line went" : " lines went") + " to the Call system. " : "") +
        (listens
          ? "The voice listens on this type: press Check the speakers again to hear the voices."
          : "The voice does not listen on this type, so the check reads the words alone.") +
        "</span>";
      toast("Saved.", { icon: "ok" });
    }).catch(function () {
      controls.forEach(function (one) { one.disabled = false; });
      toast("That could not be saved.", { problem: true, icon: "warning" });
    });
  }

  function controlsOf(box) {
    return Array.prototype.slice.call(box.querySelectorAll("select, button"));
  }

  document.addEventListener("change", function (event) {
    var select = event.target.closest(".type-hint select");
    if (!select) { return; }
    var typed = select.value;
    if (!typed) { return; }
    var box = select.closest(".type-hint");
    save(box, typed, controlsOf(box));
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".type-hint button[data-type]");
    if (!button) { return; }
    var box = button.closest(".type-hint");
    save(box, button.dataset.type, controlsOf(box));
  });
})();

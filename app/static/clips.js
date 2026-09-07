// The clips page: retry a failed render, bring stale captions up to date, and
// delete a clip. Everything else on the page is a link.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    });
  }

  document.addEventListener("click", function (event) {
    var again = event.target.closest(".rerender");
    if (again) {
      again.disabled = true;
      post("/clip/" + again.dataset.clip + "/rerender")
        .then(function () { window.location.reload(); });
      return;
    }

    var gone = event.target.closest(".delete-clip");
    if (gone) {
      UI.confirm({
        title: "Delete " + gone.dataset.title + "?",
        body: "The file goes with it. Anything not downloaded cannot be got back.",
        ok: "Delete clip",
        danger: true
      }).then(function (yes) {
        if (!yes) { return; }
        post("/clip/" + gone.dataset.clip + "/delete")
          .then(function () { window.location.reload(); });
      });
    }
  });
})();

// The filter by place on the My clips page: the rows of other places are
// hidden, heading rows and details with them, and the chooser is told.
(function () {
  "use strict";

  var filter = document.getElementById("clip-filter");
  var table = document.getElementById("recordings");
  if (!filter || !table) { return; }

  filter.addEventListener("change", function () {
    var wanted = filter.value;
    Array.prototype.forEach.call(table.querySelectorAll("tr.pick"), function (row) {
      row.hidden = !!wanted && row.dataset.of !== wanted;
    });
    Array.prototype.forEach.call(table.querySelectorAll("tr.group"), function (row) {
      row.hidden = !!wanted && row.dataset.group !== wanted;
    });
    table.dispatchEvent(new Event("rows-changed"));
  });
})();

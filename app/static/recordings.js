// Delete on a recording: one control that removes the recording and
// everything about it, behind a confirmation that says so.

(function () {
  "use strict";

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".delete");
    if (!button) { return; }

    var also = button.dataset.clips && button.dataset.clips !== "0"
      ? " and its " + button.dataset.clips + " clip" +
        (button.dataset.clips === "1" ? "" : "s")
      : "";
    UI.confirm({
      title: "Delete " + button.dataset.title + also + "?",
      body: [
        "This removes the recording, its transcript, and everything else about it.",
        "It cannot be undone. Export anything you want to keep first."
      ],
      ok: "Delete recording",
      cancel: "Keep it",
      danger: true
    }).then(function (yes) {
      if (!yes) { return; }
      fetch("/recording/" + button.dataset.recording + "/delete", {
        method: "POST",
        headers: { "X-CSRFToken": cookie("csrftoken") }
      }).then(function (answer) {
        if (answer.ok) { window.location.reload(); }
      });
    });
  });
})();

// The table and the details: one recording is chosen at a time, and its
// details block sits in the pane beside the table on a wide window, or opens
// under its row on a narrow one. The block is the same element either way;
// it is moved, not copied, so the buttons in it keep working through the
// listeners on the document.
(function () {
  "use strict";

  var table = document.getElementById("recordings");
  // Without a pane the details open under the row on every width, which is
  // the case page's shape: its pane is about the case, not the row.
  var pane = document.getElementById("detail-pane");
  if (!table) { return; }

  var WIDE = window.matchMedia("(min-width: 1280px)");
  var none = document.getElementById("detail-none");
  function onTheBench() { return WIDE.matches && pane !== null; }
  var rows = Array.prototype.slice.call(table.querySelectorAll("tr.pick"));
  var chosenRow = null;

  function detailOf(row) {
    return document.getElementById("detail-" + row.dataset.recording);
  }

  function place() {
    rows.forEach(function (row) {
      var holder = row.nextElementSibling;
      var detail = detailOf(row);
      var isChosen = row === chosenRow;
      if (onTheBench() && isChosen) {
        pane.appendChild(detail);
        holder.hidden = true;
      } else {
        var cell = holder.querySelector("td");
        if (detail.parentNode !== cell) { cell.appendChild(detail); }
        holder.hidden = !isChosen || onTheBench() || row.hidden;
      }
      row.classList.toggle("on", isChosen);
    });
    if (none) { none.hidden = chosenRow !== null; }
  }

  function choose(row) {
    chosenRow = row;
    place();
  }

  rows.forEach(function (row) {
    row.addEventListener("click", function (event) {
      // A click on Open is Open, not a choice.
      if (event.target.closest("a, button")) { return; }
      choose(row === chosenRow && !onTheBench() ? null : row);
    });
  });

  table.addEventListener("keydown", function (event) {
    var row = event.target.closest("tr.pick");
    if (!row) { return; }
    // Along the rows a filter has left showing.
    var shown = rows.filter(function (one) { return !one.hidden; });
    var at = shown.indexOf(row);
    if (event.key === "ArrowDown" && at < shown.length - 1) {
      event.preventDefault();
      shown[at + 1].focus();
      choose(shown[at + 1]);
    } else if (event.key === "ArrowUp" && at > 0) {
      event.preventDefault();
      shown[at - 1].focus();
      choose(shown[at - 1]);
    } else if (event.key === "Enter" && row.dataset.open) {
      window.location = row.dataset.open;
    } else if (event.key === " ") {
      event.preventDefault();
      choose(row);
    }
  });

  // A wide window always shows a recording's details, the first one until
  // another is chosen; a narrow one shows none until a row is clicked.
  function settle() {
    var shown = rows.filter(function (one) { return !one.hidden; });
    if (chosenRow && chosenRow.hidden) { chosenRow = null; }
    if (onTheBench() && chosenRow === null && shown.length) { chosenRow = shown[0]; }
    place();
  }
  // A filter on the page hides rows and then asks for this.
  table.addEventListener("rows-changed", settle);
  settle();
  if (WIDE.addEventListener) { WIDE.addEventListener("change", settle); }
  // A plain resize as well: not every browser fires the change above.
  window.addEventListener("resize", settle);
})();

// Rename a recording from its row: the new title is what every page and
// export shows; the file keeps its own name.
(function () {
  "use strict";
  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".rename-recording");
    if (!button || !window.UI) { return; }
    UI.prompt({ title: "Rename this recording", body: "The new title is what every page and export shows.", value: button.dataset.title, ok: "Rename" })
      .then(function (now) {
        if (!now || now.trim() === button.dataset.title) { return; }
        return fetch("/recording/" + button.dataset.recording + "/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
          body: JSON.stringify({ title: now.trim() })
        }).then(function (answer) { if (answer.ok) { window.location.reload(); } });
      });
  });
})();

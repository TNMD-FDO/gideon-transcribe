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
    if (!window.confirm(
      "Delete " + button.dataset.title + also + "? This removes the recording, " +
      "its transcript, and everything else about it. It cannot be undone, and " +
      "anything you want to keep has to be exported first."
    )) { return; }

    fetch("/recording/" + button.dataset.recording + "/delete", {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function (answer) {
      if (answer.ok) { window.location.reload(); }
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
  var pane = document.getElementById("detail-pane");
  if (!table || !pane) { return; }

  var WIDE = window.matchMedia("(min-width: 1280px)");
  var none = document.getElementById("detail-none");
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
      if (WIDE.matches && isChosen) {
        pane.appendChild(detail);
        holder.hidden = true;
      } else {
        var cell = holder.querySelector("td");
        if (detail.parentNode !== cell) { cell.appendChild(detail); }
        holder.hidden = !isChosen || WIDE.matches;
      }
      row.classList.toggle("on", isChosen);
    });
    none.hidden = chosenRow !== null;
  }

  function choose(row) {
    chosenRow = row;
    place();
  }

  rows.forEach(function (row) {
    row.addEventListener("click", function (event) {
      // A click on Open is Open, not a choice.
      if (event.target.closest("a, button")) { return; }
      choose(row === chosenRow && !WIDE.matches ? null : row);
    });
  });

  table.addEventListener("keydown", function (event) {
    var row = event.target.closest("tr.pick");
    if (!row) { return; }
    var at = rows.indexOf(row);
    if (event.key === "ArrowDown" && at < rows.length - 1) {
      event.preventDefault();
      rows[at + 1].focus();
      choose(rows[at + 1]);
    } else if (event.key === "ArrowUp" && at > 0) {
      event.preventDefault();
      rows[at - 1].focus();
      choose(rows[at - 1]);
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
    if (WIDE.matches && chosenRow === null && rows.length) { chosenRow = rows[0]; }
    place();
  }
  settle();
  if (WIDE.addEventListener) { WIDE.addEventListener("change", settle); }
  // A plain resize as well: not every browser fires the change above.
  window.addEventListener("resize", settle);
})();

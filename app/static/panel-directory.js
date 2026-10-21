// The two directory buttons, on the status page and on the sign-in settings
// page. Both are actions: they run at once and are not part of the tray.

(function () {
  "use strict";

  var test = document.getElementById("test-directory");
  var check = document.getElementById("check-directory");
  var said = document.getElementById("directory-said");
  if (!test || !said) { return; }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function escape(text) {
    return String(text === undefined || text === null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function (answer) { return answer.json(); });
  }

  // The unit's voice book (v1.146.0): the accounts per unit as the Units
  // lines place them, and the ones in no listed unit with their folder
  // chains, so the lines can be tried before anyone signs in.
  function units(placed) {
    if (!placed || !placed.listed) { return ""; }
    var counts = Object.keys(placed.counts).map(function (unit) {
      return escape(unit) + " " + placed.counts[unit];
    });
    var html = "<p class='small'>Units: " + (counts.length ? counts.join(" \u00b7 ") : "none listed") +
      " \u00b7 in no listed unit " + placed.none.length + (placed.pinned ? " \u00b7 set by hand " + placed.pinned : "") + "</p>";
    if (placed.none.length) {
      html += "<table class='small'><thead><tr><th>In no listed unit</th><th>Folder chain</th></tr></thead><tbody>" +
        placed.none.map(function (one) {
          return "<tr><td>" + escape(one.username) + "</td><td><code>" + escape(one.folder || "(no folder read yet: signs in next)") + "</code></td></tr>";
        }).join("") + "</tbody></table>";
    }
    return html;
  }

  test.addEventListener("click", function () {
    test.disabled = true;
    said.innerHTML = "<p class='quiet'>Asking the directory...</p>";
    post("/panel/directory/test")
      .then(function (result) {
        said.innerHTML = "<dl class='kv' style='margin-top:8px'>" +
          result.checks.map(function (one) {
            var mark = one.ok
              ? (one.warning
                ? "<span class='pill warn'>note</span>"
                : "<span class='pill ok'>pass</span>")
              : "<span class='pill danger'>fail</span>";
            return "<dt>" + mark + "</dt><dd>" + escape(one.name) +
              ": <span class='muted small'>" + escape(one.says) + "</span></dd>";
          }).join("") + "</dl>";
      })
      .catch(function () {
        said.innerHTML = "<p class='notice danger'>The test could not be run.</p>";
      })
      .then(function () { test.disabled = false; });
  });

  if (check) {
    check.addEventListener("click", function () {
      check.disabled = true;
      said.innerHTML = "<p class='quiet'>Checking every account...</p>";
      post("/panel/directory/check")
        .then(function (result) {
          if (!result.ran) {
            said.innerHTML = "<p class='notice warn'>The check refused and " +
              "changed nothing: " + escape(result.why) + "</p>";
            return;
          }
          said.innerHTML = "<p>" + result.signin_group_members +
            " in the sign-in group, " + result.admin_group_members +
            " in the admin group, " + result.changes.length + " change(s).</p>" +
            (result.changes.length
              ? "<ul class='small'>" + result.changes.map(function (one) {
                  return "<li>" + escape(one) + "</li>";
                }).join("") + "</ul>"
              : "") + units(result.units);
        })
        .catch(function () {
          said.innerHTML = "<p class='notice danger'>The check could not be run.</p>";
        })
        .then(function () { check.disabled = false; });
    });
  }
})();

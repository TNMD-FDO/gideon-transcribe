// The two directory buttons, on the status page and on the sign-in settings
// page. Both are actions: they run at once and are not part of the tray.

(function () {
  "use strict";

  var test = document.getElementById("test-directory");
  var check = document.getElementById("check-directory");
  var said = document.getElementById("directory-said");
  if (!test || !said) { return; }

  function cookie(name) {
    var found = document.cookie.match("(^|;)\s*" + name + "\s*=\s*([^;]+)");
    return found ? found.pop() : "";
  }

  function escape(text) {
    var holder = document.createElement("span");
    holder.textContent = text === null || text === undefined ? "" : text;
    return holder.innerHTML;
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function (answer) { return answer.json(); });
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
              : "");
        })
        .catch(function () {
          said.innerHTML = "<p class='notice danger'>The check could not be run.</p>";
        })
        .then(function () { check.disabled = false; });
    });
  }
})();

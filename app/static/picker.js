// The speaker picker (v1.142.0, the voice plan's section 13): one control
// wherever the app asks whose a line or a voice is, never a typed answer
// unless the person is new. Three groups in the same order everywhere: the
// speakers on this call with a play for their sample, the Case's People not
// yet on it with where their voice can be heard, and Someone new. Number
// keys, arrows and Enter work; Esc closes. The picker only chooses: a wrong
// sample is corrected on the Speakers page's card, and away from that page
// the picker says "Manage speakers" for the rest.
//
//   Picker.open({
//     recording: id, anchor: element (the sheet is placed after it),
//     question: "Whose line is this?", quote: "...", current: "Speaker 2",
//     exclude: ["Call system"], newSpeaker: true (offer "A new speaker on this call"),
//     play: function (start, end) {...}  (the host page's player),
//     manageUrl: "/recording/<id>/speakers" or "",
//     onPick: function (name, role) { return Promise }  (name "" means a new speaker)
//   })
(function () {
  function escape(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var opened = null;   // { box, options, data, items, lit, cycle }
  var cache = {};      // recording id -> { at, data }

  function fetchOffer(recording) {
    var kept = cache[recording];
    if (kept && Date.now() - kept.at < 15000) { return Promise.resolve(kept.data); }
    return fetch("/recording/" + recording + "/picker", { credentials: "same-origin" })
      .then(function (answer) { return answer.json(); })
      .then(function (data) { cache[recording] = { at: Date.now(), data: data }; return data; });
  }

  function forget(recording) { delete cache[recording]; }

  function close() {
    if (!opened) { return; }
    document.removeEventListener("keydown", onKey, true);
    document.removeEventListener("click", onOutside, true);
    if (opened.box.parentNode) { opened.box.parentNode.removeChild(opened.box); }
    var anchor = opened.options.anchor || null;
    opened = null;
    // The page may move again, and returns to the line in hand (v1.142.1).
    document.dispatchEvent(new CustomEvent("picker-close", { detail: { anchor: anchor } }));
  }

  function onOutside(event) {
    if (opened && !opened.box.contains(event.target)) { close(); }
  }

  function items() { return opened ? Array.prototype.slice.call(opened.box.querySelectorAll(".opt[data-name], .opt[data-new]")) : []; }

  function light(index) {
    var all = items();
    if (!all.length) { return; }
    opened.lit = Math.max(0, Math.min(all.length - 1, index));
    all.forEach(function (one, n) { one.classList.toggle("focus", n === opened.lit); });
    all[opened.lit].scrollIntoView({ block: "nearest" });
  }

  function onKey(event) {
    if (!opened) { return; }
    var box = opened.box;
    var typing = box.querySelector(".newbox input");
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (typing && document.activeElement === typing) {
      if (event.key === "Enter") { event.preventDefault(); box.querySelector(".new-go").click(); }
      return;
    }
    if (/^[1-9]$/.test(event.key)) {
      var byKey = box.querySelector(".opt[data-key='" + event.key + "']");
      if (byKey) { event.preventDefault(); event.stopPropagation(); choose(byKey); }
      return;
    }
    if (event.key === "ArrowDown") { event.preventDefault(); light(opened.lit + 1); return; }
    if (event.key === "ArrowUp") { event.preventDefault(); light(opened.lit - 1); return; }
    if (event.key === "Enter") {
      event.preventDefault();
      var lit = items()[opened.lit];
      if (lit) { choose(lit); }
    }
  }

  function choose(opt) {
    if (!opened || opt.classList.contains("now")) { return; }
    if (opt.dataset.new === "box") { openNewBox(); return; }
    var options = opened.options;
    var name = opt.dataset.new === "speaker" ? "" : opt.dataset.name;
    var done = options.onPick(name, "");
    close();
    forget(options.recording);
    return done;
  }

  function openNewBox() {
    var box = opened.box;
    var add = box.querySelector(".add");
    if (!add) { return; }
    var roles = (opened.data.roles || []);
    add.outerHTML = "<div class='newbox'>" +
      "<input type='text' maxlength='60' placeholder='Their name' aria-label='Name'>" +
      (opened.data.in_case && roles.length ? "<select aria-label='Role'><option value=''>no role</option>" + roles.map(function (r) { return "<option>" + escape(r) + "</option>"; }).join("") + "</select>" : "") +
      "<button type='button' class='primary small new-go'>Add and give this line</button>" +
      "<span class='small muted hint'>" + (opened.data.in_case ? "Makes the person in the case and a speaker on this call. A name already in the case joins that person." : "A new speaker on this recording.") + "</span>" +
      "</div>";
    var input = box.querySelector(".newbox input");
    input.focus();
    box.querySelector(".new-go").addEventListener("click", function () {
      var name = (input.value || "").trim();
      if (!name) { input.focus(); return; }
      var select = box.querySelector(".newbox select");
      var role = select ? select.value : "";
      var options = opened.options;
      var done = options.onPick(name, role);
      close();
      forget(options.recording);
      return done;
    });
  }

  function playFor(opt, data) {
    // The three samples, one at a time (1/3, 2/3, 3/3), from the host's player.
    var name = opt.dataset.name;
    var card = (data.on_call || []).filter(function (one) { return one.name === name; })[0];
    if (!card || !card.samples || !card.samples.length || !opened.options.play) { return; }
    var n = (opened.cycle[name] || 0) % card.samples.length;
    var sample = card.samples[n];
    opened.options.play(sample.start, sample.end);
    opened.cycle[name] = n + 1;
    var count = opt.querySelector(".n");
    if (count) { count.textContent = ((n + 1) % card.samples.length + 1) + "/" + card.samples.length; }
  }

  function previewFor(opt, data, from) {
    var person = (data.people || []).filter(function (one) { return one.name === opt.dataset.name; })[0];
    if (!person || !person.sample) { return; }
    if (window.Preview && window.Preview.open) {
      window.Preview.open({ recording: person.sample.recording, seconds: person.sample.start, from: from });
    } else if (window.UI && window.UI.toast) {
      window.UI.toast("Their voice is in " + person.sample.title + "; open that recording to hear it.", { icon: "info" });
    }
  }

  function row(entry, key, extra) {
    var pills = (entry.role ? " <span class='pill role'>" + escape(entry.role) + "</span>" : "") +
      (entry.system ? " <span class='pill'>not a person</span>" : "") +
      (extra || "");
    return "<div class='opt" + (entry.now ? " now" : "") + "' data-name='" + escape(entry.name) + "'" + (key ? " data-key='" + key + "'" : "") + ">" +
      "<kbd>" + (key || "") + "</kbd>" +
      "<span class='dot' style='--speaker: " + escape(entry.colour || "") + "'></span>" +
      "<span class='nm' style='--speaker: " + escape(entry.colour || "") + "'>" + escape(entry.name) + pills + "</span>" +
      "<span class='facts'>" + escape(entry.facts || "") + "</span>" +
      "<span class='hear'>" + (entry.hear || "") + "</span></div>";
  }

  function build(options, data) {
    var box = document.createElement("div");
    box.className = "picker" + (options.compact ? " compact" : "");
    box.setAttribute("role", "dialog");
    var exclude = (options.exclude || []);
    var key = 0;
    var parts = [];
    parts.push("<div class='q'><b>" + escape(options.question || "Whose line is this?") + "</b>" +
      (options.quote ? " <span class='small muted quote'>" + escape(options.quote) + "</span>" : "") +
      "<button type='button' class='ghost tiny x' title='Close (Esc)'>Esc</button></div>");
    var onCall = (data.on_call || []).map(function (one) {
      var now = one.name === options.current;
      var hear = one.samples && one.samples.length && !one.system ? "<button type='button' class='hear-one' title='Play a sample of this voice; press again for the next'>" + (window.UI && window.UI.icon ? window.UI.icon("play") : "play") + "<span class='n'>1/" + one.samples.length + "</span></button>" : "";
      key += 1;
      return row({ name: one.name, colour: one.colour, role: one.role, system: one.system, now: now || exclude.indexOf(one.name) >= 0 || one.system, facts: one.lines + (one.lines === 1 ? " line" : " lines") + (now ? "" : ""), hear: hear }, one.system ? "" : String(key), now ? " <span class='pill'>has it now</span>" : "");
    });
    parts.push("<div class='grp'><div class='gh'>On this call</div>" + (onCall.join("") || "<div class='small muted'>No other speaker on this call yet.</div>") + "</div>");
    if (data.in_case) {
      var people = (data.people || []).map(function (one) {
        key += 1;
        var facts = (one.recordings ? "in " + one.recordings + (one.recordings === 1 ? " recording" : " recordings") : "not heard yet") + (one.also_called && one.also_called.length ? " · also called " + one.also_called.join(", ") : "");
        var hear = one.sample ? "<button type='button' class='hear-else' title='Hear this person in another recording of the case'>" + (window.UI && window.UI.icon ? window.UI.icon("play") : "play") + " Preview</button>" : "";
        return row({ name: one.name, colour: "", role: one.role, facts: facts, hear: hear }, key <= 9 ? String(key) : "");
      });
      parts.push("<div class='grp'><div class='gh'>In this case, not yet on this call</div>" + (people.join("") || "<div class='small muted'>Everyone in the case is on this call already.</div>") + "</div>");
    }
    if (options.newSpeaker) {
      parts.push("<div class='grp'><div class='gh'>Or</div><div class='opt' data-new='speaker'><kbd></kbd><span class='dot'></span><span class='nm'>A new speaker on this call</span><span class='facts'>the next free label, to be named later</span><span class='hear'></span></div></div>");
    }
    parts.push("<div class='opt add' data-new='box'><span class='plus'>+</span><span class='nm'>Someone new</span><span class='facts'>" + (data.in_case ? "a person not yet in the case" : "a speaker not on this recording") + "</span></div>");
    if (options.manageUrl) {
      parts.push("<div class='manage small muted'>Doesn't sound right? <a href='" + escape(options.manageUrl) + "'>Manage speakers</a> is where a sample can be corrected.</div>");
    }
    box.innerHTML = parts.join("");
    opened = { box: box, options: options, data: data, lit: 0, cycle: {} };
    var anchor = options.anchor;
    if (anchor && anchor.parentNode) { anchor.parentNode.insertBefore(box, anchor.nextSibling); }
    else { document.body.appendChild(box); box.classList.add("floating"); }
    // The first pickable row is lit; for a Split, "a new speaker" is, so one
    // Enter does what Split did before the picker.
    var all = items();
    var first = all.findIndex(function (one) { return one.dataset.new === "speaker"; });
    if (first < 0) { first = all.findIndex(function (one) { return !one.classList.contains("now"); }); }
    light(first < 0 ? 0 : first);
    box.addEventListener("click", function (event) {
      var hearOne = event.target.closest(".hear-one");
      var hearElse = event.target.closest(".hear-else");
      var opt = event.target.closest(".opt");
      if (event.target.closest(".x")) { close(); return; }
      if (event.target.closest(".newbox")) { return; }
      if (hearOne && opt) { playFor(opt, data); return; }
      if (hearElse && opt) { previewFor(opt, data, hearElse); return; }
      if (opt) { choose(opt); }
    });
    document.addEventListener("keydown", onKey, true);
    window.setTimeout(function () { document.addEventListener("click", onOutside, true); }, 0);
    // The page holds still while the picker is open (v1.142.1): following
    // would scroll to a sample as it plays and take the row with it.
    document.dispatchEvent(new CustomEvent("picker-open", { detail: { anchor: anchor || null } }));
    box.scrollIntoView({ block: "nearest" });
  }

  function open(options) {
    close();
    return fetchOffer(options.recording).then(function (data) {
      if (data.error) { if (window.UI && window.UI.toast) { window.UI.toast(data.error, { problem: true, icon: "warning" }); } return; }
      build(options, data);
    });
  }

  window.Picker = { open: open, close: close, forget: forget, isOpen: function () { return !!opened; } };
})();

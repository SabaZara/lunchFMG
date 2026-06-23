/* Admin: card management. Works with card_id only.
 *
 * Name/department are intentionally hidden. To re-enable later, flip
 * SHOW_NAMES to true — the table head, rows, and edit form all key off it,
 * so no rewrite is needed. */
(function () {
  "use strict";

  // ---- single flag to re-enable name/department columns later ------------ //
  var SHOW_NAMES = false;

  var els = {
    userLabel: document.getElementById("userLabel"),
    logoutBtn: document.getElementById("logoutBtn"),
    globalMsg: document.getElementById("globalMsg"),
    newCard: document.getElementById("newCard"),
    addBtn: document.getElementById("addBtn"),
    captureBtn: document.getElementById("captureBtn"),
    captureHint: document.getElementById("captureHint"),
    addMsg: document.getElementById("addMsg"),
    importFile: document.getElementById("importFile"),
    importBtn: document.getElementById("importBtn"),
    importMsg: document.getElementById("importMsg"),
    search: document.getElementById("search"),
    searchBtn: document.getElementById("searchBtn"),
    countLabel: document.getElementById("countLabel"),
    tableHead: document.getElementById("tableHead"),
    tableBody: document.getElementById("tableBody"),
  };

  function notice(container, text, kind) {
    container.innerHTML = text ? '<div class="notice ' + kind + '">' + text + "</div>" : "";
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function api(method, url, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (r) {
      if (r.status === 401) { window.location.href = "/login"; throw new Error("auth"); }
      if (r.status === 204) return { ok: true, status: 204, j: null };
      return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
    });
  }

  // ----------------------------- table ----------------------------------- //
  function renderHead() {
    var cols = ["ბარათის ID"];
    if (SHOW_NAMES) { cols.push("სახელი"); cols.push("დეპარტამენტი"); }
    cols.push("სტატუსი", "დღეს ჭამა", "მოქმედებები");
    var ths = cols.map(function (c, i) {
      return '<th class="' + (i === 0 ? "ltr" : "") + '">' + c + "</th>";
    });
    els.tableHead.innerHTML = "<tr>" + ths.join("") + "</tr>";
  }

  function rowHtml(p) {
    var cells = ['<td class="ltr">' + esc(p.card_id) + "</td>"];
    if (SHOW_NAMES) {
      cells.push("<td>" + esc(p.full_name) + "</td>");
      cells.push("<td>" + esc(p.department || "") + "</td>");
    }
    cells.push(
      "<td>" + (p.active
        ? '<span class="badge ok">აქტიური</span>'
        : '<span class="badge off">გათიშული</span>') + "</td>"
    );
    cells.push(
      "<td>" + (p.ate_today
        ? '<span class="badge ok">დიახ</span>'
        : '<span class="badge off">არა</span>') + "</td>"
    );
    cells.push(
      '<td>' +
        '<button class="small ghost" data-act="toggle" data-id="' + p.id + '">' +
          (p.active ? "გათიშვა" : "ჩართვა") + "</button> " +
        '<button class="small ghost" data-act="edit" data-id="' + p.id + '" data-card="' + esc(p.card_id) + '">რედაქტ.</button> ' +
        '<button class="small danger" data-act="delete" data-id="' + p.id + '" data-card="' + esc(p.card_id) + '">წაშლა</button>' +
      "</td>"
    );
    return "<tr>" + cells.join("") + "</tr>";
  }

  function load() {
    var q = els.search.value.trim();
    var url = "/api/people" + (q ? "?q=" + encodeURIComponent(q) : "");
    api("GET", url).then(function (res) {
      var people = res.j || [];
      els.countLabel.textContent = "სულ: " + people.length;
      els.tableBody.innerHTML = people.map(rowHtml).join("") ||
        '<tr><td colspan="9" style="text-align:center;color:var(--muted)">ბარათები ვერ მოიძებნა</td></tr>';
    });
  }

  // --------------------------- row actions -------------------------------- //
  els.tableBody.addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    var act = btn.dataset.act;
    var id = btn.dataset.id;
    var card = btn.dataset.card;

    if (act === "toggle") {
      // Flip active by reading the current label.
      var enabling = btn.textContent.indexOf("ჩართვა") >= 0;
      api("PUT", "/api/people/" + id, { active: enabling }).then(function (res) {
        if (!res.ok) notice(els.globalMsg, (res.j && res.j.detail) || "შეცდომა", "bad");
        else notice(els.globalMsg, "", "");
        load();
      });
    } else if (act === "delete") {
      if (!confirm('წავშალოთ ბარათი "' + card + '"? ისტორიაც წაიშლება.')) return;
      api("DELETE", "/api/people/" + id).then(function () { load(); });
    } else if (act === "edit") {
      var nv = prompt("ბარათის ახალი ID:", card);
      if (nv === null) return;
      nv = nv.trim();
      if (!nv) return;
      api("PUT", "/api/people/" + id, { card_id: nv }).then(function (res) {
        if (!res.ok) notice(els.globalMsg, (res.j && res.j.detail) || "შეცდომა", "bad");
        else notice(els.globalMsg, "ბარათი განახლდა.", "ok");
        load();
      });
    }
  });

  // ------------------------------ add ------------------------------------- //
  function addCard() {
    var card = els.newCard.value.trim();
    if (!card) return;
    api("POST", "/api/people", { card_id: card }).then(function (res) {
      if (!res.ok) {
        notice(els.addMsg, (res.j && res.j.detail) || "დამატება ვერ მოხერხდა.", "bad");
      } else {
        notice(els.addMsg, "ბარათი დაემატა: " + esc(card), "ok");
        els.newCard.value = "";
        load();
      }
    });
  }
  els.addBtn.addEventListener("click", addCard);
  els.newCard.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); addCard(); }
  });

  // "Capture card": focus the field; a USB tap types the id + Enter -> add.
  els.captureBtn.addEventListener("click", function () {
    els.newCard.focus();
    els.captureHint.classList.remove("hidden");
    setTimeout(function () { els.captureHint.classList.add("hidden"); }, 4000);
  });

  // ----------------------------- import ----------------------------------- //
  els.importBtn.addEventListener("click", function () {
    var f = els.importFile.files[0];
    if (!f) { notice(els.importMsg, "აირჩიეთ ფაილი.", "warn"); return; }
    var fd = new FormData();
    fd.append("file", f);
    els.importBtn.disabled = true;
    notice(els.importMsg, "მიმდინარეობს იმპორტი…", "warn");
    fetch("/api/people/import", { method: "POST", body: fd })
      .then(function (r) {
        if (r.status === 401) { window.location.href = "/login"; throw new Error("auth"); }
        return r.json();
      })
      .then(function (rep) {
        var parts = [
          "დაემატა: " + rep.added,
          "დუბლიკატი: " + rep.duplicate_count,
          "შეცდომა: " + rep.invalid_count,
          "სულ ხაზი: " + rep.total_rows,
        ];
        var kind = rep.invalid_count > 0 || rep.duplicate_count > 0 ? "warn" : "ok";
        var html = parts.join(" • ");
        if (rep.duplicates && rep.duplicates.length) {
          html += "<br><small>დუბლიკატები (ხაზი): " +
            rep.duplicates.map(function (d) { return d.row + ":" + esc(d.card_id); }).join(", ") + "</small>";
        }
        if (rep.invalid && rep.invalid.length) {
          html += "<br><small>შეცდომები (ხაზი): " +
            rep.invalid.map(function (d) { return d.row + ":" + esc(d.reason); }).join(", ") + "</small>";
        }
        notice(els.importMsg, html, kind);
        els.importFile.value = "";
        load();
      })
      .catch(function () { notice(els.importMsg, "იმპორტი ვერ მოხერხდა.", "bad"); })
      .finally(function () { els.importBtn.disabled = false; });
  });

  // ----------------------------- search ----------------------------------- //
  els.searchBtn.addEventListener("click", load);
  els.search.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); load(); }
  });

  // ----------------------------- chrome ----------------------------------- //
  els.logoutBtn.addEventListener("click", function () {
    api("POST", "/api/logout").then(function () { window.location.href = "/login"; });
  });

  // Init: confirm session, then load.
  api("GET", "/api/me").then(function (res) {
    if (res.j && res.j.username) els.userLabel.textContent = res.j.username;
    renderHead();
    load();
  });
})();

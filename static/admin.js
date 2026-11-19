/* Admin paneli. Bütün dinamik mətn textContent ilə yazılır (müştəri mətni heç vaxt HTML kimi şərh olunmur). */
(function () {
  "use strict";

  // Mətnlər bir yerdədir: tərcümə etmək üçün yalnız bunu dəyişin.
  var T = {
    title: "TZ admin", signin: "Daxil ol", token: "Admin tokeni", enter: "Daxil ol", logout: "Çıxış",
    badToken: "Token yanlışdır.", tooMany: "Çox cəhd. Bir az gözləyin.", netErr: "Server cavab vermir.",
    overview: "Ümumi baxış", total: "Sessiya (cəmi)", active: "Davam edir", confirmed: "Təsdiqlənib", week: "Son 7 gün",
    withOpen: "Açıq sualı olan", rating: "Qiymətləndirmə",
    topOpen: "Ən çox keçilən suallar", topOpenNote: "Müştərilər bu suallara «bilmirəm» deyir: izahı və ya sualı yaxşılaşdırın.",
    none: "Hələ yoxdur.", llm: "LLM provayderləri", mode: "Rejim", model: "Model", ok: "Uğurlu", fail: "Xəta",
    failRate: "Xəta %", lastErr: "Son xəta", ms: "Son ms", noLlm: "LLM işlətmir (heuristik rejim) və ya hələ sorğu olmayıb.",
    system: "Sistem", db: "Baza", notify: "Bildiriş", sessions: "Sessiyalar", all: "Hamısı", st_active: "Davam edir",
    st_confirmed: "Təsdiqlənib", onlyOpen: "Yalnız açıq sualı olanlar", search: "Layihə, e-poçt və ya id", refresh: "Yenilə",
    project: "Layihə", contact: "Əlaqə", status: "Status", progress: "İrəliləyiş", open: "Açıq", updated: "Yenilənib",
    type: "Növ", prev: "‹ Əvvəlki", next: "Növbəti ›", of: "/", empty: "Sessiya tapılmadı.", capped: "Ən son {n} sessiya göstərilir.",
    close: "Bağla", openQ: "Açıq suallar", noOpenQ: "Açıq sual yoxdur.", summary: "TZ xülasəsi", chat: "Söhbət",
    files: "Fayllar", feedback: "Rəy", versions: "Versiyalar", dl: "Yüklə", del: "Sessiyanı sil",
    confirmDel: "Bu sessiya və faylları həmişəlik silinsin?", notConfirmed: "Hələ təsdiqlənməyib: yükləmək olmur.",
    budget: "Büdcə", lang: "Dil", created: "Yaradılıb", missing: "Çatışmayan məcburi sahələr", loading: "Yüklənir…"
  };

  var app = document.getElementById("app");
  var detail = document.getElementById("detail");
  var panel = document.getElementById("panel");
  var token = "";
  var state = { status: "all", open: false, q: "", offset: 0, limit: 25 };

  try { token = sessionStorage.getItem("tz_admin") || ""; } catch (e) { token = ""; }

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") el.className = attrs[k];
      else if (k.indexOf("on") === 0) el.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) el.setAttribute(k, attrs[k]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) continue;
      if (Array.isArray(c)) { c.forEach(function (x) { el.appendChild(x); }); continue; }
      el.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function fmt(iso) { return iso ? iso.replace("T", " ").slice(0, 16) : "—"; }
  function card(title) { var c = h("div", { class: "card" }); if (title) c.appendChild(h("h2", null, title)); return c; }
  function pill(text, kind) { return h("span", { class: "pill " + (kind || "") }, text); }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ Authorization: "Bearer " + token }, opts.headers || {});
    return fetch("/admin/api" + path, opts).then(function (r) {
      if (r.status === 401) { var e = new Error("auth"); e.code = 401; throw e; }
      if (r.status === 429) { var e2 = new Error("rate"); e2.code = 429; throw e2; }
      if (!r.ok) { var e3 = new Error("http " + r.status); e3.code = r.status; throw e3; }
      return r;
    });
  }

  // ---------- giriş ----------
  function showLogin(msg) {
    clear(app);
    var input = h("input", { type: "password", placeholder: T.token, autocomplete: "current-password", "aria-label": T.token });
    var err = h("div", { class: "err", role: "alert" }, msg || "");
    function go() {
      token = input.value.trim();
      if (!token) return;
      api("/overview").then(function () {
        try { sessionStorage.setItem("tz_admin", token); } catch (e) { /* sessionStorage olmaya bilər */ }
        showApp();
      }).catch(function (e) {
        token = "";
        err.textContent = e.code === 401 ? T.badToken : e.code === 429 ? T.tooMany : T.netErr;
      });
    }
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
    app.appendChild(h("div", { class: "card login" }, h("h1", null, T.title), h("div", { class: "mute" }, T.signin), input, err,
      h("button", { class: "primary", onclick: go }, T.enter)));
    input.focus();
  }

  function logout() {
    token = "";
    try { sessionStorage.removeItem("tz_admin"); } catch (e) { /* ignore */ }
    showLogin();
  }

  function onFail(e) {
    if (e && e.code === 401) { logout(); showLogin(T.badToken); return; }
    app.appendChild(h("div", { class: "card err" }, e && e.code === 429 ? T.tooMany : T.netErr));
  }

  // ---------- əsas ekran ----------
  function showApp() {
    clear(app);
    app.appendChild(h("header", null, h("h1", null, T.title),
      h("button", { onclick: loadAll }, T.refresh), h("button", { onclick: logout }, T.logout)));
    app.appendChild(h("main", { id: "main" }, h("div", { id: "ov" }, T.loading), h("div", { id: "list" })));
    loadAll();
  }

  function loadAll() { loadOverview(); loadList(); }

  function loadOverview() {
    api("/overview").then(function (r) { return r.json(); }).then(renderOverview).catch(onFail);
  }

  function stat(n, label) { return h("div", { class: "stat" }, h("b", null, n === null || n === undefined ? "—" : n), h("span", null, label)); }

  function renderOverview(o) {
    var ov = document.getElementById("ov");
    if (!ov) return;
    clear(ov);
    var s = o.sessions;
    var c1 = card(T.overview);
    c1.appendChild(h("div", { class: "grid" }, stat(s.total, T.total), stat(s.active, T.active), stat(s.confirmed, T.confirmed),
      stat(s.last_7_days, T.week), stat(s.with_open_questions, T.withOpen),
      stat(o.feedback.avg === null ? "—" : o.feedback.avg + " (" + o.feedback.count + ")", T.rating)));
    ov.appendChild(c1);

    var c2 = card(T.topOpen);
    c2.appendChild(h("div", { class: "mute", style: "margin-bottom:6px" }, T.topOpenNote));
    if (!o.top_open.length) c2.appendChild(h("div", { class: "mute" }, T.none));
    else {
      var t = h("table");
      o.top_open.forEach(function (x) { t.appendChild(h("tr", null, h("td", null, x.label), h("td", { class: "mono" }, "×" + x.count))); });
      c2.appendChild(t);
    }
    ov.appendChild(c2);

    var c3 = card(T.llm);
    c3.appendChild(h("div", { class: "mute", style: "margin-bottom:6px" }, T.mode + ": " + o.llm.mode + " · prompt: " + o.llm.prompt));
    if (!o.llm.stats.length) c3.appendChild(h("div", { class: "mute" }, T.noLlm));
    else {
      var lt = h("table", null, h("tr", null, h("th", null, T.model), h("th", null, T.ok), h("th", null, T.fail),
        h("th", null, T.failRate), h("th", null, T.lastErr), h("th", null, T.ms)));
      o.llm.stats.forEach(function (m) {
        lt.appendChild(h("tr", null, h("td", { class: "mono" }, m.model), h("td", null, m.ok), h("td", null, m.fail),
          h("td", null, pill(Math.round(m.fail_rate * 100) + "%", m.fail_rate >= 0.5 ? "bad" : m.fail_rate > 0 ? "warn" : "ok")),
          h("td", { class: "mono" }, m.last_error || "—"), h("td", null, m.last_ms)));
      });
      c3.appendChild(lt);
    }
    c3.appendChild(h("div", { class: "mute", style: "margin-top:6px" }, o.llm.note));
    ov.appendChild(c3);

    var n = o.system.notify;
    ov.appendChild(card(T.system)).appendChild(h("div", null, T.db + ": " + o.system.db + " · " + T.notify + ": e-mail " +
      (n.email ? "✓" : "✗") + ", Telegram " + (n.telegram ? "✓" : "✗")));
  }

  // ---------- sessiya siyahısı ----------
  function loadList() {
    var qs = "?status=" + encodeURIComponent(state.status) + "&open=" + (state.open ? 1 : 0) + "&q=" + encodeURIComponent(state.q) +
      "&limit=" + state.limit + "&offset=" + state.offset;
    api("/sessions" + qs).then(function (r) { return r.json(); }).then(renderList).catch(onFail);
  }

  function renderList(data) {
    var box = document.getElementById("list");
    if (!box) return;
    clear(box);
    var c = card(T.sessions);
    var sel = h("select", { "aria-label": T.status, onchange: function () { state.status = sel.value; state.offset = 0; loadList(); } },
      h("option", { value: "all" }, T.all), h("option", { value: "active" }, T.st_active), h("option", { value: "confirmed" }, T.st_confirmed));
    sel.value = state.status;
    var chk = h("input", { type: "checkbox", onchange: function () { state.open = chk.checked; state.offset = 0; loadList(); } });
    chk.checked = state.open;
    var q = h("input", { type: "search", placeholder: T.search, value: state.q, "aria-label": T.search });
    q.addEventListener("keydown", function (e) { if (e.key === "Enter") { state.q = q.value; state.offset = 0; loadList(); } });
    c.appendChild(h("div", { class: "bar" }, sel, h("label", null, chk, T.onlyOpen), q));

    if (!data.items.length) c.appendChild(h("div", { class: "mute" }, T.empty));
    else {
      var t = h("table", null, h("tr", null, h("th", null, T.project), h("th", null, T.status), h("th", null, T.progress),
        h("th", null, T.open), h("th", null, T.contact), h("th", null, T.type), h("th", null, T.updated)));
      data.items.forEach(function (s) {
        var tr = h("tr", { class: "click", tabindex: "0", onclick: function () { openDetail(s.id); } },
          h("td", null, s.project), h("td", null, pill(s.status === "confirmed" ? T.st_confirmed : T.st_active, s.status === "confirmed" ? "ok" : "")),
          h("td", null, s.progress + "%"), h("td", null, s.open_count ? pill(s.open_count, "warn") : "0"),
          h("td", null, s.contact || "—"), h("td", { class: "mute" }, s.site_type || "—"), h("td", { class: "mute" }, fmt(s.updated_at)));
        tr.addEventListener("keydown", function (e) { if (e.key === "Enter") openDetail(s.id); });
        t.appendChild(tr);
      });
      c.appendChild(t);
      var from = data.offset + 1, to = data.offset + data.items.length;
      var prev = h("button", { onclick: function () { state.offset = Math.max(0, state.offset - state.limit); loadList(); } }, T.prev);
      var next = h("button", { onclick: function () { state.offset += state.limit; loadList(); } }, T.next);
      prev.disabled = data.offset === 0;
      next.disabled = to >= data.total;
      c.appendChild(h("div", { class: "bar", style: "margin-top:10px" }, prev, h("span", { class: "mute" }, from + "–" + to + " " + T.of + " " + data.total), next));
    }
    if (data.scanned >= 500) c.appendChild(h("div", { class: "mute" }, T.capped.replace("{n}", data.scanned)));
    box.appendChild(c);
  }

  // ---------- sessiya təfərrüatı ----------
  function closeDetail() { detail.style.display = "none"; clear(panel); document.body.style.overflow = ""; }
  detail.addEventListener("click", function (e) { if (e.target === detail) closeDetail(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDetail(); });

  function openDetail(sid) {
    clear(panel);
    panel.appendChild(h("div", null, T.loading));
    detail.style.display = "block";
    document.body.style.overflow = "hidden";
    api("/sessions/" + encodeURIComponent(sid)).then(function (r) { return r.json(); }).then(renderDetail).catch(function (e) {
      closeDetail(); onFail(e);
    });
  }

  function download(sid, fmtName, btn) {
    btn.disabled = true;
    api("/sessions/" + encodeURIComponent(sid) + "/download?format=" + fmtName).then(function (r) {
      var cd = r.headers.get("content-disposition") || "";
      var m = /filename="?([^";]+)"?/.exec(cd);
      return r.blob().then(function (b) { return { b: b, name: m ? m[1] : "tz." + fmtName }; });
    }).then(function (x) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(x.b);
      a.download = x.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
    }).catch(function (e) { if (e.code === 401) { closeDetail(); onFail(e); } else alert(e.code === 409 ? T.notConfirmed : T.netErr); })
      .then(function () { btn.disabled = false; });
  }

  function renderDetail(s) {
    clear(panel);
    var confirmed = s.status === "confirmed";
    var dl = ["docx", "pdf", "assets"].map(function (f) {
      var b = h("button", { onclick: function () { download(s.id, f, b); } }, T.dl + " " + (f === "assets" ? "ZIP" : f.toUpperCase()));
      b.disabled = !confirmed;
      if (!confirmed) b.title = T.notConfirmed;
      return b;
    });
    var del = h("button", { class: "danger", onclick: function () {
      if (!window.confirm(T.confirmDel)) return;
      api("/sessions/" + encodeURIComponent(s.id), { method: "DELETE" }).then(function () { closeDetail(); loadAll(); }).catch(onFail);
    } }, T.del);
    panel.appendChild(h("div", { class: "row" }, h("h2", { style: "margin:0" }, s.project),
      h("button", { onclick: closeDetail }, T.close)));
    panel.appendChild(h("div", { class: "mute mono", style: "margin:4px 0 10px" },
      s.id + " · " + T.lang + ": " + s.language + " · " + T.created + ": " + fmt(s.created_at) + " · " + T.updated + ": " + fmt(s.updated_at)));
    var meta = [pill(confirmed ? T.st_confirmed : T.st_active, confirmed ? "ok" : ""), pill(s.progress + "%")];
    if (s.cost_min != null) meta.push(pill(T.budget + ": " + Math.round(s.cost_min) + "–" + Math.round(s.cost_max) + " AZN"));
    if (s.contact) meta.push(pill(s.contact));
    panel.appendChild(h("div", { class: "bar" }, meta));
    panel.appendChild(h("div", { class: "bar" }, dl.concat([del])));

    var cq = card(T.openQ);
    if (!s.clarifications.length) cq.appendChild(h("div", { class: "mute" }, T.noOpenQ));
    else {
      var ul = h("ul", { class: "open" });
      s.clarifications.forEach(function (x) { ul.appendChild(h("li", null, x)); });
      cq.appendChild(ul);
    }
    if (s.missing && s.missing.length) cq.appendChild(h("div", { class: "mute", style: "margin-top:6px" }, T.missing + ": " + s.missing.join(", ")));
    panel.appendChild(cq);

    var cs = card(T.summary);
    s.sections.forEach(function (sec) {
      if (!sec.items.length) return;
      cs.appendChild(h("h3", { style: "margin:10px 0 4px;font-size:14px" }, sec.title));
      var t = h("table");
      sec.items.forEach(function (i) { t.appendChild(h("tr", null, h("td", { class: "mute", style: "width:32%" }, i.label), h("td", null, i.value))); });
      cs.appendChild(t);
    });
    panel.appendChild(cs);

    var cc = card(T.chat);
    s.messages.forEach(function (m) { cc.appendChild(h("div", { class: "msg " + (m.role === "user" ? "user" : "ai"), title: fmt(m.at) }, m.content)); });
    panel.appendChild(cc);

    if (s.files.length || s.versions.length || s.feedback.length) {
      var cf = card(T.files + " / " + T.versions + " / " + T.feedback);
      s.files.forEach(function (f) { cf.appendChild(h("div", null, f.kind + ": " + f.filename + " (" + Math.round(f.size / 1024) + " KB)")); });
      s.versions.forEach(function (v) { cf.appendChild(h("div", { class: "mute" }, "v" + v.version + " · " + fmt(v.at))); });
      s.feedback.forEach(function (f) { cf.appendChild(h("div", null, "★ " + f.rating + (f.comment ? " — " + f.comment : ""))); });
      panel.appendChild(cf);
    }
  }

  if (token) showApp(); else showLogin();
})();


  var state = { table: "", page: 1, q: "", size: 20, total: 0, pages: 1, leadStatus: "", logAction: "" };
  var TABLES = [];

  function token() { return localStorage.getItem("yj_token") || ""; }
  function authHeaders() { return { Authorization: "Bearer " + token() }; }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function api(path) {
    return fetch(path, { headers: authHeaders() })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || r.status); return d; }); });
  }
  function fmtTime(s) { return s ? String(s).slice(5, 16) : "—"; }

  var STATUS_CLASS = {
    "待审批": "warn", "待处理": "warn", "待跟进": "warn", "新增意向": "warn", "跟进中": "",
    "已通过": "ok", "已解决": "ok", "已签约": "ok", "已报名": "ok", "正常": "ok",
    "已驳回": "bad", "已流失": "bad", "未处理": "bad", "高": "bad", "中": "warn", "低": "ok"
  };

  /* ---------- 图表（SVG 环形 + 横条） ---------- */
  function donut(items, size, thick, centerVal, centerLab) {
    var total = 0; items.forEach(function (it) { total += it[2]; });
    var r = (size - thick) / 2, cx = size / 2, cy = size / 2, circ = 2 * Math.PI * r;
    var out = '<svg viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '">';
    out += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="var(--track)" stroke-width="' + thick + '"/>';
    var acc = 0;
    items.forEach(function (it) {
      var seg = total ? it[2] / total * circ : 0;
      out += '<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + it[1] + '" stroke-width="' + thick +
        '" stroke-dasharray="' + Math.max(0, seg - 2) + ' ' + circ + '" stroke-dashoffset="' + (-acc) +
        '" transform="rotate(-90 ' + cx + ' ' + cy + ')"/>';
      acc += seg;
    });
    out += '<text x="' + cx + '" y="' + (cy - 2) + '" text-anchor="middle" font-size="26" font-weight="700" font-family="ui-monospace,monospace" fill="var(--tx)">' + centerVal + '</text>';
    out += '<text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" font-size="10" fill="var(--mut)">' + centerLab + '</text>';
    return out + '</svg>';
  }
  function legend(items) {
    return items.map(function (it) {
      return '<div class="lg"><i style="background:' + it[1] + '"></i><span>' + esc(it[0]) + '</span><b>' + it[2] + '</b></div>';
    }).join("");
  }
  function bars(items, color) {
    var max = 0; items.forEach(function (it) { max = Math.max(max, it[1]); });
    return items.map(function (it) {
      var pct = max ? Math.round(it[1] / max * 100) : 0;
      return '<div class="bar"><span>' + esc(it[0]) + '</span><span class="track"><span class="fill" style="width:' +
        pct + '%;background:' + (it[2] || color) + '"></span></span><b>' + it[1] + '</b></div>';
    }).join("");
  }

  /* ---------- 视图切换 ---------- */
  function showDash() {
    state.table = "";
    document.getElementById("view-dash").hidden = false;
    document.getElementById("view-table").hidden = true;
    document.getElementById("view-leads").hidden = true;
    document.getElementById("view-logs").hidden = true;
    document.getElementById("nav-leads").classList.remove("on");
    document.getElementById("nav-logs").classList.remove("on");
    document.getElementById("crumb").textContent = "DATA / 数据总览";
    document.getElementById("nav-dash").classList.add("on");
    Array.prototype.forEach.call(document.querySelectorAll("#tables a"), function (a) { a.classList.remove("on"); });
    window.scrollTo(0, 0);
  }
  function showTable() {
    document.getElementById("view-dash").hidden = true;
    document.getElementById("view-table").hidden = false;
    document.getElementById("view-leads").hidden = true;
    document.getElementById("view-logs").hidden = true;
    document.getElementById("nav-leads").classList.remove("on");
    document.getElementById("nav-logs").classList.remove("on");
    var meta = TABLES.filter(function (t) { return t.name === state.table; })[0];
    document.getElementById("crumb").textContent = "DATA / " + ((meta && meta.label) || state.table);
    document.getElementById("nav-dash").classList.remove("on");
    Array.prototype.forEach.call(document.querySelectorAll("#tables a"), function (a) {
      a.classList.toggle("on", a.getAttribute("data-table") === state.table);
    });
    window.scrollTo(0, 0);
  }

  /* ---------- 表清单 ---------- */
  function renderTables(list) {
    TABLES = list;
    document.getElementById("tables").innerHTML = list.map(function (t) {
      return '<a data-table="' + t.name + '"><span class="ic">' + t.icon + '</span><span>' +
        esc(t.label) + '</span><span class="n">' + t.count + '</span></a>';
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll("#tables a"), function (a) {
      a.addEventListener("click", function () { openTable(a.getAttribute("data-table")); });
    });
  }
  function loadTables() { return api("/api/admin/tables").then(function (d) { return renderTables(d.data); }); }

  /* ---------- 概览 ---------- */
  function renderOverview(d) {
    var v = d.data || {};
    var leads = v.leads || {}, leaves = v.leaves || {}, alerts = v.alerts || {};
    var tickets = v.tickets || {}, events = v.events || {}, chats = v.chats || {};
    var d1 = new Date();
    document.getElementById("today").textContent =
      d1.getFullYear() + " 年 " + (d1.getMonth() + 1) + " 月 " + d1.getDate() + " 日 · 周" + "日一二三四五六".charAt(d1.getDay());

    document.getElementById("k-lead").textContent = leads.total || 0;
    document.getElementById("t-lead").textContent = "今日 +" + (leads.today || 0);
    document.getElementById("k-follow").textContent = leads.following || 0;
    document.getElementById("t-follow").textContent = "已签约 " + (leads.signed || 0);
    document.getElementById("k-chat").textContent = chats.today || 0;

    document.getElementById("n-alert").textContent = alerts.open || 0;
    document.getElementById("d-alert").textContent = "3 条高风险";
    document.getElementById("n-alert2").textContent = alerts.open || 0;
    document.getElementById("d-alert2").textContent = "需今日介入";
    document.getElementById("n-leave").textContent = leaves.pending || 0;
    document.getElementById("d-leave").textContent = "共 " + (leaves.total || 0) + " 条服务记录";
    document.getElementById("n-ticket").textContent = tickets.open || 0;
    document.getElementById("d-ticket").textContent = "尚未解决";
  }

  function renderAlerts(d) {
    var box = document.getElementById("alerts");
    var rows = (d.data && d.data.rows) || [];
    if (!rows.length) { box.innerHTML = '<div class="empty">暂无未处理预警</div>'; return; }
    box.innerHTML = rows.slice(0, 5).map(function (r) {
      var lv = r.risk_level || "—";
      var cls = lv === "高" ? "h" : "m";
      return '<div class="alert-row"><span class="sid">#' + esc(r.id) + '</span>' +
        '<span><span class="risk ' + cls + '">' + esc(lv) + '风险</span></span>' +
        '<span class="msg" title="' + esc(r.trigger_reason) + '">' + esc(r.trigger_reason) + '</span>' +
        '<span class="tm">' + fmtTime(r.create_time) + '</span>' +
        '<a class="act" data-goto="student_psych_alert">查看 →</a></div>';
    }).join("");
    bindGoto(box);
  }

  var LEAD_COLORS = { "新增意向":"#0d9488", "跟进中":"#f59e0b", "已签约":"#65a30d", "已流失":"#94a3b8" };
  function renderDist(d) {
    var rows = (d.data && d.data.rows) || [];
    var counts = {};
    rows.forEach(function (r) { counts[r.status] = (counts[r.status] || 0) + 1; });
    var order = ["新增意向", "跟进中", "已签约", "已流失"];
    var items = order.map(function (k) { return [k, LEAD_COLORS[k], counts[k] || 0]; });
    document.getElementById("dist-total").textContent = rows.length;
    document.getElementById("dist-donut").innerHTML = donut(items, 112, 16, String(rows.length), "总线索");
    document.getElementById("dist-legend").innerHTML = legend(items);
  }

  function renderScore(d) {
    var rows = (d.data && d.data.rows) || [];
    var buckets = { "<60":0, "60-69":0, "70-79":0, "80-89":0, "90+":0 };
    rows.forEach(function (r) {
      var s = Number(r.score);
      if (isNaN(s)) return;
      if (s >= 90) buckets["90+"]++;
      else if (s >= 80) buckets["80-89"]++;
      else if (s >= 70) buckets["70-79"]++;
      else if (s >= 60) buckets["60-69"]++;
      else buckets["<60"]++;
    });
    var order = ["<60","60-69","70-79","80-89","90+"];
    document.getElementById("score-bars").innerHTML = bars(order.map(function (k) { return [k, buckets[k]]; }), "#0d9488");
  }

  function renderAgent(d) {
    var rows = (d.data && d.data.rows) || [];
    var counts = {};
    var LABELS = { STUDENT:"学生侧", EMPLOYEE:"员工侧", PARENT:"家长侧", "学生侧":"学生侧", "员工侧":"员工侧" };
    rows.forEach(function (r) { counts[r.agent_type] = (counts[r.agent_type] || 0) + 1; });
    var keys = Object.keys(counts);
    var palette = ["#0d9488","#0891b2","#65a30d","#d97706"];
    var items = keys.map(function (k, i) { return [LABELS[k] || k, palette[i % palette.length], counts[k]]; });
    document.getElementById("agent-total").textContent = rows.length;
    document.getElementById("agent-donut").innerHTML = donut(items.length ? items : [["暂无", "#e8f0ee", 1]], 100, 15, String(rows.length), "对话");
    document.getElementById("agent-legend").innerHTML = legend(items);
  }

  function renderEvents(d) {
    var rows = (d.data && d.data.rows) || [];
    var today = new Date().toISOString().slice(0, 10);
    rows = rows.filter(function (r) { return String(r.start_time || "") >= today; });
    var box = document.getElementById("events");
    if (!rows.length) { box.innerHTML = '<div class="empty" style="padding:24px">暂无讲座</div>'; return; }
    box.innerHTML = rows.slice(0, 5).map(function (r) {
      var cur = Number(r.current_participants || 0), max = Number(r.max_participants || 0);
      var pct = max ? Math.min(100, Math.round(cur / max * 100)) : 0;
      return '<div class="bar ev"><span class="nm" title="' + esc(r.event_name) + '">' + esc(r.event_name) +
        '</span><span class="track"><span class="fill" style="width:' + pct + '%;background:var(--ac)"></span></span>' +
        '<b>' + cur + '</b></div>';
    }).join("");
  }

  function loadDashboard() {
    return Promise.all([
      api("/api/admin/dashboard").then(renderOverview).catch(function () {}),
      api("/api/admin/table/student_psych_alert?page=1&size=100").then(renderAlerts).catch(function (e) {
        document.getElementById("alerts").innerHTML = '<div class="empty">预警读取失败：' + esc(e.message) + '</div>'; }),
      api("/api/admin/table/crm_lead?page=1&size=100").then(renderDist).catch(function () {}),
      api("/api/admin/table/student_score?page=1&size=100").then(renderScore).catch(function () {}),
      api("/api/admin/table/conversation_log?page=1&size=100").then(renderAgent).catch(function () {}),
      api("/api/admin/table/event_lecture?page=1&size=100").then(renderEvents).catch(function () {})
    ]);
  }

  function bindGoto(root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("[data-goto]"), function (a) {
      a.addEventListener("click", function () { openTable(a.getAttribute("data-goto")); });
    });
  }

  /* ---------- 表格 ---------- */
  function openTable(name) {
    state.table = name; state.page = 1; state.q = "";
    document.getElementById("q").value = "";
    showTable();
    loadRows();
  }
  function cell(key, value) {
    if (value === null || value === undefined || value === "") {
      return key === "owner_name"
        ? '<span style="color:#b6c6c1">未分配</span>'
        : '<span style="color:#b6c6c1">—</span>';
    }
    if (key === "status" || key === "risk_level") {
      return '<span class="pill ' + (STATUS_CLASS[value] || "") + '">' + esc(value) + "</span>";
    }
    if (typeof value === "number") return '<span class="num">' + value + "</span>";
    var text = String(value);
    if (text.length > 60) return '<span class="clip" title="' + esc(text) + '">' + esc(text) + "</span>";
    return esc(text);
  }
  function loadRows() {
    var url = "/api/admin/table/" + state.table + "?page=" + state.page + "&size=" + state.size +
      (state.q ? "&q=" + encodeURIComponent(state.q) : "");
    document.getElementById("table-box").innerHTML = '<div class="empty">读取中…</div>';
    api(url).then(function (d) { render(d.data); }).catch(function (e) {
      document.getElementById("table-box").innerHTML = '<div class="empty">读取失败：' + esc(e.message) + "</div>";
    });
  }
  function render(data) {
    state.total = data.total; state.pages = data.pages;
    var meta = TABLES.filter(function (t) { return t.name === state.table; })[0];
    document.getElementById("title").textContent = data.label || (meta && meta.label) || state.table;
    document.getElementById("count").textContent = "共 " + data.total + " 行";
    document.getElementById("page-info").textContent = "第 " + data.page + " / " + data.pages + " 页 · 每页 " + data.size + " 行";
    document.getElementById("prev").disabled = data.page <= 1;
    document.getElementById("next").disabled = data.page >= data.pages;
    if (!data.rows.length) { document.getElementById("table-box").innerHTML = '<div class="empty">没有匹配的数据</div>'; return; }
    var labels = data.labels || {};
    var head = "<table><thead><tr>" + data.columns.map(function (c) {
      return "<th>" + esc(labels[c] || c) + "</th>";
    }).join("") + "</tr></thead><tbody>";
    var body = data.rows.map(function (row) {
      return "<tr>" + data.columns.map(function (c) {
        return '<td' + (c === "owner_name" ? ' class="nowrap"' : "") + ">" + cell(c, row[c]) + "</td>";
      }).join("") + "</tr>";
    }).join("");
    document.getElementById("table-box").innerHTML = head + body + "</tbody></table>";
  }

  /* ---------- 线索跟进（客服留资 → 顾问接手） ---------- */
  function showLogs() {
    state.table = "";
    ["view-dash", "view-table", "view-leads"].forEach(function (id) {
      document.getElementById(id).hidden = true;
    });
    document.getElementById("view-logs").hidden = false;
    document.getElementById("crumb").textContent = "DATA / 操作日志";
    document.getElementById("nav-dash").classList.remove("on");
    document.getElementById("nav-leads").classList.remove("on");
    document.getElementById("nav-logs").classList.add("on");
    Array.prototype.forEach.call(document.querySelectorAll("#tables a"), function (a) { a.classList.remove("on"); });
    window.scrollTo(0, 0);
    loadLogs();
  }

  function loadLogs() {
    var box = document.getElementById("log-box");
    box.innerHTML = '<div class="empty">读取中…</div>';
    var url = "/api/admin/logs?size=100" + (state.logAction ? "&action=" + encodeURIComponent(state.logAction) : "");
    api(url).then(renderLogs).catch(function (e) {
      box.innerHTML = '<div class="empty">读取失败：' + esc(e.message) + "</div>";
    });
  }

  function renderLogs(d) {
    var data = d.data || {};
    var rows = data.rows || [];
    document.getElementById("log-n").textContent = data.total;
    document.getElementById("log-sub").textContent =
      "共 " + data.total + " 条 · 今日 " + ((data.today && data.today.total) || 0) + " 条 · 只读，不能修改或删除";

    var acts = [{ key: "", label: "全部" }].concat(data.actions || []);
    document.getElementById("log-filters").innerHTML = acts.map(function (a) {
      return '<button data-act="' + esc(a.key) + '" class="' + (a.key === state.logAction ? "on" : "") + '">' +
        esc(a.label) + "</button>";
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll("#log-filters button"), function (b) {
      b.addEventListener("click", function () { state.logAction = b.getAttribute("data-act"); loadLogs(); });
    });

    var box = document.getElementById("log-box");
    if (!rows.length) { box.innerHTML = '<div class="empty">这个筛选下还没有记录</div>'; return; }
    box.innerHTML = rows.map(function (r) {
      var cls = /失败|驳回/.test(r.result) ? "no" : "ok";
      return '<div class="log-row"><div class="log-t">' + esc(r.time_short) + "</div>" +
        '<div class="log-b"><div class="log-h"><b>' + esc(r.action_label) + "</b>" +
        '<span class="pill ' + cls + '">' + esc(r.result) + "</span>" +
        '<span class="log-who">' + esc(r.actor_name || "—") + " · " + esc(r.role_label || "") + "</span></div>" +
        '<div class="log-sum">' + esc(r.summary) + "</div>" +
        (r.detail ? '<div class="log-det">' + esc(r.detail) + "</div>" : "") +
        "</div></div>";
    }).join("");
  }

  document.getElementById("nav-logs").addEventListener("click", showLogs);

  function showLeads() {
    state.table = "";
    document.getElementById("view-dash").hidden = true;
    document.getElementById("view-table").hidden = true;
    document.getElementById("view-leads").hidden = false;
    document.getElementById("view-logs").hidden = true;
    document.getElementById("crumb").textContent = "DATA / 线索跟进";
    document.getElementById("nav-dash").classList.remove("on");
    document.getElementById("nav-logs").classList.remove("on");
    document.getElementById("nav-leads").classList.add("on");
    Array.prototype.forEach.call(document.querySelectorAll("#tables a"), function (a) { a.classList.remove("on"); });
    window.scrollTo(0, 0);
    loadLeads();
  }

  function loadLeads() {
    var box = document.getElementById("lead-box");
    box.innerHTML = '<div class="empty">读取中…</div>';
    var url = "/api/admin/leads?size=50" + (state.leadStatus ? "&status=" + encodeURIComponent(state.leadStatus) : "");
    api(url).then(renderLeads).catch(function (e) {
      box.innerHTML = '<div class="empty">读取失败：' + esc(e.message) + "</div>";
    });
  }

  function renderLeads(d) {
    var data = d.data || {};
    var rows = data.rows || [];
    var counts = data.counts || {};
    var statuses = data.statuses || [];
    var all = statuses.reduce(function (a, st) { return a + (counts[st] || 0); }, 0);

    document.getElementById("lead-n").textContent = all;
    document.getElementById("lead-sub").textContent =
      "在线客服留资 · 自动分配顾问 · 共 " + all + " 条 · 管理员只读，跟进与状态由所属顾问维护";

    var tabs = [{ k: "", l: "全部", n: all }].concat(statuses.map(function (st) {
      return { k: st, l: st, n: counts[st] || 0 };
    }));
    document.getElementById("lead-filters").innerHTML = tabs.map(function (t) {
      return '<button data-st="' + esc(t.k) + '" class="' + (t.k === state.leadStatus ? "on" : "") + '">' +
        esc(t.l) + " " + t.n + "</button>";
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll("#lead-filters button"), function (b) {
      b.addEventListener("click", function () { state.leadStatus = b.getAttribute("data-st"); loadLeads(); });
    });

    var box = document.getElementById("lead-box");
    if (!rows.length) { box.innerHTML = '<div class="empty">这个状态下还没有线索</div>'; return; }

    box.innerHTML = rows.map(function (r) {
      var his = (r.follow_up_history || "").trim();
      var fromCs = String(r.background_info || "").indexOf("在线客服") >= 0;
      return '<div class="lead" data-id="' + r.id + '">' +
        '<div class="lead-h"><b>' + esc(r.customer_name || "未留名") + "</b>" +
        '<span class="pill ' + (STATUS_CLASS[r.status] || "") + '">' + esc(r.status) + "</span>" +
        (fromCs ? '<span class="pill ok">客服留资</span>' : "") +
        '<span class="lead-meta">' + esc(r.contact_info || "—") + " · 顾问 " +
        esc(r.owner_name || "未分配") + " · " + fmtTime(r.create_time) + "</span></div>" +
        '<div class="lead-b">' + esc(String(r.background_info || "—")) + "</div>" +
        (his ? '<details class="lead-his"><summary>跟进记录</summary><pre>' + esc(his) + "</pre></details>" : "") +
        "</div>";
    }).join("");
  }

  document.getElementById("nav-leads").addEventListener("click", showLeads);

  document.getElementById("search-form").addEventListener("submit", function (e) {
    e.preventDefault(); state.q = document.getElementById("q").value.trim(); state.page = 1; loadRows();
  });
  document.getElementById("prev").addEventListener("click", function () {
    if (state.page > 1) { state.page -= 1; loadRows(); }
  });
  document.getElementById("next").addEventListener("click", function () {
    if (state.page < state.pages) { state.page += 1; loadRows(); }
  });
  document.getElementById("nav-dash").addEventListener("click", showDash);
  document.getElementById("logout").addEventListener("click", function () {
    localStorage.removeItem("yj_token"); location.href = "/";
  });
  bindGoto(document);

  /* ---------- 拦截页内嵌登录：原地登录，不跳走 ---------- */
  function showBlocked(title, msg) {
    document.getElementById("app").hidden = true;
    document.getElementById("blocked").hidden = false;
    if (title) document.getElementById("blocked-title").textContent = title;
    if (msg) document.getElementById("blocked-msg").textContent = msg;
  }

  document.getElementById("blocked-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var u = document.getElementById("bu").value.trim();
    var p = document.getElementById("bp").value;
    var btn = document.getElementById("bsubmit");
    var tip = document.getElementById("bmsg");
    if (!u || !p) { tip.textContent = "请输入用户名和密码"; return; }
    btn.disabled = true; btn.textContent = "登录中…"; tip.textContent = "";
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || d.msg || "登录失败"); return d; }); })
      .then(function (d) {
        localStorage.setItem("yj_token", d.data.token);
        localStorage.setItem("yj_user", JSON.stringify(d.data.user || {}));
        location.reload();
      })
      .catch(function (err) {
        btn.disabled = false; btn.textContent = "登录并进入后台";
        tip.textContent = err.message || "登录失败";
      });
  });

  /* ---------- 启动：仅管理员可见 ---------- */
  if (!token()) {
    showBlocked("需要管理员登录", "输入管理员账号后即可查看数据后台。");
  } else {
    api("/api/auth/me").then(function (d) {
      var u = d.data || {};
      if (!u.features || !u.features.admin) {
        showBlocked("需要管理员身份",
          "当前身份是「" + (u.role_label || "未知") + "」，请用管理员账号重新登录。");
        return;
      }
      document.getElementById("me").textContent = u.real_name + " · " + u.role_label;
      document.getElementById("app").hidden = false;
      return loadTables().then(function () { return loadDashboard(); });
    }).catch(function () {
      // token 过期或无效：直接原地给登录框，不用绕门户
      localStorage.removeItem("yj_token");
      showBlocked("登录已过期", "请重新登录后继续查看数据后台。");
    });
  }

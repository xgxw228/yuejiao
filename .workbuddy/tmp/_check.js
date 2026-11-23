
(function () {
  "use strict";

  var TOKEN_KEY = "yj_token";

  var state = {
    agents: [],
    agent: null,
    userId: null,
    user: null,      // 登录用户（角色决定可见 Agent / 数据范围 / 功能入口）
    perms: {},
    conversationId: "",
    streaming: false,
    controller: null,
    ws: null,        // 我的工作台缓存（按角色）
    panelKey: null,  // 当前打开的事项面板（leaves / leads / logs）
  };

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  var el = {
    agents: document.getElementById("agents"),
    quicks: document.getElementById("quicks"),
    headEmoji: document.getElementById("head-emoji"),
    headName: document.getElementById("head-name"),
    headTag: document.getElementById("head-tag"),
    userSelect: document.getElementById("user-select"),
    clearBtn: document.getElementById("clear-btn"),
    logoutBtn: document.getElementById("logout-btn"),
    meChip: document.getElementById("me-chip"),
    meAvatar: document.getElementById("me-avatar"),
    meName: document.getElementById("me-name"),
    meRole: document.getElementById("me-role"),
    chat: document.getElementById("chat"),
    input: document.getElementById("input"),
    send: document.getElementById("send"),
    footUser: document.getElementById("foot-user"),
    hintConv: document.getElementById("hint-conv"),
    wsBtn: document.getElementById("ws-btn"),
    wsLabel: document.getElementById("ws-label"),
    wsBadge: document.getElementById("ws-badge"),
    navBlock: document.getElementById("nav-block"),
    navs: document.getElementById("navs"),
    panel: document.getElementById("panel"),
    panelBack: document.getElementById("panel-back"),
    panelTitle: document.getElementById("panel-title"),
    panelSub: document.getElementById("panel-sub"),
    panelBody: document.getElementById("panel-body"),
    composer: document.querySelector(".composer"),
    approveBtn: document.getElementById("approve-btn"),
    approveBadge: document.getElementById("approve-badge"),
    drawer: document.getElementById("drawer"),
    drawerMask: document.getElementById("drawer-mask"),
    drawerSub: document.getElementById("drawer-sub"),
    drawerBody: document.getElementById("drawer-body"),
    drawerClose: document.getElementById("drawer-close"),
    toast: document.getElementById("toast"),
  };

  /* ---------------- 轻量 Markdown ---------------- */
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function inline(s) {
    s = s.replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; });
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s;
  }

  function renderMarkdown(src) {
    var lines = escapeHtml(src).split("\n");
    var out = [];
    var list = null; // "ul" | "ol"
    var inCode = false;
    var buf = [];

    function closeList() {
      if (list) { out.push("</" + list + ">"); list = null; }
    }
    function flushPara() {
      if (buf.length) { out.push("<p>" + inline(buf.join(" ")) + "</p>"); buf = []; }
    }

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];

      if (/^```/.test(line.trim())) {
        flushPara(); closeList();
        if (inCode) { out.push("</code></pre>"); inCode = false; }
        else { out.push("<pre><code>"); inCode = true; }
        continue;
      }
      if (inCode) { out.push(line + "\n"); continue; }

      if (!line.trim()) { flushPara(); closeList(); continue; }

      var h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) { flushPara(); closeList(); out.push("<h4>" + inline(h[2]) + "</h4>"); continue; }

      if (/^\s*(?:[-*·•])\s+/.test(line)) {
        flushPara();
        if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
        out.push("<li>" + inline(line.replace(/^\s*(?:[-*·•])\s+/, "")) + "</li>");
        continue;
      }
      if (/^\s*\d+[.)]\s+/.test(line)) {
        flushPara();
        if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
        out.push("<li>" + inline(line.replace(/^\s*\d+[.)]\s+/, "")) + "</li>");
        continue;
      }
      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { flushPara(); closeList(); out.push("<hr>"); continue; }

      if (list) { closeList(); }
      buf.push(line.trim());
    }

    flushPara(); closeList();
    if (inCode) out.push("</code></pre>");
    return out.join("");
  }

  /* ---------------- 渲染骨架 ---------------- */
  function renderAgents() {
    el.agents.innerHTML = "";
    state.agents.forEach(function (a) {
      var b = document.createElement("button");
      b.className = "agent" + (state.agent && state.agent.key === a.key ? " on" : "");
      b.innerHTML =
        '<span class="agent-emoji">' + a.icon + "</span>" +
        '<span class="agent-body"><span class="agent-name">' + a.name + "</span>" +
        '<span class="agent-tag">' + a.tagline + "</span></span>";
      b.addEventListener("click", function () { switchAgent(a.key); });
      el.agents.appendChild(b);
    });
  }

  function renderQuicks() {
    el.quicks.innerHTML = "";
    (state.agent.prompts || []).forEach(function (p) {
      var b = document.createElement("button");
      b.className = "quick";
      b.textContent = p;
      b.addEventListener("click", function () {
        el.input.value = p;
        autoGrow();
        el.input.focus();
      });
      el.quicks.appendChild(b);
    });
  }

  function renderUsers() {
    var canSwitch = !!(state.perms && state.perms.switch_identity);
    el.userSelect.hidden = !canSwitch;
    el.userSelect.innerHTML = "";
    state.agent.users.forEach(function (u) {
      var o = document.createElement("option");
      o.value = u.id;
      o.textContent = u.label;
      el.userSelect.appendChild(o);
    });
    el.userSelect.value = state.userId;
    var u = currentUser();
    el.footUser.innerHTML =
      "当前身份：" + escapeHtml(u.label) +
      "<br>角色：" + escapeHtml(state.user ? state.user.role_label : "—") +
      (canSwitch ? "（可模拟）" : "");
  }

  function renderMe() {
    var u = state.user;
    if (!u) return;
    el.meAvatar.textContent = u.initial || (u.real_name || "?").slice(0, 1);
    el.meName.textContent = u.real_name;
    el.meRole.textContent = u.role_label;
    el.meChip.title = u.role_desc +
      (u.students ? "（名下 " + u.students + " 名学生）" : "");
  }

  function currentUser() {
    var id = Number(state.userId);
    return state.agent.users.filter(function (u) { return u.id === id; })[0] || state.agent.users[0];
  }

  // 审批人：管理员走全校视图（用自己 id），其他人就是当前身份
  function approverId() {
    return state.perms.approve === "all" && state.user ? state.user.id : Number(state.userId);
  }

  var WS_HINT = {
    staff: "左侧「待跟进线索」能看到分给你的客户，点一条就能写跟进、改状态。",
    teacher: "左侧「待处理请假」可直接通过 / 驳回，处理完会记进你的日志。",
    student: "左侧「请假记录」能看到批没批；也可以直接问我“我的请假请完了吗”。",
    admin: "左侧可看全校待批请假，数据后台有图表、全部数据表和操作日志。",
  };

  function emptyState() {
    var a = state.agent;
    el.chat.innerHTML = "";
    var wrap = document.createElement("div");
    wrap.className = "empty";
    wrap.innerHTML =
      '<div class="empty-emoji">' + a.icon + "</div>" +
      '<div class="empty-title">' + a.name + "</div>" +
      '<div class="empty-text">' + a.welcome + "</div>" +
      (state.user && WS_HINT[state.user.role]
        ? '<div class="empty-text" style="font-size:12px;color:var(--text-faint);margin-top:8px">' +
          WS_HINT[state.user.role] + "</div>"
        : "");
    var chips = document.createElement("div");
    chips.className = "empty-chips";
    a.prompts.slice(0, 4).forEach(function (p) {
      var c = document.createElement("button");
      c.className = "chip";
      c.textContent = p;
      c.addEventListener("click", function () { send(p); });
      chips.appendChild(c);
    });
    wrap.appendChild(chips);
    el.chat.appendChild(wrap);
  }

  /* ---------------- 消息节点 ---------------- */
  function scrollBottom(force) {
    var near = el.chat.scrollHeight - el.chat.scrollTop - el.chat.clientHeight < 160;
    if (force || near) el.chat.scrollTop = el.chat.scrollHeight;
  }

  function addUserMsg(text) {
    var d = document.createElement("div");
    d.className = "msg user";
    d.innerHTML =
      '<div class="avatar">🙋</div>' +
      '<div class="bubble-wrap"><div class="bubble">' + escapeHtml(text).replace(/\n/g, "<br>") + "</div></div>";
    el.chat.appendChild(d);
    scrollBottom(true);
  }

  function addBotMsg() {
    var d = document.createElement("div");
    d.className = "msg bot";
    d.innerHTML =
      '<div class="avatar">' + state.agent.icon + "</div>" +
      '<div class="bubble-wrap">' +
        '<div class="who">' + state.agent.name + "</div>" +
        '<div class="tools" hidden></div>' +
        '<div class="bubble"><span class="body"></span><span class="cursor"></span></div>' +
        '<div class="meta" hidden></div>' +
      "</div>";
    el.chat.appendChild(d);
    scrollBottom(true);
    return {
      node: d,
      tools: d.querySelector(".tools"),
      body: d.querySelector(".body"),
      cursor: d.querySelector(".cursor"),
      meta: d.querySelector(".meta"),
      text: "",
      toolSet: {},
      startedAt: performance.now(),
    };
  }

  function pushTool(ref, title) {
    if (ref.toolSet[title]) return;
    ref.toolSet[title] = true;
    ref.tools.hidden = false;
    var s = document.createElement("span");
    s.className = "tool active";
    s.innerHTML = '<span class="mini-dot"></span>' + escapeHtml(title);
    ref.tools.appendChild(s);
  }

  /* 模型偶尔会自己补一行空的「查询语句：」，展示层兜底裁掉 */
  function tidyAnswer(t) {
    if (!t) return t;
    var prev = null;
    while (prev !== t) {
      prev = t;
      t = t.replace(/\n*[`*_\s]*查询语句\s*[：:]?[`*_\s]*$/, "");
      t = t.replace(/\n*[`*_\s]*(SQL|查询 SQL)\s*[：:]?[`*_\s]*$/, "");
    }
    return t;
  }

  function finishBotMsg(ref, usage, errMsg) {
    var clean = tidyAnswer(ref.text);
    if (clean !== ref.text) {
      ref.text = clean;
      ref.body.innerHTML = renderMarkdown(ref.text);
    }
    ref.cursor.remove();
    if (errMsg) {
      var e = document.createElement("div");
      e.className = "err";
      e.textContent = errMsg;
      ref.body.parentElement.appendChild(e);
      if (!ref.text) ref.body.parentElement.style.display = "none";
      return;
    }
    var secs = ((performance.now() - ref.startedAt) / 1000).toFixed(1);
    var parts = ["耗时 " + secs + "s"];
    if (usage && usage.total_tokens) parts.push("tokens " + usage.total_tokens);
    var price = usage ? parseFloat(usage.total_price) : 0;
    if (price > 0) parts.push("¥" + price.toFixed(4));
    ref.meta.hidden = false;
    ref.meta.textContent = parts.join(" · ");
    Array.prototype.forEach.call(ref.tools.children, function (t) { t.classList.remove("active"); });
  }

  /* ---------------- 请假审批抽屉 ---------------- */
  var toastTimer = null;

  function toast(msg, isErr) {
    el.toast.textContent = msg;
    el.toast.classList.toggle("err", !!isErr);
    el.toast.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.classList.remove("on"); }, 3600);
  }

  function apiGet(url) {
    return fetch(url).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) throw new Error((d && (d.detail || d.msg)) || ("HTTP " + r.status));
        return d.data;
      });
    });
  }

  // 头像栏按钮：员工助手 + 有审批权限的角色才出现；管理员看全校待办
  function updateApproveEntry() {
    if (!el.approveBtn) return;
    var perm = state.perms && state.perms.approve;
    var onEmployee = state.agent && state.agent.key === "employee";
    el.approveBtn.hidden = !(perm && (onEmployee || perm === "all"));
    if (el.approveBtn.hidden) return;
    var scope = perm === "all" ? "&scope=all" : "";
    apiGet("/api/leave/summary?approver_id=" + approverId() + scope)
      .then(function (d) {
        if (d.pending > 0) {
          el.approveBadge.hidden = false;
          el.approveBadge.textContent = d.pending;
          el.approveBtn.title = (perm === "all" ? "全校还有 " : "还有 ") + d.pending + " 条请假待处理";
        } else {
          el.approveBadge.hidden = true;
          el.approveBtn.title = "暂无待审批的请假";
        }
      })
      .catch(function () { el.approveBadge.hidden = true; });
  }

  function openDrawer() {
    el.drawerMask.hidden = false;
    el.drawer.classList.add("on");
    loadApprovals();
  }

  function closeDrawer() {
    el.drawer.classList.remove("on");
    el.drawerMask.hidden = true;
  }

  function loadApprovals() {
    var uid = approverId();
    var scope = state.perms.approve === "all" ? "&scope=all" : "";
    el.drawerBody.innerHTML = '<div class="dr-empty">正在读取…</div>';
    Promise.all([
      apiGet("/api/leave/summary?approver_id=" + uid + scope),
      apiGet("/api/leave/pending?approver_id=" + uid + scope),
      apiGet("/api/leave/handled?approver_id=" + uid + "&limit=6" + scope),
      apiGet("/api/leave/teachers"),
    ])
      .then(function (res) { renderApprovals(res[0], res[1], res[2], res[3]); })
      .catch(function (e) {
        el.drawerSub.textContent = "读取失败";
        el.drawerBody.innerHTML = '<div class="dr-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function renderApprovals(sum, pending, handled, teachers) {
    if (sum.is_admin_view) {
      el.drawerSub.textContent = sum.approver_name + " · " + (sum.department || "") +
        " · 全校 " + sum.students.length + " 名学生（可代任何班主任审批）";
    } else if (sum.is_homeroom) {
      el.drawerSub.textContent = sum.approver_name + " · " + (sum.department || "") +
        " · 名下 " + sum.students.length + " 名学生";
    } else {
      el.drawerSub.textContent = sum.approver_name + " · 当前身份不是班主任";
    }

    var html = "";

    if (!sum.is_homeroom) {
      html += '<div class="dr-hint">这个身份名下没有学生，无法审批。切换成下面任意一位班主任再试：</div>';
      html += '<div class="teach-chips">';
      teachers.forEach(function (t) {
        html += '<button class="teach-chip" data-switch="' + t.id + '">' + escapeHtml(t.name) +
          (t.pending ? " · 待办 <b>" + t.pending + "</b>" : " · 无待办") + "</button>";
      });
      html += "</div>";
      el.drawerBody.innerHTML = html;
      return;
    }

    html += '<div class="dr-stats">' +
      '<div class="dr-stat"><b>' + sum.pending + '</b><span>待审批</span></div>' +
      '<div class="dr-stat"><b>' + sum.handled + '</b><span>已处理</span></div>' +
      '<div class="dr-stat"><b>' + sum.students.length + '</b><span>' +
        (sum.is_admin_view ? "全校学生" : "名下学生") + '</span></div>' +
      "</div>";

    html += '<p class="dr-label">待审批</p>';
    if (!pending.length) {
      html += '<div class="dr-empty">没有待审批的请假，<br>学生提交后会自动出现在这里。</div>';
    } else {
      pending.forEach(function (r) {
        html += '<div class="lv-card">' +
          '<div class="lv-top"><span class="lv-name">' + escapeHtml(r.student_name) + "</span>" +
            '<span class="lv-class">' + escapeHtml(r.student_class || "") + "</span></div>" +
          '<div class="lv-meta">' + escapeHtml(r.period_text || "") + "</div>" +
          '<div class="lv-reason">' + escapeHtml(r.reason || "（未填写事由）") + "</div>" +
          '<div class="lv-time">' +
            (sum.is_admin_view ? "班主任 " + escapeHtml(r.approver_name || "—") + " · " : "") +
            "提交于 " + escapeHtml(r.create_time_short || "—") + "</div>" +
          '<input class="lv-comment" data-comment="' + r.id + '" placeholder="审批意见（可选，学生查询时能看到）">' +
          '<div class="lv-actions">' +
            '<button class="ok" data-act="ok" data-id="' + r.id + '">通过</button>' +
            '<button class="no" data-act="no" data-id="' + r.id + '">驳回</button>' +
          "</div></div>";
      });
    }

    html += '<p class="dr-label">最近处理</p>';
    if (!handled.length) {
      html += '<div class="dr-empty">还没有处理记录。</div>';
    } else {
      handled.forEach(function (r) {
        var ok = r.status === "已通过";
        html += '<div class="lv-done">' +
          '<span class="pill ' + (ok ? "ok" : "no") + '">' + escapeHtml(r.status) + "</span>" +
          "<div><div class=\"who2\">" + escapeHtml(r.student_name) + " · " + escapeHtml(r.period_text || "") + "</div>" +
          '<div class="what">' + (r.approve_time_short ? escapeHtml(r.approve_time_short) + " 处理" : "") +
            (r.approve_comment ? " · " + escapeHtml(r.approve_comment) : "") + "</div></div></div>";
      });
    }

    el.drawerBody.innerHTML = html;
  }

  function decide(recordId, approved, comment) {
    Array.prototype.forEach.call(
      el.drawerBody.querySelectorAll("button[data-act]"),
      function (b) { b.disabled = true; }
    );
    fetch("/api/leave/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token() },
      body: JSON.stringify({
        record_id: recordId,
        approver_id: state.user ? state.user.id : Number(state.userId),
        approved: approved,
        comment: comment || "",
      }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg + "，学生再查请假就能看到你和审批意见");
        loadApprovals();
        updateApproveEntry();
      })
      .catch(function (e) {
        toast("审批失败：" + (e.message || e), true);
        loadApprovals();
      });
  }

  if (el.approveBtn) el.approveBtn.addEventListener("click", openDrawer);
  el.drawerClose.addEventListener("click", closeDrawer);
  el.drawerMask.addEventListener("click", closeDrawer);

  el.drawerBody.addEventListener("click", function (ev) {
    var sw = ev.target.closest("[data-switch]");
    if (sw) {
      closeDrawer();
      el.userSelect.value = sw.getAttribute("data-switch");
      el.userSelect.dispatchEvent(new Event("change"));
      setTimeout(openDrawer, 260);
      return;
    }
    var btn = ev.target.closest("button[data-act]");
    if (!btn) return;
    var card = btn.closest(".lv-card");
    var input = card ? card.querySelector(".lv-comment") : null;
    decide(Number(btn.getAttribute("data-id")), btn.getAttribute("data-act") === "ok", input ? input.value.trim() : "");
  });

  /* ---------------- 我的工作台：按身份只取自己权限内的数据 ---------------- */
  var WS_LABEL = { admin: "数据总览", teacher: "我的班级", staff: "客户线索", student: "我的学业" };

  function wsHeaders() {
    var h = { "Content-Type": "application/json" };
    var t = token();
    if (t) h.Authorization = "Bearer " + t;
    return h;
  }

  function wsGet(url) {
    return fetch(url, { headers: wsHeaders() }).then(function (r) {
      return r.json().then(function (d) {
        if (!r.ok) throw new Error((d && (d.detail || d.msg)) || ("HTTP " + r.status));
        return d.data;
      });
    });
  }

  function pillClass(st) {
    if (/已签约|已通过|已解决|优秀/.test(st)) return "ok";
    if (/流失|驳回/.test(st)) return "no";
    return "wait";
  }

  /* 后端错误：detail 可能是字符串，也可能是 {msg, alternatives} 对象 */
  function detailText(d) {
    if (!d) return "";
    if (typeof d === "string") return d;
    if (typeof d.detail === "string") return d.detail;
    if (d.detail && d.detail.msg) return d.detail.msg;
    if (typeof d.message === "string") return d.message;
    return "";
  }

  /* ---- 各类型条目 ---- */
  function wsLeadItem(it, canFollow, statuses) {
    var h = '<div class="ws-item">' +
      '<div class="ws-item-h"><b>' + escapeHtml(it.name) + "</b>" +
      '<span class="pill ' + pillClass(it.status) + '">' + escapeHtml(it.status) + "</span>" +
      (it.source === "在线客服" ? '<span class="ws-tag src">在线客服留资</span>' : "") +
      '<span class="ws-meta">' + escapeHtml(it.owner) + " · " + escapeHtml(it.time) + "</span></div>" +
      '<div class="ws-item-h" style="margin-top:5px"><span class="ws-phone">' + escapeHtml(it.phone) + "</span>" +
      '<span class="ws-meta">' + escapeHtml(it.brief) + "</span></div>";

    if (canFollow) {
      h += '<div class="ws-follow" data-lead="' + it.id + '"><select class="st">' +
        statuses.map(function (st) {
          return '<option value="' + escapeHtml(st) + '"' + (st === it.status ? " selected" : "") + ">" + escapeHtml(st) + "</option>";
        }).join("") + "</select>" +
        '<input class="note" placeholder="写一条跟进，回车保存">' +
        '<button class="save">保存</button></div>';
    }
    if (it.history) {
      h += '<details class="ws-details"><summary>跟进记录</summary><pre>' + escapeHtml(it.history) + "</pre></details>";
    }
    return h + "</div>";
  }

  function wsLeaveItem(it, canAct) {
    var h = '<div class="ws-item"><div class="ws-item-h"><b>' + escapeHtml(it.student) + "</b>" +
      '<span class="pill ' + pillClass(it.status) + '">' + escapeHtml(it.status) + "</span>" +
      '<span class="ws-meta">' + escapeHtml(it.period) + " · " + it.days + " 天</span></div>" +
      '<div class="ws-brief">' + escapeHtml(it.reason) + "</div>";
    if (canAct && it.status === "待审批") {
      h += '<div class="ws-acts" data-leave="' + it.id + '">' +
        '<button class="ok">通过</button><button class="no">驳回</button></div>';
    }
    return h + "</div>";
  }

  function wsStudentItem(it) {
    var warn = it.avg !== null && it.avg < 75;
    return '<div class="ws-item"><div class="ws-item-h"><b>' + escapeHtml(it.name) + "</b>" +
      '<span class="ws-meta">' + escapeHtml(it.dept) + "</span></div>" +
      '<div class="ws-split" style="margin-top:6px"><span class="ws-score">' +
      '<span class="num' + (warn ? " warn" : "") + '">' + (it.avg === null ? "—" : it.avg) + "</span>" +
      '<span class="ws-meta">均分 · ' + escapeHtml(it.level) + "</span></span>" +
      '<span class="grow"></span>' +
      (it.pending ? '<span class="ws-tag">待批请假 ' + it.pending + "</span>" : "") +
      (it.low ? '<span class="ws-tag" style="background:#fff3e4;color:#b45309">不及格 ' + it.low + "</span>" : "") +
      "</div></div>";
  }

  function wsScoreItem(it) {
    var warn = it.score !== null && it.score < 75;
    return '<div class="ws-item"><div class="ws-split"><span class="grow">' +
      '<b style="font-size:13px">' + escapeHtml(it.course) + "</b>" +
      '<div class="ws-meta" style="margin-top:3px">' + escapeHtml(it.semester) + "</div></span>" +
      '<span class="ws-score"><span class="num' + (warn ? " warn" : "") + '">' + it.score + "</span>" +
      '<span class="ws-meta">' + escapeHtml(it.level) + "</span></span></div></div>";
  }

  function wsTicketItem(it) {
    return '<div class="ws-item"><div class="ws-item-h"><b>' + escapeHtml(it.content) + "</b></div>" +
      '<div class="ws-item-h" style="margin-top:5px">' +
      '<span class="pill ' + pillClass(it.status) + '">' + escapeHtml(it.status) + "</span>" +
      '<span class="ws-meta">' + escapeHtml(it.student) + " · " + escapeHtml(it.time) + "</span></div></div>";
  }

  /* 左栏只放入口：每个身份能做什么，这里就是全部清单 */
  var NAV_ITEMS = {
    teacher: [
      { key: "leaves", icon: "🗓", title: "待处理请假", sub: "只批自己名下学生" },
      { key: "grades", icon: "📊", title: "成绩录入", sub: "只给名下学生录 / 改" },
    ],
    admin: [
      { key: "grades", icon: "📊", title: "成绩总览", sub: "全校成绩，只读" },
      { key: "accounts", icon: "👥", title: "账户管理", sub: "开账户 · 停用 / 启用 / 删除" },
    ],
    student: [
      { key: "leaves", icon: "🗓", title: "请假记录", sub: "查看批没批、审批意见" },
      { key: "grades", icon: "📊", title: "我的成绩", sub: "只看自己的课程" },
    ],
    staff: [
      { key: "leads", icon: "📇", title: "客户线索", sub: "写跟进、改状态" },
      { key: "activities", icon: "🎪", title: "活动安排", sub: "设计活动 · 看谁报名了" },
      { key: "accounts", icon: "👥", title: "账户管理", sub: "只开自己名下的学员" },
    ],
  };

  function navItem(role, key) {
    return (NAV_ITEMS[role] || []).filter(function (x) { return x.key === key; })[0] || null;
  }

  function navList(d) {
    var cards = d.cards || [];
    function cardValue(label) {
      var hit = cards.filter(function (c) { return c.label === label; })[0];
      return hit && typeof hit.value === "number" ? hit.value : null;
    }
    var items = (NAV_ITEMS[d.role] || []).map(function (it) {
      var n = 0;
      if (it.key === "leaves") {
        // 待批数优先取概览卡（管理员概览里的明细只取前 6 条，不能拿来当角标）
        var v = cardValue("待批请假");
        n = v !== null ? v : ((d.sections || []).filter(function (x) { return x.kind === "leave"; })[0] || { items: [] }).items
          .filter(function (r) { return r.status === "待审批"; }).length;
      } else if (it.key === "leads") {
        var ls = (d.sections || []).filter(function (x) { return x.kind === "lead"; })[0];
        n = ((ls ? ls.items : []) || []).filter(function (r) { return r.status !== "已流失"; }).length;
      }
      return { key: it.key, icon: it.icon, title: it.title, sub: it.sub, count: n };
    });
    items.push({
      key: "logs", icon: "▤", title: "我的日志",
      sub: "今日 " + (d.today_logs || 0) + " 条 · 只有自己能看", count: 0,
    });
    return items;
  }

  function renderNavs(d) {
    if (!d) return;
    el.navBlock.hidden = false;
    el.navs.innerHTML = navList(d).map(function (it) {
      return '<button class="nav' + (state.panelKey === it.key ? " on" : "") +
        '" data-key="' + it.key + '" type="button">' +
        '<span class="ic">' + it.icon + "</span>" +
        '<span class="nb"><b>' + it.title + "</b><span>" + it.sub + "</span></span>" +
        (it.count > 0 ? '<i class="nav-badge">' + (it.count > 99 ? "99+" : it.count) + "</i>" : "") +
        "</button>";
    }).join("");
  }

  function renderWsBadge(d) {
    var n = 0;
    if (d.role === "teacher" || d.role === "staff") n = (d.cards[1] && d.cards[1].value) || 0;
    else if (d.role === "student") n = (d.cards[2] && d.cards[2].value) || 0;
    if (n > 0) { el.wsBadge.hidden = false; el.wsBadge.textContent = n; }
    else el.wsBadge.hidden = true;
  }

  function loadWs() {
    return wsGet("/api/workspace")
      .then(function (d) {
        state.ws = d;
        renderWsBadge(d);
        renderNavs(d);
        if (state.panelKey && state.panelKey !== "logs" &&
            state.panelKey !== "accounts" && state.panelKey !== "activities") renderPanel();

        return d;
      })
      .catch(function (e) {
        if (state.panelKey === "logs") return;
        el.panelSub.textContent = "读取失败";
        if (state.panelKey) el.panelBody.innerHTML = '<div class="ws-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function logRowsHtml(rows) {
    return rows.map(function (r) {
      var cls = /失败|驳回/.test(r.result) ? "no" : "ok";
      return '<div class="ws-item"><div class="ws-item-h"><b>' + escapeHtml(r.action_label) + "</b>" +
        '<span class="pill ' + cls + '">' + escapeHtml(r.result) + "</span>" +
        '<span class="ws-meta">' + escapeHtml(r.time_short) + "</span></div>" +
        '<div class="ws-brief">' + escapeHtml(r.summary) + "</div>" +
        (r.detail ? '<div class="ws-meta ws-logdet">' + escapeHtml(r.detail) + "</div>" : "") +
        "</div>";
    }).join("");
  }

  function loadLogsInto(box, setSub) {
    box.innerHTML = '<div class="ws-empty">正在读取…</div>';
    wsGet("/api/my/logs?limit=80")
      .then(function (d) {
        var rows = d.rows || [];
        var t = d.today || {};
        var LAB = { leave_apply: "提交请假", leave_approve: "审批", leave_delete: "删请假", score_save: "录成绩", score_delete: "删成绩", lead_follow: "跟进", lead_status: "线索状态", lead_create: "留资", chat: "问小粤同学", leave_query: "查进度" };
        var mix = Object.keys(t.by_action || {}).map(function (k) {
          return (LAB[k] || k) + " " + t.by_action[k];
        }).join(" · ");
        setSub("今天 " + (t.total || 0) + " 条" + (mix ? "（" + mix + "）" : "") + " · 只有你自己能看到");
        box.innerHTML = rows.length
          ? '<div class="ws-list">' + logRowsHtml(rows) + "</div>"
          : '<div class="ws-empty">还没有操作记录。审批、跟进、提交请假、咨询小粤同学都会记在这里。</div>';
      })
      .catch(function (e) {
        setSub("读取失败");
        box.innerHTML = '<div class="ws-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function renderPanel() {
    if (!state.panelKey) return;
    if (state.panelKey === "logs") {
      el.panelTitle.textContent = "我的日志";
      el.panelSub.textContent = "读取中…";
      loadLogsInto(el.panelBody, function (txt) { el.panelSub.textContent = txt; });
      return;
    }
    if (state.panelKey === "grades") { renderGradesPanel(); return; }
    if (state.panelKey === "accounts") { renderAccountsPanel(); return; }
    if (state.panelKey === "activities") { renderActivitiesPanel(); return; }
    var d = state.ws;
    if (!d) { el.panelBody.innerHTML = '<div class="ws-empty">正在读取…</div>'; return; }
    var kind = state.panelKey === "leads" ? "lead" : "leave";
    var sec = (d.sections || []).filter(function (x) { return x.kind === kind; })[0];
    var base = navItem(d.role, state.panelKey);
    el.panelTitle.textContent = base ? base.title : "我的事项";
    if (!sec) { el.panelBody.innerHTML = '<div class="ws-empty">这里暂时没有内容</div>'; return; }
    el.panelSub.textContent = sec.hint || "";
    if (!sec.items.length) {
      el.panelBody.innerHTML = '<div class="ws-empty">暂时没有需要处理的事项</div>';
      return;
    }
    var html = '<div class="ws-list">';
    sec.items.forEach(function (it) {
      if (sec.kind === "lead") html += wsLeadItem(it, !!d.can_follow, d.lead_statuses || []);
      else html += wsLeaveItem(it, d.role === "teacher" || d.role === "admin");
    });
    el.panelBody.innerHTML = html + "</div>";
  }

  /* ---------------- 成绩：老师只看到自己学生，学生只看到自己 ---------------- */
  function gradeRow(s, canEdit) {
    var scores = s.scores || [];
    var avgText = s.count ? "均分 " + (s.avg === null ? "—" : s.avg) : "暂无成绩";
    var h = '<div class="ws-item"><div class="ws-item-h"><b>' + escapeHtml(s.name) + "</b>" +
      '<span class="pill ' + (s.count ? pillClass(s.level) : "wait") + '">' + avgText + "</span>" +
      (s.failed ? '<span class="ws-tag" style="background:#fff3e4;color:#b45309">不及格 ' + s.failed + "</span>" : "") +
      '<span class="ws-meta">' + escapeHtml(s.dept) +
      (s.teacher && s.teacher !== "—" ? " · 班主任 " + escapeHtml(s.teacher) : "") + "</span></div>";

    if (scores.length) {
      h += '<div class="g-rows">' + scores.map(function (x) {
        return '<div class="g-row" data-score-id="' + x.id + '">' +
          '<span class="g-course">' + escapeHtml(x.course) + "</span>" +
          '<span class="g-sem">' + escapeHtml(x.semester) + "</span>" +
          '<span class="g-score' + (x.level === "待提升" ? " warn" : "") + '">' + x.score + "</span>" +
          (canEdit ? '<button type="button" class="g-edit" data-score="' + x.id +
            '" data-value="' + x.score + '" title="修改这条成绩">改</button>' : "") +
          (canEdit ? '<button type="button" class="g-del" data-score="' + x.id + '" title="删除这条成绩">✕</button>' : "") +
          "</div>";
      }).join("") + "</div>";
    } else {
      h += '<div class="ws-brief">还没有成绩记录' + (canEdit ? "，用下面的表单录一条" : "") + "。</div>";
    }

    if (canEdit) {
      h += '<form class="g-form" data-student="' + s.id + '">' +
        '<input name="course" placeholder="课程名，如 学术英语" maxlength="30">' +
        '<input name="score" placeholder="分数" inputmode="decimal" maxlength="6">' +
        '<input name="semester" placeholder="学期（可空）" maxlength="30">' +
        "<button type=\"submit\">录入</button></form>";
    }
    return h + "</div>";
  }

  function renderGradesPanel() {
    var base = navItem(state.user && state.user.role, "grades") || {};
    el.panelTitle.textContent = base.title || "成绩";
    el.panelSub.textContent = "读取中…";
    el.panelBody.innerHTML = '<div class="ws-empty">正在读取…</div>';
    wsGet("/api/grades")
      .then(function (d) {
        var rows = d.rows || [];
        var sum = d.summary || {};
        el.panelSub.textContent = (d.note || "") +
          (sum.avg !== null && sum.avg !== undefined ? " · 均分 " + sum.avg : "") +
          (sum.missing ? " · " + sum.missing + " 人还没录成绩" : "");
        if (!rows.length) {
          el.panelBody.innerHTML = '<div class="ws-empty">这里暂时没有学生</div>';
          return;
        }
        el.panelBody.innerHTML = '<div class="ws-list">' +
          rows.map(function (s) { return gradeRow(s, !!d.can_edit); }).join("") + "</div>";
      })
      .catch(function (e) {
        el.panelSub.textContent = "读取失败";
        el.panelBody.innerHTML = '<div class="ws-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function saveGrade(form) {
    var sid = Number(form.getAttribute("data-student"));
    var course = (form.querySelector('[name="course"]').value || "").trim();
    var raw = (form.querySelector('[name="score"]').value || "").trim();
    var sem = (form.querySelector('[name="semester"]').value || "").trim();
    if (!course) { toast("先填课程名", true); return; }
    if (raw === "" || isNaN(Number(raw))) { toast("分数要填数字", true); return; }

    var btn = form.querySelector("button");
    btn.disabled = true;
    fetch("/api/grades", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify({ student_id: sid, course_name: course, score: Number(raw), semester: sem || null }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已保存");
        renderGradesPanel();
        loadWs();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast("保存失败：" + (e.message || e), true);
      });
  }

  function deleteGrade(scoreId, btn) {
    if (!window.confirm("删除这条成绩？操作会记进日志，但成绩本身不能恢复。")) return;
    btn.disabled = true;
    fetch("/api/grades/" + scoreId, { method: "DELETE", headers: wsHeaders() })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已删除");
        renderGradesPanel();
        loadWs();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast("删除失败：" + (e.message || e), true);
      });
  }

  function startScoreEdit(btn) {
    var row = btn.closest(".g-row");
    if (!row) return;
    var id = btn.getAttribute("data-score");
    var val = btn.getAttribute("data-value");
    var course = row.querySelector(".g-course").textContent;
    row.classList.add("editing");
    row.innerHTML =
      '<span class="g-course">' + escapeHtml(course) + "</span>" +
      '<input class="g-input" type="text" inputmode="decimal" value="' + escapeHtml(val) + '">' +
      '<button type="button" class="g-save" data-score="' + id + '">存</button>' +
      '<button type="button" class="g-cancel">取消</button>';
    var input = row.querySelector(".g-input");
    input.focus();
    input.select();
  }

  function saveScoreEdit(btn) {
    if (btn.disabled) return;
    var row = btn.closest(".g-row");
    var input = row && row.querySelector(".g-input");
    if (!input) return;
    var raw = (input.value || "").trim();
    if (raw === "" || isNaN(Number(raw))) { toast("分数要填数字", true); return; }
    var v = Number(raw);
    if (v < 0 || v > 150) { toast("分数需在 0~150 之间", true); return; }

    btn.disabled = true;
    fetch("/api/grades/" + btn.getAttribute("data-score"), {
      method: "PUT",
      headers: wsHeaders(),
      body: JSON.stringify({ score: v }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已修改");
        renderGradesPanel();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast("修改失败：" + (e.message || e), true);
      });
  }

  /* ---------------- 活动安排：设计活动，看谁报名了 ---------------- */
  var actOpen = {};

  function actFormHtml() {
    return '<form class="acct-form act-form" data-kind="activity">' +
      '<input class="f-title" name="title" placeholder="活动名称：如 新加坡本科分享会" maxlength="40">' +
      '<select name="category" title="活动类型"><option>线下分享会</option>' +
      '<option>线上说明会</option><option>线下沙龙</option><option>校区开放日</option></select>' +
      '<input name="speaker" placeholder="主讲老师" maxlength="40">' +
      '<input name="start_time" type="datetime-local" title="活动时间">' +
      '<div class="act-cap"><i>名额</i><input name="capacity" type="number" min="1" max="500" value="30" title="名额"></div>' +
      '<input name="location" placeholder="地点 / 线上会议号" maxlength="60">' +
      '<button type="submit">发布活动</button>' +
      '<input class="f-desc" name="description" placeholder="活动简介：讲什么、适合谁（可空）" maxlength="120">' +
      "</form>" +
      '<div class="acct-hint">发布后，登录页的小粤同学会按时间顺序推荐这场活动；' +
      "名额报满会自动改推其它场次，报名人同时进你的客户线索。</div>";
  }

  function actPeopleHtml(rows) {
    if (!rows || !rows.length) return '<div class="act-empty">还没有人报名</div>';
    return '<div class="act-people">' + rows.map(function (s) {
      return '<div class="act-person"><b>' + escapeHtml(s.name) + "</b>" +
        (s.lead_status ? '<span class="pill ' + pillClass(s.lead_status) + '">' +
          escapeHtml(s.lead_status) + "</span>" : "") +
        '<span class="act-phone">' + escapeHtml(s.phone) + "</span>" +
        (s.remark ? '<span class="act-note">' + escapeHtml(s.remark) + "</span>" : "") +
        '<span class="act-time">' + escapeHtml(s.time) + "</span></div>";
    }).join("") + "</div>";
  }

  function actItemHtml(a) {
    var pct = a.capacity ? Math.min(100, Math.round(a.signed / a.capacity * 100)) : 0;
    var closed = a.status !== "开放报名";
    var stateText = closed ? "已结束" : (a.full ? "已满" : "报名中");
    var stateCls = closed ? "no" : (a.full ? "wait" : "ok");
    var open = !!actOpen[a.id];
    return '<div class="ws-item act-item" data-act-id="' + a.id + '">' +
      '<div class="ws-item-h"><b>' + escapeHtml(a.title) + "</b>" +
      '<span class="pill ' + stateCls + '">' + stateText + "</span>" +
      '<span class="ws-tag">' + escapeHtml(a.category) + "</span>" +
      '<span class="ws-meta">' + escapeHtml(a.start) + " · " + escapeHtml(a.speaker) +
      " · " + escapeHtml(a.location) +
      (a.created_by_name && a.created_by_name !== "—" ? " · 创建 " + escapeHtml(a.created_by_name) : "") +
      "</span></div>" +
      (a.description ? '<div class="ws-brief">' + escapeHtml(a.description) + "</div>" : "") +
      '<div class="act-bar"><i class="' + (a.full ? "full" : "") + '" style="width:' + pct + '%"></i></div>' +
      '<div class="act-line"><span>已报名 <b>' + a.signed + "</b> / " + a.capacity +
      " 人 · 余 " + a.remaining + " 个名额</span>" +
      '<button type="button" class="act-toggle" data-act="toggle">' +
      (open ? "收起参与人员" : "参与人员 " + a.signed) + "</button></div>" +
      (open ? actPeopleHtml(a.signups) : "") +
      '<div class="acct-acts">' +
      (closed ? '<button type="button" data-act="reopen">恢复报名</button>'
              : '<button type="button" data-act="close">结束报名</button>') +
      '<button type="button" class="danger" data-act="del">删除</button>' +
      "</div></div>";
  }

  function renderActivitiesPanel() {
    var base = navItem(state.user && state.user.role, "activities") || {};
    var keepTop = el.panelBody.scrollTop;
    el.panelTitle.textContent = base.title || "活动安排";
    el.panelSub.textContent = "读取中…";
    el.panelBody.innerHTML = '<div class="ws-empty">正在读取…</div>';
    wsGet("/api/activities")
      .then(function (d) {
        var rows = d.rows || [];
        var people = rows.reduce(function (n, a) { return n + (a.signed || 0); }, 0);
        el.panelSub.textContent = "共 " + rows.length + " 场活动 · " + people +
          " 人报名 · 只显示自己设计的活动";
        el.panelBody.innerHTML = actFormHtml() +
          (rows.length
            ? '<div class="ws-list">' + rows.map(actItemHtml).join("") + "</div>"
            : '<div class="ws-empty">还没有活动，用上面的表单发一场。</div>');
        el.panelBody.scrollTop = keepTop;
      })
      .catch(function (e) {
        el.panelSub.textContent = "读取失败";
        el.panelBody.innerHTML = '<div class="ws-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function createActivity(form) {
    if (form.getAttribute("data-busy") === "1") return;
    function val(n) {
      var box = form.querySelector('[name="' + n + '"]');
      return box ? (box.value || "").trim() : "";
    }
    var body = {
      title: val("title"),
      category: val("category"),
      speaker: val("speaker"),
      start_time: val("start_time"),
      location: val("location"),
      capacity: Number(val("capacity") || 0),
      description: val("description"),
    };
    if (!body.title) { toast("请填活动名称", true); return; }
    if (!body.start_time) { toast("请选择活动时间", true); return; }
    if (!body.capacity || body.capacity < 1) { toast("名额至少 1 人", true); return; }

    form.setAttribute("data-busy", "1");
    var btn = form.querySelector("button");
    btn.disabled = true;
    fetch("/api/activities", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify(body),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(detailText(d) || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "活动已发布");
        actOpen = {};
        renderActivitiesPanel();
      })
      .catch(function (e) {
        form.setAttribute("data-busy", "0");
        btn.disabled = false;
        toast("发布失败：" + (e.message || e), true);
      });
  }

  function handleActAction(btn) {
    var item = btn.closest(".act-item");
    if (!item) return;
    var id = item.getAttribute("data-act-id");
    var act = btn.getAttribute("data-act");

    if (act === "toggle") {
      actOpen[id] = !actOpen[id];
      renderActivitiesPanel();
      return;
    }
    if (btn.disabled) return;

    if (act === "del") {
      if (!window.confirm("删除这场活动？已经有人报名的活动不能删，可以改成结束报名。")) return;
      btn.disabled = true;
      fetch("/api/activities/" + id, { method: "DELETE", headers: wsHeaders() })
        .then(function (r) {
          return r.json().then(function (d) {
            if (!r.ok) throw new Error(detailText(d) || ("HTTP " + r.status));
            return d;
          });
        })
        .then(function (d) {
          toast(d.msg || "活动已删除");
          delete actOpen[id];
          renderActivitiesPanel();
        })
        .catch(function (e) {
          btn.disabled = false;
          toast(e.message || "删除失败", true);
        });
      return;
    }

    btn.disabled = true;
    fetch("/api/activities/" + id + "/status", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify({ action: act === "close" ? "close" : "open" }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(detailText(d) || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已更新");
        renderActivitiesPanel();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast(e.message || "操作失败", true);
      });
  }

  /* ---------------- 账户管理 ---------------- */
  function acctFormHtml(d) {
    var can = d.can_create || [];
    var teachers = d.teachers || [];
    if (can.indexOf("student") >= 0) {
      var opts = teachers.map(function (t) {
        return '<option value="' + t.id + '">' + escapeHtml(t.name) +
          "（名下 " + t.students + " 人）</option>";
      }).join("");
      return '<form class="acct-form" data-kind="student">' +
        '<input name="real_name" placeholder="学员姓名" maxlength="20">' +
        '<input name="username" placeholder="登录账号" maxlength="20">' +
        '<input name="department" placeholder="方向 / 班级（可空）" maxlength="40">' +
        '<select name="homeroom_teacher_id" title="选择班主任">' +
        (opts || '<option value="">暂无班主任</option>') + "</select>" +
        '<input name="contact" placeholder="手机号（可空）" maxlength="20">' +
        '<button type="submit">开账户</button></form>' +
        '<div class="acct-hint">账号需字母开头（3~20 位），初始密码 123456。' +
        "点「班主任」下拉选人，这位学员的请假和成绩就归该老师处理。</div>";
    }
    return '<form class="acct-form" data-kind="employee">' +
      '<select name="role" title="账户身份">' +
      '<option value="teacher">班主任</option><option value="staff">顾问</option></select>' +
      '<input name="real_name" placeholder="姓名，如 周老师 / 周顾问" maxlength="20">' +
      '<input name="username" placeholder="登录账号" maxlength="20">' +
      '<input name="department" placeholder="部门 / 方向（可空）" maxlength="40">' +
      '<input name="contact" placeholder="手机号（可空）" maxlength="20">' +
      '<button type="submit">开账户</button></form>' +
      '<div class="acct-hint">新账户初始密码 123456。姓名统一写「姓+老师 / 姓+顾问」（如 周老师、周顾问），' +
      "登录页的账号卡片才整齐。班主任只带自己名下学生，顾问只带自己的线索；学员账户由顾问开。</div>";
  }

  function acctListHtml(d) {
    var rows = d.rows || [];
    if (!rows.length) return '<div class="ws-empty">还没有账户，用上面的表单开一个。</div>';
    return '<div class="ws-list">' + rows.map(function (a) {
      return '<div class="ws-item"><div class="ws-item-h">' +
        "<b>" + escapeHtml(a.name) + "</b>" +
        '<span class="pill ' + (a.disabled ? "no" : "ok") + '">' +
        (a.disabled ? "已停用" : "正常") + "</span>" +
        '<span class="ws-tag">' + escapeHtml(a.role_label) + "</span>" +
        '<span class="ws-meta">' + escapeHtml(a.username) + "</span>" +
        (a.students ? '<span class="ws-meta">名下 ' + a.students + " 人</span>" : "") +
        "</div>" +
        '<div class="ws-brief">' + escapeHtml(a.dept) +
        (a.teacher ? " · 班主任 " + escapeHtml(a.teacher) : "") +
        (a.contact ? " · " + escapeHtml(a.contact) : "") + "</div>" +
        '<div class="acct-acts">' +
        (d.can_toggle ? '<button type="button" data-act="' + (a.disabled ? "enable" : "disable") +
          '" data-id="' + a.id + '">' + (a.disabled ? "启用" : "停用") + "</button>" : "") +
        (d.can_delete ? '<button type="button" class="danger" data-act="delete" data-id="' + a.id +
          '">删除</button>' : "") +
        "</div></div>";
    }).join("") + "</div>";
  }

  function renderAccountsPanel() {
    var base = navItem(state.user && state.user.role, "accounts") || {};
    el.panelTitle.textContent = base.title || "账户管理";
    el.panelSub.textContent = "读取中…";
    el.panelBody.innerHTML = '<div class="ws-empty">正在读取…</div>';
    wsGet("/api/accounts")
      .then(function (d) {
        var rows = d.rows || [];
        var st = d.stats || {};
        el.panelSub.textContent = (d.note || "") + " · 共 " + rows.length + " 个账户" +
          (st.disabled ? " · " + st.disabled + " 个已停用" : "");
        el.panelBody.innerHTML = acctFormHtml(d) + acctListHtml(d);
      })
      .catch(function (e) {
        el.panelSub.textContent = "读取失败";
        el.panelBody.innerHTML = '<div class="ws-empty">' + escapeHtml(e.message || String(e)) + "</div>";
      });
  }

  function createAccount(form) {
    if (form.getAttribute("data-busy") === "1") return;
    form.setAttribute("data-busy", "1");
    var kind = form.getAttribute("data-kind");
    function val(n) {
      var box = form.querySelector('[name="' + n + '"]');
      return box ? (box.value || "").trim() : "";
    }
    var body = {
      role: kind === "student" ? "student" : val("role"),
      real_name: val("real_name"),
      username: val("username"),
      department: val("department"),
      contact: val("contact"),
    };
    if (kind === "student") {
      if (!val("homeroom_teacher_id")) { toast("请先选班主任", true); return; }
      body.homeroom_teacher_id = Number(val("homeroom_teacher_id"));
    }
    if (!body.real_name) { toast("请填姓名", true); return; }
    if (!body.username) { toast("请填登录账号", true); return; }

    var btn = form.querySelector("button");
    btn.disabled = true;
    fetch("/api/accounts", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify(body),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已开户");
        renderAccountsPanel();
      })
      .catch(function (e) {
        form.setAttribute("data-busy", "0");
        btn.disabled = false;
        toast("开户失败：" + (e.message || e), true);
      });
  }

  function toggleAccount(id, act, btn) {
    if (btn.disabled) return;
    var word = act === "disable" ? "停用" : "启用";
    if (act === "disable" && !window.confirm("停用后该账号将无法登录，需要在这里重新启用。确定？")) return;
    btn.disabled = true;
    fetch("/api/accounts/" + id + "/status", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify({ action: act }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || ("已" + word));
        renderAccountsPanel();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast(word + "失败：" + (e.message || e), true);
      });
  }

  function removeAccount(id, name, btn) {
    if (btn.disabled) return;
    if (!window.confirm("删除账户「" + name + "」后，该账号将无法登录（历史请假 / 成绩 / 日志保留）。确定删除？")) return;
    btn.disabled = true;
    fetch("/api/accounts/" + id, { method: "DELETE", headers: wsHeaders() })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已删除");
        renderAccountsPanel();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast("删除失败：" + (e.message || e), true);
      });
  }

  function openPanel(key) {
    if (!state.user) return;
    state.panelKey = key;
    el.panel.hidden = false;
    el.chat.hidden = true;
    el.composer.hidden = true;
    renderNavs(state.ws);
    renderPanel();
    if (state.panelKey !== "logs" && state.panelKey !== "grades" &&
        state.panelKey !== "accounts" && state.panelKey !== "activities") loadWs();
  }

  function closePanel() {
    state.panelKey = null;
    el.panel.hidden = true;
    el.chat.hidden = false;
    el.composer.hidden = false;
    renderNavs(state.ws);
    el.input.focus();
  }

  function initWs() {
    if (!state.user) return;
    el.wsBtn.hidden = false;
    el.navBlock.hidden = false;
    el.wsLabel.textContent = WS_LABEL[state.user.role] || "我的工作台";
    el.wsBtn.title = state.user.role_desc || "";
    loadWs();
  }

  function saveLead(box) {
    var id = box.getAttribute("data-lead");
    var sel = box.querySelector("select");
    var note = box.querySelector("input");
    var btn = box.querySelector("button");
    btn.disabled = true;
    fetch("/api/workspace/lead/" + id + "/follow", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify({ note: note.value.trim(), status: sel.value }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已保存");
        loadWs();
      })
      .catch(function (e) {
        btn.disabled = false;
        toast("保存失败：" + (e.message || e), true);
      });
  }

  function decideLeave(id, approved, btn) {
    var box = btn.parentNode;
    Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) { b.disabled = true; });
    fetch("/api/leave/approve", {
      method: "POST",
      headers: wsHeaders(),
      body: JSON.stringify({
        record_id: Number(id),
        approver_id: state.user ? state.user.id : 0,
        approved: approved,
        comment: "",
      }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        toast(d.msg || "已处理");
        loadWs();
        updateApproveEntry();
      })
      .catch(function (e) {
        Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) { b.disabled = false; });
        toast("审批失败：" + (e.message || e), true);
      });
  }

  function panelClickHandler(ev) {
    var edit = ev.target.closest(".g-edit");
    if (edit) { startScoreEdit(edit); return; }
    var save = ev.target.closest(".g-save");
    if (save) { saveScoreEdit(save); return; }
    var cancel = ev.target.closest(".g-cancel");
    if (cancel) { renderGradesPanel(); return; }
    var del = ev.target.closest(".g-del");
    if (del) { deleteGrade(del.getAttribute("data-score"), del); return; }
    var actBtn = ev.target.closest(".act-item [data-act]");
    if (actBtn) { handleActAction(actBtn); return; }
    var acct = ev.target.closest(".acct-acts button");
    if (acct) {
      var aid = acct.getAttribute("data-id");
      var aact = acct.getAttribute("data-act");
      if (aact === "delete") removeAccount(aid, acct.closest(".ws-item").querySelector("b").textContent, acct);
      else toggleAccount(aid, aact, acct);
      return;
    }
    var saveLeadBtn = ev.target.closest(".ws-follow .save");
    if (saveLeadBtn) { saveLead(saveLeadBtn.closest(".ws-follow")); return; }
    var act = ev.target.closest(".ws-acts button");
    if (act && act.parentNode.getAttribute("data-leave")) {
      decideLeave(act.parentNode.getAttribute("data-leave"), act.className === "ok", act);
    }
  }

  el.navs.addEventListener("click", function (ev) {
    var n = ev.target.closest(".nav");
    if (!n) return;
    var key = n.getAttribute("data-key");
    if (state.panelKey === key) { closePanel(); return; }
    openPanel(key);
  });

  el.panelBack.addEventListener("click", closePanel);
  el.panelBody.addEventListener("click", panelClickHandler);
  el.panelBody.addEventListener("submit", function (ev) {
    var acct = ev.target.closest(".acct-form");
    if (acct) {
      ev.preventDefault();
      if (acct.getAttribute("data-kind") === "activity") createActivity(acct);
      else createAccount(acct);
      return;
    }
    var form = ev.target.closest(".g-form");
    if (!form) return;
    ev.preventDefault();
    saveGrade(form);
  });
  el.panelBody.addEventListener("keydown", function (ev) {
    if (ev.key !== "Enter") return;
    var score = ev.target.closest(".g-input");
    if (score) {
      ev.preventDefault();
      var btn = score.closest(".g-row").querySelector(".g-save");
      if (btn) saveScoreEdit(btn);
      return;
    }
    var note = ev.target.closest(".ws-follow .note");
    if (!note) return;
    ev.preventDefault();
    saveLead(note.closest(".ws-follow"));
  });

  // 窄屏侧栏隐藏时，用右上角按钮直接进事项页
  el.wsBtn.addEventListener("click", function () {
    var base = (NAV_ITEMS[state.user && state.user.role] || [])[0];
    openPanel(base ? base.key : "logs");
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (state.panelKey) closePanel();
    if (el.drawer && el.drawer.classList.contains("on")) closeDrawer();
  });

  /* ---------------- 发送 ---------------- */
  function send(text) {
    if (state.streaming) return;
    text = (text || el.input.value).trim();
    if (!text) return;

    var empty = el.chat.querySelector(".empty");
    if (empty) el.chat.innerHTML = "";

    addUserMsg(text);
    el.input.value = "";
    autoGrow();

    var ref = addBotMsg();
    setStreaming(true);
    state.controller = new AbortController();

    fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: state.agent.key,
        query: text,
        user_id: Number(state.userId),
        conversation_id: state.conversationId || "",
        token: token(),
      }),
      signal: state.controller.signal,
    })
      .then(function (res) {
        if (!res.ok || !res.body) {
          return res.text().then(function (t) {
            throw new Error("HTTP " + res.status + " " + t.slice(0, 200));
          });
        }
        var reader = res.body.getReader();
        var decoder = new TextDecoder("utf-8");
        var buffer = "";

        function pump() {
          return reader.read().then(function (r) {
            if (r.done) return;
            buffer += decoder.decode(r.value, { stream: true });
            var idx;
            while ((idx = buffer.indexOf("\n\n")) >= 0) {
              handleFrame(buffer.slice(0, idx), ref);
              buffer = buffer.slice(idx + 2);
            }
            return pump();
          });
        }
        return pump();
      })
      .catch(function (e) {
        if (e.name === "AbortError") {
          finishBotMsg(ref, null, null);
          ref.meta.hidden = false;
          ref.meta.textContent = "已停止";
        } else {
          finishBotMsg(ref, null, e.message || String(e));
        }
      })
      .finally(function () {
        setStreaming(false);
      });
  }

  function handleFrame(frame, ref) {
    var evt = "", data = "";
    frame.split("\n").forEach(function (line) {
      if (line.indexOf("event:") === 0) evt = line.slice(6).trim();
      else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
    });
    if (!data) return;

    var obj;
    try { obj = JSON.parse(data); } catch (e) { return; }

    if (evt === "delta") {
      ref.text += obj.text || "";
      ref.body.innerHTML = renderMarkdown(tidyAnswer(ref.text));
      scrollBottom(false);
    } else if (evt === "node") {
      pushTool(ref, obj.title);
    } else if (evt === "done") {
      if (obj.conversation_id) {
        state.conversationId = obj.conversation_id;
        el.hintConv.textContent = "会话 " + obj.conversation_id.slice(0, 8);
      }
      finishBotMsg(ref, obj.usage, null);
    } else if (evt === "error") {
      finishBotMsg(ref, null, obj.message || "出错了");
    }
  }

  function setStreaming(on) {
    state.streaming = on;
    el.send.textContent = on ? "停止" : "发送";
    el.send.classList.toggle("stop", on);
    el.input.disabled = on;
  }

  /* ---------------- 切换 ---------------- */
  function switchAgent(key) {
    if (state.streaming) return;
    closeDrawer();
    if (state.panelKey) closePanel();
    if (state.panelKey) closePanel();
    state.agent = state.agents.filter(function (a) { return a.key === key; })[0];
    state.userId = state.agent.users[0].id;
    state.conversationId = "";
    el.hintConv.textContent = "";
    document.documentElement.style.setProperty("--accent", state.agent.accent);
    el.headEmoji.textContent = state.agent.icon;
    el.headName.textContent = state.agent.name;
    el.headTag.textContent = state.agent.tagline;
    el.headEmoji.style.background = state.agent.accent + "18";
    renderAgents();
    renderQuicks();
    renderUsers();
    updateApproveEntry();
    emptyState();
    el.input.focus();
  }

  /* ---------------- 输入框 ---------------- */
  function autoGrow() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 132) + "px";
  }

  el.input.addEventListener("input", autoGrow);
  el.input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  el.send.addEventListener("click", function () {
    if (state.streaming) {
      if (state.controller) state.controller.abort();
      return;
    }
    send();
  });
  el.clearBtn.addEventListener("click", function () {
    if (state.streaming) return;
    state.conversationId = "";
    el.hintConv.textContent = "";
    emptyState();
  });
  el.userSelect.addEventListener("change", function () {
    state.userId = Number(el.userSelect.value);
    state.conversationId = "";
    renderUsers();
    updateApproveEntry();
    emptyState();
  });

  el.logoutBtn.addEventListener("click", function () {
    if (state.streaming && state.controller) state.controller.abort();
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem("yj_user");
    fetch("/api/auth/logout", { method: "POST" }).catch(function () {});
    location.replace("/");
  });

  /* ---------------- 启动：先校验登录，再按角色裁剪 ---------------- */
  function boot() {
    if (!token()) {
      location.replace("/?next=" + encodeURIComponent("/demo/"));
      return;
    }
    fetch("/api/auth/me", { headers: { Authorization: "Bearer " + token() } })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || "登录已过期");
          return d.data;
        });
      })
      .then(function (user) {
        state.user = user;
        state.perms = user.features || {};
        renderMe();
        initWs();
        // 数据后台只对管理员开放
        if (state.perms && state.perms.admin) {
          var adminLink = document.getElementById("admin-link");
          if (adminLink) adminLink.hidden = false;
        }
        return fetch("/api/chat/agents")
          .then(function (r) { return r.json(); })
          .then(function (d) {
            var allowed = user.agents || [];
            state.agents = (d.data || []).filter(function (a) {
              return allowed.indexOf(a.key) >= 0;
            });
            if (!state.agents.length) throw new Error("当前角色没有可用的 Agent");
            if (!state.perms.switch_identity) {
              // 非管理员：身份锁死本人，前端不给"切成别人"的入口
              state.agents.forEach(function (a) {
                var mine = a.users.filter(function (u) { return u.id === user.id; })[0];
                a.users = [mine || { id: user.id, name: user.real_name, label: user.label }];
              });
            }
            switchAgent(state.agents[0].key);
            setStreaming(false);
          });
      })
      .catch(function (e) {
        var msg = e.message || String(e);
        if (/登录|过期|401/.test(msg)) {
          localStorage.removeItem(TOKEN_KEY);
          location.replace("/");
          return;
        }
        el.headTag.textContent = "连接后端失败";
        el.chat.innerHTML =
          '<div class="empty"><div class="empty-emoji">⚠️</div>' +
          '<div class="empty-title">无法进入控制台</div>' +
          '<div class="empty-text">' + escapeHtml(msg) + "</div></div>";
      });
  }

  boot();
})();

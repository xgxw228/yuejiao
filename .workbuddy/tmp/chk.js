
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

  function emptyState() {
    var a = state.agent;
    el.chat.innerHTML = "";
    var wrap = document.createElement("div");
    wrap.className = "empty";
    wrap.innerHTML =
      '<div class="empty-emoji">' + a.icon + "</div>" +
      '<div class="empty-title">' + a.name + "</div>" +
      '<div class="empty-text">' + a.welcome + "</div>";
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

  el.approveBtn.addEventListener("click", openDrawer);
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

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && el.drawer.classList.contains("on")) closeDrawer();
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
    location.replace("/?logout=1");
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
          location.replace("/?logout=1");
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

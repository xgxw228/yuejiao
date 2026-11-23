
(function () {
  "use strict";

  var TOKEN_KEY = "yj_token";
  var USER_KEY = "yj_user";
  var NEXT = new URLSearchParams(location.search).get("next") || "/demo/";
  var FORCE_LOGOUT = new URLSearchParams(location.search).has("logout");

  var el = {
    form: document.getElementById("form"),
    username: document.getElementById("username"),
    password: document.getElementById("password"),
    userWrap: document.getElementById("user-wrap"),
    pwdWrap: document.getElementById("pwd-wrap"),
    eye: document.getElementById("eye"),
    submit: document.getElementById("submit"),
    msg: document.getElementById("msg"),
    roles: document.getElementById("roleCards"),
    rolesNote: document.getElementById("rolesNote"),
    register: document.getElementById("register"),
    toast: document.getElementById("toast"),
    nav: document.getElementById("nav"),
  };

  var toastTimer = null;
  function toast(text, isErr) {
    el.toast.textContent = text;
    el.toast.classList.toggle("err", !!isErr);
    el.toast.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.classList.remove("on"); }, 2800);
  }

  function setMsg(text, ok) {
    el.msg.textContent = text || "";
    el.msg.classList.toggle("ok", !!ok);
  }

  /* ---------- 已登录直接进控制台 ---------- */
  if (!FORCE_LOGOUT) {
    var saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      fetch("/api/auth/me", { headers: { Authorization: "Bearer " + saved } })
        .then(function (r) { return r.json().then(function (d) { return r.ok ? d.data : null; }); })
        .then(function (user) {
          if (user) location.replace(NEXT);
          else localStorage.removeItem(TOKEN_KEY);
        })
        .catch(function () {});
    }
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  /* ---------- 吸顶导航：滚过首屏加白底 ---------- */
  function onScroll() {
    el.nav.classList.toggle("solid", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- 滚动进场 ---------- */
  var rvs = document.querySelectorAll(".rv");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.14, rootMargin: "0px 0px -8% 0px" });
    Array.prototype.forEach.call(rvs, function (n) { io.observe(n); });
  } else {
    Array.prototype.forEach.call(rvs, function (n) { n.classList.add("in"); });
  }

  /* ---------- 演示账号：按身份分组，同身份多账号 ---------- */
  var cards = [];
  var order = ["admin", "teacher", "activity_teacher", "student", "staff"];

  function renderRoles(list) {
    cards = list.slice().sort(function (a, b) {
      var d = order.indexOf(a.key) - order.indexOf(b.key);
      return d !== 0 ? d : String(a.username).localeCompare(String(b.username));
    });
    var html = "";
    order.forEach(function (key) {
      var group = cards.filter(function (r) { return r.key === key; });
      if (!group.length) return;
      html += '<div class="role-group"><b>' + group[0].label + "</b><span>" + group.length + " 个账号</span></div>";
      group.forEach(function (r) {
        var sub = r.group && r.group !== r.desc ? r.group + " · " + r.desc : r.desc;
        html += '<button type="button" class="role-card' + (group.length === 1 ? " solo" : "") +
          (r.disabled ? " off" : "") +
          '" data-account="' + r.username + '" title="' +
          r.label + " · " + r.name + " · " + r.username + "／" + r.password +
          (r.disabled ? "（已停用，登录会被拒绝）" : "") + '">' +
          '<span class="role-name">' + r.name + "<em>" + r.username + "</em></span>" +
          '<span class="role-desc">' + sub + "</span></button>";
      });
    });
    el.roles.innerHTML = html;
    if (el.rolesNote) {
      var base = "共 " + cards.length + " 个演示账号，密码统一 " +
        (cards[0] ? cards[0].password : "123456") +
        "。换一位老师或学员登录，能看到的就只有他自己名下那部分。";
      el.rolesNote.textContent = base;
      // 账号多到一屏放不下时才提示可滚动，放得下就别多嘴
      setTimeout(function () {
        if (el.roles.scrollHeight > el.roles.clientHeight + 4) {
          el.rolesNote.textContent = base + "（账号区可上下滚动）";
        }
      }, 0);
    }
  }

  function fill(role) {
    el.username.value = role.username;
    el.password.value = role.password;
    clearErr();
    setMsg("已填入：" + role.name + "（" + role.label + (role.group ? " · " + role.group : "") + "）", true);
    Array.prototype.forEach.call(el.roles.querySelectorAll(".role-card"), function (c) {
      c.classList.toggle("on", c.getAttribute("data-account") === role.username);
    });
    el.submit.focus();
  }

  el.roles.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".role-card");
    if (!btn) return;
    var uname = btn.getAttribute("data-account");
    var role = cards.filter(function (r) { return r.username === uname; })[0];
    if (role) fill(role);
  });

  function clearErr() {
    el.userWrap.classList.remove("err");
    el.pwdWrap.classList.remove("err");
  }

  fetch("/api/auth/roles")
    .then(function (r) { return r.json(); })
    .then(function (d) { if (d && d.data && d.data.length) renderRoles(d.data); })
    .catch(function () { toast("读取演示角色失败，可手动输入账号", true); });

  /* ---------- 密码显隐 ---------- */
  el.eye.addEventListener("click", function () {
    var show = el.password.type === "password";
    el.password.type = show ? "text" : "password";
    el.eye.style.color = show ? "#2563eb" : "";
  });

  /* ---------- 登录 ---------- */
  function doLogin(username, password, silent) {
    var u = (username || el.username.value).trim();
    var p = password || el.password.value;
    clearErr();
    setMsg("");

    if (!u) { el.userWrap.classList.add("err"); setMsg("请输入用户名"); el.form.classList.add("shake"); setTimeout(function () { el.form.classList.remove("shake"); }, 340); return; }
    if (!p) { el.pwdWrap.classList.add("err"); setMsg("请输入密码"); return; }

    el.submit.disabled = true;
    el.submit.textContent = "登录中…";

    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) throw new Error(d.detail || d.msg || ("HTTP " + r.status));
          return d;
        });
      })
      .then(function (d) {
        var data = d.data || {};
        localStorage.setItem(TOKEN_KEY, data.token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user || {}));
        setMsg(d.msg || "登录成功，正在进入…", true);
        if (silent) setMsg("已按游客身份进入…", true);
        /* 没指定 next 时：管理员直接进数据后台，其余进对话工作台 */
        var go = NEXT;
        if (NEXT === "/demo/" && (data.user || {}).role === "admin") go = "/admin";
        location.replace(go);
      })
      .catch(function (e) {
        el.submit.disabled = false;
        el.submit.textContent = "进入系统";
        setMsg(e.message || "登录失败");
        el.form.classList.add("shake");
        setTimeout(function () { el.form.classList.remove("shake"); }, 340);
      });
  }

  el.form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    doLogin();
  });

  /* ---------- 没有账号 / 还没想好：一律转到在线客服 ---------- */
  function openConsult() {
    var fab = document.getElementById("csFab");
    if (fab) { if (!document.getElementById("csPanel").classList.contains("on")) fab.click(); }
    else document.getElementById("login").scrollIntoView({ behavior: "smooth" });
  }
  var ctaConsult = document.getElementById("ctaConsult");
  if (ctaConsult) ctaConsult.addEventListener("click", openConsult);

  el.register.addEventListener("click", openConsult);

  el.username.addEventListener("input", clearErr);
  el.password.addEventListener("input", clearErr);

  /* 首屏不抢焦点：无锚点时回到顶部 */
  if (!location.hash) window.scrollTo(0, 0);
})();


/* ============ 登录页在线客服（匿名访客 · 只答公开信息） ============ */
(function () {
  "use strict";

  var fab = document.getElementById("csFab");
  var panel = document.getElementById("csPanel");
  var body = document.getElementById("csBody");
  var chipsBox = document.getElementById("csChips");
  var form = document.getElementById("csForm");
  var input = document.getElementById("csInput");
  var sendBtn = document.getElementById("csSend");
  var closeBtn = document.getElementById("csClose");
  var loginLink = document.getElementById("csLogin");
  if (!fab || !panel || !body) return;

  var convId = "";
  var busy = false;

  var PROMPTS = [
    "19岁高中毕业，想快点拿本科",
    "德国双元制是什么",
    "一年十万预算能去哪些国家",
    "现在有哪些项目在招生"
  ];

  PROMPTS.forEach(function (p) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "cs-chip";
    b.textContent = p;
    b.addEventListener("click", function () { ask(p); });
    chipsBox.appendChild(b);
  });

  function scrollEnd() { body.scrollTop = body.scrollHeight; }

  function bubble(role, text) {
    var d = document.createElement("div");
    d.className = "cs-msg " + role;
    d.textContent = text || "";
    body.appendChild(d);
    scrollEnd();
    return d;
  }

  function setOpen(v) {
    panel.classList.toggle("on", v);
    fab.setAttribute("aria-expanded", v ? "true" : "false");
    if (v) setTimeout(function () { input.focus(); }, 90);
  }

  fab.addEventListener("click", function () { setOpen(!panel.classList.contains("on")); });
  closeBtn.addEventListener("click", function () { setOpen(false); });
  if (loginLink) loginLink.addEventListener("click", function () { setOpen(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && panel.classList.contains("on")) setOpen(false);
  });

  form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });

  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 92) + "px";
  });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input.value); }
  });

  /* 问到个人数据就不调模型，直接引导登录——避免访客以为这里能查到自己的进度 */
  var NEED_LOGIN = /(我的|我孩子|我家孩子|孩子的|学员的|学生的)[^。？！?]{0,10}(进度|成绩|分数|请假|审批|记录|状态|材料|合同|缴费|申请到)/;
  var LOGIN_TIP = "个人进度、成绩、请假、缴费这些要登录后才能查看——点右上角「进入系统」，或用下面的「登录后查看」。\n项目、费用、申请条件、开班时间这些是公开的，我现在就能答。";

  /* ---------- 留资：识别到手机号就写线索，转给顾问 ---------- */
  var lastQuery = "";

  /* ---------- 活动：公开信息，客服直接答；报名走公开接口 ---------- */
  var ACTIVITIES = [];
  var pending = null;              // 正在报名的那一场
  var leadDraft = { name: "" };    // 电话格式不对时，先把说过的名字记住
  var PHONE_RE = /^1\d{10}$/;
  var PHONE_TIP = "电话格式错误，请重新填写。\n要 11 位纯数字（1 开头），比如 13800138000。";

  function loadActivities() {
    fetch("/api/public/activities")
      .then(function (r) { return r.json(); })
      .then(function (d) { ACTIVITIES = (d && d.data) || []; })
      .catch(function () {});
  }
  loadActivities();

  /* 从一句话里抠出可能的号码（6 位以上连续数字，允许中间有空格/横线） */
  function phoneCandidates(text) {
    var out = [];
    var re = /\d[\d\s\-]{4,}\d/g;
    var m;
    while ((m = re.exec(text)) !== null) {
      var p = m[0].replace(/[\s\-]/g, "");
      if (p.length >= 6) out.push(p);
    }
    return out;
  }

  function validPhone(text) {
    var c = phoneCandidates(text);
    for (var i = 0; i < c.length; i++) if (PHONE_RE.test(c[i])) return c[i];
    return "";
  }

  function phoneish(text) {
    return phoneCandidates(text).length > 0 || /电话|手机|号码|联系方式/.test(text);
  }

  function pickName(text) {
    var t = text
      .replace(/1\d{10}/g, " ")
      .replace(/(我叫|我是|我姓|姓名|名字|叫|电话|手机号|手机|号码|联系方式|方便|可以|好的|好|您好|请|加我|微信|是)/g, " ")
      .replace(/[^\u4e00-\u9fa5]/g, " ")
      .trim();
    var m = t.match(/[\u4e00-\u9fa5]{2,4}/);
    return m ? m[0] : "";
  }

  function nameIn(text) {
    var m = text.match(/(?:我叫|姓名是|名字是|我是)\s*([\u4e00-\u9fa5]{2,4})/);
    return m ? m[1] : "";
  }

  var ACT_WORD = /活动|讲座|分享会|说明会|沙龙|开放日/;
  var PLACES = ["新加坡", "德国", "香港", "澳门", "马来", "日本", "韩国", "澳洲", "英国", "美国", "加拿大"];

  /* 只按地名匹配（换场次时用，"那就新加坡吧"这种不带"活动"二字也能认） */
  function matchByPlace(text) {
    for (var j = 0; j < ACTIVITIES.length; j++) {
      for (var k = 0; k < PLACES.length; k++) {
        if (text.indexOf(PLACES[k]) >= 0 && ACTIVITIES[j].title.indexOf(PLACES[k]) >= 0) {
          return ACTIVITIES[j];
        }
      }
    }
    return null;
  }

  /* 只有「完整活动名」或「地名 + 活动字样」才当成活动，避免把普通咨询误判成报名 */
  function matchActivity(text) {
    for (var i = 0; i < ACTIVITIES.length; i++) {
      if (text.indexOf(ACTIVITIES[i].title) >= 0) return ACTIVITIES[i];
    }
    return ACT_WORD.test(text) ? matchByPlace(text) : null;
  }

  function actListText() {
    if (!ACTIVITIES.length) {
      return "这两天暂时没排新的活动。留个姓名和手机号，我让顾问把最近的场次发你。";
    }
    var lines = ["近期活动（按时间排）："];
    ACTIVITIES.slice(0, 5).forEach(function (a) {
      lines.push("· " + a.title + "\n  " + a.start + " · " + a.speaker + " 主讲 · " +
        a.location + " · " + (a.full ? "名额已满" : "余 " + a.remaining + " 个名额"));
    });
    lines.push("想参加哪一场？说地名或活动名就行，留个姓名和手机号我帮你占位。");
    return lines.join("\n");
  }

  function fullMessage(a) {
    var alts = ACTIVITIES.filter(function (x) { return !x.full && x.id !== a.id; }).slice(0, 3);
    var msg = "「" + a.title + "」名额已经满了（" + a.signed + "/" + a.capacity + "），没法再报名。";
    if (alts.length) {
      msg += "\n还有这些场次有空位：\n" + alts.map(function (x) {
        return "· " + x.title + " · " + x.start + " · 余 " + x.remaining + " 个名额";
      }).join("\n");
      msg += "\n想参加哪一场？说地名就行；或者留个手机号，我让顾问帮你安排。";
    } else {
      msg += "\n近期没有别的场次了，留个电话我让顾问给你安排下一场。";
    }
    return msg;
  }

  function beginActivity(a, text) {
    var name = nameIn(text) || leadDraft.name || "";
    if (a.full) {
      pending = { id: null, title: "", name: name };
      bubble("bot", fullMessage(a));
      return;
    }
    pending = { id: a.id, title: a.title, name: name };
    if (phoneish(text)) { handleSignupFlow(text); return; }
    bubble("bot", "「" + a.title + "」\n" + a.start + " · " + a.speaker + " 主讲 · " +
      a.location + "\n还有 " + a.remaining + " 个名额（共 " + a.capacity + " 个）。\n" +
      (pending.name ? pending.name + "，留一下手机号就行（11 位数字）。"
                    : "把姓名和手机号发我，我帮你占位。"));
  }

  /* 报名上下文：返回 true 表示这条消息已经被消化，不再走模型 */
  function handleSignupFlow(text) {
    if (!pending) return false;

    // 满员后正在换场次
    if (!pending.id) {
      var alt = matchByPlace(text) || matchActivity(text);
      if (alt) {
        if (alt.full) { bubble("bot", fullMessage(alt)); return true; }
        pending.id = alt.id;
        pending.title = alt.title;
        if (phoneish(text)) { handleSignupFlow(text); return true; }
        bubble("bot", "好，改报「" + alt.title + "」（" + alt.start + " · 余 " + alt.remaining +
          " 个名额）。" + (pending.name ? pending.name + "，留一下手机号就行。"
                                      : "留个姓名和手机号，我帮你占位。"));
        return true;
      }
      if (!phoneish(text)) {
        bubble("bot", "想去哪一场？说地名就行，比如「新加坡」「香港」；也可以留个电话，我让顾问帮你安排。");
        return true;
      }
    }

    var nm = nameIn(text);
    if (nm) pending.name = nm;

    var good = validPhone(text);
    if (good) {
      if (!pending.id) {
        var free = ACTIVITIES.filter(function (x) { return !x.full; })[0];
        if (!free) {
          pending = null;
          bubble("bot", "近期场次都满了，留个电话我让顾问帮你安排下一场。");
          return true;
        }
        pending.id = free.id;
        pending.title = free.title;
      }
      if (!pending.name) {
        // 只发了一串号码：去掉数字和提示词后若剩 2~4 个汉字，当作姓名
        var bare = text.replace(/[\d\s\-]/g, "")
          .replace(/[，,。.、:：]|电话|手机号|手机|号码|联系方式|是|我|叫|的/g, "")
          .trim();
        if (/^[\u4e00-\u9fa5]{2,4}$/.test(bare)) pending.name = bare;
      }
      if (!pending.name) {
        bubble("bot", "号码记下了（" + good + "）。报名人叫什么名字？");
        return true;
      }
      submitSignup(pending.id, pending.title, pending.name, good);
      return true;
    }

    if (phoneish(text)) {
      if (pending.name) leadDraft.name = pending.name;
      bubble("bot", PHONE_TIP + (pending.name ? "\n" + pending.name + " 的名字我先记着，只补电话就行。" : ""));
      return true;
    }

    if (!pending.name) {
      var short = text.replace(/[，,。.\s]/g, "");
      if (/^[\u4e00-\u9fa5]{2,4}$/.test(short)) {
        pending.name = short;
        bubble("bot", "好的" + short + "，留一下手机号（11 位数字）就报好了。");
        return true;
      }
    }
    return false;
  }

  var signupBusy = false;

  function submitSignup(id, title, name, phone) {
    if (signupBusy) return;
    signupBusy = true;
    var out = bubble("bot", "正在报名…");
    out.classList.add("typing");
    busy = true;
    sendBtn.disabled = true;
    fetch("/api/public/activity-signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activity_id: id, name: name, phone: phone, remark: lastQuery || "" })
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, status: r.status, d: d || {} }; });
      })
      .then(function (res) {
        signupBusy = false;
        busy = false;
        sendBtn.disabled = false;
        out.classList.remove("typing");
        var d = res.d;
        if (!res.ok) {
          var det = d.detail;
          if (res.status === 409 && det && typeof det === "object") {
            var alts = det.alternatives || [];
            var msg = "「" + (det.activity || title) + "」名额刚满，没法再报了。";
            if (alts.length) {
              msg += "\n还有这些场次有空位：\n" + alts.map(function (x) {
                return "· " + x.title + " · " + x.start + " · 余 " + x.remaining + " 个名额";
              }).join("\n");
              msg += "\n想参加哪一场？说地名就行，姓名我先帮你留着。";
              pending = { id: null, title: "", name: name };
            } else {
              msg += "\n近期没有别的场次了，我让顾问给你安排。";
              pending = null;
            }
            out.textContent = msg;
          } else {
            var txt = typeof det === "string" ? det : ((det && det.msg) || "报名没成功");
            out.textContent = txt + (txt.indexOf("电话") >= 0 ? "" : "。可以重新发一次姓名和电话。");
            if (txt.indexOf("电话") >= 0) pending = { id: id, title: title, name: name };
          }
          scrollEnd();
          return;
        }
        var ok = d.data || {};
        var info = ACTIVITIES.filter(function (x) { return x.id === id; })[0] || {};
        pending = null;
        leadDraft.name = "";
        if (ok.repeated) {
          out.textContent = "这个号码之前已经报过「" + (ok.activity || title || info.title) +
            "」了，不用重复报名。\n开始前顾问会再联系你确认。";
          scrollEnd();
          return;
        }
        out.textContent = "报名成功。\n活动：" + (ok.activity || title || info.title) +
          "\n时间：" + (ok.start || info.start || "") +
          "\n地点：" + (ok.location || info.location || "") +
          "\n姓名：" + name + "　电话：" + phone +
          "\n" + (ok.consultant ? ok.consultant + " 会联系你确认" : "顾问会联系你确认") +
          "，开始前再提醒一次。";
        scrollEnd();
        loadActivities();
      })
      .catch(function () {
        signupBusy = false;
        busy = false;
        sendBtn.disabled = false;
        out.classList.remove("typing");
        out.textContent = "网络不太顺，报名没提交上。可以直接致电 020-37628058 找顾问老师。";
        scrollEnd();
      });
  }

  function captureLead(text, phone) {
    var name = leadDraft.name || pickName(text);
    var out = bubble("bot", "正在登记联系方式…");
    out.classList.add("typing");
    fetch("/api/public/lead", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phone: phone,
        name: name,
        intent: lastQuery || "",
        summary: text.slice(0, 200)
      })
    })
      .then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok || !d.ok) throw new Error((d && d.detail) || "登记失败");
          return d;
        });
      })
      .then(function (d) {
        out.classList.remove("typing");
        leadDraft.name = "";
        var who = d.consultant || "顾问";
        var label = /顾问$/.test(who) ? who : ("顾问" + who);
        var tel = d.consultant_phone || "020-37628058";
        out.textContent = (name ? name + "（" + phone + "）" : phone) + " 已经记下了。" +
          (d.repeated ? "你之前留过联系方式，这次也记上了。" : "已记录，正在转给负责顾问。") +
          "\n对接顾问：" + label + "　电话：" + tel +
          "\n" + label + "会在工作时间内按你留的号码联系你；急的话可以直接打这个电话。" +
          "这期间想先了解哪个项目，也可以继续问我。";
        scrollEnd();
      })
      .catch(function () {
        out.classList.remove("typing");
        out.textContent = "号码这边没登记上。" +
          "可以直接致电 020-37628058 找顾问老师，项目问题我也能继续答。";
        scrollEnd();
      });
  }

  function ask(text) {
    text = (text || "").trim();
    if (!text || busy) return;

    bubble("me", text);
    chipsBox.style.display = "none";
    input.value = "";
    input.style.height = "40px";

    // 报名上下文最优先：已经在填资料，先把这单处理完
    if (handleSignupFlow(text)) return;

    // 活动走本地：名额、时间要实时，且报名流程要能接住电话
    var act = matchActivity(text);
    if (act) { beginActivity(act, text); return; }
    if (/报名|参加|活动|讲座|分享会|说明会|沙龙|开放日/.test(text)) {
      bubble("bot", actListText());
      return;
    }

    var good = validPhone(text);
    if (good) { captureLead(text, good); return; }
    if (phoneish(text)) {
      var draft = pickName(text);
      if (draft) leadDraft.name = draft;
      bubble("bot", PHONE_TIP +
        (leadDraft.name ? "\n" + leadDraft.name + " 的名字我先记着，只补电话就行。" : ""));
      return;
    }

    if (NEED_LOGIN.test(text)) {
      setTimeout(function () { bubble("bot", LOGIN_TIP); }, 220);
      return;
    }
    if (text.length >= 4) lastQuery = text;

    busy = true;
    sendBtn.disabled = true;

    var out = bubble("bot", "正在查资料…");
    out.classList.add("typing");
    var acc = "";
    var errored = false;
    var lastNode = "";

    function onEvent(chunk) {
      var ev = "";
      var data = "";
      chunk.split("\n").forEach(function (line) {
        if (line.indexOf("event:") === 0) ev = line.slice(6).trim();
        else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
      });
      if (!data) return;
      var d;
      try { d = JSON.parse(data); } catch (err) { return; }

      if (ev === "delta" && d.text) {
        if (!acc) { out.classList.remove("typing"); out.textContent = ""; }
        acc += d.text;
        out.textContent = acc;
        scrollEnd();
      } else if (ev === "node" && d.title) {
        // 等待期间显示 Dify 正在跑哪个业务节点，避免只看到「正在查资料…」像卡死
        if (!acc) { lastNode = d.title; out.textContent = "正在查资料…（" + d.title + "）"; scrollEnd(); }
      } else if (ev === "done") {
        convId = d.conversation_id || convId;
      } else if (ev === "error") {
        errored = true;
        out.classList.remove("typing");
        out.textContent = d.message || "这次没答上来，换个说法再问一次试试。";
        scrollEnd();
      }
    }

    function finish() {
      out.classList.remove("typing");
      if (!acc && !errored) {
        out.textContent = "这次没查到内容，换个说法再问一次，或致电 020-37628058 找顾问老师。";
      }
      busy = false;
      sendBtn.disabled = false;
      scrollEnd();
    }

    fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: "customer",
        query: text,
        user_id: 14,
        conversation_id: convId,
        token: null,
        public: true
      })
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        if (!r.body || !r.body.getReader) return r.text().then(function (t) { t.split("\n\n").forEach(onEvent); });
        var reader = r.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function pump() {
          return reader.read().then(function (res) {
            if (res.done) return;
            buf += dec.decode(res.value, { stream: true });
            var i;
            while ((i = buf.indexOf("\n\n")) >= 0) {
              onEvent(buf.slice(0, i));
              buf = buf.slice(i + 2);
            }
            return pump();
          });
        }
        return pump();
      })
      .catch(function () {
        errored = true;
        out.classList.remove("typing");
        out.textContent = "网络有点问题，稍后再试；急着问可以直接打 020-37628058。";
      })
      .then(finish);
  }
})();

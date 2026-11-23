import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def login(u, p="123456"):
    s, d = call("/api/auth/login", "POST", {"username": u, "password": p})
    assert s == 200, (s, d)
    return d["data"]["token"], d["data"]["user"]


s, roles = call("/api/auth/roles")
print("roles", s, roles["msg"])
for r in roles["data"]:
    print("   ", r["key"], r["username"], r["name"], "|", r["desc"], "|", r["group"])

tk_li, u_li = login("emp001")
tk_zhao, _ = login("emp003")
tk_sun, _ = login("emp005" if False else "emp004")
tk_stu, _ = login("stu001")
tk_adm, _ = login("admin")
tk_staff, _ = login("emp006")
print("teachers:", u_li["real_name"], u_li["students"], "| zhao", _["students"] if False else "")

for name, tk in [("李", tk_li), ("赵", tk_zhao), ("孙", tk_sun), ("学员", tk_stu), ("管理员", tk_adm), ("顾问", tk_staff)]:
    s, d = call("/api/leave/pending?approver_id=9&scope=all", token=tk)
    if s == 200:
        names = sorted({x["student_name"] for x in d["data"]})
        print(f"pending[{name}]", names)
    else:
        print(f"pending[{name}]", s, d.get("detail"))

for name, tk in [("李", tk_li), ("赵", tk_zhao), ("学员", tk_stu), ("管理员", tk_adm)]:
    s, d = call("/api/grades", token=tk)
    if s == 200:
        dd = d["data"]
        print(f"grades[{name}]", [x["name"] for x in dd["rows"]], "can_edit", dd["can_edit"], "|", dd["note"])
    else:
        print(f"grades[{name}]", s, d.get("detail"))

# 越权写：李老师给赵敏名下学生 6 录成绩
s, d = call("/api/grades", "POST", {"student_id": 6, "course_name": "越权测试", "score": 90}, tk_li)
print("cross-teacher write", s, d.get("detail") or d.get("msg"))
# 本班学生 1 录入
s, d = call("/api/grades", "POST", {"student_id": 1, "course_name": "越权测试", "score": 90, "semester": "测试学期"}, tk_li)
print("own write", s, d.get("msg"))
s, d = call("/api/grades", "POST", {"student_id": 1, "course_name": "越权测试", "score": 95, "semester": "测试学期"}, tk_li)
print("own overwrite", s, d.get("msg"))
# 学生自己写 / 管理员写 / 顾问看
s, d = call("/api/grades", "POST", {"student_id": 1, "course_name": "x", "score": 1}, tk_stu)
print("student write", s, d.get("detail"))
s, d = call("/api/grades", "POST", {"student_id": 6, "course_name": "x", "score": 1}, tk_adm)
print("admin write", s, d.get("detail"))
s, d = call("/api/grades", token=tk_staff)
print("staff read", s, d.get("detail"))
# 学生看别人请假
s, d = call("/api/leave/student/6", token=tk_stu)
print("student other leave", s, d.get("detail"))
s, d = call("/api/leave/student/6", token=tk_li)
print("teacher other leave", s, d.get("detail"))
s, d = call("/api/leave/student/1", token=tk_li)
print("teacher own student leave", s, len(d.get("data", {}).get("records", [])))
# 无 token
s, d = call("/api/leave/pending?approver_id=3")
print("no token pending", s, d.get("detail"))
s, d = call("/api/leave/summary?approver_id=3&scope=all", token=tk_li)
print("teacher asks all", s, d["data"]["scope"], d["data"]["pending"])

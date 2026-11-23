import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://localhost/console/api"
HERE = os.path.dirname(os.path.abspath(__file__))


def _cookies():
    out = {}
    path = os.path.join(HERE, "cookies.txt")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            elif line.startswith("#") or not line.strip():
                continue
            flds = line.rstrip("\n").split("\t")
            if len(flds) >= 7:
                out[flds[5]] = flds[6]
    return out


def headers():
    c = _cookies()
    return {
        "Cookie": "; ".join(f"{k}={v}" for k, v in c.items()),
        "X-CSRF-Token": c.get("csrf_token", ""),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def call(method, path, payload=None, raw=None, content_type=None):
    url = BASE + path
    h = headers()
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    elif raw is not None:
        data = raw
        if content_type:
            h["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read().decode("utf-8")
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


if __name__ == "__main__":
    method = sys.argv[1]
    path = sys.argv[2]
    payload = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    code, data = call(method, path, payload)
    print("HTTP", code)
    text = json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data
    print(text[:7000])

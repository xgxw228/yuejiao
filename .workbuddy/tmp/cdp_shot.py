"""用 CDP 驱动 Edge 无头浏览器，跑一次真实对话并截图（仅本地验证用）"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

from websockets.sync.client import connect

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = sys.argv[1] if len(sys.argv) > 1 else r"D:\项目1\.workbuddy\tmp\shot2.png"
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/demo/"
WAIT = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
PROFILE = r"D:\项目1\.workbuddy\tmp\edge-profile"

proc = subprocess.Popen(
    [
        EDGE,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1440,950",
        "--remote-debugging-port=9222",
        f"--user-data-dir={PROFILE}",
        "about:blank",
    ],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

ws_url = None
for _ in range(40):
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=2) as r:
            targets = json.load(r)
        page = next((t for t in targets if t["type"] == "page"), None)
        if page:
            ws_url = page["webSocketDebuggerUrl"]
            break
    except Exception:
        pass
    time.sleep(0.5)

if not ws_url:
    print("CDP 未就绪")
    proc.kill()
    raise SystemExit(1)

mid = [0]


def cmd(ws, method, params=None):
    mid[0] += 1
    ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid[0]:
            return msg.get("result", {})


with connect(ws_url, max_size=60 * 1024 * 1024) as ws:
    cmd(ws, "Page.enable")
    cmd(ws, "Runtime.enable")
    cmd(ws, "Emulation.setDeviceMetricsOverride",
        {"width": 1440, "height": 950, "deviceScaleFactor": 1, "mobile": False})
    cmd(ws, "Page.navigate", {"url": URL})
    time.sleep(2.0)
    r = cmd(ws, "Runtime.evaluate",
            {"expression": "typeof switchAgent==='function'", "returnByValue": True})
    time.sleep(WAIT)
    shot = cmd(ws, "Page.captureScreenshot", {"format": "png"})
    data = shot.get("data")
    if data:
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", OUT, os.path.getsize(OUT))
    else:
        print("no data")

proc.kill()

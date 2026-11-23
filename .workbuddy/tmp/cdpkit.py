"""CDP 小工具：每次用独立端口 + 独立 profile 启一个无头 Edge，确保连的是自己这个实例。"""

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from itertools import count

from websockets.sync.client import connect

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HERE = os.path.dirname(os.path.abspath(__file__))


class Browser:
    _seq = count(9333)

    def __init__(self, width=1440, height=980):
        self.port = next(Browser._seq)
        self.profile = os.path.join(HERE, f"edge-profile-{self.port}")
        shutil.rmtree(self.profile, ignore_errors=True)
        self.proc = subprocess.Popen(
            [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={width},{height}", f"--remote-debugging-port={self.port}",
             f"--user-data-dir={self.profile}", "--no-first-run", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.mid = 0
        self.ws = connect(self._wait_ws(), max_size=80 * 1024 * 1024)

    def _wait_ws(self):
        for _ in range(60):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=2) as r:
                    for t in json.load(r):
                        if t["type"] == "page":
                            return t["webSocketDebuggerUrl"]
            except Exception:
                pass
            time.sleep(0.4)
        raise RuntimeError("CDP 未就绪")

    def cmd(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr, wait=0.0):
        r = self.cmd("Runtime.evaluate",
                     {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if wait:
            time.sleep(wait)
        if r.get("exceptionDetails"):
            desc = r["exceptionDetails"].get("exception", {}).get("description")
            print("JS ERROR:", (desc or "")[:300])
        return r.get("result", {}).get("value")

    def shot(self, name):
        import base64
        data = self.cmd("Page.captureScreenshot", {"format": "png"}).get("data")
        path = os.path.join(HERE, name)
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", path, os.path.getsize(path))
        return path

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.kill()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(self.profile, ignore_errors=True)


def open_page(browser, url, width=1440, height=980):
    browser.cmd("Page.enable")
    browser.cmd("Runtime.enable")
    browser.cmd("Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})
    browser.cmd("Page.navigate", {"url": url})
    time.sleep(3)


if __name__ == "__main__":
    b = Browser()
    open_page(b, "http://127.0.0.1:8000/demo/")
    print(b.js("document.title"))
    b.close()

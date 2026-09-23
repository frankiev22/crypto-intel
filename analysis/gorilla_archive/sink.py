"""A localhost-only sink so the browser can hand us the scraped archive in one go.

The browser tool truncates results at about 1 KB and the archive is 67 KB, so
pulling it back through tool output would take sixty round trips.

⛔ x.com's Content-Security-Policy blocks `fetch` to any other origin, so the
page cannot POST to us directly. The way through is a NAVIGATION: a URL fragment
is not governed by connect-src and is never sent to a server, so the x.com page
puts the payload in `#...` and navigates here, and this page (same origin as the
sink, no CSP) reads its own hash and POSTs it back.

⛔ Binds 127.0.0.1 only. Nothing is exposed off this machine, and this file
fetches nothing from the internet.
"""
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "posts_raw.json")

PAGE = b"""<!doctype html><meta charset=utf-8><title>sink</title>
<body style="font:14px system-ui;padding:2rem">
<pre id=o>reading fragment...</pre>
<script>
const o = document.getElementById('o');
(async () => {
  const h = location.hash.slice(1);
  if (!h) { o.textContent = 'NO FRAGMENT'; return; }
  let body;
  try { body = decodeURIComponent(h); }
  catch (e) { o.textContent = 'DECODE FAILED ' + e.message; return; }
  try {
    const r = await fetch('/save', {method:'POST', headers:{'content-type':'application/json'}, body});
    o.textContent = 'SAVED ' + r.status + ' ' + (await r.text());
  } catch (e) { o.textContent = 'POST FAILED ' + e.message; }
})();
</script>
"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode())
            return
        with io.open(OUT, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        msg = json.dumps({"ok": True, "n": len(data)}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)
        print(f"WROTE {OUT} entries={len(data)} bytes={len(body)}", flush=True)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    HTTPServer(("127.0.0.1", port), H).serve_forever()

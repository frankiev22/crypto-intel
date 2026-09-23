"""HTTP in front of `intel.py`. Stdlib only, GET only, read only.

    python intelserve.py [port]        # default 8799

⭐ This exists so the site has something to call. The site is a Vercel Node app
and this is Python, so the two cannot share a process; the contract between them
is `docs/SITE_API.md` and the JSON below.

⛔ **GET ONLY, and that is enforced rather than assumed.** Every other method is
refused with 405 before routing. A read-only API that quietly accepts POST is one
refactor away from not being read-only, and this service must never be able to
move anything. `test_intel.py` fails at the AST level if `intel.py` ever gains a
signing call.

⛔ **No authentication, no secrets, no keys, no cookies.** Everything it serves
is public chain and public index data. Nothing here reads `.env`.

⚠️ **CORS is wide open on purpose**: the responses are public reads and contain
nothing private. If that ever stops being true, this line is the thing to change
first.
"""
import json
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import intel

# endpoint -> (function, required arg name, optional arg names)
ROUTES = {
    "liquidity":    (intel.liquidity,    "mint",   ()),
    "phantom":      (intel.phantom,      "mint",   ()),
    "exit_depth":   (intel.exit_depth,   "mint",   ("size_usd", "raw_qty")),
    "resolve":      (intel.resolve,      "ticker", ("since", "chain", "max_candidates")),
    "safety":       (intel.safety,       "mint",   ()),
    "bundle_check": (intel.bundle_check, "mint",   ("n_buyers",)),
    "paired":       (intel.paired,       "mint",   ()),
    # ⭐ both legs: who can freeze, seize or pause the asset you are PAID in.
    "pair_legs":    (intel.pair_legs,    "mint",   ()),
    "concentration": (intel.concentration, "mint",  ("deep", "max_walk")),
    "wallet":       (intel.wallet,       "pubkey", ("price_all", "max_positions")),
}
INTS = {"size_usd", "raw_qty", "max_positions", "max_candidates",
        "n_buyers", "max_walk"}
BOOLS = {"price_all", "deep"}

STARTED = time.time()
HITS = {"served": 0, "errors": 0, "refused": 0}


class Handler(BaseHTTPRequestHandler):
    server_version = "crypto-intel/1.0"

    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % a))

    # ---- the only verbs this service has -------------------------------
    def do_GET(self):
        try:
            self._route()
        except Exception:
            HITS["errors"] += 1
            traceback.print_exc()
            self._json({"ok": False, "error": "internal error"}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _refuse(self):
        """⛔ Anything that is not a read is refused before it can route."""
        HITS["refused"] += 1
        self._json({"ok": False, "error":
                    "this API is READ ONLY and serves GET only. It has no "
                    "endpoint that can sign, send, approve or custody anything."},
                   405)

    do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _refuse

    # ---------------------------------------------------------------------
    def _route(self):
        u = urlparse(self.path)
        path = u.path.rstrip("/")
        q = {k: v[0] for k, v in parse_qs(u.query).items()}

        if path in ("", "/api", "/health"):
            return self._json({
                "ok": True, "service": "crypto-intel",
                "uptime_s": round(time.time() - STARTED, 1),
                "read_only": True, "counters": dict(HITS),
                "endpoints": {k: {"arg": v[1], "optional": list(v[2])}
                              for k, v in ROUTES.items()},
                "contract": "docs/SITE_API.md",
                "note": "every response carries `provenance` and `not_checked`. "
                        "A field in `not_checked` was NOT checked and must never "
                        "be rendered as a pass.",
            })

        name = path.split("/")[-1]
        route = ROUTES.get(name)
        if not route:
            return self._json({"ok": False, "error": f"no endpoint {name!r}",
                               "endpoints": sorted(ROUTES)}, 404)

        fn, req, opt = route
        if req not in q or not q[req].strip():
            return self._json({"ok": False,
                               "error": f"missing required parameter {req!r}"}, 400)

        kwargs = {}
        for k in opt:
            if k in q:
                v = q[k]
                if k in INTS:
                    try:
                        v = int(float(v))
                    except ValueError:
                        return self._json({"ok": False,
                                           "error": f"{k} must be a number"}, 400)
                elif k in BOOLS:
                    v = str(v).lower() in ("1", "true", "yes")
                kwargs[k] = v

        t0 = time.time()
        out = fn(q[req].strip(), **kwargs)
        HITS["served"] += 1
        if isinstance(out, dict):
            out["took_ms"] = int(1000 * (time.time() - t0))
        self._json(out, 200 if (not isinstance(out, dict) or out.get("ok", True))
                   else 422, ttl=intel.TTL.get(name, 60))

    # ---------------------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200, ttl=None):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Public reads, so let every layer cache them.
        self.send_header("Cache-Control",
                         f"public, max-age={ttl}" if ttl else "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)


def main(argv):
    port = int(argv[0]) if argv else 8799
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"crypto-intel read-only API on http://127.0.0.1:{port}")
    print("  endpoints: " + ", ".join(sorted(ROUTES)))
    print("  GET only. Nothing here can sign, send or approve anything.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(sys.argv[1:])

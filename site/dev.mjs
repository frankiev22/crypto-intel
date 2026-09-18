// Local preview: static files plus the api/ handlers, the way Vercel routes them.
//   node dev.mjs            -> http://localhost:4173
// DEV_FAULT simulates failure modes, because the states that matter most are
// the ones that cannot be produced on demand against a healthy collector:
//   DEV_FAULT=outage     collector dead for 3 days, nothing in any window
//   DEV_FAULT=unreadable every source file fails to read
//   DEV_FAULT=feeddown   /api/feed itself returns 500
// Not deployed (.vercelignore).
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, normalize, extname } from "node:path";

const ROOT = dirname(fileURLToPath(import.meta.url));
const PORT = +(process.env.PORT || 4173);
const FAULT = process.env.DEV_FAULT || "";
const TYPES = { ".html": "text/html; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".json": "application/json" };

function applyFault(j) {
  if (FAULT === "outage") {
    const old = new Date(Date.now() - 74 * 3600000).toISOString();
    j.collector.last_unattended_at = old; j.collector.last_any_at = old; j.collector.last_origin = "runner";
    j.collector.passes = [];
    for (const s of Object.values(j.sections)) {
      s.as_of = old; s.coverage = { passes: 0, complete: 0, newest_at: null };
      s.rows = []; s.total_n = 0; s.raw_n = 0; s.fdv_only = []; s.fdv_only_n = 0;
      s.over_1m_raw_n = 0; s.remeasured_n = 0; s.contracts_examined = 0;
    }
  } else if (FAULT === "unreadable") {
    j.collector.readable = false; j.collector.error = "HTTP 503";
    for (const s of Object.values(j.sections)) { s.readable = false; s.error = "HTTP 503"; s.rows = []; }
  }
  return j;
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  try {
    if (url.pathname.startsWith("/api/")) {
      if (FAULT === "feeddown" && url.pathname === "/api/feed") { res.writeHead(500); res.end("simulated"); return; }
      const name = url.pathname.slice(5).replace(/[^a-z0-9_-]/gi, "");
      const mod = await import(pathToFileURL(join(ROOT, "api", name + ".mjs")).href);
      const shim = {
        setHeader: (k, v) => res.setHeader(k, v),
        status: (s) => { res.statusCode = s; return shim; },
        send: (b) => {
          if (FAULT && name === "feed") b = JSON.stringify(applyFault(JSON.parse(b)));
          res.end(b);
        },
      };
      await mod.default({ query: Object.fromEntries(url.searchParams), method: req.method }, shim);
      return;
    }
    const rel = normalize(url.pathname === "/" ? "/index.html" : url.pathname);
    const file = join(ROOT, rel);
    if (!file.startsWith(ROOT)) { res.writeHead(403); res.end(); return; }
    const body = await readFile(file);
    res.writeHead(200, { "Content-Type": TYPES[extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(body);
  } catch (e) {
    res.writeHead(e.code === "ENOENT" || e.code === "ERR_MODULE_NOT_FOUND" ? 404 : 500);
    res.end(String(e.message || e));
  }
}).listen(PORT, () => console.log(`site preview on http://localhost:${PORT}${FAULT ? "  [fault: " + FAULT + "]" : ""}`));

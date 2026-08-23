#!/usr/bin/env python3
"""
Resume bot server — runs on Arch laptop.
Receives job postings via HTTP, screens them via `claude -p`, returns JSON verdict.

Usage:
    python3 server.py

Listens on 0.0.0.0:8080. Test:
    curl -X POST http://SCREENER_HOST:8080/screen \
         -H "Content-Type: application/json" \
         -d '{"text": "We are hiring a Python dev...", "url": "https://..."}'
"""

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BOT_DIR = Path(__file__).parent.resolve()
PROFILE_PATH = BOT_DIR / "profile.md"
PORT = 8080
CLAUDE_TIMEOUT = 120  # seconds

EDITOR_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>resume_bot — profile</title>
<style>
body{font-family:system-ui,sans-serif;max-width:900px;margin:20px auto;padding:0 16px;}
textarea{width:100%;height:75vh;font-family:ui-monospace,monospace;font-size:13px;padding:12px;box-sizing:border-box;}
button{padding:10px 20px;font-size:15px;background:#ff6600;color:#fff;border:none;border-radius:6px;cursor:pointer;margin-right:8px;}
button:disabled{opacity:.5;}
.bar{display:flex;align-items:center;gap:12px;margin:8px 0;}
.status{color:#666;font-size:13px;}
</style></head><body>
<h2>profile.md</h2>
<div class="bar">
<button id="save">Save</button>
<button id="reload">Reload</button>
<span class="status" id="status">loading…</span>
</div>
<textarea id="ta"></textarea>
<script>
const ta=document.getElementById('ta'),st=document.getElementById('status');
async function load(){st.textContent='loading…';const r=await fetch('/profile');ta.value=await r.text();st.textContent='loaded '+new Date().toLocaleTimeString();}
async function save(){st.textContent='saving…';const r=await fetch('/profile',{method:'POST',headers:{'Content-Type':'text/plain'},body:ta.value});st.textContent=r.ok?'saved '+new Date().toLocaleTimeString():'ERR '+r.status;}
document.getElementById('save').onclick=save;
document.getElementById('reload').onclick=load;
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();save();}});
load();
</script></body></html>"""

PROMPT = """Vyhodnoť následující pracovní nabídku podle profilu v profile.md.
Vrať POUZE JSON podle schématu v CLAUDE.md, žádný jiný text.

=== JOB POSTING ===
{text}
=== END ===
"""


def run_claude(job_text: str) -> dict:
    full_prompt = PROMPT.format(text=job_text)
    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            cwd=str(BOT_DIR),
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"error": "claude -p timed out", "verdict": "ERROR"}

    if result.returncode != 0:
        return {"error": f"claude failed: {result.stderr[:500]}", "verdict": "ERROR"}

    out = result.stdout.strip()
    # try direct parse, then strip code fences
    for candidate in (out, out.strip("`").replace("json\n", "", 1)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    # last resort: find first { and last }
    start, end = out.find("{"), out.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(out[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"error": "could not parse claude output", "raw": out[:1000], "verdict": "ERROR"}


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(EDITOR_HTML.encode("utf-8"))
            return
        if self.path == "/profile":
            try:
                content = PROFILE_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                content = ""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/profile":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            PROFILE_PATH.write_text(body, encoding="utf-8")
            print(f"[profile] saved {len(body)} chars", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if self.path != "/screen":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"error":"bad json"}')
            return

        text = payload.get("text", "").strip()
        if not text:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b'{"error":"empty text"}')
            return

        print(f"[screen] {len(text)} chars from {payload.get('url', '?')}", flush=True)
        verdict = run_claude(text)
        print(f"[verdict] {verdict.get('verdict')} score={verdict.get('score')}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(verdict, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[http] {fmt % args}\n")


if __name__ == "__main__":
    print(f"resume_bot server listening on 0.0.0.0:{PORT}")
    print(f"bot dir: {BOT_DIR}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

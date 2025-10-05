# 07_add_audit_writer.ps1 — create audit_writer.py and wire API + Manager
$ErrorActionPreference = "Stop"
$Root = "D:\ChameleFX"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
function Backup($p){ if(Test-Path $p){ Copy-Item $p "$p.bak.$ts" -Force } }

# --- a) Write chamelefx/audit_writer.py (idempotent) ---
$pkgDir = Join-Path $Root "chamelefx"
if(!(Test-Path $pkgDir)){ New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null }
$audit = Join-Path $pkgDir "audit_writer.py"
Backup $audit
$code = @"
from __future__ import annotations
import datetime as _dt, hashlib as _hashlib, json as _json, os as _os, threading as _threading
from typing import Any, Dict, Optional
class AuditWriter:
    def __init__(self, root: Optional[str] = None, logs_dir: Optional[str] = None, rotate_daily: bool = True, max_bytes: int = 0):
        self.root = _os.path.abspath(root or "."); self.logs_dir = _os.path.join(self.root, (logs_dir or "logs"))
        self.rotate_daily = rotate_daily; self.max_bytes = int(max_bytes or 0); _os.makedirs(self.logs_dir, exist_ok=True)
        self._lock = _threading.RLock(); self._prev_hash_cache: Dict[str, str] = {}
    def _today_file(self) -> str: return _os.path.join(self.logs_dir, f"audit_{_dt.date.today():%Y%m%d}.jsonl")
    def _compute_hash(self, obj: Dict[str, Any]) -> str:
        core = {k: obj.get(k) for k in ("ts","actor","kind","payload","prev_hash")}
        return _hashlib.sha256(_json.dumps(core, sort_keys=True, separators=(",",":")).encode("utf-8")).hexdigest()
    def _last_hash(self, fn: str) -> Optional[str]:
        if fn in self._prev_hash_cache: return self._prev_hash_cache[fn]
        if not _os.path.exists(fn): return None
        try:
            size = _os.path.getsize(fn)
            with open(fn, "rb") as f:
                if size > 65536: f.seek(-65536, 2)
                tail = f.read().decode("utf-8", "ignore").splitlines()
            for line in reversed(tail):
                line = line.strip()
                if not line: continue
                obj = _json.loads(line); h = obj.get("hash")
                if h: self._prev_hash_cache[fn] = h; return h
        except Exception: return None
        return None
    def _maybe_rotate_size(self, fn: str) -> str:
        import os as _os2
        if self.max_bytes and _os2.path.exists(fn) and _os2.path.getsize(fn) >= self.max_bytes:
            base = _os2.path.splitext(fn)[0]; idx = 1
            while True:
                candidate = f"{base}.{idx}.jsonl"
                if not _os2.path.exists(candidate):
                    _os2.replace(fn, candidate); self._prev_hash_cache.pop(fn, None); break
                idx += 1
        return fn
    def event(self, actor: str, kind: str, payload: Dict[str, Any]) -> str:
        try:
            with self._lock:
                fn = self._today_file() if self.rotate_daily else _os.path.join(self.logs_dir, "audit.jsonl")
                fn = self._maybe_rotate_size(fn); prev = self._last_hash(fn)
                obj = {"ts": _dt.datetime.utcnow().timestamp(), "actor": str(actor), "kind": str(kind), "payload": payload or {}, "prev_hash": prev}
                h = self._compute_hash(obj); obj["hash"] = h
                with open(fn, "a", encoding="utf-8") as fh: fh.write(_json.dumps(obj, separators=(",",":")) + "\n")
                self._prev_hash_cache[fn] = h; return h
        except Exception: return ""
_writer: Optional[AuditWriter] = None
def get_writer() -> AuditWriter:
    global _writer
    if _writer is None: _writer = AuditWriter()
    return _writer
def log(actor: str, kind: str, payload: Dict[str, Any]) -> str:
    return get_writer().event(actor, kind, payload)
"@
Set-Content $audit $code -Encoding UTF8
Write-Host "[OK] audit_writer.py written at $audit"

# --- b) Wire FastAPI server: import + startup + middleware (idempotent) ---
$server = Join-Path $Root "app\api\server.py"
if(Test-Path $server){
  Backup $server
  $src = Get-Content $server -Raw
  if($src -notmatch "from chamelefx\.audit_writer import log as audit_log"){
    $src = "from chamelefx.audit_writer import log as audit_log`r`n" + $src
  }
  if($src -notmatch "@app\.on_event\(['""]startup['""]\)"){
    $startup = @"
@app.on_event("startup")
async def _audit_startup():
    try:
        audit_log("api","startup",{"msg":"FastAPI started"})
    except Exception:
        pass
"@
    $src += "`r`n$startup"
  }
  if($src -notmatch "@app\.middleware\('http'\)"):
    $mw = @"
from starlette.requests import Request
@app.middleware('http')
async def _audit_selected_requests(request: Request, call_next):
    try:
        if request.method in ('POST','PUT','DELETE'):
            p = str(request.url.path)
            if p.startswith('/api/v1/orders/market') or p.startswith('/api/v1/orders/pending') or p.startswith('/positions/close') or p.startswith('/guardrails/'):
                try:
                    body = await request.body()
                    audit_log("api","endpoint_call",{"path":p,"method":request.method,"body":body.decode('utf-8','ignore')[:4000]})
                except Exception:
                    pass
    except Exception:
        pass
    return await call_next(request)
"@
    $src += "`r`n$mw"
  }
  Set-Content $server $src -Encoding UTF8
  Write-Host "[OK] server.py wired"
} else {
  Write-Host "[WARN] server.py not found — skipped API wiring"
}

# --- c) Wire Manager: import + startup + exit (idempotent) ---
$mgr = Join-Path $Root "chamelefx\manager.py"
if(Test-Path $mgr){
  Backup $mgr
  $msrc = Get-Content $mgr -Raw
  if($msrc -notmatch "from chamelefx\.audit_writer import log as audit_log"){
    $msrc = "from chamelefx.audit_writer import log as audit_log`r`n" + $msrc
  }
  # ensure atexit present for shutdown log
  if($msrc -notmatch "(?m)^import\s+atexit\b"){
    $msrc = "import atexit`r`n" + $msrc
  }
  # add startup log inside def main() if found; else add at end guarded try
  if($msrc -match "(?ms)(def\s+main\s*\(\s*\)\s*:\s*\n)"){
    $msrc = $msrc -replace "(?ms)(def\s+main\s*\(\s*\)\s*:\s*\n)", "`$1    try:`r`n        audit_log('manager','startup',{'msg':'Manager started'})`r`n    except Exception:`r`n        pass`r`n"
  } elseif ($msrc -notmatch "audit_log\('manager','startup'"){
    $msrc += "`r`ntry:`r`n    audit_log('manager','startup',{'msg':'Manager started'})`r`nexcept Exception:`r`n    pass`r`n"
  }
  if($msrc -notmatch "atexit\.register\(_audit_on_exit\)"){
    $msrc += @"

def _audit_on_exit():
    try:
        audit_log('manager','shutdown',{'msg':'Manager exiting'})
    except Exception:
        pass
atexit.register(_audit_on_exit)
"
  }
  Set-Content $mgr $msrc -Encoding UTF8
  Write-Host "[OK] manager.py wired"
} else {
  Write-Host "[WARN] manager.py not found — skipped Manager wiring"
}

# tools/patch_py/apply_bundle_P_weekly_report.py
from __future__ import annotations
from pathlib import Path
import json, time, re, shutil

ROOT = Path(__file__).resolve().parents[2]
APP  = ROOT / "app" / "api"
CFX  = ROOT / "chamelefx"
RUN  = CFX / "runtime"
REP  = RUN / "reports"
REP.mkdir(parents=True, exist_ok=True)

def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip()+"\n", encoding="utf-8")
    print("[P] wrote", p)

CORE = r"""
from __future__ import annotations
from pathlib import Path
import json, time, platform

ROOT = Path(__file__).resolve().parents[1]
RUN  = ROOT / "runtime"
REP  = RUN / "reports"
REP.mkdir(parents=True, exist_ok=True)

def _read_json(p: Path, dflt):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dflt

def _router_penalty_preview(symbol: str, notional: float = 100_000.0):
    try:
        from chamelefx.router import cost_model as cm # Bundle L
        p = float(cm.cost_penalty_bps(symbol=symbol, notional=notional, venue=None, mode="p95"))
        return p
    except Exception:
        return 0.0

def _alpha_health():
    mon = _read_json(RUN / "alpha_monitor.json", {"symbols":{}, "ts": 0})
    out = {}
    for sym, rec in (mon.get("symbols") or {}).items():
        last = (rec.get("last") or {})
        stats = last.get("stats", {})
        regime = last.get("regime", {})
        out[sym] = {
            "snr": float(stats.get("snr", 0.0) or 0.0),
            "mean": float(stats.get("mean", 0.0) or 0.0),
            "stdev": float(stats.get("stdev", 0.0) or 0.0),
            "degrade": bool(last.get("degrade", False)),
            "regime": {"trend": str(regime.get("trend","unknown")), "vol": str(regime.get("vol","unknown"))}
        }
    return out, float(mon.get("ts", 0))

def _sizing_state():
    rsz = _read_json(RUN / "regime_sizing.json", {})
    mults = (rsz.get("multipliers") or {})
    bounds = (rsz.get("bounds") or {})
    fallback = float(rsz.get("fallback", 1.0))
    return {"multipliers": mults, "bounds": bounds, "fallback": fallback}

def _parity_state():
    par = _read_json(RUN / "parity_last.json", {})
    return {
        "drift": float(par.get("drift", 0.0) or 0.0),
        "ts": float(par.get("ts", 0) or 0),
        "meta": par.get("meta") or {}
    }

def _costs_summary():
    tab = _read_json(RUN / "router_costs.json", {"updated": 0, "symbols": {}})
    return tab

def build_weekly():
    ts = time.time()
    alpha, alpha_ts = _alpha_health()
    sizing = _sizing_state()
    parity = _parity_state()
    costs  = _costs_summary()

    symbols = sorted(list(alpha.keys()))
    penalties = {s: _router_penalty_preview(s) for s in symbols}

    report = {
        "ok": True,
        "ts": ts,
        "meta": {
            "host": platform.node(),
            "py": platform.python_version(),
            "alpha_ts": alpha_ts
        },
        "alpha": alpha,
        "sizing": sizing,
        "parity": parity,
        "costs": costs,
        "router_penalty_preview_bps": penalties
    }

    stamp = time.strftime("%Y%m%d_%H%M", time.localtime(ts))
    out_path = REP / f"weekly_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # keep a stable filename too
    latest = REP / "weekly_latest.json"
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(out_path), "latest": str(latest), "symbols": symbols, "ts": ts}
"""

API = r"""
from __future__ import annotations
from fastapi import APIRouter
from pathlib import Path
import json
from chamelefx.ops import weekly_report as wr

router = APIRouter()

@router.post("/ops/weekly_report/run")
def ops_weekly_report_run():
    return wr.build_weekly()

@router.get("/ops/weekly_report/latest")
def ops_weekly_report_latest():
    p = (Path(__file__).resolve().parents[2] / "chamelefx" / "runtime" / "reports" / "weekly_latest.json")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "error": "no_weekly_report"}
"""

def patch_server():
    sp = APP / "server.py"
    txt = sp.read_text(encoding="utf-8")
    m = re.match(r'(?s)(\s*from __future__ import [^\n]+\n)(.*)', txt)
    future, rest = (m.group(1), m.group(2)) if m else ("", txt)
    imp = "from app.api.ext_ops_weekly_report import router as weekly_report_router"
    inc = "app.include_router(weekly_report_router)"
    if imp not in rest:
        rest = imp + "\n" + rest
    if inc not in rest:
        rest += "\n" + inc + "\n"
    (APP/"server.py").write_text(future + rest, encoding="utf-8")
    print("[P] server.py patched (weekly_report_router)")

def main():
    w(CFX / "ops" / "weekly_report.py", CORE)
    w(APP / "ext_ops_weekly_report.py", API)
    patch_server()
    print("[P] Bundle P installed.")

if __name__ == "__main__":
    main()

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

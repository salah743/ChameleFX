from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json

from chamelefx.utils.atomic_json import read_json, write_json_atomic

ROOT = Path(__file__).resolve().parents[1]
CFX  = ROOT
RUN  = ROOT / "runtime"

# Minimal schema with safe defaults; extend as needed.
DEFAULT_CONFIG: Dict[str, Any] = {
    "api": {"host": "127.0.0.1", "port": 18124, "timeout_s": 15},
    "execution": {
        "max_spread_pips": 2.5,
        "news_blackout": False,
        "slippage_log": True
    },
    "portfolio": {
        "rebalance": "weekly",
        "correlation": 0.65,
        "risk_budget": 0.20
    },
    "guardrails": {
        "dd_throttle": 0.35,
        "daily_loss_cap": 0.06
    },
    "routing": {"twap": True},
    "scaling": {"queue": True},
    "capital": {"rebalance": "monthly"}
}

def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def validate_and_fix_config(cfg_path: Path) -> dict:
    cfg = read_json(cfg_path, {})
    fixed = _deep_merge(DEFAULT_CONFIG, cfg if isinstance(cfg, dict) else {})
    write_json_atomic(cfg_path, fixed)
    return fixed

def ensure_runtime_layout() -> dict:
    created = []
    for rel in ["runtime", "runtime/reports", "runtime/cache", "runtime/logs"]:
        p = ROOT / rel
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(str(p))
    # seed tiny files if missing
    seeds = {
        "runtime/alpha_monitor.json": {"symbols": {}, "ts": 0},
        "runtime/regime_sizing.json": {
            "multipliers":{
                "trend":{"low":1.1,"normal":1.0,"high":0.8},
                "range":{"low":0.9,"normal":1.0,"high":1.0},
                "unknown":{"low":1.0,"normal":1.0,"high":1.0}
            },
            "fallback":1.0,
            "bounds":{"min":0.70,"max":1.30},
            "nudge":{"step":0.005,"snr_boost":0.9,"snr_cut":0.25,"drift_cut":0.15,"drift_mul":0.5}
        }
    }
    for rel, val in seeds.items():
        p = ROOT / rel
        if not p.exists():
            write_json_atomic(p, val)
            created.append(str(p))
    return {"ok": True, "created": created}

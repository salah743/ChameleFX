
from pathlib import Path
from patchlib import project_root, backup_write

ROOT = project_root(Path(__file__))
p = ROOT / "app/api/server.py"
new_src = """from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Core routers
from app.api.mw_gate import Gatekeeper

# Hard imports (must exist in tree)
from app.api.ext_risk_status import router as risk_router
from app.api.ext_exec_quality import router as execq_router
from app.api.ext_alerts import router as alerts_router
from app.api.ext_actions import router as actions_router
from app.api.ext_portfolio_optimize import router as portopt_router
from app.api.ext_alpha_features import router as alpha_feat_router

# Optional imports guarded by try/except
try:
    from app.api.ext_alpha_trade_live import router as alpha_trade_router
except Exception:
    alpha_trade_router = None

# Customer/diagnostics and bundles
try:
    from app.api.ext_alpha_health import router as alpha_health_router
except Exception:
    alpha_health_router = None

try:
    from app.api.ext_bt_validate import router as bt_validate_router
except Exception:
    bt_validate_router = None

try:
    from app.api.ext_risk_plus import router as risk_plus_router
except Exception:
    risk_plus_router = None

try:
    from app.api.ext_customer_metrics import router as customer_metrics_router
except Exception:
    customer_metrics_router = None

try:
    from app.api.ext_router_costs import router as router_costs_router
except Exception:
    router_costs_router = None

try:
    from app.api.ext_alpha_monitor import router as alpha_monitor_router
except Exception:
    alpha_monitor_router = None

try:
    from app.api.ext_sizing_regime import router as sizing_regime_router
except Exception:
    sizing_regime_router = None

try:
    from app.api.ext_alpha_feedback import router as alpha_feedback_router
except Exception:
    alpha_feedback_router = None

try:
    from app.api.ext_ops_weekly_report import router as weekly_report_router
except Exception:
    weekly_report_router = None

try:
    from app.api.ext_mt5_resilience import router as mt5_resilience_router
except Exception:
    mt5_resilience_router = None

# Bundle R
try:
    from app.api.ext_diag_snapshot import router as diag_router
    from app.api.ext_runtime_safety import wire as runtime_wire
except Exception:
    diag_router = None
    def runtime_wire(app):  # no-op
        return

# Other execution/exec routers
try:
    from app.api.ext_exec_router import router as exec_router
except Exception:
    exec_router = None

# Construct app
app = FastAPI(title="ChameleFX API", version="KO6")

# Middleware
app.add_middleware(Gatekeeper, global_limit=8, per_path_qps=6.0, sequential_paths=("/alpha/", "/portfolio/"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/debug/routes")
def debug_routes():
    out = []
    for r in app.routes:
        try:
            out.append(getattr(r, "path", str(r)))
        except Exception:
            out.append(str(r))
    return {"ok": True, "routes": out}

# Mount core routers
app.include_router(risk_router)
app.include_router(execq_router)
app.include_router(alerts_router)
app.include_router(actions_router)
app.include_router(portopt_router)
app.include_router(alpha_feat_router)
if alpha_trade_router is not None:
    app.include_router(alpha_trade_router)

# Mount optional routers (if available)
for r in [
    alpha_health_router,
    bt_validate_router,
    risk_plus_router,
    customer_metrics_router,
    router_costs_router,
    alpha_monitor_router,
    sizing_regime_router,
    alpha_feedback_router,
    weekly_report_router,
    mt5_resilience_router,
    exec_router,
]:
    if r is not None:
        app.include_router(r)

# Bundle R wiring (runtime safety) and diag router
try:
    runtime_wire(app)
except Exception:
    pass
if diag_router is not None:
    app.include_router(diag_router)
"""
backup_write(p, new_src)
print("[OK] server.py replaced with clean implementation")


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
try:
    from app.api.mw_gate import Gatekeeper  # type: ignore
except Exception:
    Gatekeeper = None  # type: ignore

app = FastAPI(title="ChameleFX API", version="KO-FullFix")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1","http://localhost"], allow_methods=["*"], allow_headers=["*"])
if Gatekeeper:
    app.add_middleware(Gatekeeper, global_limit=8, per_path_qps=6.0, sequential_paths=("/alpha/","/portfolio/"))

@app.get("/health")
def health(): return {"ok": True}

@app.get("/debug/routes")
def debug_routes(): return {"ok": True, "routes": [getattr(r,"path",str(r)) for r in app.routes]}

def _try_include(module_path: str, attr: str = "router") -> bool:
    try:
        mod = __import__(module_path, fromlist=[attr]); r = getattr(mod, attr, None)
        if r is not None: app.include_router(r); print(f"[API] loaded {module_path}"); return True
        else: print(f"[API] {module_path} has no '{attr}'")
    except Exception as e:
        print(f"[API] NOT loaded {module_path}: {e!r}")
    return False

for mod in [
    "app.api.ext_alpha_features","app.api.ext_alpha_weight","app.api.ext_alpha_trade",
    "app.api.ext_portfolio_apply","app.api.ext_portfolio_opt","app.api.ext_perf",
    "app.api.ext_mt5_resilience","app.api.ext_replay_db","app.api.ext_diag_snapshot",
    "app.api.ext_ops_effective_config","app.api.ext_ops_weekly_report",
]:
    _try_include(mod)

try:
    from app.api.ext_runtime_safety import wire as runtime_wire  # type: ignore
    runtime_wire(app)
except Exception:
    pass

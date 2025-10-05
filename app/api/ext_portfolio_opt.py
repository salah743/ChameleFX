
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict
router = APIRouter(prefix="/portfolio/opt", tags=["portfolio"])
class OptReq(BaseModel):
    method: str = "risk_parity"
    symbols: List[str] | None = None
    target: float | None = None
def _solve_local(method: str, symbols: List[str] | None, target: float | None) -> Dict[str,float]:
    syms = symbols or ["EURUSD","GBPUSD","USDJPY"]; m = (method or "").lower()
    if m in ("risk_parity","rp"): w = 1.0/len(syms); return {s: round(w,6) for s in syms}
    if m in ("vol_target","vt","vol"): w = min(1.0,max(0.0,float(target or 0.10)))/len(syms); return {s: round(w,6) for s in syms}
    base=0.6; rest=(1.0-base)/max(1,len(syms)-1); out={syms[0]:round(base,6)}
    for s in syms[1:]: out[s]=round(rest,6); return out
try:
    from chamelefx.portfolio.optimizer import solve as solve_opt
except Exception:
    solve_opt = None
@router.post("/solve")
def solve(req: OptReq):
    if solve_opt: res = solve_opt(req.method, req.symbols, target=(req.target or 0.10))
    else: res = _solve_local(req.method, req.symbols, req.target)
    return {"ok": True, "weights": res}

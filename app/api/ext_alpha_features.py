
from fastapi import APIRouter
from pydantic import BaseModel
router = APIRouter(prefix="/alpha", tags=["alpha"])
class FeatureReq(BaseModel): symbol: str
try:
    from chamelefx.alpha import features as fx
except Exception:
    fx = None
@router.post("/features/compute")
def compute_features(req: FeatureReq):
    symbol = (req.symbol or "EURUSD")
    try:
        if fx and hasattr(fx,"compute"): res = fx.compute(symbol=symbol)
        else: res = {"raw": {}, "norm": {}, "meta": {"src": "stub"}}
        if not isinstance(res, dict): res = {"raw": {}, "norm": {}, "meta": {"src": "coerced"}}
        res.setdefault("ok", True); res["symbol"] = symbol; return res
    except Exception as e:
        return {"ok": False, "symbol": symbol, "error": str(e), "raw": {}, "norm": {}}

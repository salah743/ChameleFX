from __future__ import annotations
from chamelefx.log import get_logger
from chamelefx.utils.admin_gate import require_admin
from fastapi import Depends
from fastapi import APIRouter
from chamelefx.ops import diag_snapshot as diag

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("/ops/diag/health")
def ops_diag_health():
    return diag.health()

@router.get("/ops/diag/snapshot")
def ops_diag_snapshot():
    return diag.snapshot()

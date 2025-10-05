from __future__ import annotations
import numpy as np, math
from typing import Dict, Any

def sharpe(ret)->float:
    r=np.asarray(ret, dtype=float)
    if r.size==0: return 0.0
    return float(np.mean(r)/(np.std(r)+1e-9)*math.sqrt(252*24*60))

def sortino(ret)->float:
    r=np.asarray(ret, dtype=float)
    if r.size==0: return 0.0
    downside=np.std(np.clip(r, None, 0.0))
    return float(np.mean(r)/(downside+1e-9)*math.sqrt(252*24*60))

def max_drawdown(eq)->float:
    e=np.asarray(eq, dtype=float)
    return float((np.maximum.accumulate(e)-e).max() if e.size else 0.0)

def pvalue_bootstrap(ret, n=1000, seed=42)->float:
    """Right-tail: mean>0 significance by bootstrap resampling."""
    r=np.asarray(ret, dtype=float); 
    if r.size<10: return 1.0
    rng=np.random.default_rng(seed)
    base=np.mean(r)
    cnt=0
    for _ in range(n):
        s=r[rng.integers(0, r.size, size=r.size)]
        if np.mean(s)>=base: cnt+=1
    return float(1.0 - cnt/max(1,n))

def pvalue_permutation(ret, sig, n=1000, seed=43)->float:
    """Null: signal independent of returns. Permute returns vs signals."""
    r=np.asarray(ret, dtype=float); s=np.asarray(sig, dtype=float)
    if r.size==0 or r.size!=s.size: return 1.0
    base=np.mean(r*s)
    rng=np.random.default_rng(seed)
    cnt=0
    for _ in range(n):
        rp=r[rng.permutation(r.size)]
        if np.mean(rp*s)>=base: cnt+=1
    return float(1.0 - cnt/max(1,n))

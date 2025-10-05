from __future__ import annotations
# == CFX Backtester: metrics upgrade ==

import os, time, math, json, statistics as st
from typing import List, Dict, Any, Callable, Tuple

try:
    from chamelefx.audit_writer import log as audit_log
except Exception:
    def audit_log(*a, **k): pass

def _safe(listlike): return [float(x) for x in listlike if x is not None]

def _max_drawdown(equity: List[float])->Tuple[float,float,int,int]:
    """Returns (max_dd, peak, trough, idx_peak, idx_trough) with dd as positive number."""
    if not equity: return (0.0,0.0,-1,-1)
    max_dd=0.0; peak=equity[0]; p_i=0; t_i=0
    for i,v in enumerate(equity):
        if v>peak: peak=v; p_i=i
        dd=peak - v
        if dd>max_dd: max_dd=dd; t_i=i
    return (float(max_dd), float(peak), int(p_i), int(t_i))

class Trade:
    def __init__(self,symbol,side,lots,price,sl=None,tp=None):
        self.symbol=symbol; self.side=side; self.lots=float(lots)
        self.entry=float(price); self.sl=sl; self.tp=tp
        self.open_ts=time.time(); self.close_ts=None
        self.exit=None; self.pnl=0.0; self.r=None

    def check_exit(self,price):
        p=float(price)
        if self.side=="buy":
            if self.sl and p<=self.sl: return ("sl",p)
            if self.tp and p>=self.tp: return ("tp",p)
        if self.side=="sell":
            if self.sl and p>=self.sl: return ("sl",p)
            if self.tp and p<=self.tp: return ("tp",p)
        return None

    def close(self,reason,price,point_value=10000.0):
        p=float(price); self.exit=p; self.close_ts=time.time()
        if self.side=="buy":
            self.pnl=(p-self.entry)*self.lots*point_value
        else:
            self.pnl=(self.entry-p)*self.lots*point_value
        if self.sl and self.entry:
            risk_per_lot = abs(self.entry - self.sl) * point_value
            denom = max(1e-9, risk_per_lot*self.lots)
            self.r = float(self.pnl/denom)
        return {"symbol":self.symbol,"side":self.side,"entry":self.entry,"exit":p,"lots":self.lots,"pnl":self.pnl,"reason":reason,"r":self.r}

class Backtester:
    def __init__(self,symbol="EURUSD",strategy:Callable=None,spread=0.0002,commission=0.0,slippage=0.0,point_value=10000.0):
        self.symbol=symbol; self.strategy=strategy
        self.spread=float(spread); self.commission=float(commission); self.slippage=float(slippage)
        self.point_value=float(point_value)
        self.trades=[]; self.balance=10000.0; self.equity=[self.balance]; self.history=[]

    def run(self,ticks:List[Dict[str,Any]]):
        open_positions=[]
        bal=self.balance
        for t in ticks:
            px=float(t.get("p",0))
            # strategy decision
            dec=None
            if self.strategy: dec=self.strategy({"price":px,"ts":t.get("ts")})
            if dec and dec.get("action") in ("buy","sell"):
                side=dec["action"]; lots=float(dec.get("lots",0.1))
                sl,tp=dec.get("sl"),dec.get("tp")
                fill=px+(self.spread if side=="buy" else -self.spread)
                if self.slippage: fill+=self.slippage*(1 if side=="buy" else -1)
                tr=Trade(self.symbol,side,lots,fill,sl,tp)
                open_positions.append(tr)
                audit_log("backtest","entry",{"symbol":self.symbol,"side":side,"price":fill})
            # check exits
            for tr in list(open_positions):
                exit=tr.check_exit(px)
                if exit:
                    reason,price=exit
                    rec=tr.close(reason,price,point_value=self.point_value)
                    rec["commission"]=-self.commission
                    bal+=rec["pnl"]-self.commission
                    self.history.append(rec)
                    open_positions.remove(tr)
                    audit_log("backtest","exit",rec)
            self.equity.append(bal)
        self.balance=bal
        return {"balance":self.balance,"trades":self.history,"equity":self.equity}

def metrics(summary:dict)->dict:
    eq=_safe(summary.get("equity",[]))
    tr=summary.get("trades",[])
    ret=[(eq[i]-eq[i-1]) for i in range(1,len(eq))] if len(eq)>1 else []
    maxdd,peak,pi,ti=_max_drawdown(eq)
    wins=[x for x in tr if x.get("pnl",0)>0]; losses=[x for x in tr if x.get("pnl",0)<=0]
    rlist=[x.get("r") for x in tr if x.get("r") is not None]
    m={
        "n_trades":len(tr),
        "winrate": (len(wins)/max(1,len(tr))) if tr else 0.0,
        "avg_pnl": (sum(x.get("pnl",0) for x in tr)/len(tr)) if tr else 0.0,
        "avg_r": (sum(rlist)/len(rlist)) if rlist else None,
        "max_drawdown": maxdd,
        "equity_end": eq[-1] if eq else None,
        "sharpe": ( (st.mean(ret)/(st.pstdev(ret)+1e-9))*math.sqrt(252*24*60) ) if len(ret)>2 else None,
        "sortino": ( (st.mean([x for x in ret if x>0])/(st.pstdev([x for x in ret if x<0]) + 1e-9))*math.sqrt(252*24*60) ) if len(ret)>2 and any(x<0 for x in ret) else None
    }
    return m

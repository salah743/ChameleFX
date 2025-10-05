from __future__ import annotations
def slices(total_qty: float, n: int) -> list[float]:
    n = max(1, int(n))
    slice_sz = float(total_qty)/n
    return [slice_sz]*n

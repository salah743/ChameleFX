# -*- coding: utf-8 -*-
"""
Back-compat aliasing so old code like:
  from chamelefx.Manager_Components.bus import Bus
keeps working while we migrate to:
  from chamelefx.manager_core.components.bus import Bus
"""
import sys, types, importlib

_CANON = "chamelefx.manager_core.components"
_LEGACY = "chamelefx.Manager_Components"

def _alias_legacy():
    try:
        mod = importlib.import_module(_CANON)  # ensure canonical package is importable
    except Exception:
        return
    pkg = types.ModuleType(_LEGACY)
    pkg.__path__ = []  # mark as namespace-like
    sys.modules[_LEGACY] = pkg

    # expose canonical submodules under legacy path
    for name in ("bus", "api_poller", "updater"):
        try:
            sub = importlib.import_module(f"{_CANON}.{name}")
            sys.modules[f"{_LEGACY}.{name}"] = sub
        except Exception:
            pass

_alias_legacy()


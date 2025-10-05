import os, json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# ---------------------------------------------------------------------
# Required tree map (folders + must-have files)
# ---------------------------------------------------------------------
TREE = {
    "app/api": [
        "server.py",
        "ext_core_stubs.py",
        "ext_perf_v2.py",
        "ext_alpha_features.py",
        "ext_alpha_trade_live.py",
        "ext_portfolio_opt.py",
        "__init__.py",
    ],
    "chamelefx": [
        "__init__.py", "manager.py", "setup_gui.py"
    ],
    "chamelefx/ui": [
        "__init__.py", "dashboard.py", "alpha_tab.py",
        "portfolio_tab.py", "order_blotter.py", "perf_tab.py"
    ],
    "chamelefx/alpha": [
        "__init__.py", "features.py", "weighting.py", "ensemble.py"
    ],
    "chamelefx/portfolio": [
        "__init__.py", "optimizer.py", "rebalance.py"
    ],
    "chamelefx/performance": [
        "__init__.py", "live_metrics.py", "backtester.py"
    ],
    "chamelefx/ops": [
        "__init__.py", "risk.py", "watchdog.py"
    ],
    "chamelefx/runtime": [
        "__init__.py", "account.json", "positions.json", "orders_recent.json"
    ],
    "data/history": [],
    "data/logs": [],
    "tools/patches": [],
    "tools/patch_py": [],
}

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def ensure_file(path, content=""):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def ensure_json(path, obj):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)

# ---------------------------------------------------------------------
# Build skeleton
# ---------------------------------------------------------------------
for folder, files in TREE.items():
    full_folder = os.path.join(ROOT, folder)
    os.makedirs(full_folder, exist_ok=True)

    for f in files:
        fp = os.path.join(full_folder, f)
        if f.endswith("__init__.py"):
            ensure_file(fp, "# package marker\n")
        elif f.endswith(".json"):
            if f == "account.json":
                ensure_json(fp, {"balance": 100000.0, "equity": 100000.0})
            elif f == "positions.json":
                ensure_json(fp, [])
            elif f == "orders_recent.json":
                ensure_json(fp, [])
        else:
            if not os.path.exists(fp):
                ensure_file(fp, f"# {f} placeholder - implement logic\n")

# Root-level musts
ensure_file(os.path.join(ROOT, "README.md"), "# ChameleFX\n")
ensure_file(os.path.join(ROOT, "requirements.txt"), "fastapi\nuvicorn\n")

print("[OK] Skeleton ensured.")

import os, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# Master whitelist (folders + required files)
WHITELIST = {
    "": ["README.md", "requirements.txt", "config.json",
         "run_live.bat", "run_guarded_one.bat"],
    "py-portable": None,  # keep whole portable Python
    "app/api": [
        "server.py", "ext_core_stubs.py", "ext_perf_v2.py",
        "ext_alpha_features.py", "ext_alpha_trade_live.py",
        "ext_portfolio_opt.py", "__init__.py"
    ],
    "chamelefx": ["__init__.py", "manager.py", "setup_gui.py"],
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
    "data/history": None,   # keep entire history folder
    "data/logs": None,      # keep logs
    "tools/patches": None,  # keep empty folder
    "tools/patch_py": [
        "apply_batch_REBUILD_SKELETON.py",
        "apply_batch_CLEAN_TREE.py",
        "audit_integrity.py"
    ],
}

def is_whitelisted(path_rel):
    for folder, files in WHITELIST.items():
        if not path_rel.startswith(folder):
            continue
        if files is None:
            return True  # keep all in this folder
        # check file match
        base = os.path.basename(path_rel)
        if base in files:
            return True
    return False

# Traverse and delete
for dirpath, dirnames, filenames in os.walk(ROOT, topdown=False):
    rel = os.path.relpath(dirpath, ROOT).replace("\\", "/")
    if rel == ".":
        rel = ""
    # Remove files
    for f in filenames:
        path_rel = os.path.join(rel, f).replace("\\", "/")
        if not is_whitelisted(path_rel):
            try:
                os.remove(os.path.join(dirpath, f))
                print("[DEL]", path_rel)
            except Exception as e:
                print("[ERR]", path_rel, e)
    # Remove dirs if empty and not whitelisted
    if rel not in WHITELIST and not os.listdir(dirpath):
        try:
            shutil.rmtree(dirpath)
            print("[RMDIR]", rel)
        except Exception as e:
            print("[ERRDIR]", rel, e)

print("[OK] Cleanup complete.")


from pathlib import Path
import sys, importlib

order = [
    "Fix_0001_Normalize_Paths",
    "Fix_0002_AlphaConfidence_Signature",
    "Fix_0003_GUI_BOM_and_AlphaTab",
    "Fix_0004_Logging_and_Excepts",
    "Fix_0005_Add_HTTP_Timeouts",
    "Fix_0006_Gate_Ops_Routes",
    "Fix_0007_CORS_Localhost",
    "Fix_0008_Readme_Notes",
]

def main():
    base = Path(__file__).parent
    sys.path.insert(0, str(base))
    for name in order:
        print(f"\n=== Running {name} ===")
        importlib.invalidate_caches()
        importlib.import_module(name)
    print("\n[OK] All patches executed.")

if __name__ == "__main__":
    main()


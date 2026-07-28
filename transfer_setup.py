#!/usr/bin/env python3
"""
Quick setup checker for Predator_5 transfer pipeline.

Run this first to verify all dependencies and files are present.
"""

import os
import sys
import json

def check(desc, condition, hint=""):
    status = "✓" if condition else "✗"
    print(f"  {status} {desc}")
    if not condition and hint:
        print(f"      → {hint}")
    return condition

def main():
    print("\n=== Predator_5 Transfer Setup Checker ===\n")

    ok = True

    # Python version
    print("Python & Dependencies:")
    ok &= check("Python 3.8+", sys.version_info >= (3, 8))

    try:
        import numpy
        ok &= check("numpy", True)
    except ImportError:
        ok &= check("numpy", False, "pip install numpy")

    try:
        from sklearn.ensemble import RandomForestClassifier
        ok &= check("scikit-learn", True)
    except ImportError:
        ok &= check("scikit-learn", False, "pip install scikit-learn")

    # Files
    print("\nFiles in current directory:")
    ok &= check("predator5.py", os.path.isfile("predator5.py"),
                "Copy from outputs/predator5.py")
    ok &= check("predator5_transfer.py", os.path.isfile("predator5_transfer.py"),
                "Copy from outputs/predator5_transfer.py")
    ok &= check("predator5_bridge.py", os.path.isfile("predator5_bridge.py"),
                "Copy from outputs/predator5_bridge.py")
    ok &= check("set.mm", os.path.isfile("set.mm"),
                "Download from https://github.com/metamath/set.mm/blob/develop/set.mm")

    # Stage 1 output (ranker.json)
    print("\nOptional (produced by workflow):")
    if os.path.isfile("ranker.json"):
        try:
            with open("ranker.json") as f:
                data = json.load(f)
            has_ranker = any(r.get("ranker", {}).get("model") == "logistic"
                           for r in data.get("results", []))
            check("ranker.json with logistic weights", has_ranker)
        except:
            check("ranker.json (valid JSON)", False)
    else:
        print("  • ranker.json (will be created by predator5.py compare)")

    # Stage 2 output (theorems_setmm.json)
    if os.path.isfile("theorems_setmm.json"):
        try:
            with open("theorems_setmm.json") as f:
                data = json.load(f)
            n = len(data)
            check(f"theorems_setmm.json ({n} theorems)", n > 0)
        except:
            check("theorems_setmm.json (valid JSON)", False)
    else:
        print("  • theorems_setmm.json (will be created by predator5_transfer.py load-set-mm)")

    print("\n=== Ready? ===\n")

    if ok:
        print("✓ All checks passed. Run the workflow:\n")
        print("  1. python predator5.py compare --depth 4 --out ranker.json")
        print("  2. python predator5_transfer.py load-set-mm")
        print("  3. python predator5_bridge.py evaluate --ranker ranker.json\n")
    else:
        print("✗ Some checks failed. Fix the issues above.\n")

if __name__ == "__main__":
    main()

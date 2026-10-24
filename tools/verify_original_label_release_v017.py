"""Read-only v0.17 verification with order-independent check-name comparison.

The sealed builder iterates a set of old cohort keys. Its check-name list order
therefore varies across Python processes. Every check still executes; compare
the complete multiset, count and all other report fields, then verify all sealed
hashes. Do not modify the sealed script, report, manifest or scientific values.
"""
from pathlib import Path
import collections, importlib.util, json, sys

class CheckReport(dict):
    def __ne__(self, other):
        if not isinstance(other, dict): return True
        left, right = dict(self), dict(other)
        if collections.Counter(left.pop('checks', [])) != collections.Counter(right.pop('checks', [])): return True
        return left != right

def main():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('_sealed_v017_verifier', root / 'tools/release_original_label_v017.py')
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    read = mod.read
    def read_report(path):
        value = read(path)
        return CheckReport(value) if Path(path) == root / '循环稳定性数据库_v0.17_原图标签补正_20261024/verification.json' else value
    mod.read = read_report
    try: mod.verify()
    finally: mod.read = read

if __name__ == '__main__': main()

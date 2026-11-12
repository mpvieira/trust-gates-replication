"""G2 test-independence + G3 own-suite sensitivity: mutate only the PR's changed lines, run
(G2) the package test suite and (G3) only the tests the PR itself added/modified."""
import ast, copy, sys, json, shutil, subprocess
from pathlib import Path
from common import changed_lines, package_root, Evidence, run

class Mutator(ast.NodeTransformer):
    """Enumerate single-point mutants on target lines. Each call to visit with index k applies the k-th mutation."""
    CMP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
           ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
    BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
    def __init__(self, lines, target=None):
        self.lines, self.target, self.count, self.desc = lines, target, 0, None
    def hit(self, node, desc):
        if getattr(node, "lineno", None) not in self.lines: return False
        self.count += 1
        if self.target == self.count - 1:
            self.desc = f"L{node.lineno}: {desc}"; return True
        return False
    def visit_Compare(self, node):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            if type(op) in self.CMP and self.hit(node, f"{type(op).__name__} -> {self.CMP[type(op)].__name__}"):
                node.ops[i] = self.CMP[type(op)]()
        return node
    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self.hit(node, "and<->or"): node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return node
    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self.hit(node, "remove not"): return node.operand
        return node
    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in self.BIN and self.hit(node, f"{type(node.op).__name__} -> {self.BIN[type(node.op)].__name__}"):
            node.op = self.BIN[type(node.op)]()
        return node
    def visit_Constant(self, node):
        v = node.value
        if isinstance(v, bool) and self.hit(node, f"{v} -> {not v}"): node.value = not v
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and self.hit(node, f"{v} -> {v+1}"): node.value = v + 1
        elif isinstance(v, str) and v and self.hit(node, f"str {v[:20]!r} -> mutated"): node.value = v + "_MUT"
        return node
    def visit_Return(self, node):
        self.generic_visit(node)
        if node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None) and self.hit(node, "return X -> return None"):
            node.value = ast.Constant(None)
        return node
    def visit_Raise(self, node):
        if self.hit(node, "remove raise"): return ast.Pass()
        return node
    def visit_If(self, node):
        self.generic_visit(node)
        if self.hit(node, "negate if-condition"): node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        return node

def gen_mutants(path, lines):
    src = Path(path).read_text(encoding="utf-8-sig"); tree = ast.parse(src)
    n = Mutator(lines); n.visit(copy.deepcopy(tree)); total = n.count
    for k in range(total):
        m = Mutator(lines, target=k); t = m.visit(copy.deepcopy(tree)); ast.fix_missing_locations(t)
        yield m.desc, ast.unparse(t)

import os
EXTRA = os.environ.get("EXTRA_PYTEST_ARGS", "").split()
NO_PYC = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

def drop_pyc(path):
    """Delete cached bytecode for a source file. A .pyc is reused when the source's mtime (whole seconds) and size match;
    consecutive mutants of equal size written within one second would otherwise run the previous mutant's code."""
    for pyc in (Path(path).parent / "__pycache__").glob(Path(path).stem + ".*.pyc"):
        try: pyc.unlink()
        except OSError: pass

def pytest_ok(pkg, args, timeout=600):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *EXTRA, *args],
                       cwd=pkg, capture_output=True, text=True, timeout=timeout, env=NO_PYC)
    return r.returncode == 0, r

def main(repo, commit, pr, outdir, test_args=None):
    src, tests = changed_lines(repo, commit)
    pkg = package_root(repo, next(iter(src)))
    test_args = test_args or ["tests"]
    own_tests = [str(Path(repo, t)) for t in tests if Path(repo, t).exists() and str(Path(repo, t)).startswith(str(pkg))]
    ref = dict(repo="Azure/azure-sdk-for-python", pr=pr, commit=commit, files=list(src))
    g2 = Evidence("G2", "test_independence_mutation", ref); g3 = Evidence("G3", "own_suite_sensitivity", ref)
    ok, r = pytest_ok(pkg, test_args)
    assert ok, "baseline suite not green:\n" + r.stdout[-2000:]
    if own_tests:
        ok2, _ = pytest_ok(pkg, own_tests); assert ok2, "PR's own tests not green"
    for ev in (g2, g3):
        ev.rec["assumptions"] = [f"baseline suite green at {commit} ({' '.join(test_args)})",
                                 "mutants confined to lines added/modified by the PR; formatting/comments lost via ast.unparse",
                                 "test order-dependence and flakiness not controlled"]
    results = []
    for path, lines in src.items():
        full = Path(repo, path); backup = full.read_text()
        try:
            drop_pyc(full)
            for desc, code in gen_mutants(full, lines):
                full.write_text(code); drop_pyc(full)
                killed_full, _ = pytest_ok(pkg, test_args); killed_full = not killed_full
                if own_tests:
                    killed_own, _ = pytest_ok(pkg, own_tests); killed_own = not killed_own
                else:
                    killed_own = None
                results.append(dict(file=path, mutant=desc, killed_by_suite=killed_full, killed_by_pr_tests=killed_own))
                print(f"  {path.split('/')[-1]} {desc:45s} suite={'K' if killed_full else 'SURVIVED'} own={'K' if killed_own else ('n/a' if killed_own is None else 'SURVIVED')}", flush=True)
        finally:
            full.write_text(backup); drop_pyc(full)
    n = len(results); ks = sum(r["killed_by_suite"] for r in results)
    g2.rec["exercised"] = [f"{n} mutants on {sum(len(l) for l in src.values())} changed lines across {len(src)} files; full package suite ({' '.join(test_args)})"]
    g2.rec["mutation_score"] = round(ks / n, 2) if n else None
    for r_ in results:
        if not r_["killed_by_suite"]: g2.finding(kind="surviving_mutant", **{k: r_[k] for k in ("file","mutant")})
    g2.rec["not_evaluated"] = ["equivalent-mutant analysis (surviving mutants need manual review)", "lines outside the PR diff",
                               "mutation operators beyond the 9 implemented (no statement deletion, no call-argument mutation)"]
    if own_tests:
        ko = sum(bool(r["killed_by_pr_tests"]) for r in results)
        g3.rec["exercised"] = [f"{n} mutants; PR-authored/modified tests only: {[Path(t).name for t in own_tests]}"]
        g3.rec["own_suite_detection_rate"] = round(ko / n, 2) if n else None
        for r_ in results:
            if not r_["killed_by_pr_tests"]: g3.finding(kind="undetected_by_pr_tests", **{k: r_[k] for k in ("file","mutant")})
        g3.rec["not_evaluated"] = ["whether PR tests were AI-generated alongside the code (assumed: same author)", "equivalent mutants"]
    else:
        g3.rec["exercised"] = ["none: PR added or modified no test files"]
        g3.rec["result"] = "no_pr_tests"; g3.rec["not_evaluated"] = ["own-suite sensitivity: PR shipped without tests; only pre-existing tests exercised the change"]
    g2.rec["mutants"] = results
    g2.save(Path(outdir, f"pr{pr}_G2.json")); g3.save(Path(outdir, f"pr{pr}_G3.json"))
    print(json.dumps(dict(mutants=n, mutation_score=g2.rec["mutation_score"], own_rate=g3.rec.get("own_suite_detection_rate"), own_tests=[Path(t).name for t in own_tests])))

if __name__ == "__main__":
    repo, commit, pr, outdir = sys.argv[1:5]; main(repo, commit, pr, outdir, sys.argv[5:] or None)

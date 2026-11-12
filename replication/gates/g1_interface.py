"""G1 Interface reality gate: do the names, modules and attributes the changed lines reference actually exist?"""
import ast, importlib, importlib.util, sys, json
from pathlib import Path
from common import changed_lines, Evidence, run

def check(repo, commit, pr, outdir):
    src, _ = changed_lines(repo, commit)
    ev = Evidence("G1", "interface_reality", dict(repo="Azure/azure-sdk-for-python", pr=pr, commit=commit, files=list(src)))
    ev.rec["assumptions"] = ["package installed in the analysis environment at the PR's own dependency pins",
                             "attribute existence checked against the installed module, not the version pinned in CI"]
    for path, lines in src.items():
        full = Path(repo, path); tree = ast.parse(full.read_text(encoding="utf-8-sig"))
        # 1. pyflakes on the whole file: undefined names anywhere the PR could have introduced
        pf = run([sys.executable, "-m", "pyflakes", str(full)])
        for l in pf.stdout.splitlines():
            if "undefined name" in l or "imported but unused" not in l and "undefined" in l:
                ln = int(l.split(":")[1]); 
                if ln in lines: ev.finding(file=path, line=ln, kind="undefined_name", detail=l.split(":",3)[-1].strip())
        ev.rec["exercised"].append(f"{path}: pyflakes undefined-name scan, restricted to {len(lines)} changed lines")
        # 2. imports on changed lines resolve; imported names exist in the module
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    aliases[a.asname or a.name.split(".")[0]] = a.name
                    if node.lineno in lines and importlib.util.find_spec(a.name) is None:
                        ev.finding(file=path, line=node.lineno, kind="unresolvable_import", detail=a.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.lineno in lines:
                    try:
                        mod = importlib.import_module(node.module)
                        for a in node.names:
                            if a.name != "*" and not hasattr(mod, a.name) and importlib.util.find_spec(f"{node.module}.{a.name}") is None:
                                ev.finding(file=path, line=node.lineno, kind="missing_symbol", detail=f"{node.module}.{a.name}")
                    except Exception as e:
                        ev.finding(file=path, line=node.lineno, kind="unresolvable_import", detail=f"{node.module}: {e}")
                for a in node.names: aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        # 3. module.attr accesses on changed lines against real modules
        n_attr = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.lineno in lines and isinstance(node.value, ast.Name) and node.value.id in aliases:
                target = aliases[node.value.id]
                try:
                    mod = importlib.import_module(target); n_attr += 1
                    if not hasattr(mod, node.attr):
                        ev.finding(file=path, line=node.lineno, kind="missing_attribute", detail=f"{target}.{node.attr}")
                except Exception:
                    pass
        ev.rec["exercised"].append(f"{path}: {n_attr} module-attribute references on changed lines resolved against installed modules")
    ev.rec["not_evaluated"] = ["method calls on objects of inferred type (no type inference performed)",
                               "HTTP endpoints, service API versions, and config keys referenced as strings",
                               "packages added to manifests (checked by pip install, not by this gate)"]
    return ev.save(Path(outdir, f"pr{pr}_G1.json"))

if __name__ == "__main__":
    repo, commit, pr, outdir = sys.argv[1:5]
    r = check(repo, commit, pr, outdir); print(json.dumps({k: r[k] for k in ("result","findings","exercised")}, indent=1))

#!/usr/bin/env python3
"""Run the trust-gate experiments for the PRs listed in experiments.yaml.

Usage (with the venv active, from this directory; `--help` on any command for its options):

    python run_experiments.py list                  # configured PRs, hypotheses, gate scripts, environments
    python run_experiments.py setup                 # install requirements + NLTK data, clone the repo (sparse, treeless), install packages
    python run_experiments.py run                   # run every enabled PR: baseline tests, G1, G2/G3, extra gates, G4
    python run_experiments.py run --prs 44844,41852 # only these PRs, regardless of `enabled`
    python run_experiments.py run --gates G1,G2     # subset of gates (G2 and G3 always together); --dry-run to print the plan
    python run_experiments.py summary               # table of results from the evidence directory
    python run_experiments.py compare               # diff this run's records against ../results/evidence/ (enabled PRs, or --prs)
    python run_experiments.py clean results|clone|all   # remove generated state (asks first; -y to skip)

Layout: this directory holds experiments.yaml, gates/ and this script; the work directory (-w/--work-dir, $W, default: this
directory) holds azsdk/ (the clone) and evidence/ (this run's results). Shipped records are read from ../results/evidence/.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = Path(__file__).resolve().parent
# Work directory: --work-dir, else $W, else the directory this script is in (running in place is fine).
def _pick_w(argv):
    for i, a in enumerate(argv):
        if a in ("-w", "--work-dir") and i + 1 < len(argv): return Path(argv[i + 1]).expanduser().resolve()
        if a.startswith("--work-dir="): return Path(a.split("=", 1)[1]).expanduser().resolve()
    return Path(os.environ["W"]).expanduser().resolve() if os.environ.get("W") else HERE
W = _pick_w(sys.argv)
AZ, GATES, EV = W / "azsdk", HERE / "gates", W / "evidence"
# Shipped records: the package's results/evidence/ (next to this folder) if present, else <work dir>/evidence_original
EV0 = (HERE.parent / "results" / "evidence") if (HERE.parent / "results" / "evidence").exists() else W / "evidence_original"
CFG = yaml.safe_load(open(HERE / "experiments.yaml"))
SCRIPTS = {"G1": "g1_interface.py", "G2_G3": "g2_g3_mutation.py", "common": "common.py"}
SCRIPTS.update(CFG.get("scripts") or {})
def gate_script(key):
    f = GATES / SCRIPTS[key]
    if not f.exists(): raise SystemExit(f"gate script for {key} not found: {f}  (set scripts.{key} in experiments.yaml)")
    return f

def sh(cmd, cwd=None, env=None, check=True, capture=False, timeout=1800):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, env=env, text=True,
                       capture_output=capture, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed ({r.returncode}): {cmd}\n{(r.stdout or '')[-2000:]}{(r.stderr or '')[-2000:]}")
    return r

QUIET = False
_T0 = time.time()
def log(msg): print(f"\n== {msg}", flush=True)
def step(msg):
    """Progress line with elapsed time since the run started (suppressed by --quiet)."""
    if not QUIET: print(f"   [{time.time() - _T0:6.1f}s] {msg}", flush=True)

def stream(cmd, cwd=None, env=None, prefix="      ", skip=lambda l: False):
    """Run cmd, echoing its output lines as they arrive (unless --quiet or skip(line)); return (returncode, all_output)."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
    lines = []
    for line in proc.stdout:
        lines.append(line)
        if not QUIET and not skip(line): print(prefix + line.rstrip(), flush=True)
    proc.wait()
    return proc.returncode, "".join(lines)

def link_hypotheses(pr, gate):
    """Copy the PR's trust hypotheses served by `gate` (rater's `hypotheses` and the analyst's `analyst_hypotheses`,
    from experiments.yaml) into the gate's evidence record, each tagged with its source."""
    f = EV / f"pr{pr['number']}_{gate}.json"
    if not f.exists(): return
    hyps = [h for h in pr.get("hypotheses", []) + pr.get("analyst_hypotheses", []) if gate in (h.get("gates") or [])]
    d = json.load(open(f))
    d["linked_hypothesis_ids"] = [h["id"] for h in hyps]
    d["hypotheses"] = {h["id"]: dict(category=h["category"], statement=h["statement"], source=h.get("source", "rater")) for h in hyps}
    json.dump(d, open(f, "w"), indent=2)

# ---------------------------------------------------------------- setup
def prepare_dirs():
    """Create the work directory; if the shipped evidence sits in evidence/ (running in place), move it aside."""
    W.mkdir(parents=True, exist_ok=True); EV.mkdir(parents=True, exist_ok=True)
    if EV.resolve() == EV0.resolve():
        raise SystemExit(f"refusing to write results into the shipped results folder {EV0}; use --work-dir")
    if any(k in str(W) for k in ("Mobile Documents", "iCloud", "Dropbox", "OneDrive", "Google Drive")):
        print(f"   WARNING: {W} looks like a cloud-synced folder; the clone is ~1 GB with many small files.\n"
              f"            Consider: python run_experiments.py --work-dir ~/trustgates setup   (the config and gates stay here)")

PIP_NAME = {"yaml": "pyyaml", "jwt": "pyjwt", "jinja2": "Jinja2", "azure.storage.blob": "azure-storage-blob", "azure.cosmos": "azure-cosmos (setup installs it from the clone)"}

def preflight(pr):
    prof = env_profile(pr)
    if prof.get("needs_nltk_data"):
        m = nltk_data_missing()
        if m: raise SystemExit(f"#{pr['number']} needs NLTK data that is not installed: {', '.join(m)}\n"
                               f"   run `python run_experiments.py setup` (downloads it), or: python -c \"import nltk; nltk.download('{m[0]}')\"")
    missing = []
    for mod in prof.get("preflight", []):
        if subprocess.run([sys.executable, "-c", f"import {mod}"], capture_output=True).returncode != 0: missing.append(PIP_NAME.get(mod, mod))
    if missing:
        raise SystemExit(f"#{pr['number']} needs Python packages that are not installed in {sys.executable}:\n"
                         f"     {', '.join(missing)}\n"
                         f"   install them with:  python -m pip install -r {HERE / 'requirements.txt'}\n"
                         f"   (or run `python run_experiments.py setup`, which installs them)")

SETUP = CFG.get("setup") or {}
ENVS = CFG.get("environments") or {"NONE": {}}
COMMON_ENV = CFG.get("common_env") or {}
_NLTK_DIR = {"punkt": "tokenizers/punkt", "punkt_tab": "tokenizers/punkt_tab", "wordnet": "corpora/wordnet", "omw-1.4": "corpora/omw-1.4"}
NLTK_DATA = [(n, _NLTK_DIR.get(n, f"corpora/{n}")) for n in SETUP.get("nltk_data", [])]

def nltk_data_missing():
    try:
        import nltk
    except ImportError:
        return [n for n, _ in NLTK_DATA]
    missing = []
    for name, path in NLTK_DATA:
        found = False
        for cand in (path, path + ".zip"):      # wordnet/omw are kept zipped by nltk.download
            try: nltk.data.find(cand); found = True; break
            except LookupError: pass
        if not found: missing.append(name)
    return missing

def ensure_nltk_data():
    """The evaluation package's Bleu/Meteor tests tokenize with NLTK and try to download these on first use; that silent
    download fails on some machines. Fetch the four data files directly (NLTK's downloader uses urllib, which on many
    macOS Python builds has no usable CA certificates), verifying TLS with certifi, then with the OS trust store."""
    missing = nltk_data_missing()
    if not missing: print("   NLTK data present"); return
    import nltk, zipfile, io
    dest = Path(nltk.data.path[0])          # usually ~/nltk_data
    log(f"downloading NLTK data to {dest}: {', '.join(missing)}")
    base = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"
    for name in missing:
        sub = "tokenizers" if name.startswith("punkt") else "corpora"
        url = f"{base}/{sub}/{name}.zip"
        data = _fetch(url)
        (dest / sub).mkdir(parents=True, exist_ok=True)
        (dest / sub / f"{name}.zip").write_bytes(data)
        if sub == "tokenizers":              # tokenizer models must be unzipped; corpora may stay zipped
            zipfile.ZipFile(io.BytesIO(data)).extractall(dest / sub)
        print(f"   {name}: ok ({len(data)//1024} kB)")
    still = nltk_data_missing()
    if still: raise SystemExit(f"NLTK data still not found after download: {still}; searched {nltk.data.path}")

def _fetch(url):
    """GET url as bytes, trying: requests with certifi (as pip does), then the OS trust store via `truststore`."""
    import requests
    attempts = []
    try:
        import certifi; return requests.get(url, timeout=120, verify=certifi.where()).content
    except Exception as e: attempts.append(f"certifi: {type(e).__name__}: {str(e)[:120]}")
    try:
        import truststore, ssl
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        import urllib.request
        return urllib.request.urlopen(url, timeout=120, context=ctx).read()
    except ImportError: attempts.append("truststore: not installed (pip install truststore)")
    except Exception as e: attempts.append(f"truststore: {type(e).__name__}: {str(e)[:120]}")
    raise SystemExit(f"could not download {url}\n   " + "\n   ".join(attempts) + "\n"
                     f"   Fallbacks: (a) pip install truststore, then retry;  (b) macOS python.org build: run\n"
                     f"   '/Applications/Python 3.12/Install Certificates.command' and retry;  (c) download the file in a\n"
                     f"   browser and place it under ~/nltk_data/<tokenizers|corpora>/ (unzip tokenizer files), then retry.")

def setup():
    prepare_dirs()
    log(f"installing Python requirements into {sys.executable}")
    sh([sys.executable, "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])
    ensure_nltk_data()
    if not (AZ / ".git").exists():
        log(f"cloning {CFG['repo']} (treeless, depth {CFG['clone_depth']})")
        sh(["git", "clone", "--filter=tree:0", f"--depth={CFG['clone_depth']}", "--no-checkout",
            "--single-branch", "--branch", "main", CFG["repo"], str(AZ)])
    sh(["git", "sparse-checkout", "init", "--cone"], cwd=AZ)
    sh(["git", "sparse-checkout", "set", *CFG["sparse_paths"]], cwd=AZ)
    log("checking merge commits are reachable")
    missing = [p["number"] for p in CFG["prs"]
               if not sh(f'git log --format=%h --grep="(#{p["number"]})"', cwd=AZ, capture=True).stdout.strip()]
    if missing:
        log(f"deepening history for {missing}"); sh(["git", "fetch", "-q", "--deepen=10000"], cwd=AZ)
    sh(["git", "checkout", "-q", CFG["prs"][0]["commit"]], cwd=AZ)
    log("installing SDK packages (editable) listed under setup.editable_packages")
    pkgs = SETUP.get("editable_packages", [])
    if pkgs: sh([sys.executable, "-m", "pip", "install", "-q", *sum((["-e", str(AZ / p)] for p in pkgs), [])])
    retools()
    mods = SETUP.get("import_check", [])
    if mods: sh([sys.executable, "-c", "import " + ", ".join(mods) + "; print('packages ok')"])
    (EV / "requirements-frozen.txt").write_text(sh([sys.executable, "-m", "pip", "freeze"], capture=True).stdout)

def retools():
    """The repo's test-tools package moves between commits (setup.tools_package_candidates); re-point the editable install."""
    cands = SETUP.get("tools_package_candidates", [])
    if not cands: return
    for p in cands:
        if (AZ / p / "pyproject.toml").exists() or (AZ / p / "setup.py").exists():
            sh([sys.executable, "-m", "pip", "install", "-q", "-e", str(AZ / p)]); return
    raise SystemExit(f"none of setup.tools_package_candidates exists at this commit: {cands}")

# ---------------------------------------------------------------- per-PR
def env_profile(pr):
    name = pr.get("env", "NONE")
    if name not in ENVS: raise SystemExit(f"#{pr['number']}: env '{name}' is not defined under environments: in experiments.yaml")
    return ENVS[name] or {}

def env_for(pr):
    """Subprocess environment for a PR: the current environment, minus runner-controlled keys, plus common_env and the profile."""
    prof = env_profile(pr)
    managed = {"PYTHONPATH", "EXTRA_PYTEST_ARGS", *COMMON_ENV, *(prof.get("env") or {})}
    e = {k: v for k, v in os.environ.items() if k not in managed}
    e.update({k: str(v) for k, v in COMMON_ENV.items()})
    e.update({k: str(v).format(repo=AZ, work=W) for k, v in (prof.get("env") or {}).items()})
    if prof.get("pytest_args"): e["EXTRA_PYTEST_ARGS"] = " ".join(prof["pytest_args"])
    return e

def checkout(pr):
    step(f"restoring a clean tree and checking out {pr['commit']}")
    sh(["git", "checkout", "-q", "--", "."], cwd=AZ, check=False)
    sh(["git", "checkout", "-q", pr["commit"]], cwd=AZ)
    step("re-pointing the azure-sdk-tools editable install to this commit's location")
    retools()

def baseline(pr, env):
    extra = env.get("EXTRA_PYTEST_ARGS", "").split()
    step(f"environment: {pr['env']}" + (f"  (PYTHONPATH={env['PYTHONPATH']})" if "PYTHONPATH" in env else "") + (f"  (pytest {' '.join(extra)})" if extra else ""))
    step(f"baseline: running the package test suite once, it must be green before mutation:  pytest {' '.join(pr['suite'])}")
    r = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra, *pr["suite"]], cwd=AZ / pr["package"], env=env, capture=True, check=False)
    lines = r.stdout.splitlines() + r.stderr.splitlines()
    last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    print(f"   baseline: {last}")
    if r.returncode != 0:
        EV.mkdir(parents=True, exist_ok=True); (EV / f"pr{pr['number']}_baseline_failure.txt").write_text(r.stdout + r.stderr)
        # Show the distinct error messages, not the parametrized test ids.
        errs = []
        for l in lines:
            if l.startswith("E "):
                m = re.sub(r" at 0x[0-9a-f]+", "", l[1:].strip())      # drop object addresses so repeats collapse
                if m and m not in errs: errs.append(m)
        first_tb = next((l for l in lines if l.endswith("Error") or "Error:" in l), "")
        msg = "\n".join("     " + e for e in errs[:8]) or "     " + first_tb
        failure_file = EV / f"pr{pr['number']}_baseline_failure.txt"
        raise SystemExit(f"baseline suite for #{pr['number']} is not green; fix the environment first.\n"
                         f"   distinct errors:\n{msg}\n"
                         f"   full output: {failure_file}\n"
                         f"   (rerun by hand: cd {AZ / pr['package']} && python -m pytest -q {' '.join(extra + pr['suite'])})")

def run_g1(pr, env):
    step("G1 interface resolution: pyflakes on changed files, imports and module attributes on changed lines resolved against the installed packages")
    sh([sys.executable, str(gate_script("G1")), str(AZ), pr["commit"], str(pr["number"]), str(EV)], cwd=GATES, env=env, capture=True)
    link_hypotheses(pr, "G1")
    rec = json.load(open(EV / f"pr{pr['number']}_G1.json"))
    print(f"   G1: {rec['result']}, {len(rec['findings'])} findings")

def run_g2(pr, env):
    step("G2/G3 mutation: generating single-point mutants on the PR's changed lines, then for each mutant running the package suite (G2) and the PR's own tests (G3); one line per mutant follows")
    rc, out = stream([sys.executable, str(gate_script("G2_G3")), str(AZ), pr["commit"], str(pr["number"]), str(EV), *pr["suite"]],
                     cwd=GATES, env=env, skip=lambda l: l.startswith("{"))   # the JSON summary is printed once, below
    (EV / f"pr{pr['number']}_G2_log.txt").write_text(out)
    if rc != 0: raise SystemExit(f"mutation gate failed for #{pr['number']}; see evidence/pr{pr['number']}_G2_log.txt")
    link_hypotheses(pr, "G2"); link_hypotheses(pr, "G3")
    print("   G2/G3: " + out.strip().splitlines()[-1])

def run_g4(pr, env):
    g4 = pr.get("g4")
    n = pr["number"]; out = [f"# G4 for PR #{n} at {pr['commit']} — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", f"# expected: {g4.get('expect', '')}" if g4 else ""]
    out += [f"# hypothesis {h['id']} ({h['category']}, {h.get('source', 'rater')}): {h['statement']}" for h in pr.get("hypotheses", []) + pr.get("analyst_hypotheses", []) if "G4" in (h.get("gates") or [])]
    if not g4:
        step("G4: no claim check configured for this PR"); print("   G4: none configured"); return
    if pr.get("requires_absent_module"):
        r = sh([sys.executable, "-c", f"import {pr['requires_absent_module']}"], env=env, capture=True, check=False)
        if r.returncode == 0:
            raise SystemExit(f"#{n}: the G4 check requires module {pr['requires_absent_module']} to be ABSENT; uninstall it")
    pkg = AZ / pr["package"]
    if "script" in g4:
        script = GATES / g4["script"]
        modes = [[]] + ([["-O"]] if g4.get("also_optimized") else [])
        def run_phase(label):
            step(f"G4 {label}: running {script.name}" + (", also under python -O" if len(modes) > 1 else ""))
            for m in modes:
                r = sh([sys.executable, *m, str(script)], cwd=pkg, env=env, capture=True, check=False)
                txt = (r.stdout + r.stderr)
                # drop the packages' own log noise, but keep check lines that quote it (e.g. "C1 import-time output: '[INFO] ...'")
                txt = "\n".join(l for l in txt.splitlines() if "execution.flow" not in l and not l.startswith("Error calc") and not l.startswith("[INFO]"))
                out.append(f"\n## {label}{' (python -O)' if m else ''}\n{txt.strip()}")
        run_phase("AFTER the PR (merge commit)")
        files = [f"{pr['package']}/{f}" for f in g4["files"]]   # paths in the yaml are relative to the package
        step(f"G4: checking out {len(files)} changed file(s) from the parent commit {pr['commit']}~1")
        sh(["git", "checkout", "-q", pr["commit"] + "~1", "--", *files], cwd=AZ)
        try:
            run_phase("BEFORE the PR (changed files from parent)")
        finally:
            step("G4: restoring the merge-commit files")
            sh(["git", "checkout", "-q", pr["commit"], "--", *files], cwd=AZ)
    else:
        step(f"G4: running {len(g4['commands'])} shell command(s) in the clone (static/diff checks)")
        for c in g4["commands"]:
            r = sh(c, cwd=AZ, env=env, capture=True, check=False)
            out.append(f"\n$ {c}\n{(r.stdout + r.stderr).strip()}")
    (EV / f"pr{n}_G4_output.txt").write_text("\n".join(out))
    print(f"   G4: output written to evidence/pr{n}_G4_output.txt (read it against the 'expect' line)")

def run_extra_gates(pr, env):
    for g in CFG.get("extra_gates") or []:
        script = GATES / g["script"]
        if not script.exists(): raise SystemExit(f"extra gate {g['id']}: script not found: {script}")
        step(f"{g['id']}: {g.get('description', script.name)}")
        r = sh([sys.executable, str(script), str(AZ), pr["commit"], str(pr["number"]), str(EV)], cwd=GATES, env=env, capture=True, check=False)
        (EV / f"pr{pr['number']}_{g['id']}_log.txt").write_text(r.stdout + r.stderr)
        if r.returncode != 0: raise SystemExit(f"extra gate {g['id']} failed for #{pr['number']}; see evidence/pr{pr['number']}_{g['id']}_log.txt")
        link_hypotheses(pr, g["id"])
        rec = EV / g.get("record", f"pr{{pr}}_{g['id']}.json").format(pr=pr["number"])
        if rec.exists():
            d = json.load(open(rec)); print(f"   {g['id']}: {d.get('result', '?')}, {len(d.get('findings', []))} findings")
        else:
            print(f"   {g['id']}: ran (no record file {rec.name})")

def run(prs, gates):
    prepare_dirs()
    for k, pr in enumerate(prs, 1):
        log(f"PR #{pr['number']}  ({k}/{len(prs)})  {pr['commit']}  {pr['package']}")
        step("preflight: checking the Python packages this environment needs are importable")
        preflight(pr)
        checkout(pr); env = env_for(pr)
        baseline(pr, env)
        if "G1" in gates: run_g1(pr, env)
        if "G2" in gates: run_g2(pr, env)
        extra_ids = {g["id"] for g in CFG.get("extra_gates") or []}
        if extra_ids & gates or (extra_ids and gates == set(CFG.get("gates", []))): run_extra_gates(pr, env)
        if "G4" in gates: run_g4(pr, env)
        step("leaving the tree clean (git checkout -- .)")
        sh(["git", "checkout", "-q", "--", "."], cwd=AZ, check=False)
    log(f"done in {time.time() - _T0:.0f}s"); summary()

# ---------------------------------------------------------------- reporting
def summary():
    rows = []
    for pr in CFG["prs"]:
        n = pr["number"]; g2 = EV / f"pr{n}_G2.json"; g3 = EV / f"pr{n}_G3.json"; g1 = EV / f"pr{n}_G1.json"
        if not g2.exists(): continue
        d2 = json.load(open(g2)); d3 = json.load(open(g3)) if g3.exists() else {}
        m = d2.get("mutants", []); k = sum(x["killed_by_suite"] for x in m); ko = sum(bool(x["killed_by_pr_tests"]) for x in m)
        own = f"{ko}/{len(m)}" if d3 and d3.get("result") != "no_pr_tests" and m else "—"
        g1r = json.load(open(g1))["result"] if g1.exists() else "?"
        g4 = "output" if (EV / f"pr{n}_G4_output.txt").exists() else ("record" if (EV / f"pr{n}_G4.json").exists() else "—")
        cats = {}
        for h in pr.get("hypotheses", []): cats[h["category"]] = cats.get(h["category"], 0) + 1
        hyp = ", ".join(f"{v} {k}" for k, v in cats.items()) or "—"
        rows.append((n, pr["package"].split("/")[-1], hyp, g1r, f"{k}/{len(m)}", own, g4))
    print(f"\n{'PR':>6}  {'package':24} {'hypotheses':30} {'G1':6} {'G2':7} {'G3':7} G4")
    for r in rows: print(f"{r[0]:>6}  {r[1]:24} {r[2]:30} {r[3]:6} {r[4]:7} {r[5]:7} {r[6]}")
    print("  (G4: 'output' = this run's before/after output; 'record' = shipped triage record only. Per-gate hypothesis links are in each record's linked_hypothesis_ids.)")

def clean(what, yes):
    """Remove generated state. what: results | clone | all. Never touches experiments.yaml, gates/, or ../results/."""
    prepare_dirs()
    targets = []
    if what in ("results", "all"):
        targets += sorted({f for f in EV.glob("pr*_G*") if f.is_file()} | {f for f in EV.glob("*.txt") if f.is_file()})
    if what in ("clone", "all"):
        if AZ.exists(): targets.append(AZ)
    if what == "all":
        for d in (HERE / "gates" / "__pycache__", HERE / "__pycache__"):
            if d.exists(): targets.append(d)
    if not targets:
        print(f"nothing to clean for '{what}' under {W}"); return
    print(f"clean {what}: will remove under {W}:")
    for t in targets: print("  ", t.relative_to(W) if str(t).startswith(str(W)) else t, "(directory)" if t.is_dir() else "")
    if not yes:
        ans = input("proceed? [y/N] ").strip().lower()
        if ans != "y": print("aborted"); return
    for t in targets:
        shutil.rmtree(t) if t.is_dir() else t.unlink()
    if what in ("clone", "all"):
        print("note: the editable installs in the virtualenv still point at the removed clone; re-run `setup` before `run`,")
        print("      or delete the virtualenv (venv/) as well to start completely fresh.")
    print("done")

IGNORE_KEYS = {"timestamp", "machine_time_s", "analyst_time_min", "tool_versions"}

def _explain_diff(d0, d):
    """Return human-readable lines describing how record d (this run) differs from d0 (shipped)."""
    out = []
    for k in sorted(set(d0) | set(d)):
        if k in IGNORE_KEYS: continue
        if k == "mutants":
            m0 = {(m["file"], m["mutant"]): m for m in d0.get("mutants", [])}
            m1 = {(m["file"], m["mutant"]): m for m in d.get("mutants", [])}
            for key in sorted(set(m0) | set(m1)):
                if key not in m1: out.append(f"mutant only in shipped: {key[0].split('/')[-1]} {key[1]}")
                elif key not in m0: out.append(f"mutant only in this run: {key[0].split('/')[-1]} {key[1]}")
                else:
                    for f in ("killed_by_suite", "killed_by_pr_tests"):
                        if m0[key].get(f) != m1[key].get(f):
                            out.append(f"{key[0].split('/')[-1]} {key[1]}: {f} shipped={m0[key].get(f)} now={m1[key].get(f)}")
        elif k == "findings":
            f0 = {json.dumps(x, sort_keys=True) for x in d0.get(k, [])}; f1 = {json.dumps(x, sort_keys=True) for x in d.get(k, [])}
            if f0 != f1: out.append(f"findings: {len(f0)} shipped vs {len(f1)} now" + ("" if len(f0) == len(f1) else "") +
                                    "".join(f"\n        only shipped: {x}" for x in sorted(f0 - f1)) + "".join(f"\n        only now: {x}" for x in sorted(f1 - f0)))
        elif d0.get(k) != d.get(k):
            v0, v1 = json.dumps(d0.get(k)), json.dumps(d.get(k))
            out.append(f"{k}: shipped={v0[:100]}{'…' if len(v0) > 100 else ''}  now={v1[:100]}{'…' if len(v1) > 100 else ''}")
    return out

def compare(prs):
    """Compare this run's automated records (G1, G2, G3) for the selected PRs with the shipped ones."""
    if not EV0.exists(): raise SystemExit(f"no shipped records found at {EV0} (expected the package's results/evidence/ folder)")
    print(f"\nComparing {EV} (this run) with {EV0} (shipped), PRs: {', '.join('#' + str(p['number']) for p in prs)}")
    print(f"(ignoring {', '.join(sorted(IGNORE_KEYS))})\n")
    n_same = n_diff = n_notrun = 0
    for pr in prs:
        for g in ("G1", "G2", "G3"):
            name = f"pr{pr['number']}_{g}.json"; f0 = EV0 / name; f = EV / name
            if not f0.exists(): print(f"   {name}: no shipped record"); continue
            if not f.exists(): print(f"   {name}: not run yet (nothing in {EV.name}/)"); n_notrun += 1; continue
            diffs = _explain_diff(json.load(open(f0)), json.load(open(f)))
            if not diffs: print(f"   {name}: identical"); n_same += 1
            else:
                n_diff += 1; print(f"   {name}: DIFFERS")
                for line in diffs: print(f"      - {line}")
    print(f"\n{n_same} identical, {n_diff} differ, {n_notrun} not run yet.")
    if n_notrun and not n_same and not n_diff: print("Run `python run_experiments.py run` first (or `run --prs N,N`), then compare.")
    if n_diff: print("A differing kill status usually means a test-suite or dependency difference; a differing mutant list means a different commit or parse.")

def list_prs():
    print(f"\nPRs in {HERE / 'experiments.yaml'}  (enabled = run by default; use `run --prs` to override)\n")
    print(f"  {'PR':>6}  {'enabled':7}  {'commit':12}  {'env':6}  {'package':44}  hypotheses")
    for p in CFG["prs"]:
        hyp = "; ".join(f"{h['id']} {h['category']}" for h in p.get("hypotheses", []))
        if p.get("analyst_hypotheses"): hyp += "  + analyst: " + "; ".join(f"{h['id']} {h['category']}" for h in p["analyst_hypotheses"])
        print(f"  {p['number']:>6}  {str(p.get('enabled', True)):7}  {p['commit'][:12]:12}  {p['env']:6}  {p['package']:44}  {hyp}")
    print(f"\n  gates by default: {', '.join(CFG.get('gates', ['G1','G2','G3','G4']))}  (G2 and G3 come from one mutation run)")
    print(f"  gate scripts: G1 = gates/{SCRIPTS['G1']}   G2/G3 = gates/{SCRIPTS['G2_G3']}   G4 = per PR (see each PR's g4 block)")
    if CFG.get("extra_gates"): print("  extra gates: " + ", ".join(f"{g['id']} (gates/{g['script']})" for g in CFG["extra_gates"]))
    print(f"  environments: " + ", ".join(f"{k} [{', '.join(f'{a}={b}' for a, b in (v or {}).get('env', {}).items()) or 'no env'}; pytest {' '.join((v or {}).get('pytest_args', [])) or '-'}]" for k, v in ENVS.items()))
    print(f"  work dir = {W}   clone = {AZ}   evidence -> {EV}   (change with -w DIR or $W)")

DESCRIPTION = """Run the trust-gate experiments on agent-authored PRs (config: experiments.yaml next to this script).

Typical sequence:
  python run_experiments.py list                    show the configured PRs and what will run
  python run_experiments.py setup                   install requirements.txt, clone the repository, install packages (once)
  python run_experiments.py run                     run all PRs marked enabled: true
  python run_experiments.py run --prs 44844,41852   run only these PRs (ignores the enabled flag)
  python run_experiments.py run --gates G4          run only some gates (G1, G2, G3, G4; G2/G3 always run together)
  python run_experiments.py summary                 table of results found in the evidence directory
  python run_experiments.py compare                 diff this run's records (enabled PRs, or --prs) against results/evidence/
  python run_experiments.py clean results|clone|all remove this run's results, the clone, or both (asks first; -y to skip)

Work directory (-w/--work-dir, or $W; default: the directory containing this script, so running in place works):
  <work dir>/azsdk/              the repository clone (~1 GB; keep it out of cloud-synced folders)
  <work dir>/evidence/           results of this run
  experiments.yaml and gates/ are always read from the directory containing this script;
  `compare` reads the shipped records from ../results/evidence/ (the package's results folder).
"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-q", "--quiet", action="store_true", help="suppress step-by-step progress; print only per-PR results")
    ap.add_argument("-w", "--work-dir", metavar="DIR", default=str(W),
                    help="where the clone (azsdk/) and results (evidence/) go; default: $W if set, else this script's directory (current: %(default)s)")
    sub = ap.add_subparsers(dest="cmd", metavar="command", required=True)
    sub.add_parser("list", help="show the PRs and gates configured in experiments.yaml")
    sub.add_parser("setup", help="install requirements.txt, clone Azure/azure-sdk-for-python (sparse, treeless) into W/azsdk, install the SDK packages (once)")
    r = sub.add_parser("run", help="run the gates on the enabled PRs (or on --prs)", formatter_class=argparse.RawDescriptionHelpFormatter,
                       description="For each selected PR: checkout the merge commit, verify the baseline test suite is green, then run the selected gates.\n"
                                   "G1 = interface resolution; G2 = mutation on changed lines vs the package suite; G3 = the same mutants vs the PR's own tests (one run produces both);\n"
                                   "G4 = claim checks run after and before the PR, written to evidence/pr<N>_G4_output.txt for a person to read.")
    r.add_argument("--prs", metavar="N,N,...", help="PR numbers to run, comma-separated; overrides the enabled flags in experiments.yaml (e.g. --prs 44844,41852)")
    r.add_argument("--gates", metavar="G,G,...", default=",".join(CFG.get("gates", ["G1", "G2", "G3", "G4"])),
                   help="gates to run, comma-separated subset of G1,G2,G3,G4 (default: %(default)s); G2 and G3 come from one mutation run, so naming either runs both")
    r.add_argument("--dry-run", action="store_true", help="print the plan (PRs, commits, suites, gates) and exit without running anything")
    sub.add_parser("summary", help="print a results table from the records in W/evidence")
    cp = sub.add_parser("compare", help="compare this run's G1/G2/G3 records with the shipped ones in ../results/evidence (enabled PRs, or --prs)")
    cp.add_argument("--prs", metavar="N,N,...", help="PR numbers to compare; default: the PRs enabled in experiments.yaml")
    c = sub.add_parser("clean", help="remove generated state: results, the clone, or both (never the config, gates or the shipped results/)",
                       description="clean results  = delete this run's records in W/evidence (pr*_G*.json, logs, G4 outputs)\n"
                                   "clean clone    = delete the repository clone W/azsdk (~1 GB); run `setup` again afterwards\n"
                                   "clean all      = both, plus __pycache__ directories\n"
                                   "The virtualenv is not touched; delete venv/ by hand for a completely fresh start.",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    c.add_argument("what", choices=["results", "clone", "all"], help="what to remove")
    c.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    a = ap.parse_args()
    QUIET = a.quiet
    def select(prs_arg):
        want = {int(x) for x in prs_arg.split(",")} if prs_arg else None
        unknown = (want or set()) - {p["number"] for p in CFG["prs"]}
        if unknown: raise SystemExit(f"PR(s) not in experiments.yaml: {sorted(unknown)}  (run `list` to see the configured PRs)")
        sel = [p for p in CFG["prs"] if (p["number"] in want if want else p.get("enabled", True))]
        if not sel: raise SystemExit("no PRs selected: none are enabled in experiments.yaml and --prs was not given")
        return sel
    if a.cmd == "list": list_prs()
    elif a.cmd == "setup": setup()
    elif a.cmd == "run":
        sel = select(a.prs)
        gates = {g.strip().upper() for g in a.gates.split(",")}
        known = {"G1", "G2", "G3", "G4"} | {g["id"] for g in CFG.get("extra_gates") or []}
        bad = gates - known
        if bad: raise SystemExit(f"unknown gate(s) {sorted(bad)}; choose from {', '.join(sorted(known))}")
        if gates & {"G2", "G3"}: gates |= {"G2", "G3"}     # one mutation run produces both
        print(f"\nPlan: {len(sel)} PR(s), gates {', '.join(g for g in ('G1','G2','G3','G4') if g in gates)}, work dir {W}")
        for p in sel: print(f"  #{p['number']}  {p['commit'][:12]}  {p['package']}  env={p['env']}  suite={' '.join(p['suite'])}  G4={'script ' + p['g4']['script'] if p.get('g4') and 'script' in p['g4'] else 'commands' if p.get('g4') else 'none'}")
        if a.dry_run: sys.exit(0)
        if not (AZ / ".git").exists(): raise SystemExit(f"no clone at {AZ}; run `python run_experiments.py setup` first")
        run(sel, gates)
    elif a.cmd == "summary": summary()
    elif a.cmd == "clean": clean(a.what, a.yes)
    else: compare(select(a.prs))

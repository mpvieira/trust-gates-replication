"""Shared helpers: changed-line extraction from a squash commit, evidence records."""
import subprocess, re, json, time, os, sys
from pathlib import Path

def run(cmd, cwd=None, timeout=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def changed_lines(repo, commit):
    """Return {path: set(new-file line numbers added/modified)} and list of test files touched."""
    out = run(["git", "show", "--format=", "--unified=0", commit], cwd=repo).stdout
    files, cur = {}, None
    for line in out.splitlines():
        if line.startswith("+++ "):
            cur = line[4:].strip()
            cur = None if cur == "/dev/null" else cur[2:] if cur.startswith("b/") else cur
            if cur: files.setdefault(cur, set())
        elif line.startswith("@@") and cur:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            start = int(m.group(1)); n = int(m.group(2)) if m.group(2) is not None else 1
            files[cur].update(range(start, start + n))
    src = {p: ls for p, ls in files.items() if p.endswith(".py") and "/tests/" not in p and "/test" not in Path(p).name}
    tests = [p for p in files if p.endswith(".py") and ("/tests/" in p or Path(p).name.startswith("test_"))]
    return src, tests

def package_root(repo, path):
    """Walk up from a file to the directory containing pyproject.toml/setup.py."""
    p = Path(repo, path).parent
    while p != Path(repo):
        if (p / "pyproject.toml").exists() or (p / "setup.py").exists():
            return p
        p = p.parent
    return None

class Evidence:
    def __init__(self, gate_id, gate_type, artifact_ref, linked_hypotheses=None):
        self.t0 = time.time()
        self.rec = dict(gate_id=gate_id, gate_type=gate_type, linked_hypothesis_ids=linked_hypotheses or [],
                        artifact_ref=artifact_ref, exercised=[], assumptions=[], result="pass",
                        findings=[], not_evaluated=[], tool_versions={"python": sys.version.split()[0]},
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    def finding(self, **kw):
        self.rec["findings"].append(kw); self.rec["result"] = "findings"
    def save(self, path):
        self.rec["machine_time_s"] = round(time.time() - self.t0, 1)
        assert self.rec["not_evaluated"], "evidence record without not_evaluated is invalid"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.rec, indent=2))
        return self.rec

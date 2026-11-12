"""Template for an additional gate. Command line: <repo> <commit> <PR> <outdir>.
This example flags TODO/FIXME markers on the PR's changed lines. Copy it, change GATE_ID/GATE_TYPE and the check."""
import sys, json
from pathlib import Path
from common import changed_lines, Evidence

GATE_ID, GATE_TYPE = "G5", "todo_markers_on_changed_lines"

def main(repo, commit, pr, outdir):
    src, _ = changed_lines(repo, commit)
    ev = Evidence(GATE_ID, GATE_TYPE, dict(repo=repo, pr=pr, commit=commit, files=list(src)))
    ev.rec["assumptions"] = ["a TODO/FIXME on a changed line marks behaviour the author knew was incomplete"]
    for path, lines in src.items():
        text = Path(repo, path).read_text(encoding="utf-8-sig").splitlines()
        for ln in sorted(lines):
            if ln <= len(text) and any(m in text[ln - 1] for m in ("TODO", "FIXME")):
                ev.finding(file=path, line=ln, kind="todo_marker", detail=text[ln - 1].strip()[:120])
        ev.rec["exercised"].append(f"{path}: {len(lines)} changed lines scanned")
    ev.rec["not_evaluated"] = ["markers outside the diff", "comments that describe incompleteness without the keywords"]
    ev.save(Path(outdir, f"pr{pr}_{GATE_ID}.json"))
    print(json.dumps({k: ev.rec[k] for k in ("result", "findings")}))

if __name__ == "__main__":
    main(*sys.argv[1:5])

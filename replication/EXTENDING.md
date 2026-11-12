# Extending the replication package

This manual explains how to take the case-study tooling beyond the eight pull requests it ships with: more PRs from the same repository, a different repository, a different test environment, new trust hypotheses, new claim checks, and new gates. Everything described here is driven by `replication/experiments.yaml` and the scripts in `replication/gates/`; the runner (`run_experiments.py`) contains no project-specific knowledge.

Read `README.md` in this folder first for how to run what exists. Section numbers below refer to the five extension points, in increasing order of effort.

---

## 0. How the pieces fit

```
experiments.yaml
  repo, sparse_paths, setup        -> what `setup` clones and installs
  environments, common_env         -> how tests are made runnable per package
  scripts, extra_gates, gates      -> which gate implementations run
  prs[]                            -> one entry per PR: commit, package, env, suite, hypotheses, g4

run_experiments.py                 -> for each selected PR: checkout -> baseline tests -> G1 -> G2/G3 -> extra gates -> G4
gates/common.py                    -> changed-line extraction from the diff; the Evidence record class
gates/g1_interface.py              -> G1
gates/g2_g3_mutation.py            -> G2 + G3
gates/g4_checks_pr<N>.py           -> G4, one per PR
gates/example_extra_gate.py        -> template for a new gate
```

Every gate writes one JSON evidence record per PR with the same schema (`gate_id`, `artifact_ref`, `linked_hypothesis_ids`, `hypotheses`, `exercised`, `assumptions`, `result`, `findings`, `not_evaluated`, timing). The runner links each record to the hypotheses the config says the gate serves. `summary` and `compare` read those records.

The invariant to preserve when extending: **a gate's job is to produce evidence about the artifact, never a verdict**; the `not_evaluated` field is mandatory and `Evidence.save()` refuses a record without it.

---

## 1. Adding a PR from the same repository

Effort: 30–60 minutes, most of it writing the G4 check.

1. **Find the squash-merge commit** on `main`: `git -C <work>/azsdk log --format='%h %ad %s' --date=short --grep='(#<N>)'`. If nothing is found, the PR may be older than the clone depth (`git fetch --deepen=10000`) or merged into a feature branch (exclude it).
2. **Check the inclusion criteria** (methodology document §3.2): changes library code, has or is covered by offline-runnable tests, 20–800 lines, builds at the commit.
3. **Find an offline test suite**: the package's `tests/` folder; look for `*_unit.py`, `unittests/`, and avoid anything that needs credentials or an emulator. Run it by hand at the commit with the package's environment profile (step 5) and confirm it is green; that is the `suite` list.
4. **Extract requirements and classify** from the PR description and linked issue, before reading the diff (ideally by someone who will not triage the findings; `../rater_package/` is a template), with the two questions. Ask explicitly what the change promises *not* to alter: in the case study a description-only rater missed all three requirements the defects violated. Then apply the two questions (Q1 unfit/security/integrity → must-hold; else Q2 ambiguity/unobservable/open-ended/no reference → cannot-guarantee; else may-fail). Record both answers. Keep H0 (interfaces exist, served by G1).
5. **Add the entry** to `prs:`:
   ```yaml
   - number: 12345
     enabled: true
     commit: abc1234
     package: sdk/<area>/<package>
     env: NONE            # or a profile from environments:
     suite: [tests/unittests/test_x.py]
     hypotheses:
       - {id: H0, category: must-hold, statement: The change references only interfaces that exist, gates: [G1], source: standing}
       - {id: H1, category: must-hold, statement: ..., gates: [G2, G3, G4], source: rater}
     analyst_hypotheses:          # optional: requirements found later (e.g. by reading callers); not blind
       - {id: A1, category: must-hold, statement: ..., gates: [G4], source: analyst}
     g4:
       script: g4_checks_pr12345.py
       files: [azure/.../changed_module.py]   # relative to package; restored from the parent for the "before" run
       expect: "one line stating what after/before should show"
   ```
   If the package is not yet installed by `setup`, add it to `setup.editable_packages` (and to `sparse_paths`), then re-run `setup`.
6. **Write the G4 script** (Section 4).
7. `python run_experiments.py run --prs 12345`, read `evidence/pr12345_G4_output.txt` against `expect`, triage the findings by the rules in the methodology document §4.6, and write `evidence/pr12345_G4.json` (copy the structure of a shipped one).

---

## 2. Adding a different repository

Effort: half a day to a day, dominated by getting the project's tests to run offline.

The runner assumes: a git repository; Python packages installable editable from the clone; pytest; and a squash-merge commit per PR on one branch. Beyond that everything is configuration.

1. **`repo`, `repo_name`, `clone_depth`, `sparse_paths`.** Set the URL, the display name used in records, how many commits back you need, and which directories to materialize (keep the clone small; treeless + sparse is what makes a monorepo tractable).
2. **`setup`.** `editable_packages`: the packages to `pip install -e` from the clone. `tools_package_candidates`: paths where the project's shared test helpers live, tried in order at each checkout (the Azure repo moved its helpers between `tools/` and `eng/tools/`; leave empty if not applicable). `import_check`: modules that must import after setup. `nltk_data`: leave empty unless tests need it.
3. **`common_env`.** Environment variables set for every PR. For Azure this neutralizes the test-proxy fixture; for another project it may be empty or something like `CI=1`.
4. **`environments`.** One profile per distinct test setup the project's packages need (Section 3).
5. **`requirements.txt`.** Add the project's test-time Python dependencies; `setup` installs this file. Expect to iterate: the runner's preflight check names any missing module before a PR starts, and a failed baseline prints the distinct error lines.
6. **Populate `prs:`** as in Section 1, and set `enabled: false` on the shipped Azure entries (or delete them).
7. **Selecting PRs.** For agent-authored PRs, the AIDev dataset (Li et al., MSR 2026) lists them per repository and agent; or use GitHub search (`is:pr is:merged author:app/copilot-swe-agent repo:<owner>/<repo>`, similarly `app/devin-ai-integration`, or `"Generated with Claude Code" in:body`). Record the funnel: candidates, and why each excluded one was excluded.

What does not transfer without code changes: non-Python projects (the mutator is Python-AST based, G1 uses pyflakes and importlib) and test runners other than pytest. Section 5 says where those assumptions live.

---

## 3. Adding a test-environment profile

Effort: minutes, once you know what the package needs.

A profile is a named entry under `environments:` that a PR references with `env:`:

```yaml
environments:
  MYPKG:
    env:                              # variables set for the tests and gates; {repo} and {work} expand
      PYTHONPATH: "{repo}/src/mypkg"
      MYPKG_OFFLINE: "1"
    pytest_args: [--noconftest, -p, no:randomly]   # extra pytest arguments for baseline, G2 and G3
    preflight: [yaml, pytest, pyflakes, somedep]  # modules that must import before the PR starts
    needs_nltk_data: false
```

Use `env.PYTHONPATH` when a package will not install editable at some commit (the Azure evaluation package). Use `pytest_args: [--noconftest]` when the package's `conftest.py` reaches for a service or emulator; check which tests still run without it. `preflight` turns a mid-run `ModuleNotFoundError` into a clear message up front; add to it whenever a baseline fails on an import.

---

## 4. Writing a G4 claim check

Effort: 20–40 minutes per PR. This is the analyst's step and the one the paper's argument depends on; it is deliberately not automated.

**What a check is.** One executable probe per behavioural statement in the PR description, written so that its output differs if the claimed behaviour is absent. The runner runs the script twice, at the merge commit and with `g4.files` restored from the parent commit, so each probe gets a before/after value.

**Contract.** A plain Python script in `gates/`, run with the package directory as working directory and the PR's environment profile; it prints one labelled line per check (`C1 ... -> <value>`) to stdout or stderr and exits 0. It must not depend on files outside the checkout and the package's dependencies. See the five shipped scripts.

**How to derive the checks**, in this order:
1. Copy the description's claims as sentences. Number them.
2. For each claim, find the smallest call that exercises it. If the claim is about a code path, call that path; if it is about output, capture the output.
3. Ask which readings of each claim the author did *not* have in mind. The classification helps: any hypothesis that answered "yes" to Q2 names an ambiguity, and each reading of that ambiguity is a check (for #41852: `import *` and `hasattr`; for #44844: nested managers *with* run contexts).
4. Take call sequences from the production callers, not from what seems plausible. `grep` for the changed class or function in the package and mirror how it is actually used. The #44844 supplement documents a check that was discarded for using an invented sequence.
5. Where a claim cannot be exercised offline (needs a live service), say so in `expect` and in the record's `not_evaluated`; do not guess. Static checks can be expressed as shell `commands` instead of a script (see #42047, #44770 in the config).

**Preconditions.** If a check only makes sense in a particular state (a dependency absent, as for #41852), add `requires_absent_module:` to the PR entry so the runner verifies it.

**Recording the result.** After reading the output, write `evidence/pr<N>_G4.json` with `claims` (each with a status: supported / not supported / not checkable), `findings` (kind, and for defects the failure mode and severity), `exercised`, `assumptions`, `not_evaluated`. The triage rules are in the methodology document §4.6.

---

## 5. Adding a gate

Effort: an hour for something simple; the value is in choosing what the gate should measure.

**When a new gate is warranted.** A gate should produce evidence about a failure mode that G1–G4 do not cover, for a hypothesis category that recurs. Candidates seen in the case study: a secret/credential scan on changed lines; a docstring-versus-signature check (the #43269 `response_hook` mismatch); a "changelog present for behaviour change" check (also #43269); a check that tests added by a PR import the module they name (the #41852 and #42047 pattern, currently found only through G2/G3 survivors). Do not add a gate that returns a verdict; it must report what it exercised and what it did not.

**Contract.** A script in `gates/` invoked as `python <script> <repo> <commit> <PR> <outdir>`, in the PR's environment. It should use `common.changed_lines()` to confine itself to the PR's diff and `common.Evidence` to write `<outdir>/pr<PR>_<ID>.json`. `gates/example_extra_gate.py` is a complete, working template (it flags TODO/FIXME markers on changed lines).

**Registering it.** Add an entry under `extra_gates:`:
```yaml
extra_gates:
  - id: G5
    script: my_gate.py
    description: one line shown in the progress output
    record: pr{pr}_G5.json
```
The runner then runs it for every PR after G2/G3, links it to the hypotheses whose `gates` list names its id, writes its stdout to `evidence/pr<N>_G5_log.txt`, and accepts `G5` in `--gates`. Add the gate to the relevant hypotheses' `gates:` lists so the link is recorded, and add it to `gates:` if it should run by default.

**Replacing a built-in gate.** `scripts.G1` and `scripts.G2_G3` name the implementations; a replacement must accept the same command line (`<repo> <commit> <PR> <outdir> [pytest args]` for G2/G3) and write records with the same `gate_id`s so `summary`/`compare` keep working.

**Where the language assumptions are.** `common.changed_lines()` only mutates `.py` files; `g1_interface.py` uses pyflakes and importlib; `g2_g3_mutation.py` mutates a Python AST and runs pytest; the runner's `baseline()` and `run_g2()` call pytest. Porting to another language means replacing those four places and the mutation operators.

---

## 6. Keeping results comparable

- `compare` diffs G1/G2/G3 records field by field and names differing mutants. If you change the mutator's operators, all G2/G3 records change; keep the old evidence folder and say which mutator version produced which records.
- Record the environment: `setup` writes `evidence/requirements-frozen.txt`. For a deposit, add the commit hashes (already in the config) and the Python version.
- Do not edit shipped records in `results/evidence/`; new runs go to `<work>/evidence/`. The runner refuses to write into the results folder.
- Every judgment (classification, triage, severity) should be attributable to a named person. The shipped records say who made them; keep that habit.

---

## 7. Checklist for a new study

1. Config: repo, sparse paths, setup, environments, requirements.
2. `setup` green; `list` shows what you expect.
3. One PR end to end: baseline green, G1, G2/G3, G4 output read and triaged, record written.
4. `compare` against your own first run reproduces it (catches nondeterminism in the suite).
5. Then the rest of the PRs; classification by a human, blind to diffs, before triage.
6. Funnel, hashes, frozen requirements, and the evidence folder into the archive.

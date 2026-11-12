# Trust Gates on Agent-Authored Pull Requests: Full Methodology and Replication Record

**Purpose.** This document records, in enough detail to repeat from scratch, everything that was done to produce the case-study results in the revised manuscript "Engineering Trust When AI Writes Your Software" (the case-study table and the PR accounts). It is written for someone with no prior context.

**Provenance.** All steps were executed by an AI assistant (Claude) on 2026-09-28 and 2026-09-29 in a Linux container (Ubuntu 24.04, Python 3.12.3, git, pdflatex), with network access limited to GitHub, PyPI and npm. Every number reported was produced by a command whose output was inspected at the time; the raw outputs are preserved in `results/evidence/`. All classification, triage and severity decisions were made by the same assistant and have **not** been independently verified. Section 9 lists what must be re-done by humans before any of this is cited.

---

## 1. Research question and design

The manuscript proposes three constructs (trust hypotheses, trust gates, claim–evidence–limitation statements) for validating AI-generated software artifacts. Reviewers asked for evidence, on industrial code, that the constructs find things conventional practice does not.

The design that answers this cheaply is a retrospective case study on pull requests (PRs) that an industrial coding agent authored and that a real project merged after continuous integration (CI) passed and a human reviewer approved. Every such PR has already been accepted by conventional practice. Anything the gates find in it is therefore, by construction, something conventional practice missed. No separate control group is needed.

**Subject.** PRs authored by the GitHub Copilot coding agent (GitHub account `copilot-swe-agent[bot]`, displayed as "Copilot") merged into `Azure/azure-sdk-for-python`, Microsoft's Python SDK monorepo.

**Unit of analysis.** One merged PR, examined at its squash-merge commit on `main`, compared where relevant against that commit's parent.

**Gates run.** Four, described in Section 4: G1 interface resolution; G2 mutation testing scoped to the PR's changed lines, run against the package's test suite; G3 the same mutants run against only the tests the PR itself added or modified; G4 a per-claim check that turns each behavioral statement in the PR description into an executable test run at the merge commit and at its parent. 

**Outputs per PR.** One evidence record per gate (JSON, schema in Section 4.5), a triage of every finding, and a claim–evidence–limitation statement.

---

## 2. Environment

### 2.1 Container and tools

```
Python 3.12.3, git 2.x, pdflatex (TeX Live 2023), curl
```

A virtual environment at `a Python virtual environment` held all Python dependencies. Packages installed over the course of the study (versions were whatever PyPI served on 2026-09-28; pin them in a real replication):

```
pip install mutmut pytest pytest-cov pyflakes trio requests aiohttp pytest-trio pytest-asyncio \
    typing-extensions "opentelemetry-sdk~=1.26" opentelemetry-instrumentation-requests packaging \
    pyjwt "nltk>=3.9.1" azure-storage-blob httpx "pandas<3" "openai>=1.108.0" ruamel.yaml msrest Jinja2 pytest-mock
```

`mutmut` was installed but not used (it does not handle this monorepo layout well); a purpose-built line-scoped mutator was written instead (Section 4.2). The authoritative dependency list for replication is `replication/requirements.txt`, which adds `filelock`, `certifi` and `truststore` found necessary during replication on a Mac.

### 2.2 Repository acquisition

The monorepo is very large. A treeless, shallow, no-checkout clone with sparse checkout kept it tractable:

```
git clone --filter=tree:0 --depth 12000 --no-checkout --single-branch --branch main \
    https://github.com/Azure/azure-sdk-for-python.git azsdk
cd azsdk
git sparse-checkout init --cone
git sparse-checkout set sdk/core/azure-core sdk/confidentialledger/azure-confidentialledger eng/
# later additions as needed:
git sparse-checkout add sdk/identity/azure-identity sdk/confidentialledger/azure-confidentialledger-certificate \
    sdk/evaluation/azure-ai-evaluation sdk/cosmos/azure-cosmos tools/azure-sdk-tools eng/tools/azure-sdk-tools
```

`--depth 12000` reached back to roughly October 2025 on `main`. Squash-merge commits were located by PR number in the commit subject:

```
git log --oneline --grep="(#<PR>)"
```

Note: `git log` over paths is slow in a treeless clone (it fetches trees lazily); `git show <commit>:<path>` and `git show --stat <commit>` are fast. The parent of a squash commit is `<commit>~1`; checking out one file from the parent (`git checkout <commit>~1 -- <path>`) is how "before the PR" behaviour was obtained without a second worktree.

Some PRs listed by the GitHub search were **not** found on `main` within the 12,000-commit window (#44987, #46760, #47005, #46449, #46355). Inspection of their descriptions suggested they were merged into feature branches, not `main`. They were excluded.

### 2.3 Package installation and test-environment quirks

Each package was installed editable from the checkout (`pip install -e sdk/<area>/<package>`), except `azure-ai-evaluation`, whose `setup.py` failed to build editable at the 2025 commits; for it, the runtime dependencies were installed manually (list in 2.1) and the package directory was put on `PYTHONPATH` instead.

Five environment issues had to be worked around; each is required for reproduction (the runner's `environments` profiles and `common_env` in `experiments.yaml` encode them):

| Package / commit era | Problem | Workaround |
|---|---|---|
| every package (autouse `test_proxy` fixture in each `tests/conftest.py`) | the fixture downloads and starts the Azure test-proxy binary; this fails on some machines (it did on a Mac) | `export AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true` makes the fixture a no-op; the runner sets both for every package |
| azure-ai-evaluation | Bleu/Meteor tests tokenize with NLTK and try to download `punkt`, `punkt_tab`, `wordnet`, `omw-1.4` on first use; the silent download fails on some machines (macOS certificate issues) | `setup` downloads them explicitly; `run` checks they are present before an EVAL-environment PR |
| azure-ai-evaluation | imports `filelock` and `msrest` at test time although neither is in the pip list one would guess from the package | both are in `requirements.txt` |
| azure-cosmos | `tests/conftest.py` connects to a Cosmos emulator on `localhost:8081` at session start | run pytest with `--noconftest`; only the `*_unit.py` and `tests/routing/` tests are usable |
| azure-sdk-tools (`ci_tools`, `devtools_testutils`) | lives at `tools/azure-sdk-tools` in 2025 commits and `eng/tools/azure-sdk-tools` in 2026 commits | reinstall editable from whichever path exists at the checked-out commit |

Two test files in azure-ai-evaluation (`test_simulator.py`, `test_jailbreak_simulator.py`) fail at collection without Azure credentials and were excluded from suites.

---

## 3. PR selection

### 3.1 Search

The GitHub issue-search API (`GET /search/issues`, unauthenticated, 10 requests/minute) was used; the core REST API was rate-limited to zero for most of the session, so PR bodies were taken from the search results, which include them. Script `search.py`:

```python
import requests, json, sys
q = sys.argv[1]
r = requests.get("https://api.github.com/search/issues",
                 params={"q": q, "sort": "updated", "order": "desc", "per_page": 50})
for it in r.json().get("items", []):
    print(it["repository_url"].split("repos/")[1], it["number"], it["user"]["login"], it["title"], it["closed_at"][:10])
```

Query used to enumerate the population:

```
is:pr is:merged author:app/copilot-swe-agent repo:Azure/azure-sdk-for-python
```

This returned 111 merged PRs (three pages of results; the JSON is not shipped, but the PR descriptions used are quoted in `results/classification_sheet.md`). Other queries were tried to find well-known repositories (`microsoft/semantic-kernel`, Devin PRs, "Generated with Claude Code" in body); `azure-sdk-for-python` was chosen because it is a recognizable industrial codebase with many agent PRs, pure-Python packages, and runnable unit tests.

### 3.2 Inclusion criteria applied

A PR was considered if, from its title and `git show --stat`, it:

1. was merged to `main` (found by `git log --grep`);
2. changed executable library code under `sdk/*/azure/…`, not only docs, CI, `cspell`, manifests or samples;
3. touched or was covered by tests that can run offline;
4. changed roughly 20–800 lines;
5. built and ran its tests at the merge commit in the container.

The population is dominated by CI/config/doc PRs; after screening the titles of the 111, about a dozen code-changing candidates remained. The eight retained, in the order they were run:

| PR | Merge commit | Merged | Package | Size (src + test lines) | PR tests |
|---|---|---|---|---|---|
| #45366 | `41391f1e7b5ad52e3d480a7adcbf3fa5b99e2326` | 2026-03-02 | azure-core | 1 + 8 | yes |
| #46707 | `53dcd7783357a76ba374dec23c46ef772865231c` | 2026-05-05 | azure-confidentialledger | 54 | none |
| #44844 | `7d26b949` | 2026-02-03 | azure-ai-evaluation | 29 + 42 | yes (new file) |
| #41492 | `0c347e994` | 2025-06-10 | azure-ai-evaluation | 4 + 47 | yes |
| #42047 | `54d45994a` | 2025-07-17 | azure-ai-evaluation | ~34 + 48 | yes |
| #41852 | `d76b8ba34` | 2025-07-14 | azure-ai-evaluation | 63 + 135 | yes (new file) |
| #44770 | `9a8a19a39` | 2026-01-22 | azure-cosmos | ~120 + 645 | yes (new files) |
| #43269 | `7e59645b2` | 2025-10-09 | azure-cosmos | 140 | none |

#45366 is below the size threshold and was run only as a smoke test of the tooling; the paper's table says so.

The exact count of candidates screened before these eight was not recorded and is a placeholder in the manuscript. A replication should record the full funnel.

---

## 4. The gates

All gate code is in `replication/gates/`. `common.py` provides the shared pieces.

### 4.1 Changed-line extraction (`common.py`)

`changed_lines(repo, commit)` runs `git show --format= --unified=0 <commit>`, parses the `@@ -a,b +c,d @@` hunk headers, and returns, for every `.py` file, the set of line numbers in the *new* version that were added or modified. Files whose path contains `/tests/` or whose name starts with `test_` are separated out as the PR's test files. Only source files are mutated; only lines in the changed set are mutation targets.

Files with a UTF-8 byte-order mark (some cosmos files) are read with `encoding="utf-8-sig"`; the first run on cosmos failed until this was added.

### 4.2 G1 — interface resolution (`g1_interface.py`)

Targets hallucinated interfaces. For each changed source file:

1. `pyflakes` is run on the whole file; "undefined name" reports whose line is in the changed set are findings.
2. Every `import` / `from … import …` statement on a changed line is resolved with `importlib` in the analysis environment; unresolvable modules or missing symbols are findings.
3. Every `module.attr` expression on a changed line whose `module` is an imported alias is checked with `hasattr()` against the real imported module.

The record's `not_evaluated` field states what this cannot see: method calls on objects of inferred type, string-referenced endpoints and config keys, and packages added to manifests. G1 produced no findings on any PR; in a mature, dependency-pinned monorepo this is expected, and the record of *what resolved* is still evidence.

### 4.3 G2 / G3 — line-scoped mutation (`g2_g3_mutation.py`)

A single-point mutator implemented as an `ast.NodeTransformer` enumerates every mutation opportunity on the changed lines, then generates one mutant per opportunity by re-walking a deep copy of the tree with a target index and writing the result back with `ast.unparse` (formatting and comments are lost in the mutant, which does not matter because the original file is restored afterwards). Operators:

| Node | Mutation |
|---|---|
| Compare | `==`↔`!=`, `<`↔`<=`, `>`↔`>=`, `is`↔`is not`, `in`↔`not in` |
| BoolOp | `and`↔`or` |
| UnaryOp Not | remove the `not` |
| BinOp | `+`↔`-`, `*`↔`/` |
| Constant | `True`↔`False`; number `n`→`n+1`; non-empty string `s`→`s+"_MUT"` |
| Return | `return X`→`return None` (when X is not already None) |
| Raise | replace with `pass` |
| If | negate the condition |

Per mutant, the runner: writes the mutant file and deletes its cached bytecode (Python reuses a `.pyc` when the source's mtime in whole seconds and size match, and all string mutants have the same size, so without this a fast machine can run the previous mutant's code; found during replication on a Mac, fixed on 2026-09-29, and the shipped records were re-verified mutant by mutant with the fix); runs `pytest -q -x -p no:cacheprovider [EXTRA_PYTEST_ARGS] <suite args>` in the package directory (G2); if the PR touched test files, runs the same against only those files (G3); records killed/survived for each; restores the original file (in a `finally`). The baseline suite must be green before mutation starts, or the script aborts.

`EXTRA_PYTEST_ARGS` is read from the environment (used for `--noconftest` on cosmos). Suite arguments are passed after the four positional arguments.

Invocation pattern (the runner does this for every enabled PR):

```
cd gates
python g1_interface.py   <repo> <commit> <PR> <outdir>
python g2_g3_mutation.py <repo> <commit> <PR> <outdir> <pytest args for the package suite...>
```

Outputs: `pr<N>_G2.json` (includes `mutation_score` and the full `mutants` list) and `pr<N>_G3.json` (own-suite detection rate, or `no_pr_tests`).

Limitations of the mutator that affected results: a line that only deletes a call (e.g. `.rstrip("/")`) yields zero mutants (#45366); string mutations on log messages are cosmetic and inflate the survivor count (#44770, #46707, #41852); a version-string mutation is equivalent (#41492). Survivors were therefore reviewed by hand before being counted as meaningful. The paper's case-study table reports raw tool counts except for #41492, where the equivalent version-string mutant was excluded (1/4 rather than 1/5); this is stated in the change log.

### 4.4 G4 — claim–implementation correspondence (manual, one script per PR)

For each PR, the behavioral statements in the PR description were listed as claims. For each claim, a short Python script was written that would fail (or print a distinguishable result) if the claimed behaviour were absent. Each script was run twice: at the merge commit, and after checking out only the changed source files from the parent commit (`git checkout <commit>~1 -- <files>`), then the merge-commit files were restored. Where a claim could not be exercised offline (needs a live Azure service), this was recorded as "not checkable" rather than guessed.

Scripts: `g4_checks_pr44844.py`, `g4_checks_pr46707.py`, `g4_checks_pr41492.py`, `g4_checks_pr41852.py`, `g4_checks_pr43269.py`. For #44770 the check was a `git diff` against the hotfix PR it claims to port (Section 6.7). For #42047 the check was static (Section 6.5). The G4 evidence records were written by hand from the script outputs, with the same schema as the automated ones.

### 4.5 Evidence record schema

Every gate writes one JSON record:

```
gate_id, gate_type, linked_hypothesis_ids[], hypotheses{id: {category, statement}}   (links copied from experiments.yaml by the runner)
artifact_ref: {repo, pr, commit, files[]}
exercised[]        what was actually checked
assumptions[]      preconditions the gate relied on
result             "pass" | "findings" | "no_pr_tests"
findings[]         each with kind, and for defects: failure_mode, severity, detail
not_evaluated[]    what the gate could not or did not check  (mandatory; save() asserts it is non-empty)
tool_versions, timestamp, machine_time_s
```

Finding kinds used: `confirmed_defect`, `undocumented_limitation`, `evidence_gap`, `possible_claim_divergence`, `surviving_mutant`, `undetected_by_pr_tests`.

### 4.6 Triage rules

- **Confirmed defect**: behaviour at the merge commit contradicts a stated requirement, the PR's own description, or an unambiguous project convention; reproduced by a script; and it *escaped* (CI green at merge, no review comment mentioning it, present in merged code).
- **Undocumented limitation**: behaviour is defensible but the PR claims more than it delivers, or a property it restores/introduces has no test protecting it.
- **Evidence gap**: a surviving mutant or untested path that does not by itself contradict a claim.
- **False positive**: equivalent mutant, tool artifact, misread requirement.

Severity: *blocking* (violates a must-hold, or data loss/security exposure); *major* (user-visible wrong behaviour on a may-fail/cannot-guarantee or must-hold path); *minor* (no functional consequence or documentation-only).

Downstream confirmation: after triage, the repository's later history was searched (GitHub search API, `git show main:<path>`) for a fix or report of the same defect.

---

## 5. Trust-hypothesis classification

The hypotheses for each PR, with category, the gates serving each, and their source, are recorded in `replication/experiments.yaml` and copied into every gate's evidence record (`linked_hypothesis_ids`, `hypotheses`). **Classification of record:** an external rater (RN), who is not an author, extracted and classified the requirements from the PR descriptions alone, before seeing any code or result (`results/classification_rater_RN.md`): 15 requirements, 6 must-hold, 2 cannot-guarantee, 7 may-fail, none answered yes to both questions. These are the `hypotheses` H1..Hn. Requirements the analyst extracted and the rater did not are kept as `analyst_hypotheses` (A1..); they are not blind. The rater extracted none of the three requirements the confirmed defects violate; those three are analyst requirements (A1 of #41852, #43269, #44844). Requirements were extracted from each PR's description and linked issue and classified with the two-question procedure in the manuscript (question 1: would violation be a security/safety/integrity/compliance failure or make the system unfit? → must-hold; question 2: does correctness depend on an ambiguity, unobservable state, open-ended completeness, or absent reference? → cannot-guarantee; otherwise may-fail). The assistant's own labels (not blind) are kept in `results/classification_ai_pass.md` for the record.

---

## 6. Per-PR record

Each subsection gives: what the PR did, how tests were run, gate results with the exact survivors, the G4 checks with before/after output, and the triage.

### 6.1 PR #45366 — azure-core, `format_url` trailing slash (smoke test)

**Change.** One line in `azure/core/pipeline/transport/_base.py`: removed `.rstrip("/")` from the base-URL computation; one new test in `tests/test_pipeline.py`.

**Tests.** `pytest tests/test_pipeline.py` — 54 passed (after installing `opentelemetry-sdk`, the package's `coretestserver` test helper, and `azure-sdk-tools`).

**G1.** Pass; 1 changed line, 0 module-attribute references.
**G2/G3.** 0 mutants: the changed line has no node the operators apply to. Reported as such.
**G4.** Not run; the PR's own test covers the exact scenario from the linked issue.
**Triage.** No findings. Retained in the table as a tooling smoke test only.

### 6.2 PR #46707 — azure-confidentialledger, `assert` → `ValueError` in receipt verification

**Change.** 54 lines in `azure/confidentialledger/receipt/_receipt_verification.py`: every `assert` in receipt-content validation replaced by `_check(cond)` raising `ValueError("The receipt content is invalid.")`; two explicit `ValueError`s in certificate handling. No test changes. PR body cites an internal incident (IcM link).

**Hypotheses.** H1 must-hold: malformed receipts are rejected. H2 must-hold: rejection holds under `python -O` (which strips `assert`).

**Tests.** `pytest tests/receipt` — 67 passed (needs `azure-identity` and `azure-confidentialledger-certificate` from the monorepo).

**G1.** Pass; 32 changed lines, 1 attribute reference resolved.

**G2.** 46 mutants, 42 killed (0.91). Survivors:

| Line | Mutant | Meaning |
|---|---|---|
| 143 | `"right"` → `"right_MUT"` | in `_check("left" in elem or "right" in elem)` |
| 143 | `in` → `not in` (right operand) | same line |
| 147 | `"right"` → `"right_MUT"` | in `_check(isinstance(elem["right"], str))` |
| 381 | remove `raise` | non-EC public-key rejection |

Interpretation: no receipt in the test corpus has a Merkle-proof element with only a `right` sibling, and no test feeds a non-EC certificate. Both paths are must-hold validation logic.

**G3.** Not applicable (no PR tests). Recorded as `no_pr_tests`.

**G4** (`g4_checks_pr46707.py`). Five inputs: receipt missing `signature`; proof element with neither `left` nor `right`; `right` not a string; a valid right-only element; an RSA (non-EC) certificate generated with `cryptography`. Run under `python` and `python -O`, at merge commit and parent:

| Input | Parent, `python` | Parent, `python -O` | PR, `python` | PR, `python -O` |
|---|---|---|---|---|
| missing signature | ValueError | **accepted** | ValueError | ValueError |
| no left/right | ValueError | **accepted** | ValueError | ValueError |
| right not str | ValueError | **accepted** | ValueError | ValueError |
| right-only valid | accepted | accepted | accepted | accepted |
| RSA cert | ValueError | **accepted** | ValueError | ValueError |

Also: `grep -c "^\s*assert "` on the file → 0 after the PR.

**Triage.** Claim supported; the fix is real and closes a genuine must-hold gap. Two undocumented limitations: (a) no test runs under `-O`, so the restored property has no regression protection (a future revert to `assert` passes CI); (b) right-sibling and non-EC paths unverified. No defect attributed to the PR.

**CEL.** Claim: receipt validation rejects the malformed classes exercised, with or without assert stripping; scope: left-sibling proofs, EC certificates. Evidence: G4 table; 42/46 mutants killed; 67 tests green. Limitations: right-sibling and non-EC paths unverified; no `-O` regression test; live-ledger receipts not tested.

### 6.3 PR #44844 — azure-ai-evaluation, nested `NodeLogManager` recursion guard

**Change.** `azure/ai/evaluation/_legacy/_common/_logging.py` (+25/−4): `NodeLogManager.__init__` reuses an existing `NodeLogWriter` if `sys.stdout`/`sys.stderr` already is one; `NodeLogWriter` gains `_resolve_prev_out()` that unwraps chained writers with cycle detection and falls back to `sys.__stdout__`/`__stderr__`. New `tests/unittests/test_logging.py` with two tests (a 2-writer chain writes through; 500-deep nested managers don't recurse and text reaches the base streams).

**Hypotheses.** H1 must-hold: nested managers do not recurse. H2 must-hold: per-run log attribution is preserved across nesting. H3 cannot-guarantee: fallback when real streams are replaced.

**Tests.** `PYTHONPATH=<pkg> pytest tests/unittests/test_logging.py` — 2 passed. `grep -rl NodeLogManager tests` shows this is the only test file touching the module, so package suite = PR tests here.

**G1.** Pass; 25 changed lines, 8 attribute references resolved.

**G2 = G3.** 13 mutants, 6 killed (0.46). Survivors: L174 negate `if isinstance(sys.stdout, NodeLogWriter)`; L178 negate the stderr twin; L181 `is_stderr=True`→`False`; L263 `return 0`→`return 1` (write when no stream); L282 `is not`→`is` and negate (flush path); L295 `return self._fallback_out`→`None` (cycle path). Both "reuse existing writer" branches can be negated without any test noticing.

**G4** (`g4_checks_pr44844.py`). Three checks. C1: construct a two-writer cycle (`a._prev_out = b; b._prev_out = a`) and write → reaches fallback at merge commit; `RecursionError` at parent. C2: nested `with NodeLogManager()` → `inner.stdout_logger is outer.stdout_logger` True at merge commit, False at parent. S (the decisive one): the production caller's exact sequence, taken from `azure/ai/evaluation/_legacy/_batch_engine/_engine.py` lines 445–446 (`log_manager = NodeLogManager(); log_manager.set_node_context(run_id, "Flex", line_number); with log_manager, ...:`), nested once:

```
outer = NodeLogManager(); outer.set_node_context("r1", "Flex", 1)
with outer:
    print("outer-before")
    inner = NodeLogManager(); inner.set_node_context("r2", "Flex", 1)
    with inner:
        print("inner-line")
    print("outer-after")
```

| | r1 log has `outer-after` | r2 log has `outer-after` |
|---|---|---|
| parent | yes | no |
| merge commit | **no** | **yes** |

Note: the first version of this check used a hypothetical sequence (inner calls `clear_node_context`); it was replaced by the engine's actual sequence before the finding was accepted. Only the second result is reported.

**Downstream check.** `git show main:<path> | grep "isinstance(sys.stdout, NodeLogWriter)"` → present on 2026-09-28; no later fix found.

**Triage.** Confirmed defect, failure mode assumption injection, severity major: sharing one writer shares its `ContextVar` and `run_id_to_stdout` map; the inner `set_node_context` overwrites the outer context and nothing restores it on inner exit, so outer-line output after a nested evaluation is attributed to the inner run. Escaped: CI green, no review comment, PR tests check only that text reaches the base stream. Evidence gap: 7/13 mutants survive including both reuse branches.

### 6.4 PR #41492 — azure-ai-evaluation, `int()` → `float()` in threshold comparison

**Change.** Two lines in `_evaluators/_common/_base_eval.py` (`int(score_value)` → `float(score_value)` in both the higher-is-better and lower-is-better branches); version bump; 47 new test lines in `tests/unittests/test_evaluators/test_threshold_behavior.py` (Meteor and Bleu evaluators with decimal thresholds).

**Hypotheses.** H1 must-hold: pass/fail reflects a float comparison. H2 must-hold: lower-is-better evaluators (the content-safety ones) fail when the score exceeds the threshold.

**Tests.** With `AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true`: PR file 18 passed; `tests/unittests/test_evaluators` 38 passed.

**G1.** Pass.

**G2 = G3.** 5 mutants, 1 killed (L419 negate). Survivors: L419 `>=`→`>`; L424 `<=`→`<`; L424 negate (entire lower-is-better branch); `_version.py` string (equivalent, excluded → reported 1/4).

**G4** (`g4_checks_pr41492.py`). C2: `F1ScoreEvaluator(threshold=0.5)` on strings giving f1 = 0.800 → parent `fail`, PR `pass`. C3: a synthetic `EvaluatorBase` subclass with `_higher_is_better=False` and a stubbed `_do_eval`: score 2.5 vs threshold 2 → parent `pass` (wrong), PR `fail`; score 0.4 vs 0.5 → pass both; 2.0 vs 2 → pass both. C4: score == threshold (higher-is-better) → parent `fail`, PR `pass`. R: score `"N/A"` → both versions swallow the exception with `print()` and emit no `_result` key (pre-existing).

**Triage.** All claims supported. Two undocumented limitations: the lower-is-better branch had the inverse bug and is fixed but untested by the PR (its negate mutant survives); the equality boundary is untested. Pre-existing evidence gap: non-numeric scores are silently swallowed. No defect attributed.

### 6.5 PR #42047 — azure-ai-evaluation, randomization seed across simulators

**Change.** `_safety_evaluation.py` forwards `randomization_seed` to `Simulator`; `_adversarial_simulator.py` uses a local `random.Random(seed)` for template shuffling instead of `random.seed()`; `_indirect_attack_simulator.py` and `_simulator.py` gain a `randomization_seed` parameter and seeded shuffle. 48 new test lines in `tests/unittests/test_safety_evaluation.py`.

**Hypotheses.** H1 must-hold: same seed yields the same query set (the PR's stated purpose). H2 may-fail: global random state untouched.

**Tests.** Suite used: `test_safety_evaluation.py` + `test_non_adv_simulator.py` (54 tests). `test_simulator.py` and `test_jailbreak_simulator.py` error at collection without credentials and were excluded.

**G1.** Pass.

**G2 = G3.** 5 mutants, 0 killed: `_indirect_attack_simulator.py` L200 `is not`→`is`, negate; `_simulator.py` L168 `is not`→`is`, `and`→`or`, negate. (The adversarial-simulator lines have no mutable nodes.) Inspection of the two new tests: `test_randomization_seed_consistency` and `test_local_random_no_global_state_pollution` construct `random.Random(seed)` objects and assert on them; neither imports or calls a simulator.

**G4** (static; no script). `_safety_evaluation.py` does forward the seed (diff line confirms). `_adversarial_simulator.py` collects results with `for task in asyncio.as_completed(tasks): sim_results.append(await task)` (line ~304), so returned order is completion order regardless of seed. Row count is `min(total_tasks, max_simulation_results)` and `template_parameter_pairs[:max_simulation_results]`; nothing in the diff touches this. The PR body's problem statement is that two runs with the same seed returned *different counts*.

**Triage.** Seed forwarding and no-global-pollution supported statically. "Identical query sets" not checkable offline; the seeding change does not obviously address the reported count symptom. Recorded as *possible* claim divergence pending a live run, plus an evidence gap (0/5; tests exercise the standard library). Not counted as a confirmed defect.

### 6.6 PR #41852 — azure-ai-evaluation, lazy imports for optional converters

**Change.** `azure/ai/evaluation/__init__.py`: the import-time `try/except ImportError: print("[INFO] …")` blocks for `AIAgentConverter` and `SKAgentConverter` replaced by a `_lazy_imports` dict, a module-level `__getattr__` that performs the import on access and raises `ImportError` with an install hint, and the two names added to `__all__` ("so they appear as available"). New `tests/unittests/test_lazy_imports.py` (135 lines).

**Hypotheses.** H1 may-fail: no output at import time. H2 must-hold: the public import surface remains usable for users without the optional dependency.

**Tests.** `test_lazy_imports.py` + `tests/unittests/test_evaluators` as suite. Inspection of `test_lazy_imports.py`: it defines its own `_create_lazy_import` and a "Mock `__getattr__` function like the one in `__init__.py`" and tests those.

**G1.** Pass.

**G2 = G3.** 20 mutants, 0 killed, including L148 negate `if name in _lazy_imports`, L149 `return None`, L150 remove `raise`, and every string in the lazy-import table.

**G4** (`g4_checks_pr41852.py`), with `azure-ai-projects` absent (verified: `import azure.ai.projects` → `ModuleNotFoundError`):

| Check | Parent | Merge commit |
|---|---|---|
| C1 stdout during `import azure.ai.evaluation` | `[INFO] Could not import AIAgentConverter…` | (nothing) |
| C2 `ev.AIAgentConverter` | `AttributeError` | `ImportError` with install hint |
| S1 `hasattr(ev, "AIAgentConverter")` | `False` | **raises `ImportError`** |
| S2 `from azure.ai.evaluation import *` | succeeds | **raises `ImportError`** |
| S3 `"AIAgentConverter" in ev.__all__` | `False` | `True` |

**Downstream check.** `git show main:…/__init__.py`: `__getattr__` and `_lazy_imports` still present, but the two names are no longer in `__all__`. GitHub search `repo:Azure/azure-sdk-for-python is:pr is:merged AIAgentConverter import` returned PR **#42313** by a human maintainer (`kdestin`), merged 2025-07-31, titled "[evaluation] fix: Remove lazy imports from `__all__`", whose description says it removes lazy imports from `__all__` "to unblock a release gate that tries to import everything from `__all__` (which fails since we raise an ImportError)". #41852 merged 2025-07-14: 17 days earlier.

**Triage.** Confirmed defect, failure mode assumption injection, severity major, escaped (CI green at merge, no review comment), and downstream-confirmed by #42313. Evidence gap: 0/20; the PR's tests test a copy of the mechanism.

### 6.7 PR #44770 — azure-cosmos, port of hotfix #44649 (partition-split recursion)

**Change.** Ports six source files from a human-authored hotfix PR (#44649, hotfix branch) to `main`: an `_internal_pk_range_fetch` flag set by the routing-map provider when it fetches partition-key ranges and popped before the HTTP request; the execution context skips its 410 retry loop when the flag is set (preventing infinite recursion); state reset (`_has_started=False`, `_continuation=None`) on 410 retry; logging. Two new unit-test files (328 + 317 lines) and a one-line `**kwargs` change in an existing test.

**Hypotheses.** H1 must-hold: the port matches #44649. H2 must-hold: a PK-range fetch never recurses on 410.

**Tests.** `pytest --noconftest tests/test_partition_split_retry_unit.py tests/test_partition_split_retry_unit_async.py tests/routing/test_routing_map_provider.py tests/test_base_unit.py` (baseline green; the async file's collection count was not separately verified).

**G1.** Pass.

**G2 = G3.** 34 mutants, 8 killed (0.24). Killed: the execution-context guard (`_internal_pk_range_fetch` key string, `False`→`True` default, negate, `return None`) in both sync and async. Survivors: all log-message strings (cosmetic); **`self._has_started = False`→`True` in sync (L186) and async (L188)** (the state reset is untested); `return []`→`None` at the unreachable loop exit; **`_internal_pk_range_fetch: True`→`False` and its key string in `routing_map_provider.py` (sync L77, async L91)**; the key string in `_synchronized_request.py` L90 and `_asynchronous_request.py` L60 (the pop). I.e. the anti-recursion mechanism is tested only at the execution-context layer.

**G4** (port fidelity). `git fetch --depth=1 origin pull/44649/head:pr44649`, then `git diff pr44649 9a8a19a39 -- <each of the six files>`:

| File | Difference |
|---|---|
| `_execution_context/base_execution_context.py` | +4 lines: one `_LOGGER.warning` before the unreachable `return []` (requested in review) |
| `_execution_context/aio/base_execution_context.py` | same |
| `_routing/routing_map_provider.py`, `_routing/aio/routing_map_provider.py` | identical |
| `_synchronized_request.py`, `aio/_asynchronous_request.py` | differ only by unrelated `main`-branch drift (hedging / availability-strategy code); `kwargs.pop("_internal_pk_range_fetch", None)` present in both versions of both files |

**Triage.** Port claim supported. Two undocumented limitations: state reset untested; flag untested at provider and request layers. No defect attributed.

### 6.8 PR #43269 — azure-cosmos, optional `max_concurrency` and `create_database` overloads

**Change.** Sync `read_items`: `max_concurrency` becomes `Optional[int] = None` (ThreadPoolExecutor default). Async: `aio/_container.py` default `None`; **`aio/_read_items_helper_async.py` default changed from `10` to `5` with `self.max_concurrency = max_concurrency if max_concurrency and max_concurrency > 0 else 5`**. `create_database` overloads gain `response_hook`, drop `populate_query_metrics`, make `offer_throughput` keyword-only; implementations call `response_hook(self.client_connection.last_response_headers)`. No tests, no CHANGELOG entry. The PR body states: "**Async path unchanged:** The async version … retains `max_concurrency: int = 10`" and "# Async: Continues to use default of 10".

**Hypotheses.** H1 may-fail: sync default follows ThreadPoolExecutor. H2 must-hold: async behaviour unchanged (as stated). H3 may-fail: `response_hook` invoked.

**Tests.** `--noconftest` with `test_base_unit.py`, `test_session_token_unit.py`, `tests/routing/test_routing_map_provider.py` (none cover the changed code).

**G1.** Pass (after the BOM fix).

**G2.** 9 mutants, 0 killed (including `5`→`6`, `and`→`or`, `>`→`>=` on the async helper line and the `response_hook` negate). **G3** n/a.

**G4** (`g4_checks_pr43269.py`): `inspect.signature(ReadItemsHelperAsync.__init__).parameters["max_concurrency"].default` and the effective `self.max_concurrency` when the argument is omitted:

| | Parent | Merge commit | `main` (2026-09-28) |
|---|---|---|---|
| async helper default | 10 | **5** | 5 |

The docstring the PR wrote for `create_database`'s `response_hook` types it as a two-argument callable; the implementation calls it with one argument (consistent with other `cosmos_client.py` hooks); minor documentation inconsistency.

**Triage.** Confirmed defect, failure mode claim–implementation divergence, severity minor: the description asserts the async path is unchanged; the code halves the async default with no changelog. Escaped; still on `main`. Evidence gap: 0/9, no tests.

---

## 7. Aggregate results (as reported in the article's case-study table, Table 1 after the length cuts)

| PR | PR tests | G2 killed/total | G3 killed/total | Outcome |
|---|---|---|---|---|
| #44844 | yes | 6/13 | 6/13 | escaped defect (assumption injection) |
| #41852 | yes | 0/20 | 0/20 | escaped defect, downstream-confirmed (#42313) |
| #43269 | none | 0/9 | — | escaped defect (claim–implementation divergence) |
| #46707 | none | 42/46 | — | 2 limitations |
| #41492 | yes | 1/4* | 1/4* | 2 limitations |
| #44770 | yes | 8/34 | 8/34 | 2 limitations |
| #42047 | yes | 0/5 | 0/5 | possible divergence (unconfirmed) + gap |
| #45366 | yes | 0/0 | — | smoke test |

\* tool reported 1/5; one equivalent version-string mutant excluded.

Totals: 8 PRs (7 substantive); 3 escaped confirmed defects in 3 PRs, 1 confirmed downstream; 7 undocumented limitations; of the 5 PRs with their own tests, none killed more than half of the mutants on its changed lines with those tests, and 2 killed none. G4 accounted for all three defects; a surviving G2 mutant pointed at the relevant line in two of the three (#44844 L174/L178; #43269 L51/L60), not in #41852 (where the survivors were global and the pointer was the `__all__` change itself). G1 produced no findings.

Effort: machine time per PR under two minutes (mutation runs of 5–46 mutants × 0.3–5 s suites); analyst time 25–45 minutes per PR for G4 design and triage, plus 10–40 minutes of one-off environment setup per package.

---

## 8. Files

```
replication/
  experiments.yaml              repo, setup, environment profiles, gate scripts, extra gates, PR list (enabled flag), hypotheses, G4 checks
  requirements.txt              Python dependencies (installed by `setup`)
  run_experiments.py            config-driven runner (list | setup | run | summary | compare | clean)
  EXTENDING.md                  manual for extending to new PRs, repositories, environments and gates
  gates/common.py               changed-line extraction, package-root lookup, Evidence class
  gates/g1_interface.py         G1
  gates/g2_g3_mutation.py       G2 + G3
  gates/g4_checks_pr<N>.py      G4 scripts for #44844, #46707, #41492, #41852, #43269 (run at merge commit and at parent)
  gates/example_extra_gate.py   template for a new gate
results/
  evidence/pr<N>_G1.json, _G2.json, _G3.json   for the eight PRs;  _G4.json and _G4_output.txt for the seven with a G4 check
  classification_sheet.md       blind classification sheet for the human rater; classification_ai_pass.md holds the assistant's labels
  RESULTS.md                    narrative write-up
supplement/
  pr41852_walkthrough.tex/.pdf, pr44844_walkthrough.tex/.pdf, case_cards.tex/.pdf
```

---

## 9. What a human must redo before citing any of this

1. ~~Reproduce the three defects~~ Done 2026-09-29 by the first author on macOS (`results/evidence_replication_macos_2026-09-29/`): all 24 automated records and all 7 G4 outputs identical to the originals. Still to do: verify the #42313 description on GitHub directly.
2. ~~Blind classification by a human rater~~ Done 2026-10-02 by RN (`results/classification_rater_RN.md`); labels in `experiments.yaml`, shipped records re-linked.
3. **Independent triage** of every finding in `results/evidence/*_G4.json` and of the severity labels; decide #42047 (live run, or downgrade to a limitation).
4. **Equivalent-mutant review** of the G2 survivors for #46707, #44770, #41852 (log strings) and record which were discounted.
5. **Record the selection funnel**: number of Copilot-agent PRs in the repository meeting each inclusion criterion, and the reason each excluded candidate was excluded.
6. Pin dependency versions and container image for the replication package.

## 10. Known limitations of this study as run

- One repository, one agent, Python only.
- One analyst for all judgment steps (the assistant); no blinding. In particular, the assistant's trust-hypothesis labels were written after the diffs had been inspected and the gates run, so they are informed by the findings; only the external human rater's classification (and the second, blind AI pass) were made from the descriptions alone.
- The mutator has nine operators and no statement deletion; single-call removals produce no mutants.
- Test-suite selection per package was pragmatic (offline-runnable subsets), so G2 kill rates are against a subset of each package's tests, not its full CI suite; G3 is unaffected by this.
- "Still on `main`" checks were done on one date (2026-09-28).
- The stale-bytecode bug in the mutation runner (Section 4.3) was found only during replication on a faster machine; with the fix, the full study was reproduced on that machine (macOS, Python 3.12.4) with every record and G4 output identical to the originals.
- Analyst-time figures are the assistant's, not a human's.

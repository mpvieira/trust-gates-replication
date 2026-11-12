# Replication Runbook: every command, in order

This runbook repeats the case study from a fresh Linux machine. Commands are meant to be pasted verbatim; each block states what it does and what output to expect. Paths assume a working directory `$W` (set in Step 0). Steps 0–3 are done once; Step 4 is repeated per PR (or automated, Section 8); Steps 5–7 are done once at the end. `replication/run_experiments.py` (Section 8) automates Steps 4a–4f for the PRs enabled in `replication/experiments.yaml`; G4 outputs are captured to files for a person to read.

Requirements: Linux with Python 3.12, git ≥ 2.40, ~4 GB disk, network access to github.com and pypi.org.

---

## Step 0 — Working directory

The manual steps below use `$W` for the work directory. The simplest choice is the package's `replication/` folder itself (the runner's default); if that folder is cloud-synced, use a separate directory and copy the scripts:

```bash
export W=$HOME/trustgates
cp -r <repo>/replication $W
mkdir -p $W/evidence
cp -r <repo>/results/evidence $W/evidence_original     # shipped records, for comparison
ls $W $W/gates
```
Expected: `EXTENDING.md README.md experiments.yaml gates requirements.txt run_experiments.py evidence evidence_original` and, in `gates/`: `common.py example_extra_gate.py g1_interface.py g2_g3_mutation.py g4_checks_pr41492.py g4_checks_pr41852.py g4_checks_pr43269.py g4_checks_pr44844.py g4_checks_pr46707.py`.

## Step 1 — Python environment

```bash
cd $W && python3 -m venv venv && . venv/bin/activate && pip install -q --upgrade pip
pip install -q -r $W/requirements.txt          # the authoritative list; equivalently:
pip install -q pyyaml pytest pytest-cov pytest-mock pytest-asyncio pytest-trio pyflakes trio requests aiohttp httpx \
  typing-extensions packaging cryptography "opentelemetry-sdk~=1.26" opentelemetry-instrumentation-requests \
  "pyjwt>=2.8.0" "nltk>=3.9.1" azure-storage-blob "pandas<3" "openai>=1.108.0" ruamel.yaml msrest Jinja2 filelock certifi truststore
# NLTK data for the evaluation tests (punkt, punkt_tab, wordnet, omw-1.4). NLTK's own downloader fails on many macOS builds
# (CERTIFICATE_VERIFY_FAILED); the runner's `setup` fetches the four files directly with requests+certifi. By hand:
python - << 'PY'
import nltk, requests, certifi, zipfile, io
from pathlib import Path
dest = Path(nltk.data.path[0]); base = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages"
for name, sub in [("punkt","tokenizers"),("punkt_tab","tokenizers"),("wordnet","corpora"),("omw-1.4","corpora")]:
    data = requests.get(f"{base}/{sub}/{name}.zip", timeout=120, verify=certifi.where()).content
    (dest/sub).mkdir(parents=True, exist_ok=True); (dest/sub/f"{name}.zip").write_bytes(data)
    if sub == "tokenizers": zipfile.ZipFile(io.BytesIO(data)).extractall(dest/sub)
    print(name, "ok")
PY
pip freeze > $W/requirements-frozen.txt     # keep this with the replication package
```

## Step 2 — Clone the repository (treeless, shallow, sparse)

```bash
cd $W
git clone --filter=tree:0 --depth 12000 --no-checkout --single-branch --branch main \
  https://github.com/Azure/azure-sdk-for-python.git azsdk
cd azsdk
git sparse-checkout init --cone
git sparse-checkout set sdk/core/azure-core sdk/confidentialledger/azure-confidentialledger \
  sdk/confidentialledger/azure-confidentialledger-certificate sdk/identity/azure-identity \
  sdk/evaluation/azure-ai-evaluation sdk/cosmos/azure-cosmos eng/tools/azure-sdk-tools tools/azure-sdk-tools
git log --oneline | wc -l
```
Expected: `12000`. Note: `main` has moved since 2026-09-28; if a merge commit below is no longer within 12,000 commits, increase `--depth` (or use `git fetch --deepen=10000`).

Locate the eight squash-merge commits and confirm the hashes:

```bash
cd $W/azsdk
for n in 45366 46707 44844 41492 42047 41852 44770 43269; do
  printf "#%s  " $n; git log --format='%h %ad %s' --date=short --grep="(#$n)" | head -1
done
```
Expected first 9 characters of each hash: `41391f1e7`, `53dcd7783`, `7d26b949`, `0c347e994`, `54d45994a`, `d76b8ba34`, `9a8a19a39`, `7e59645b2`. If a PR is missing, deepen the clone.

## Step 3 — Install the SDK packages used by the gates

Packages are installed editable from the checkout so that `git checkout <commit>` changes what is imported. Install once at any recent commit; reinstall `azure-sdk-tools` when its path changes (see 4b).

```bash
cd $W/azsdk && git checkout -q 7d26b949 && . $W/venv/bin/activate
pip install -q -e sdk/core/azure-core -e sdk/identity/azure-identity \
  -e sdk/confidentialledger/azure-confidentialledger-certificate -e sdk/confidentialledger/azure-confidentialledger \
  -e sdk/core/azure-core/tests/testserver_tests/coretestserver -e sdk/cosmos/azure-cosmos
pip install -q -e eng/tools/azure-sdk-tools
python -c "import azure.core, azure.confidentialledger, azure.cosmos, ci_tools, devtools_testutils; print('ok')"
```
`azure-ai-evaluation` is **not** pip-installed (its `setup.py` fails to build editable at 2025 commits); it is used via `PYTHONPATH` (Step 4).

---

## Step 4 — Per-PR procedure

Do 4a–4f for each PR. The per-PR parameters are in the table; the commands follow.

| PR | commit | package dir (`$PKG`) | `$ENV` | suite args (`$SUITE`) |
|---|---|---|---|---|
| 45366 | `41391f1e7b5ad52e3d480a7adcbf3fa5b99e2326` | `sdk/core/azure-core` | — | `tests/test_pipeline.py tests/test_basic_transport.py` |
| 46707 | `53dcd7783357a76ba374dec23c46ef772865231c` | `sdk/confidentialledger/azure-confidentialledger` | — | `tests/receipt` |
| 44844 | `7d26b949` | `sdk/evaluation/azure-ai-evaluation` | EVAL | `tests/unittests/test_logging.py` |
| 41492 | `0c347e994` | `sdk/evaluation/azure-ai-evaluation` | EVAL | `tests/unittests/test_evaluators` |
| 42047 | `54d45994a` | `sdk/evaluation/azure-ai-evaluation` | EVAL | `tests/unittests/test_safety_evaluation.py tests/unittests/test_non_adv_simulator.py` |
| 41852 | `d76b8ba34` | `sdk/evaluation/azure-ai-evaluation` | EVAL | `tests/unittests/test_lazy_imports.py tests/unittests/test_evaluators` |
| 44770 | `9a8a19a39` | `sdk/cosmos/azure-cosmos` | COSMOS | `tests/test_partition_split_retry_unit.py tests/test_partition_split_retry_unit_async.py tests/routing/test_routing_map_provider.py tests/test_base_unit.py` |
| 43269 | `7e59645b2` | `sdk/cosmos/azure-cosmos` | COSMOS | `tests/test_base_unit.py tests/test_session_token_unit.py tests/routing/test_routing_map_provider.py` |

`$ENV` meanings:
- **all packages**: `export AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true` (makes the autouse `test_proxy` fixture in every `tests/conftest.py` a no-op; without it the fixture tries to download and start a proxy binary, which fails on some machines).
- **EVAL**: additionally `export PYTHONPATH=$W/azsdk/sdk/evaluation/azure-ai-evaluation`.
- **COSMOS**: `export EXTRA_PYTEST_ARGS=--noconftest` (the cosmos conftest connects to an emulator). Unset `PYTHONPATH`.
- **—**: nothing beyond the two variables above. Unset `PYTHONPATH` and `EXTRA_PYTEST_ARGS`.

### 4a. Check out the merge commit and inspect the change

```bash
cd $W/azsdk && git checkout -q <commit>
git show --stat --format="%H %ad %s" --date=short <commit> | cat        # files changed
git show --format= <commit> -- '*.py' | grep -E '^[+-]' | grep -v '^+++\|^---' | head -80   # the diff
```

### 4b. Re-point `azure-sdk-tools` if its location changed

At 2025 commits the tools live in `tools/azure-sdk-tools`; at 2026 commits in `eng/tools/azure-sdk-tools`. The editable install must point at whichever exists:

```bash
cd $W/azsdk && . $W/venv/bin/activate
if [ -f eng/tools/azure-sdk-tools/pyproject.toml ] || [ -f eng/tools/azure-sdk-tools/setup.py ]; then
  pip install -q -e eng/tools/azure-sdk-tools
else
  pip install -q -e tools/azure-sdk-tools
fi
python -c "import ci_tools, devtools_testutils; print('tools ok')"
```

### 4c. Set the environment and confirm the baseline suite is green

```bash
unset PYTHONPATH EXTRA_PYTEST_ARGS
export AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true
# then, per the table:
#   EVAL:   export PYTHONPATH=$W/azsdk/sdk/evaluation/azure-ai-evaluation AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true
#   COSMOS: export EXTRA_PYTEST_ARGS=--noconftest
cd $W/azsdk/$PKG
python -m pytest -q -p no:cacheprovider $EXTRA_PYTEST_ARGS $SUITE | tail -2
```
Expected: all passed (counts from a clean environment on 2026-09-29: 45366 → 118; 46707 → 67; 44844 → 2; 41492 → 38; 42047 → 52 plus 2 warnings; 41852 → 41; 44770 → 21; 43269 → 19; small count differences with other dependency versions are normal as long as nothing fails). If the suite is not green, `g2_g3_mutation.py` refuses to run; fix the environment first.

### 4d. Gate G1

```bash
cd $W/gates && python g1_interface.py $W/azsdk <commit> <PR> $W/evidence
```
Expected for all eight: `"result": "pass"`, `"findings": []`. Output file `$W/evidence/pr<PR>_G1.json`.

### 4e. Gates G2 and G3

```bash
cd $W/gates && python g2_g3_mutation.py $W/azsdk <commit> <PR> $W/evidence $SUITE
```
Prints one line per mutant (`suite=K|SURVIVED  own=K|SURVIVED|n/a`) and a JSON summary. Expected summaries:

| PR | mutants | killed by suite | killed by PR tests |
|---|---|---|---|
| 45366 | 0 | — | — |
| 46707 | 46 | 42 | n/a (no PR tests) |
| 44844 | 13 | 6 | 6 |
| 41492 | 5 | 1 | 1 (version-string mutant is equivalent → report 1/4) |
| 42047 | 5 | 0 | 0 |
| 41852 | 20 | 0 | 0 |
| 44770 | 34 | 8 | 8 |
| 43269 | 9 | 0 | n/a |

Compare with the originals with the runner, which ignores timing and tool-version fields and names any mutant whose result differs: `cd $W && python run_experiments.py compare --prs <PR>` (it reads the shipped records from the package's `results/evidence/`, so keep `results/` next to `replication/`).

The script restores the mutated file in a `finally` block; if it is interrupted, run `git -C $W/azsdk checkout -- .` before continuing.

### 4f. Gate G4 (claim checks) — run at the merge commit, then at the parent

The pattern is identical for every PR: run the script, check out only the changed source files from the parent, run again, restore.

**#46707**
```bash
cd $W/azsdk/sdk/confidentialledger/azure-confidentialledger && F=azure/confidentialledger/receipt/_receipt_verification.py
echo "== after PR";     python    $W/gates/g4_checks_pr46707.py
echo "== after, -O";    python -O $W/gates/g4_checks_pr46707.py
git checkout -q 53dcd7783357a76ba374dec23c46ef772865231c~1 -- $F
echo "== before PR";    python    $W/gates/g4_checks_pr46707.py
echo "== before, -O";   python -O $W/gates/g4_checks_pr46707.py
git checkout -q 53dcd7783357a76ba374dec23c46ef772865231c -- $F
grep -c '^\s*assert ' $F        # expected 0
```
Expected: after the PR all five inputs → `ValueError` in both modes; before the PR under `-O` all five → `accepted`.

**#44844** (EVAL env)
```bash
cd $W/azsdk/sdk/evaluation/azure-ai-evaluation && F=azure/ai/evaluation/_legacy/_common/_logging.py
echo "== after PR";  python $W/gates/g4_checks_pr44844.py 2>&1 | grep -v execution.flow
git checkout -q 7d26b949~1 -- $F
echo "== before PR"; python $W/gates/g4_checks_pr44844.py 2>&1 | grep -v execution.flow
git checkout -q 7d26b949 -- $F
sed -n 443,448p azure/ai/evaluation/_legacy/_batch_engine/_engine.py    # the production call sequence the script mirrors
```
Expected after PR: `r1 log has outer-before=True outer-after=False` and `r2 log has inner-line=True outer-after=True`. Before PR: `outer-after=True` in r1, `False` in r2.

**#41492** (EVAL env)
```bash
cd $W/azsdk/sdk/evaluation/azure-ai-evaluation && F=azure/ai/evaluation/_evaluators/_common/_base_eval.py
echo "== after PR";  python $W/gates/g4_checks_pr41492.py 2>&1 | grep -v "^Error calc\|INFO"
git checkout -q 0c347e994~1 -- $F
echo "== before PR"; python $W/gates/g4_checks_pr41492.py 2>&1 | grep -v "^Error calc\|INFO"
git checkout -q 0c347e994 -- $F
```
Expected after PR: `C2 … -> pass`, `C3 … score=2.5 threshold=2 -> fail`, `C4 … -> pass`. Before PR: `C2 -> fail`, `C3 score=2.5 -> pass (correct: fail)`, `C4 -> fail`.

**#41852** (EVAL env; requires `azure-ai-projects` to be absent — verify with `python -c "import azure.ai.projects"` → `ModuleNotFoundError`)
```bash
cd $W/azsdk/sdk/evaluation/azure-ai-evaluation
F="azure/ai/evaluation/__init__.py azure/ai/evaluation/red_team/__init__.py"
echo "== after PR";  python $W/gates/g4_checks_pr41852.py
git checkout -q d76b8ba34~1 -- $F
echo "== before PR"; python $W/gates/g4_checks_pr41852.py
git checkout -q d76b8ba34 -- $F
```
Expected after PR: `S1 hasattr -> raises ImportError`, `S2 'from azure.ai.evaluation import *' -> raises ImportError`, `S3 … True`. Before: `S1 -> False`, `S2 -> ok`, `S3 False`, and `C1` shows the `[INFO]` line.

**#43269** (COSMOS env)
```bash
cd $W/azsdk/sdk/cosmos/azure-cosmos
F="azure/cosmos/aio/_read_items_helper_async.py azure/cosmos/cosmos_client.py"
echo "== after PR";  python $W/gates/g4_checks_pr43269.py
git checkout -q 7e59645b2~1 -- $F
echo "== before PR"; python $W/gates/g4_checks_pr43269.py
git checkout -q 7e59645b2 -- $F
```
Expected: `async helper signature default: 5` / `effective … 5` after; `10` / `10` before.

**#44770** — port fidelity by diff against the human hotfix PR
```bash
cd $W/azsdk && git fetch -q --depth=1 origin pull/44649/head:pr44649
for f in azure/cosmos/_execution_context/base_execution_context.py azure/cosmos/_execution_context/aio/base_execution_context.py \
         azure/cosmos/_routing/routing_map_provider.py azure/cosmos/_routing/aio/routing_map_provider.py \
         azure/cosmos/_synchronized_request.py azure/cosmos/aio/_asynchronous_request.py; do
  echo "== $f: $(git diff --stat pr44649 9a8a19a39 -- sdk/cosmos/azure-cosmos/$f | tail -1)"
done
git diff pr44649 9a8a19a39 -- sdk/cosmos/azure-cosmos/azure/cosmos/_execution_context/base_execution_context.py | grep '^[+-]' | grep -v '^+++\|^---'
for r in pr44649 9a8a19a39; do echo "== $r"; git show $r:sdk/cosmos/azure-cosmos/azure/cosmos/_synchronized_request.py | grep -n _internal_pk_range_fetch; done
```
Expected: execution-context files differ by 4 added lines (one `_LOGGER.warning`); routing-map providers identical; request files differ only by unrelated code; the `kwargs.pop("_internal_pk_range_fetch", None)` line present in both.

**#42047** — static checks only
```bash
cd $W/azsdk/sdk/evaluation/azure-ai-evaluation
git show 54d45994a --format= -- '*_safety_evaluation.py' | grep '^+'                 # seed forwarded to Simulator
grep -n "as_completed\|max_simulation_results" azure/ai/evaluation/simulator/_adversarial_simulator.py | head
git show 54d45994a --format= -- '*test_safety_evaluation.py' | grep '^+' | grep -n "random.Random\|Simulator("   # tests use random.Random, never a simulator
```

**#45366** — G4 not run (the PR's own test covers the issue scenario).

### 4g. Leave the tree clean

```bash
cd $W/azsdk && git status --short | head     # expected: empty
```

---

## Step 5 — Downstream confirmation checks

```bash
cd $W/azsdk
# #44844: still present on main?
git show main:sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/_legacy/_common/_logging.py | grep -n "isinstance(sys.stdout, NodeLogWriter)"
# #43269: async default still 5?
git show main:sdk/cosmos/azure-cosmos/azure/cosmos/aio/_read_items_helper_async.py | grep -n "max_concurrency: int =\|else 5"
# #41852: names removed from __all__ on main?
git show main:sdk/evaluation/azure-ai-evaluation/azure/ai/evaluation/__init__.py > /tmp/init_main.py
grep -n '"AIAgentConverter",\|"SKAgentConverter",' /tmp/init_main.py      # expected: only inside _create_lazy_import(...) calls, not in __all__
# the fixing PR:
python - << 'EOF'
import requests
r = requests.get("https://api.github.com/search/issues", params={"q": "repo:Azure/azure-sdk-for-python is:pr is:merged AIAgentConverter import"})
for it in r.json()["items"]:
    print(it["number"], it["user"]["login"], it["closed_at"][:10], it["title"])
EOF
```
Expected: #42313 by `kdestin`, closed 2025-07-31, "[evaluation] fix: Remove lazy imports from __all__". Open https://github.com/Azure/azure-sdk-for-python/pull/42313 and confirm the description mentions a release gate that imports everything from `__all__`. (Note: on 2026-09-28 the outputs of the "still on main" commands were as stated in the paper; `main` has since moved and may differ.)

---

## Step 6 — Human-only steps (not automatable)

**6a. Classification by a human rater.** (Done 2026-10-02: `results/classification_rater_RN.md`; to repeat with another rater, hand over `rater_package/` only.) Open `results/classification_sheet.md` and, from the PR descriptions it quotes, extract the requirements and answer the two questions for each, **before** looking at any diff or at `results/classification_ai_pass.md`. Fill the summary lines at the end (number of requirements; agreement with the AI pass, checked only afterwards; the double-yes cases). Copy your levels into each PR's `hypotheses:` block in `replication/experiments.yaml` and re-run `run` so the evidence records carry them. Replace the two placeholders in the case-study section with the counts.

**6b. Triage by a human.** Open each `results/evidence/pr<PR>_G4.json`, read `findings[]` against the G4 output, and for each write agree/disagree with kind and severity. Any disagreement overrides the paper text.

**6c. Equivalent-mutant review.** For #46707, #44770, #41852 open `pr<PR>_G2.json`, list `findings[]` with `kind == surviving_mutant`, and mark each as equivalent/cosmetic/meaningful. Record the counts you will report.

**6d. #42047 decision.** Either run a seeded `AdversarialSimulator` twice against the RAI service and compare returned query sets and counts, or change the row to "undocumented limitation" and remove "possible divergence".

**6e. Selection funnel.** Download the AIDev curated subset (`https://huggingface.co/datasets/hao-li/AIDev`), filter to `repo == "Azure/azure-sdk-for-python" and agent == "GitHub Copilot" and merged`, then count how many satisfy each inclusion criterion of Section 3.2 of the methodology document. Fill the placeholder in the manuscript.

---

## Step 7 — Package the evidence

```bash
cd $W && for f in evidence/*.json; do python -m json.tool $f > /dev/null || echo "invalid: $f"; done
pip freeze > requirements-frozen.txt
tar czf replication-$(date +%F).tgz gates evidence requirements-frozen.txt
```
Upload the archive, the PR list with exclusion reasons, and the completed classification sheet to Zenodo; put the DOI in the manuscript's `\bibitem{replication}`.

---

## Section 8 — Automated runner

Steps 4a–4f are automated by `$W/run_experiments.py`, driven by `$W/experiments.yaml`, where each PR has an `enabled` flag (`python run_experiments.py run`, or `run --prs 44844,41852`; `list` shows the configuration, `run --dry-run` prints the plan, `--help` on any command explains its options). `python run_experiments.py setup` also performs Steps 2–3. See `replication/README.md` for usage. The runner writes the same evidence files as the manual steps plus `pr<N>_G4_output.txt`, which contains the G4 output after and before each PR and must still be read by a person. `python run_experiments.py compare` checks the automated records against the originals shipped in `results/evidence/`; `-q` reduces the progress output; `clean results|clone|all` removes generated state. Additional gates registered under `extra_gates:` in the config run after G2/G3 (see `replication/EXTENDING.md`).

## Section 9 — If something differs from the recorded numbers

- **Different mutant count**: the mutator is deterministic on identical source; a different count means a different commit or a changed `changed_lines` parse. Check `git rev-parse HEAD` and `git status`.
- **Different kill result for one mutant**: `compare` names the mutant. Usually a test-suite difference (a test skipped for missing credentials, or a newer dependency); compare the `exercised` field of the two G2 records. Two string mutants swapping results was a stale-bytecode bug in the runner, fixed 2026-09-29; make sure you have that version of `gates/g2_g3_mutation.py`.
- **Baseline suite not green**: see the three environment quirks in the methodology document, Section 2.3.
- **G4 script fails to import**: you are at the wrong commit or `PYTHONPATH`/editable installs point elsewhere; re-run Step 4b–4c.
- **Downstream checks differ**: `main` has moved; report the date you checked and what you found.

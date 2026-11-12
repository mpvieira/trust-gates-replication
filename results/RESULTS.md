# Case study: trust gates on eight Copilot-authored PRs in Azure/azure-sdk-for-python

Run 2026-09-28/29. All eight PRs were authored by the GitHub Copilot coding agent, merged into `main` with CI green after human review. Gates were run at the squash-merge commit; before/after comparisons use the parent commit. Evidence records are in `evidence/`, scripts in `../replication/gates/`. Full walkthroughs of #41852 and #44844 and one-page cards for the other six are in `../supplement/`.

## Summary

| PR | Package | Change | Lines | PR tests | G1 | G2 mutants (killed) | G3 own-suite | G4 | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| #45366 | azure-core | `format_url` trailing-slash fix | 1 + 8 test | yes | pass | 0 (n/a) | n/a | not run | smoke test only: change deletes a call, no mutable node on the line |
| #46707 | azure-confidentialledger | `assert` → explicit `ValueError` in receipt verification | 32 | **none** | pass | 46 (91%) | n/a | claim supported | 2 evidence gaps; property restored by the PR has no regression test |
| #44844 | azure-ai-evaluation | guard `NodeLogManager` against recursion | 25 + 42 test | yes | pass | 13 (46%) | 46% | claim partially supported | **1 confirmed defect (escaped), still on `main`** |
| #41852 | azure-ai-evaluation | lazy imports for optional converters | 59 + 135 test | yes | pass | 20 (0%) | 0% | intent claim not supported | **1 confirmed defect (escaped); fixed downstream by maintainer PR #42313 after a release gate failed** |
| #43269 | azure-cosmos | optional `max_concurrency`; `create_database` overloads | 140 | **none** | pass | 9 (0%) | n/a | async-unchanged claim not supported | **1 confirmed claim–implementation divergence**: async default halved 10→5, no changelog; reported as #49273, confirmed by the maintainer (intended change, missed changelog entry, "the Copilot PR description is also wrong"); closed as completed by PR #49306 |
| #41492 | azure-ai-evaluation | float vs int threshold comparison | 4 + 47 test | yes | pass | 4 (25%)¹ | 25% | all claims supported | 2 limitations: lower-is-better branch (had the inverse bug) and equality boundary untested |
| #44770 | azure-cosmos | port of human hotfix #44649 (partition split) | 120 + 645 test | yes | pass | 34 (24%) | 24% | port fidelity supported (diffed against #44649) | 2 limitations: state reset and anti-recursion flag untested at provider/request layers |
| #42047 | azure-ai-evaluation | randomization seed across simulators | 30 + 48 test | yes | pass | 5 (0%) | 0% | partly checkable offline | possible divergence: seeding does not address the reported row-count symptom; PR tests exercise `random.Random`, not the simulators |

¹ The tool generated 5 mutants; a version-string mutant was excluded as equivalent, so 1/4 is reported.

## PR #46707: receipt verification (must-hold, security)

**Trust hypotheses.** H1 must-hold: malformed receipts are rejected. H2 must-hold: rejection survives `python -O`. The pre-PR code defended H1 with `assert`, which is a cannot-guarantee under `-O`. The PR was triggered by an internal incident (IcM reference in the PR body), consistent with that.

**G4.** Five malformed inputs (missing signature, proof element without left/right, non-string right, RSA certificate) were run under `python` and `python -O` at parent and at PR commit. Parent under `-O`: all five accepted. PR commit: all five rejected in both modes. The claim holds and the fix is real.

**G2.** 46 mutants on changed lines, 42 killed by the existing suite. Four survivors cluster on two paths the suite never exercises: a Merkle proof element with only a `right` sibling (L143, L147) and a non-EC certificate (L381, `remove raise` survives).

**G3.** Not applicable: the PR shipped no tests. Consequence: nothing in CI runs under `-O`, so a future reversion to `assert` would pass. The property the PR restores is unprotected.

**CEL statement.**
- *Claim:* receipt content validation rejects the malformed-receipt classes exercised, with or without assert stripping. *Scope:* left-sibling proofs, EC certificates.
- *Evidence:* G4 before/after runs; 42/46 mutants killed; 67 pre-existing receipt tests green.
- *Limitations:* right-sibling proof path and non-EC certificate path unverified; no `-O` regression test; live-ledger receipts not tested.

## PR #44844: nested log manager (confirmed defect)

**Trust hypotheses.** H1 must-hold: nested managers do not recurse. H2 must-hold: per-run log attribution is preserved across nesting. H3 cannot-guarantee: fallback when real streams are replaced.

**G2/G3.** The only tests for this module are the two the PR wrote (the closed-loop case from the paper's introduction). 13 mutants; 6 killed, 7 survive. Negating either "reuse existing writer" branch (L174, L178) survives, so the PR's own "idempotent wrapping" claim is not protected by its own tests. The cycle-detection return (L295) and the `None`-stream paths also survive.

**G4.** Cycle detection and fallback: supported. Idempotent wrapping: supported, and it is the cause of the defect. Reproducing the production caller's exact sequence (`_batch_engine._exec_line_context`: construct, `set_node_context`, enter; nested once):

| | outer-after attributed to r1 (outer) | attributed to r2 (inner) |
|---|---|---|
| parent commit | yes | no |
| PR commit | **no** | **yes** |

With a shared writer, the inner `set_node_context` overwrites the shared context variable and nothing restores it on inner exit, so outer-line output after a nested evaluation is logged under the inner run id. Failure mode: assumption injection (the agent resolved "should nested managers share state?" in favor of sharing, which fixed the recursion and broke attribution). Escaped: CI green, no review comment touches it, PR tests only check that text reaches the base stream. Present on `main` on 2026-09-28; no downstream fix found. Reported to the project as issue #49274 on 2026-09-30.

**CEL statement.**
- *Claim:* nested `NodeLogManager` contexts no longer recurse and output reaches the underlying stream. *Scope:* nesting without per-run context switches.
- *Evidence:* PR tests (500-deep nesting); G4 cycle check.
- *Limitations:* per-run attribution across a nesting boundary is incorrect (confirmed); concurrent execution, also claimed by the PR, not evaluated; 7/13 mutants survive.

## Additional notes on the five later PRs

Environment notes for reproduction: azure-ai-evaluation tests at 2025 commits require `AZURE_TEST_RUN_LIVE=true AZURE_SKIP_LIVE_RECORDING=true` to bypass the test-proxy download; azure-cosmos unit tests require `--noconftest` (the conftest connects to an emulator); azure-sdk-tools moved from `tools/` to `eng/tools/` between the 2025 and 2026 commits, so reinstall it per checkout. The gate runner reads `EXTRA_PYTEST_ARGS`.

G4 scripts: `g4_checks_pr41492.py`, `g4_checks_pr41852.py`, `g4_checks_pr43269.py` (run at merge commit and parent). #44770's G4 is a `git diff pr44649..9a8a19a39` on the six source files. #42047's G4 is static; the ordering/count claim needs a live run.

Triage caveat: all classification and triage so far is by one analyst (Claude). The human rater's blind classification (`classification_sheet.md`) and a human re-run of the three defect checks are required before any of this is cited.

## What the eight PRs say about the case-study design

1. **G4 is where all three defects came from**, not the automated gates. Same pattern as the classroom "metadata honesty" finding. Budget analyst time there.
2. **G2 survivors were the pointer in two of the three.** For #44844 (L174/L178) and #43269 (the async-default line) a surviving mutant marked the line to examine; for #41852 the survivors were global and the pointer was the `__all__` change itself. The automated gate directs the manual one, which is the argument for running them together.
3. **G1 did not fire.** Expected in a mature monorepo with pinned dependencies. Keep it (cheap, and the record of what resolved is itself evidence) but do not expect findings.
4. **Add a statement-deletion operator** so single-line call removals (#45366) produce at least one mutant.
5. **"No tests in PR" is a result, not a gap in the method.** #46707 shipped a security fix with no test; record it as a G3 finding.
6. Effort: 25–45 min of analyst time per PR, dominated by G4, plus one-off environment setup per package. Per-PR machine time under 2 min.

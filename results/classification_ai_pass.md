# AI-assisted first pass (do not open before completing classification_sheet.md)

Labels assigned by the assistant on 2026-09-28. **Correction (2026-10-02): these labels were not blind.** The assistant had already inspected the diffs while selecting the PRs and wrote the hypotheses down during and after running the gates, so they were informed by the findings. They must not be presented as an independent classification or compared with the human rater's as if they were; the fair comparison for the human rater is `classification_ai_pass_2.md` (blind, descriptions only). Kept for the record only; the paper reports the human rater's labels.


## PR #44844

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | must-hold | Nested NodeLogManager contexts do not recurse | G2, G3, G4 |
| H2 | must-hold | Per-run log attribution is preserved across a nesting boundary | G4 |
| H3 | cannot-guarantee | Fallback behaviour when the real streams have been replaced | G2, G3 |

## PR #41852

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | may-fail | No output is printed at import time when an optional dependency is absent | G4 |
| H2 | must-hold | The public import surface (import *, hasattr) remains usable without the optional dependency | G1, G4 |

## PR #43269

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | may-fail | Sync read_items default concurrency follows ThreadPoolExecutor | G2 |
| H2 | must-hold | Async behaviour unchanged, as the PR description states | G2, G4 |
| H3 | may-fail | response_hook is invoked on create_database | G2, G4 |

## PR #46707

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | must-hold | Malformed receipts are rejected | G2, G3, G4 |
| H2 | must-hold | Rejection holds under python -O (assert stripping) | G4 |

## PR #41492

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | must-hold | Pass/fail result reflects a float comparison against the threshold | G2, G3, G4 |
| H2 | must-hold | Lower-is-better evaluators fail when the score exceeds the threshold | G2, G3, G4 |

## PR #44770

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | must-hold | The port matches the human hotfix PR #44649 | G4 |
| H2 | must-hold | A partition-key-range fetch never recurses on a 410 | G2, G3 |

## PR #42047

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | must-hold | The same randomization seed yields the same query set | G2, G3, G4 |
| H2 | may-fail | Global random state is not modified | G4 |

## PR #45366

| id | Level | Statement | Gates |
|---|---|---|---|
| H0 | must-hold | The change references only modules, symbols and attributes that exist (no hallucinated interfaces) | G1 |
| H1 | may-fail | format_url preserves a trailing slash when the template is query-only | G2, G3 |
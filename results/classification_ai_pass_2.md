> **Not a human classification.** This form was returned on 2026-09-29 filled in by a separate AI session (its own summary line says so). It was done blind, from the descriptions only, on the earlier version of the form in which four descriptions were truncated at 1,800 characters. It is kept as a second AI pass for comparison with `classification_ai_pass.md` and with the human rater's form; it must not be used in place of the human classification.

# Classification form

Fill in one table per change. Read the instructions in `INSTRUCTIONS.md` first. Add rows if you find more requirements than there are rows; delete rows you do not need.

## Change 44844 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim):

> Nested NodeLogManager contexts could recursively forward stdout/stderr through stacked NodeLogWriter instances, leading to RecursionError during evaluation runs. This change ensures nested logging remains safe and deterministic under concurrent execution.
> 
> - **Logging guardrails**: unwrap chained NodeLogWriter targets with cycle detection and safe fallback to real streams.
> - **Idempotent wrapping**: reuse existing NodeLogWriter instances when streams are already wrapped.
> - **Tests**: add focused unit coverage for nested writers and nested NodeLogManager usage.
> - **Changelog**: note the recursion fix for azure-ai-evaluation.
> 
> Example behavior:
> ```python
> with NodeLogManager():
>     with NodeLogManager():
>         print("nested")
>         sys.stderr.write("stderr")
> ```


| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | Writing to stdout or stderr inside nested `NodeLogManager` contexts does not raise `RecursionError` | yes | no | must-hold | a crash mid-evaluation makes the library unfit for anyone who nests contexts (Q1); the failure mode and the triggering pattern are fully specified by the example (Q2) |
| R2 | Text written inside nested contexts is still delivered (captured by the manager and/or reaching the real streams via the fallback), not silently dropped | yes | yes | must-hold | losing log output during evaluation runs is a data-integrity problem for users relying on those logs (Q1); the description never says what the correct destination of nested output is (outer manager, inner, both, real stream), so there is no reference to compare against (Q2) |
| R3 | Wrapping a stream that is already wrapped by a `NodeLogWriter` reuses the existing writer instead of stacking a new one | no | no | may-fail | this is an internal mechanism whose user-visible consequences are already covered by R1/R2, so a violation on its own is not a failure of fitness (Q1); the behaviour is stated precisely (Q2) |
| R4 | Nested logging behaves safely and deterministically when evaluations run concurrently | yes | yes | must-hold | interleaved, lost or misattributed output under concurrency would make the logging feature unfit for the concurrent runs it exists for (Q1); "concurrent execution" (threads? asyncio? processes?) and "deterministic" are not defined, and nothing in the description says what output is expected (Q2) |

## Change 41852 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim):

> ## Problem
> 
> When importing `azure.ai.evaluation`, an INFO message was logged about `AIAgentConverter` requiring `azure-ai-projects` dependency, even when the user doesn't intend to use this converter:
> 
> ```python
> >>> import azure.ai.evaluation
> [INFO] Could not import AIAgentConverter. Please install the dependency with `pip install azure-ai-projects`.
> ```
> 
> This created unnecessary noise for users who just want to use the evaluation library without the optional converter functionality.
> 
> ## Solution
> 
> Implemented lazy loading mechanism using Python's module-level `__getattr__` to defer imports until the classes are actually accessed:
> 
> - **Before**: Import-time try-except blocks immediately printed messages when optional dependencies weren't available
> - **After**: Messages are only shown when someone actually tries to use the converter classes
> 
> ## Changes
> 
> 1. **Removed import-time print statements** from try-except blocks
> 2. **Added lazy import functions** that handle imports and error messages only when needed
> 3. **Implemented module-level `__getattr__`** to intercept attribute access
> 4. **Updated both `AIAgentConverter` and `SKAgentConverter`** to use the same pattern
> 5. **Added comprehensive tests** to validate the new behavior
> 
> ## Behavior
> 
> ```python
> # ✅ No messages during import
> import azure.ai.evaluation
> 
> # ✅ Message only when actually accessing the converter
> try:
>     converter = azure.ai.evaluation.AIAgentConverter
> except AttributeError:
>     # [INFO] Could not import AIAgentConverter. Please install the dependency with `pip install azure-ai-projects`.
>     pass
> ```
> 
> The fix ensures backward compatibility while eliminating the noisy import-time messages for users who don't need the optional functionality.
> 
> Fixes #41743.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | `import azure.ai.evaluation` emits no message about `AIAgentConverter` or `SKAgentConverter` when their optional dependencies are missing | no | no | may-fail | an unwanted INFO line is noise, not a security or fitness failure (Q1); the condition and the expected absence of output are exactly stated (Q2) |
| R2 | Accessing `AIAgentConverter` or `SKAgentConverter` on the module when the optional dependency is missing raises `AttributeError` and emits the install-hint message | no | no | may-fail | a wrong exception type or missing hint is inconvenient but the converter is unusable either way without the dependency (Q1); the exception type and message are given in the example (Q2) |
| R3 | When the optional dependencies are installed, both converter classes remain accessible from `azure.ai.evaluation` exactly as before (backward compatibility) | yes | yes | must-hold | breaking existing imports of the converters makes the library unfit for those users (Q1); "backward compatibility" is asserted but not enumerated, and module-level `__getattr__` subtly changes `from ... import`, `dir()`, `__all__`, `hasattr`, static type checkers and pickling, so completeness over those access paths has no stated reference (Q2) |

## Change 43269 — package `azure-cosmos`

Description written by the author of the change (verbatim):

> ## Overview
> 
> This PR addresses <a href="https://github.com/Azure/azure-sdk-for-python/issues/43211">Issue #43211</a> which is based on the main parent <a href="https://github.com/Azure/azure-sdk-for-python/issues/43211">Issue #43211</a> by implementing two related improvements to the Azure Cosmos DB Python SDK:
> 
> 1. **Make `max_concurrency` optional with adaptive ThreadPool default (sync only)**
> 2. **Fix `create_database` and `create_database_if_not_exists` overload signatures**
> 
> ## Changes
> 
> ### 1. Optional `max_concurrency` for Adaptive Resource Usage (Sync Path Only)
> 
> **Problem:** The hardcoded default of `max_concurrency=10` was arbitrary and could be too high for resource-constrained systems or too low for high-core-count systems.
> 
> **Solution:** Changed `max_concurrency` to `Optional[int]` with default `None` **for the sync path only**, allowing Python's ThreadPoolExecutor to use its adaptive default.
> 
> **Modified files:**
> - `azure/cosmos/container.py` - `read_items()` method signature and docstring (sync)
> - `azure/cosmos/_read_items_helper.py` - Helper class initialization (sync)
> - `azure/cosmos/_cosmos_client_connection.py` - Client connection default and docstring (sync)
> 
> **Async path unchanged:** The async version (`aio/_container.py` and `aio/_cosmos_client_connection_async.py`) retains `max_concurrency: int = 10` because it uses `asyncio.Semaphore` instead of `ThreadPoolExecutor`, which has different concurrency semantics.
> 
> **Example:**
> ```python
> # Sync: Uses adaptive default based on CPU cores
> items = container.read_items(items=[(id1, pk1), (id2, pk2)])
> 
> # Sync: Explicitly set workers
> items = container.read_items(items=[(id1, pk1)], max_concurrency=5)
> 
> # Async: Continues to use default of 10 (uses asyncio.Semaphore)
> items = await container.read_items(items=[(id
> [...]

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | Sync `read_items` accepts `max_concurrency=None` (now the default) and in that case lets `ThreadPoolExecutor` choose its own worker count | no | no | may-fail | a wrong default changes throughput, not correctness, security or fitness (Q1); the intended behaviour (pass through to the executor default) is stated precisely (Q2) |
| R2 | When a caller passes an explicit integer `max_concurrency` on the sync path, at most that many concurrent reads are used | yes | no | must-hold | users on resource-constrained or rate-limited systems rely on the cap; exceeding it can exhaust resources or trigger throttling, making the call unfit for them (Q1); the bound is a plain integer (Q2) |
| R3 | The async `read_items` default stays at 10 and its behaviour is unchanged | yes | no | must-hold | the description explicitly promises no change on the async path, so any change breaks existing users (Q1); the promise is concrete (Q2) |
| R4 | The typing overloads of `create_database` and `create_database_if_not_exists` are corrected | no | yes | cannot-guarantee | overload signatures affect type checkers, not runtime behaviour, so a mistake is not a fitness failure (Q1); the description is truncated before it says what was wrong or what the corrected signatures are, so there is nothing to compare against (Q2) |
| R5 | The items returned by sync `read_items` are the same regardless of the `max_concurrency` value (included with some doubt: not stated, but obviously must not break when only the concurrency default changes) | yes | no | must-hold | returning missing or wrong items is a data-integrity failure (Q1); the reference is the pre-change output for the same inputs (Q2) |

## Change 46707 — package `azure-confidentialledger`

Description written by the author of the change (verbatim):

> - [x] Replace `assert` statements in `_receipt_verification.py` with explicit checks raising `ValueError`
> - [x] Update CHANGELOG.md (azure-confidentialledger 2.0.0b3)
> - [x] Add `Merkle` to cspell allowlist for `sdk/confidentialledger/azure-confidentialledger/azure/confidentialledger/receipt/*.py` to fix CI spell check failure
> 
> This is in regards to this IcM: https://portal.microsofticm.com/imp/v5/incidents/details/31000000596408/summary

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | Every condition previously enforced by an `assert` in receipt verification is now enforced by an explicit check that raises `ValueError`, so invalid receipts are rejected even when Python runs with assertions disabled (`-O`) | yes | yes | must-hold | receipt verification is a security control and an incident is referenced; a check that is skipped under `-O` lets a forged or tampered receipt pass (Q1); the description does not list which assertions exist, so completeness over that set cannot be judged from it (Q2) |
| R2 | Receipts that verified successfully before the change still verify successfully (no new false rejections) | yes | no | must-hold | rejecting valid receipts makes the verification API unfit for its users (Q1); the reference is the pre-change acceptance behaviour on the same inputs (Q2) |

## Change 41492 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim):

> ## Problem
> 
> The `MeteorScoreEvaluator` was returning incorrect binary results when comparing decimal scores against thresholds. For example:
> 
> ```python
> from azure.ai.evaluation import MeteorScoreEvaluator
> 
> result = MeteorScoreEvaluator()(ground_truth="Hello world", response="Hello world")
> print(result)
> # Expected: {'meteor_score': 0.9375, 'meteor_result': 'pass', 'meteor_threshold': 0.5}
> # Actual:   {'meteor_score': 0.9375, 'meteor_result': 'fail', 'meteor_threshold': 0.5}
> ```
> 
> The score `0.9375` is clearly greater than the threshold `0.5`, but the evaluator was incorrectly returning `'fail'` instead of `'pass'`.
> 
> ## Root Cause
> 
> In `EvaluatorBase._real_call()`, the threshold comparison logic was incorrectly converting float scores to integers before comparison:
> 
> ```python
> if int(score_value) >= self._threshold:  # BUG: int(0.9375) = 0
> ```
> 
> This caused decimal scores like `0.9375` to become `0` when converted to int, making them fail threshold comparisons.
> 
> ## Solution
> 
> Changed the comparison logic to preserve float precision:
> 
> ```python
> if float(score_value) >= self._threshold:  # FIXED: preserves decimal precision
> ```
> 
> This fix affects both `higher_is_better` and `lower_is_better` comparison branches.
> 
> ## Impact
> 
> - ✅ **MeteorScoreEvaluator** now correctly returns `'pass'` when scores exceed thresholds
> - ✅ **BleuScoreEvaluator** and other score-based evaluators also benefit from this fix
> - ✅ **Backward compatible** - no API changes, only corrected behavior
> - ✅ **Comprehensive tests** added to prevent regression
> 
> ## Testing
> 
> Added comprehensive test coverage including:
> - Original issue reproduction case
> - Multiple threshold levels (0.1, 0.5, 0.8, 0.95, 1.0)
> - Edge cases with different input strings
> - Validation for both MeteorScoreEvaluator and BleuScoreEvaluator
> 
> Fixes 
> [...]

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | For higher-is-better evaluators, the result is `'pass'` exactly when the float score is `>=` the threshold, with no integer truncation | yes | no | must-hold | a wrong pass/fail verdict is wrong data and defeats the evaluator's purpose (Q1); operator and operands are given verbatim (Q2) |
| R2 | For lower-is-better evaluators, the comparison likewise uses the float score without truncation | yes | yes | must-hold | same data-integrity stake as R1 (Q1); the description says this branch is fixed too but never shows its operator (`<=` vs `<`), so the exact expected verdict at the boundary has no reference (Q2) |
| R3 | Score values, output keys and the public API are unchanged; only the `*_result` verdicts change | yes | no | must-hold | the description promises backward compatibility with no API change, so any other change breaks existing users (Q1); the reference is the pre-change output shape (Q2) |
| R4 | The corrected comparison applies to every score-based evaluator that goes through `EvaluatorBase._real_call` (Bleu and the unnamed "other" evaluators), not only Meteor | yes | yes | must-hold | those evaluators have the same wrong-verdict problem (Q1); "other score-based evaluators" is an open-ended set the description does not enumerate, so coverage cannot be checked against it (Q2) |

## Change 44770 — package `azure-cosmos`

Description written by the author of the change (verbatim):

> ## Port Cosmos DB Partition Split Recursion Fix from PR #44649
> 
> This task involves porting critical bug fixes from PR #44649 that was merged to the hotfix branch. The fix addresses an infinite recursion issue during partition split (410 error) handling.
> 
> ### Plan Checklist:
> 
> - [x] Review and understand all changes from PR #44649
> - [x] Update CHANGELOG.md with bug fix entry (do not bump version - keep current version)
> - [x] Apply fixes to sync base_execution_context.py (add logging, _internal_pk_range_fetch flag, state reset)
> - [x] Apply fixes to async base_execution_context.py (same changes as sync)
> - [x] Apply fixes to sync routing_map_provider.py (add logging, _internal_pk_range_fetch flag)
> - [x] Apply fixes to async routing_map_provider.py (same changes as sync)
> - [x] Update _synchronized_request.py to pop internal flag
> - [x] Update aio/_asynchronous_request.py to pop internal flag
> - [x] Update test_routing_map_provider.py to accept **kwargs
> - [x] Add test_partition_split_retry_unit.py (new sync tests)
> - [x] Add test_partition_split_retry_unit_async.py (new async tests)
> - [x] Verify syntax of all modified files (all pass)
> - [x] Run code review (completed - minor suggestions, keeping PR #44649 approach)
> - [x] Add warning logs before unreachable return statements (per PR review feedback)
> - [x] Review and finalize changes
> 
> ## Summary
> 
> Successfully ported all changes from PR #44649 to the main branch and addressed PR review feedback:
> 
> ### Key Changes:
> 1. **_internal_pk_range_fetch flag**: Prevents infinite recursion by marking partition key range queries as internal
> 2. **State reset logic**: Resets _has_started and _continuation to ensure retry logic works correctly
> 3. **Comprehensive logging**: Added debug, warning, and error logging for partition split scenarios (inclu
> [...]

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | A 410 (partition split) received during an internal partition-key-range fetch does not itself trigger split handling, so the handling can no longer recurse without bound | yes | no | must-hold | unbounded recursion crashes or hangs the query, making the SDK unfit whenever a split happens (Q1); the mechanism (internal flag, no re-entry) is stated concretely (Q2) |
| R2 | After a split is detected, the query is retried from a reset state (started flag and continuation cleared) and returns the complete and correct result set | yes | yes | must-hold | duplicated or missing items after a split is a data-integrity failure (Q1); "retry logic works correctly" has no reference in the description, and the correct result depends on the service's partition-range state, which the client cannot observe (Q2) |
| R3 | The sync and async execution paths behave the same way for this scenario | yes | no | must-hold | async users would otherwise still hit the crash (Q1); the description states the async changes are the same as sync, which is a concrete reference (Q2) |
| R4 | The internal `_internal_pk_range_fetch` flag is removed from request options before the request is sent, so it never affects or breaks the outgoing request | yes | no | must-hold | an unexpected option leaking into the request layer could reject or alter every request that carries it (Q1); the expected behaviour ("pop the internal flag") is specific (Q2) |
| R5 | The behaviour on the main branch matches the already-merged hotfix PR #44649 | no | yes | cannot-guarantee | parity with the hotfix is a process goal; a divergence only matters through R1–R4 (Q1); the reference (the hotfix diff) is outside the description and the summary is truncated, so parity cannot be judged from it (Q2) |

## Change 42047 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim):

> ## Problem
> 
> When using the same `randomization_seed` to get single-turn query sets by invoking the SafetyEvaluation SDK twice (e.g., once for a treatment group and once for a control group), the returned query sets had different counts, which was unexpected. Users expected identical query sets when using the same seed.
> 
> ```python
> # This should produce identical query sets but didn't
> outputs_treatment = await _SafetyEvaluation_instance(
>     evaluators=[evaluator],
>     evaluation_name="safety evaluation", 
>     target=conversation_generator.get_llm_reply,
>     num_turns=1,
>     num_rows=200,
>     concurrent_async_tasks=30,
>     output_path="evaluation_outputs_safety.jsonl",
>     randomization_seed=1  # Same seed
> )
> 
> outputs_control = await _SafetyEvaluation_instance(
>     evaluators=[evaluator],
>     evaluation_name="safety evaluation",
>     target=conversation_generator.get_llm_reply, 
>     num_turns=1,
>     num_rows=200,
>     concurrent_async_tasks=30,
>     output_path="evaluation_outputs_control.jsonl", 
>     randomization_seed=1  # Same seed - should produce identical results
> )
> ```
> 
> ## Root Cause Analysis
> 
> The issue was caused by inconsistent randomization handling across different simulator paths:
> 
> 1. **IndirectAttackSimulator** completely ignored the `randomization_seed` parameter
> 2. **Regular Simulator** (when `adversarial_scenario is None`) didn't receive the `randomization_seed` parameter
> 3. **AdversarialSimulator** used global `random.seed()` which could pollute global state between calls
> 4. Inconsistent randomization logic across different simulator types
> 
> ## Solution
> 
> ### 🔧 **Fixed IndirectAttackSimulator** (`_indirect_attack_simulator.py`)
> - Added `randomization_seed: Optional[int] = None` parameter to `__call__` method
> - Implemented template shuffling using local `Random` 
> [...]

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | Two SafetyEvaluation calls with the same `randomization_seed` and the same other arguments produce identical query sets (same queries, same count) | yes | yes | must-hold | treatment/control comparisons built on unequal query sets are invalid, a data-integrity failure for the users the description names (Q1); "identical" also depends on sources of nondeterminism the description does not address (30 concurrent async tasks, service-side template content), which the client cannot control or observe, and the description is truncated (Q2) |
| R2 | Every simulator path (IndirectAttack, regular Simulator, Adversarial) receives and applies the `randomization_seed` | yes | no | must-hold | any path that ignores the seed breaks R1 for users of that path (Q1); the description enumerates the paths and the fix for each (Q2) |
| R3 | Seeding is done with a local `Random` instance and no longer mutates the global `random` state | no | no | may-fail | leaking into global state is a code-hygiene issue whose user-visible effect is already captured by R1 (Q1); the requirement is concrete and observable (Q2) |
| R4 | When `randomization_seed` is not given (default `None`), behaviour is as before | no | yes | cannot-guarantee | the unseeded case is random anyway, so a change there is not a fitness failure (Q1); "as before" for random behaviour has no usable reference (Q2) |

## Change 45366 — package `azure-core`

Description written by the author of the change (verbatim):

> When `format_url` is called with a query-string-only template (e.g. `?key=value`) and the base URL (resolved from `path_format_arguments`) has a trailing slash, the trailing slash is incorrectly stripped.
> 
> ```python
> client = PipelineClientBase("{url}")
> client.format_url(
>     "?versionid=2026-02-25T17%3A48%3A15Z",
>     url="https://storage.blob.core.windows.net/sample//a/a/"
> )
> # Before: https://storage.blob.core.windows.net/sample//a/a?versionid=...
> # After:  https://storage.blob.core.windows.net/sample//a/a/?versionid=...
> ```
> 
> ## Changes
> 
> - **`_base.py`**: Removed the unconditional `.rstrip("/")` from the base URL computation in `format_url`. This was always redundant for path stubs — `_urljoin` already strips the trailing slash from the base path inside its `if stub_url_path:` branch when actually joining path segments. For query-string-only stubs where `stub_url_path` is empty, `_urljoin` leaves the base path untouched, so the trailing slash is now correctly preserved before the `?`.
> - **`test_pipeline.py`**: Added test covering the exact scenario from the issue.
> - **`CHANGELOG.md`**: Updated unreleased section.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | For a query-string-only template and a base URL ending in `/`, `format_url` keeps the trailing slash immediately before the `?` | yes | no | must-hold | `/a/a/` and `/a/a` are different resources on a storage service, so the request goes to the wrong object (Q1); the input and the exact expected output are given (Q2) |
| R2 | For every other template, in particular templates with a path component, `format_url` output is byte-for-byte unchanged | yes | yes | must-hold | `format_url` builds every request URL in the SDK, so any unintended change misroutes requests for many users (Q1); "unchanged" must hold over an open-ended set of templates and bases, and the description's argument covers only path stubs and query stubs, not e.g. an empty template with a trailing-slash base, where removing the `rstrip` plausibly does change the result (Q2) |

## Summary

- Total requirements you classified: 29
- Requirements answered **yes** to both Q1 and Q2: 10 — 44844 R2, 44844 R4; 41852 R3; 46707 R1; 41492 R2, 41492 R4; 44770 R2; 42047 R1; 45366 R2
- Changes where you found the description too vague to extract a requirement, if any: none. Notes: 46707 is very terse (two requirements only, both inferred from a one-line bullet); the descriptions for 43269, 41492, 44770 and 42047 are truncated in the form ("[...]"), which is why 43269 R4 and 44770 R5 have no reference to judge against.
- Approximate time spent: completed in a single sitting by Claude (an AI assistant) rather than a human participant, so no meaningful wall-clock figure; worked from the descriptions only, no code or web lookup.

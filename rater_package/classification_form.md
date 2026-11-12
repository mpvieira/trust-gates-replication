# Classification form

Fill in one table per change. Read the instructions in `INSTRUCTIONS.md` first. Add rows if you find more requirements than there are rows; delete rows you do not need. The descriptions are complete; nothing has been cut.

## Change 44844 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim, complete):

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
| R1 | | | | | |
| R2 | | | | | |
| R3 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 41852 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim, complete):

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
| R1 | | | | | |
| R2 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 43269 — package `azure-cosmos`

Description written by the author of the change (verbatim, complete):

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
> items = await container.read_items(items=[(id1, pk1), (id2, pk2)])
> ```
> 
> ### 2. Fix `create_database` Overload Signatures
> 
> **Problem:** The overloads were missing `response_hook` parameter, included the deprecated `populate_query_metrics`, and `offer_throughput` was not consistently keyword-only.
> 
> **Solution:** Updated overload signatures for both sync and async versions:
> - ✅ Added `response_hook` parameter to all overloads
> - ✅ Removed `populate_query_metrics` from overload signatures (kept in implementation with deprecation warning)
> - ✅ Made `offer_throughput` keyword-only in sync overloads
> - ✅ Updated implementations to properly invoke `response_hook`
> 
> **Modified files:**
> - `azure/cosmos/cosmos_client.py` - Sync versions
> - `azure/cosmos/aio/_cosmos_client.py` - Async versions
> 
> **Example:**
> ```python
> # Recommended usage with keyword arguments
> db = client.create_database("mydb", offer_throughput=400)
> 
> # Access response metadata with response_hook
> def log_charge(headers):
>     print(f"RU charge: {headers.get('x-ms-request-charge')}")
> 
> db = client.create_database("mydb", response_hook=log_charge)
> 
> # Get both proxy and properties
> db_proxy, properties = client.create_database(
>     "mydb",
>     return_properties=True,
>     response_hook=log_charge
> )
> ```
> 
> ## Testing
> 
> - Added `tests/test_max_concurrency.py` with unit tests verifying the optional behavior
> - Tests include validation that max_concurrency is ignored when executor is provided
> - Tests verify Python's ThreadPoolExecutor default behavior
> - All existing tests remain compatible
> - Syntax and import validation passed
> 
> ## Backward Compatibility
> 
> ✅ **100% backward compatible** - All existing code continues to work:
> - Code using `max_concurrency=10` still works (both sync and async)
> - Code not specifying `max_concurrency` now gets adaptive behavior in sync path (better default)
> - Async path behavior unchanged - continues to use default of 10
> - `populate_query_metrics` still accepted in implementation (with deprecation warning)
> - `offer_throughput` can still be passed positionally in implementation
> 
> ## Files Changed
> 
> **Sync path (max_concurrency changes):**
> - `azure/cosmos/container.py` - Updated signature and docstring
> - `azure/cosmos/_read_items_helper.py` - Updated initialization
> - `azure/cosmos/_cosmos_client_connection.py` - Updated default and docstring
> 
> **Both sync and async (create_database changes):**
> - `azure/cosmos/cosmos_client.py` - Updated overloads (sync)
> - `azure/cosmos/aio/_cosmos_client.py` - Updated overloads (async)
> 
> **Tests:**
> - `tests/test_max_concurrency.py` - New file with 4 unit tests
> 
> **Total: 6 files changed**
> 
> 
> 
> 
> 
> 
> Fixes Azure/azure-sdk-for-python#43268
> 
> 
> ---
> 
> 💡 You can make Copilot smarter by setting up custom instructions, customizing its development environment and configuring Model Context Protocol (MCP) servers. Learn more <a href="https://gh.io/copilot-coding-agent-tips">Copilot coding agent tips</a> in the docs.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | | | | | |
| R2 | | | | | |
| R3 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 46707 — package `azure-confidentialledger`

Description written by the author of the change (verbatim, complete):

> - [x] Replace `assert` statements in `_receipt_verification.py` with explicit checks raising `ValueError`
> - [x] Update CHANGELOG.md (azure-confidentialledger 2.0.0b3)
> - [x] Add `Merkle` to cspell allowlist for `sdk/confidentialledger/azure-confidentialledger/azure/confidentialledger/receipt/*.py` to fix CI spell check failure
> 
> This is in regards to this IcM: https://portal.microsofticm.com/imp/v5/incidents/details/31000000596408/summary

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | | | | | |
| R2 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 41492 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim, complete):

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
> Fixes #41415.
> 
> ---
> 
> 💡 You can make Copilot smarter by setting up custom instructions, customizing its development environment and configuring Model Context Protocol (MCP) servers. Learn more [Copilot coding agent tips](https://gh.io/copilot-coding-agent-tips) in the docs.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | | | | | |
| R2 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 44770 — package `azure-cosmos`

Description written by the author of the change (verbatim, complete):

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
> 3. **Comprehensive logging**: Added debug, warning, and error logging for partition split scenarios (including warnings for unreachable code paths)
> 4. **Request handlers updated**: Both sync and async request handlers now pop internal flags
> 
> ### Files Modified (10):
> - CHANGELOG.md (bug fix entry added)
> - 4 execution context files (sync + async) - now with additional warning logs
> - 4 routing provider files (sync + async)
> - 2 request handler files (sync + async)
> - 1 existing test file (kwargs support)
> - 2 new comprehensive test files (sync + async unit tests)
> 
> All files are syntactically correct and ready for testing with Cosmos DB emulator.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | | | | | |
| R2 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 42047 — package `azure-ai-evaluation`

Description written by the author of the change (verbatim, complete):

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
> - Implemented template shuffling using local `Random` instance to avoid global state pollution
> - Added proper documentation for the new parameter
> 
> ### 🔧 **Fixed Regular Simulator** (`_simulator.py`) 
> - Added `randomization_seed: Optional[int] = None` parameter to `__call__` method
> - Implemented task shuffling logic using local `Random` instance
> - Added proper documentation for the new parameter
> 
> ### 🔧 **Fixed AdversarialSimulator** (`_adversarial_simulator.py`)
> - Replaced global `random.seed()` + `random.shuffle()` with local `Random` instance
> - Prevents global random state pollution between simulator calls
> 
> ### 🔧 **Updated SafetyEvaluation** (`_safety_evaluation.py`)
> - Fixed to pass `randomization_seed` to regular Simulator (was missing)
> - All simulator paths now properly receive and use the randomization_seed parameter
> 
> ### 🧪 **Added Tests** (`test_safety_evaluation.py`)
> - Added `test_randomization_seed_consistency()` to verify same seed produces identical results
> - Added `test_local_random_no_global_state_pollution()` to verify local Random instances don't affect global state
> 
> ## Verification
> 
> The fix ensures:
> - ✅ **Same seed = Identical results**: Multiple invocations with the same `randomization_seed` now produce identical query sets
> - ✅ **No global state pollution**: Local `Random` instances prevent interference between calls  
> - ✅ **Consistent behavior**: All simulator paths handle randomization consistently
> - ✅ **Backward compatibility**: Existing code continues to work without changes
> 
> ## Testing
> 
> ```python
> # Before fix: Different results with same seed
> treatment_queries = [...]  # 198 queries
> control_queries = [...]    # 201 queries (different!)
> 
> # After fix: Identical results with same seed  
> treatment_queries = [...]  # 200 queries
> control_queries = [...]    # 200 queries (identical!)
> assert treatment_queries == control_queries  # ✅ Passes
> ```
> 
> Fixes the randomization seed consistency issue where the same seed would produce different query counts across multiple SDK invocations.

| # | Requirement (your wording) | Q1 (yes/no) | Q2 (yes/no) | Level | Reasoning (one line) |
|---|---|---|---|---|---|
| R1 | | | | | |
| R2 | | | | | |
| R+ | (add rows as needed) | | | | |

## Change 45366 — package `azure-core`

Description written by the author of the change (verbatim, complete):

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
| R1 | | | | | |
| R+ | (add rows as needed) | | | | |

## Summary

- Total requirements you classified: ___
- Requirements answered **yes** to both Q1 and Q2: ___ (list the change numbers and requirement ids)
- Changes where you found the description too vague to extract a requirement, if any: ___
- Approximate time spent: ___
- Your name (or initials), and a confirmation that you completed this yourself, from the descriptions only: ___

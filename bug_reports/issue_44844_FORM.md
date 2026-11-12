**Title:** [evaluation] Nested NodeLogManager attributes the outer run's output to the inner run id after #44844

- **Package Name**: azure-ai-evaluation
- **Package Version**: main (regressed in #44844, commit 7d26b949, 2026-02-03; changelog entry "Prevent recursive stdout/stderr forwarding when NodeLogManager is nested" in 1.15.0, so 1.15.0 and later)
- **Operating System**: macOS 15 (also reproduced on Ubuntu 24.04)
- **Python Version**: 3.12.4

**Describe the bug**
Since #44844, nested `NodeLogManager` contexts reuse the outer `NodeLogWriter` instead of wrapping it, so the writer's run context (`ContextVar`) and its `run_id_to_stdout` map are shared by the outer and inner managers. When the inner manager calls `set_node_context(inner_run_id, ...)` it overwrites the shared context, and nothing restores the outer run id when the inner manager exits. Output written by the outer run after the inner run has finished is stored under the inner run's id. Before #44844 each manager had its own writer and context, so the outer run's later output stayed under the outer run id.

This is the call sequence `_batch_engine/_engine.py::_exec_line_context` uses (construct, `set_node_context`, enter; it never calls `clear_node_context`), nested once, which is what happens when an evaluation runs an evaluation.

**To Reproduce**
Steps to reproduce the behavior:
1. Install azure-ai-evaluation from main (or 1.15.0+).
2. Run:
```python
import sys, io
from azure.ai.evaluation._legacy._common._logging import NodeLogManager

real_out = io.StringIO(); sys.stdout = real_out; sys.__stdout__ = real_out

outer = NodeLogManager(); outer.set_node_context("r1", "Flex", 1)
with outer:
    print("outer-before")
    inner = NodeLogManager(); inner.set_node_context("r2", "Flex", 1)
    with inner:
        print("inner-line")
    print("outer-after")
    r1 = outer.get_logs("r1")["stdout"]
    r2 = outer.get_logs("r2")["stdout"]

sys.stdout = sys.__stderr__
print("outer-after in r1:", "outer-after" in r1)
print("outer-after in r2:", "outer-after" in r2)
```
3. Observe:
```
outer-after in r1: False
outer-after in r2: True
```

**Expected behavior**
`outer-after` is recorded under `r1`, the run that wrote it (this is what the parent of 7d26b949 does):
```
outer-after in r1: True
outer-after in r2: False
```

**Screenshots**
n/a

**Additional context**
Impact: per-run logs for nested evaluations are misfiled; everything the outer line writes after a nested evaluation returns is recorded against the inner run. No exception, no failing test, the logs are just wrong.

Possible fix: when a manager reuses an existing writer, save the writer's current context in `__enter__` (or in `set_node_context`) and restore it in `__exit__`, so that leaving the inner context returns the shared writer to the outer run id. The `_resolve_prev_out` unwrapping added in #44844 already prevents the recursion on its own, so the writer reuse is not needed for the recursion fix.

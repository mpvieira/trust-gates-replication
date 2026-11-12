"""G4 claim check for PR #44844 (azure-ai-evaluation, nested NodeLogManager recursion guard).
Run from sdk/evaluation/azure-ai-evaluation with the EVAL profile, at the merge commit and again with _logging.py from
the parent. Mirrors the production caller (_batch_engine/_engine.py _exec_line_context: construct, set_node_context,
enter) nested once, and reports which run id the outer run's output after the inner run is attributed to."""
import sys, io
from azure.ai.evaluation._legacy._common._logging import NodeLogManager
real_out = io.StringIO(); sys.stdout = real_out; sys.__stdout__ = real_out
def report(m): sys.__stderr__.write(m + "\n")
# exact engine sequence (_exec_line_context): construct, set_node_context, then enter; nested for an inner evaluation
outer = NodeLogManager(); outer.set_node_context("r1", "Flex", 1)
with outer:
    print("outer-before")
    inner = NodeLogManager(); inner.set_node_context("r2", "Flex", 1)
    with inner:
        print("inner-line")
    print("outer-after")
    o, i = outer.get_logs("r1")["stdout"], outer.get_logs("r2")["stdout"]
    report(f"r1 log has outer-before={'outer-before' in o} outer-after={'outer-after' in o}")
    report(f"r2 log has inner-line={'inner-line' in i} outer-after={'outer-after' in i}   <- misattribution if True")
    report(f"real stdout got outer-after={'outer-after' in real_out.getvalue()}")

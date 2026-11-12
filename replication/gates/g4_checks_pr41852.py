"""G4 claim checks for PR #41852 (azure-ai-evaluation, lazy imports for optional converters).
Requires azure-ai-projects to be ABSENT. Run from sdk/evaluation/azure-ai-evaluation with the EVAL profile, at the merge
commit and again with the two __init__.py files from the parent. C1: import-time output; C2: attribute access;
S1: hasattr(); S2: from azure.ai.evaluation import *; S3: membership in __all__."""
import sys, io, importlib
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
import azure.ai.evaluation as ev
sys.stdout = old
print("C1 import-time output:", repr(buf.getvalue().strip()[:80]) or "''")
try:
    ev.AIAgentConverter; print("C2 attribute access -> resolved (dependency present)")
except ImportError as e: print("C2 attribute access -> ImportError:", str(e)[:60])
except AttributeError as e: print("C2 attribute access -> AttributeError")
try:
    print("S1 hasattr(module,'AIAgentConverter') ->", hasattr(ev, "AIAgentConverter"))
except Exception as e: print("S1 hasattr -> raises", type(e).__name__)
try:
    ns = {}; exec("from azure.ai.evaluation import *", ns); print("S2 'from azure.ai.evaluation import *' -> ok, AIAgentConverter in ns:", "AIAgentConverter" in ns)
except Exception as e: print("S2 'from azure.ai.evaluation import *' -> raises", type(e).__name__, str(e)[:50])
print("S3 'AIAgentConverter' in __all__:", "AIAgentConverter" in ev.__all__)

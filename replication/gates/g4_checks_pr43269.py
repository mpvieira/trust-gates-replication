"""G4 claim checks for PR #43269 (azure-cosmos, optional max_concurrency; create_database overloads).
Run from sdk/cosmos/azure-cosmos with the COSMOS profile, at the merge commit and again with the two changed files from
the parent. Reports the async helper's max_concurrency default (signature and effective value) and the create_database
response_hook call versus its docstring."""
import inspect, sys
from azure.cosmos.aio._read_items_helper_async import ReadItemsHelperAsync as H

def report(m): sys.__stderr__.write(m+"\n")
sig = inspect.signature(H.__init__).parameters["max_concurrency"]
report(f"async helper signature default: {sig.default}")
class FakeConn:  # minimal stand-in; helper only stores fields in __init__
    pass
try:
    h = H.__new__(H); H.__init__(h, **{k: None for k in inspect.signature(H.__init__).parameters if k not in ("self","max_concurrency")})
    report(f"async effective max_concurrency when not provided: {h.max_concurrency}")
except Exception as e:
    report(f"async helper init failed: {type(e).__name__}: {e}")
import azure.cosmos.cosmos_client as cc, re
src = inspect.getsource(cc.CosmosClient.create_database)
doc = re.search(r"response_hook: (Callable\[[^\n]*)", src); call = re.search(r"response_hook\((.*)\)", src)
report(f"create_database docstring hook type: {doc.group(1) if doc else None}")
report(f"create_database actual call:          response_hook({call.group(1) if call else None})")

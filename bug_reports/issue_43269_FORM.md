**Title:** [cosmos] Async read_items max_concurrency default changed from 10 to 5 in #43269, contrary to the PR description and without a changelog entry

- **Package Name**: azure-cosmos
- **Package Version**: main (changed in #43269, commit 7e59645b2, 2025-10-09; present in releases after that date)
- **Operating System**: macOS 15 (also checked on Ubuntu 24.04)
- **Python Version**: 3.12.4

**Describe the bug**
#43269 ("Make max_concurrency optional in read_items; fix create_database overloads") says in its description that the async path is unchanged and keeps `max_concurrency: int = 10` ("Async: Continues to use default of 10"). The merged code sets the async helper's default to 5:
```python
# azure/cosmos/aio/_read_items_helper_async.py after #43269
max_concurrency: Optional[int] = 5
...
self.max_concurrency = max_concurrency if max_concurrency and max_concurrency > 0 else 5
```
At the parent commit the default was 10. There is no CHANGELOG entry, and the async client docs still describe the previous behaviour. So either the code or the description/changelog is wrong.

**To Reproduce**
Steps to reproduce the behavior:
1. Install azure-cosmos from main.
2. Run:
```python
import inspect
from azure.cosmos.aio._read_items_helper_async import ReadItemsHelperAsync
print(inspect.signature(ReadItemsHelperAsync.__init__).parameters["max_concurrency"].default)
```
3. Observe `5` (at 7e59645b2 and on main); at the parent of 7e59645b2 the same command prints `10`.

**Expected behavior**
Either the async default stays at 10 (or becomes `None` with the same "executor chooses" semantics as the sync path), or the change to 5 is intended and gets a CHANGELOG entry, since it changes behaviour for existing async `read_items` callers who rely on the default.

**Screenshots**
n/a

**Additional context**
Also in the same PR: the new `create_database` docstring types `response_hook` as a two-argument callable, while the implementation calls it with one argument (`response_hook(self.client_connection.last_response_headers)`), consistent with the other hooks in `cosmos_client.py`. The docstring should match the call.

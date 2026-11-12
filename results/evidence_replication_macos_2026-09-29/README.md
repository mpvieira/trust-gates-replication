# Independent replication, 2026-09-29

Produced by the first author on a MacBook Pro (Apple M3 Max, macOS, python.org Python 3.12.4) from the shipped
`replication/` folder with all eight PRs enabled, using `python run_experiments.py setup` and `run`. The environment
is in `requirements-frozen.txt` (423 packages).

Result against the original records in `../evidence/` (produced by the assistant in a Linux container):

- `compare`: 24 of 24 automated records (G1, G2, G3 for eight PRs) identical, mutant by mutant.
- G4 outputs: all seven `pr<N>_G4_output.txt` files identical line for line (timestamp line excluded).

The three defects reported in the paper therefore reproduce on a second machine and operating system:
#44844 (outer-run output attributed to the inner run id after the PR), #41852 (`hasattr` and `import *` raise
`ImportError` after the PR), #43269 (async `max_concurrency` default 10 before, 5 after).

This replication also exercised the fix for the stale-bytecode bug in the mutation runner: the first attempt on this
machine, before the fix, had reported two string mutants with swapped results.

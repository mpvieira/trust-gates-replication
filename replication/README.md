# replication/ — code and configuration for the case study (no results)

```
experiments.yaml       repo, setup, environment profiles, gate scripts, extra gates; per PR: enabled flag, commit, package, suite, hypotheses, G4 check
run_experiments.py     config-driven runner: list | setup | run | summary | compare | clean
requirements.txt       Python dependencies (installed by `setup`)
EXTENDING.md           how to add PRs, repositories, environment profiles, claim checks and gates
gates/                 the four gates: common.py, g1_interface.py, g2_g3_mutation.py (G2+G3), g4_checks_pr<N>.py; example_extra_gate.py (template for a new gate)
```
The results obtained on 2026-09-28/29 are in `../results/` (evidence records and the write-up); `compare` diffs a new run against them.

## Quick start

Run in place from this folder; the clone and results go next to it unless you say otherwise. The clone is ~1 GB with many small files, so if this folder is in iCloud/Dropbox/OneDrive, pass `--work-dir` to keep the clone elsewhere (the config and gate scripts are always read from here).

```bash
cd replication
python3 -m venv venv && . venv/bin/activate          # Python 3.12
pip install -r requirements.txt                       # (setup also does this)
python run_experiments.py --help                     # commands; `run --help` for run options
python run_experiments.py list                       # configured PRs, hypotheses, where results go
python run_experiments.py setup                      # install requirements.txt + NLTK data, clone the repo (sparse, treeless), install packages
python run_experiments.py run                        # all PRs with enabled: true (as shipped: all eight, 15–25 min)
python run_experiments.py summary                    # results table
python run_experiments.py compare                    # this run's G1/G2/G3 records vs ../results/evidence, for the enabled PRs (or --prs)
```

With a separate work directory (recommended on cloud-synced folders):

```bash
python run_experiments.py -w ~/trustgates setup
python run_experiments.py -w ~/trustgates run
```
(or `export W=~/trustgates` once.)

New results are written to `<work dir>/evidence/` (i.e. `replication/evidence/` when running in place); the shipped records in `../results/evidence/` are never written to.

Select PRs either by editing `enabled:` in `experiments.yaml` or on the command line:

```bash
python run_experiments.py run --prs 44844,41852        # just these two
python run_experiments.py run --prs 46707 --gates G4   # one gate only (G2 and G3 always run together)
python run_experiments.py run --dry-run                # print the plan without running
python run_experiments.py -q run                       # quiet: only per-PR results, no step-by-step progress
```

By default `run` prints a timestamped line for every step (checkout, baseline suite, each gate, each G4 phase) and one line per mutant while G2/G3 runs, so a long mutation run is visibly progressing; `-q` reduces this to the per-PR result lines.

Outputs in `evidence/`: `pr<N>_G1.json`, `pr<N>_G2.json` (mutants and kill results), `pr<N>_G3.json` (own-suite sensitivity), `pr<N>_G2_log.txt` (per-mutant lines), and `pr<N>_G4_output.txt` (the claim-check output after the PR and before it, with the expected result and the hypotheses served quoted at the top). G4 outputs must be read by a person; the runner does not judge them. The shipped `results/evidence/pr<N>_G4.json` records are the original analyst's triage of those outputs.

## Cleaning up

```bash
python run_experiments.py clean results      # delete this run's records in evidence/ (asks for confirmation; -y to skip)
python run_experiments.py clean clone        # delete the ~1 GB clone; run `setup` again before the next `run`
python run_experiments.py clean all          # both, plus __pycache__
```
`clean` never touches `experiments.yaml`, `gates/`, or `../results/`. The virtualenv is not removed; delete `venv/` by hand for a completely fresh start.

## Trust hypotheses

Each PR's trust hypotheses are defined once in `experiments.yaml`: `hypotheses:` holds the independent rater's classification (H1..Hn, blind, from the description only) plus the standing H0, and `analyst_hypotheses:` holds requirements the analyst extracted that the rater did not (A1.., not blind). Each entry has an id, a category (`must-hold`, `may-fail`, `cannot-guarantee`), the statement, the gates that serve it, and its `source`. The runner copies the relevant subset into every gate record it writes (`linked_hypothesis_ids` and `hypotheses` fields of `pr<N>_G1/G2/G3.json`); the shipped records in `../results/evidence/` already carry them, as do the `pr<N>_G4.json` triage records. The G4 output file also lists the hypotheses the check serves at the top. `summary` shows the category counts per PR. The rater's form is `../results/classification_rater_RN.md`.

## Renaming or replacing a gate script

The `scripts:` section of `experiments.yaml` maps `G1` and `G2_G3` to file names under `gates/` (defaults `g1_interface.py`, `g2_g3_mutation.py`). Change the entry if you rename a script or drop in a different implementation with the same command-line interface (`<repo> <commit> <PR> <outdir> [pytest args]`). `common.py` is imported by both and is listed for reference only. G4 scripts are named per PR in each PR's `g4` block.

## Extending

Adding PRs, another repository, a new environment profile, a new claim check or a new gate: see `EXTENDING.md`. The config's `setup`, `environments`, `scripts` and `extra_gates` sections are the extension points; the runner has no project-specific code.

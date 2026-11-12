# Trust gates on agent-authored pull requests

Replication package for the case study in **"Engineering Trust When AI Writes Your Software"** (M. Vieira, A. Reddy, V. Devabhaktuni; *Computer*, under review).

The article proposes three constructs for validating AI-generated software artifacts: trust hypotheses, trust gates, and claim–evidence–limitation statements. The case study applies four trust gates to eight pull requests authored by the GitHub Copilot coding agent and merged into `Azure/azure-sdk-for-python` after continuous integration and human review. Three of the eight contained defects that had escaped CI and review; two were later confirmed by the project's maintainers ([PR #42313](https://github.com/Azure/azure-sdk-for-python/pull/42313); [issue #49273](https://github.com/Azure/azure-sdk-for-python/issues/49273) / [PR #49306](https://github.com/Azure/azure-sdk-for-python/pull/49306)), and the third is reported ([issue #49274](https://github.com/Azure/azure-sdk-for-python/issues/49274), open as of November 2026).

**Archived snapshot (citable):** each GitHub release of this repository is archived on Zenodo with a DOI; the DOI of the version the article cites is shown in the release notes and in the article's reference list. This repository is the living copy.

## What is here

```
replication/        code and configuration to re-run the study (no results)
  experiments.yaml  repository, setup, environment profiles, gate scripts; per PR: commit, package, test suite, hypotheses, claim check
  run_experiments.py config-driven runner: list | setup | run | summary | compare | clean
  gates/            G1 interface resolution, G2+G3 mutation on changed lines, G4 claim checks (one per PR), template for new gates
  requirements.txt, README.md, EXTENDING.md
results/            what was obtained
  evidence/         gate records for all eight PRs (G1, G2, G3, G4) and raw claim-check outputs
  evidence_replication_macos_2026-09-29/   independent re-run on a second machine: all records identical
  classification_rater_RN.md   the independent rater's blind classification of the requirements (the classification of record)
  classification_ai_pass*.md   two AI passes, kept for comparison only
  RESULTS.md        narrative write-up
supplement/         full worked cases for PR #41852 and PR #44844; one-page cards for the other six (LaTeX + PDF)
rater_package/      what the external rater received (instructions and form); reusable for a new rater
METHODOLOGY_AND_REPLICATION.md   what was done, why, per-PR results and triage, limitations
RUNBOOK.md          every command, in order, with expected outputs
```

## Reproduce

```bash
cd replication
python3 -m venv venv && . venv/bin/activate        # Python 3.12
pip install -r requirements.txt
python run_experiments.py setup                    # installs deps + NLTK data, clones the repo (sparse, ~1 GB), installs packages
python run_experiments.py run                      # all eight PRs, 15–25 minutes
python run_experiments.py compare                  # this run's records vs results/evidence (expect 24 identical)
```

The three defects are reproduced by the claim checks; read `replication/evidence/pr44844_G4_output.txt`, `pr41852_G4_output.txt` and `pr43269_G4_output.txt` against the `expect` line at the top of each. See `replication/README.md` for options and `RUNBOOK.md` for the manual version.

## Use of AI

The gate tooling, the claim checks and the triage in `results/` were produced with an AI assistant (Claude, Anthropic) under the first author's direction; the authors reviewed this work and reproduced all results on a separate machine. The requirement classification of record (`results/classification_rater_RN.md`) was performed by a human rater without AI assistance. See the article's Acknowledgments and `METHODOLOGY_AND_REPLICATION.md`.

## License

Code under MIT; documents, evidence and supplements under CC BY 4.0 (see `LICENSE`). Excerpts of code and pull-request text from `Azure/azure-sdk-for-python` are reproduced under its MIT License for the purpose of documenting the study.

## Citation

See `CITATION.cff`. Please cite the article and the archived DOI of this package.

# results/ — what was obtained on 2026-09-28/29

```
evidence/pr<N>_G1.json      G1 interface-resolution record            (8 PRs)
evidence/pr<N>_G2.json      G2 mutation record, with every mutant     (8 PRs)
evidence/pr<N>_G3.json      G3 own-suite sensitivity record           (8 PRs)
evidence/pr<N>_G4.json      G4 claim-check triage record              (7 PRs; #45366 has none)
evidence/pr<N>_G4_output.txt  raw before/after G4 output from the runner (7 PRs; #45366 has no G4)
classification_rater_RN.md  THE CLASSIFICATION OF RECORD: the independent rater's completed form (RN, blind, descriptions only, 2026-10-02): 15 requirements, 6 must-hold, 2 cannot-guarantee, 7 may-fail, none double-yes
classification_sheet.md     the internal blank sheet the rater form was derived from (superseded)
classification_ai_pass.md   the assistant's labels; NOT blind (written after diffs and gate results were seen); kept for the record
classification_ai_pass_2.md a second, independent AI pass on the rater form (blind, truncated descriptions); comparison only, not a human rating
RESULTS.md                  narrative write-up of the eight PRs and design notes
evidence_replication_macos_2026-09-29/   independent re-run by the first author on macOS: 24/24 records and 7/7 G4 outputs identical (see its README)
```
Produced by the code in `../replication/` with the configuration there, all eight PRs enabled, as in the shipped `experiments.yaml`. Classification and triage in these records are the original single analyst's; see `../METHODOLOGY_AND_REPLICATION.md` §9 for what must be redone by humans. `python ../replication/run_experiments.py compare` checks a new run's G1/G2/G3 records against this folder.

## The external rater

The rater (RN) received only `../rater_package/` (instructions and the eight descriptions) and returned `classification_rater_RN.md`. His labels are in `replication/experiments.yaml` as each PR's `hypotheses` (H1..Hn); requirements only the analyst extracted are kept separately as `analyst_hypotheses` (A1..), marked not blind. The shipped evidence records were re-linked accordingly on 2026-10-02 (`linked_hypothesis_ids`, and `hypotheses` with a `source` field: rater, analyst, or standing). The macOS replication folder keeps the links it was produced with.

What the comparison shows (stated in the paper's case-study section): the rater extracted none of the three requirements the confirmed defects violate (#41852 import surface, #43269 async default unchanged, #44844 per-run attribution); those are A1 in the respective PRs.

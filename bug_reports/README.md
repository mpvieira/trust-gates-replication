# Bug reports to file with Azure/azure-sdk-for-python

Two drafts, written as plain bug reports from a user who noticed a behaviour. They contain reproductions and commit references only; they do not mention the study, the paper, the framework or the tooling, and should be filed that way. File them as the author, after re-running the two checks locally (both already reproduced on 2026-09-29).

- `issue_44844_FORM.md` / `issue_43269_FORM.md`: the reports laid out in the repository's issue-template fields (package, version, OS, Python, describe / reproduce / expected / screenshots / additional context). Paste each into a new issue; the first line is the issue title.

#44844 is a functional defect (logs misfiled under the wrong run id) and the one that matters; #43269 is a description/code/changelog discrepancy, for which "intended, will fix the changelog" is a plausible answer.

Filed 2026-09-30 by the first author: issue #49274 (#44844 log attribution), issue #49273 (#43269 async default). Status: #49273 CLOSED as completed by PR #49306. The Cosmos maintainer (Simon Moreno) confirmed the 10→5 change was intended (4.14 betas → 4.14.0) but that the changelog entry was missed and "the Copilot PR description is also wrong"; the #43269 description was corrected and #49306 added the 4.14.0 release note and async docstring. The response_hook docstring mismatch was acknowledged and left out of scope. #49274 open, labelled Evaluation / Service Attention, unassigned, no maintainer response as of 2026-11-11.

After filing, record the issue numbers and dates here and in the paper's change log; whatever the state at submission, the paper reports it as "reported to the project as issue #N on <date>; <status>".

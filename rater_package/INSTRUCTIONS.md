# Instructions for classifying requirements in software changes

Thank you for helping with this. The task takes one to two hours. You need no access to any code, and you should not look any of these changes up online; everything you need is in `classification_form.md`.

## What you are being asked to do

You will read the descriptions of eight software changes (pull requests to a Python library). For each change, write down the requirements the change is meant to satisfy, then classify each requirement by answering two yes/no questions. The classification says how much evidence the team would owe before trusting that the requirement is met; it is **not** a judgment of how important the requirement is, and it is **not** a judgment of whether the change is good or bad.

You classify the requirements, not the change. Do not try to guess whether the change works.

## Step 1: extract the requirements

From the description alone, list the things the change must achieve or must not break. Write each as one short, testable sentence in your own words, for example:

- "Importing the package prints nothing when an optional dependency is missing."
- "Requests are retried at most five times."

Guidance:

- Include what the description says the change does.
- Also include what the change must obviously **not break** for the users of that functionality, if the description makes that clear. If the description says "changed the default from X to Y", a requirement is that Y is now the default; if it says "no behaviour change", that promise is a requirement.
- Do not invent requirements the description gives no basis for. If you are unsure whether something is a requirement, include it and say why in the reasoning column.
- Two to four requirements per change is typical; one or five is fine.
- Ignore statements about tests, changelogs and documentation ("added tests", "updated the changelog"); those are not requirements on the software's behaviour.

## Step 2: answer two questions for each requirement

**Q1.** If this requirement were violated, would that be a security, safety, data-integrity or compliance failure, or would it make the software unfit for its purpose for some of its users?

**Q2.** Does whether this requirement is met depend on something the description leaves open, such as: an ambiguity in what is being asked; a state the software cannot observe; being complete over an open-ended set of inputs; or behaviour for which there is no reference to compare against?

Answer both questions for every requirement, even when the first already settles the level.

## Step 3: assign the level

| Q1 | Q2 | Level |
|---|---|---|
| yes | either | **must-hold** |
| no | yes | **cannot-guarantee** |
| no | no | **may-fail** |

Meaning of the levels:

- **must-hold**: a violation is unacceptable; the strongest available evidence is owed before trusting it.
- **cannot-guarantee**: the property cannot be promised as stated; the limit should be stated explicitly and worked around.
- **may-fail**: occasional deviation is tolerable if it is detected and handled.

Note: a requirement can be must-hold *and* have Q2 answered yes. That combination is meaningful; it is why both answers are recorded.

## Step 4: reasoning

One line per requirement saying why you answered Q1 and Q2 as you did. This matters more than the level itself.

## Worked example (fictional change, not one of the eight)

Description: *"Fix: `parse_date` crashed on ISO strings with a timezone suffix. It now accepts `+HH:MM` suffixes. Behaviour for strings without a suffix is unchanged."*

| # | Requirement | Q1 | Q2 | Level | Reasoning |
|---|---|---|---|---|---|
| R1 | `parse_date` accepts ISO strings with a `+HH:MM` timezone suffix without crashing | yes | no | must-hold | a crash on valid input makes the function unfit; the input format is fully specified |
| R2 | Parsing of strings without a suffix behaves exactly as before | yes | no | must-hold | the description promises no change; a change would break existing users |
| R3 | The parsed result reflects the timezone offset correctly | yes | yes | must-hold | wrong times are wrong data (Q1); "correctly" is not defined in the description, e.g. whether the result is converted to UTC or kept as an offset-aware value (Q2) |

## Rules

- Work from the descriptions only. Do not search for the changes, the project, or the package online, and do not read any source code. If someone offers you more material, decline until you have finished.
- Do not discuss the changes with anyone else who may be classifying them.
- Do it in one or two sittings; do not revise earlier answers after seeing later changes unless you note that you did.
- If a description is too vague to yield any requirement, say so in the summary rather than inventing one.

## What to return

The completed `classification_form.md`, including the summary at the end, with your name or initials and the confirmation line filled in. Plain text or Markdown is fine; a photo of handwritten tables is fine too.

Please complete the form yourself. Do not delegate it to, or draft it with, an AI assistant: the purpose of the exercise is to obtain a human judgment, and a form produced with AI help cannot be used.

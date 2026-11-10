# Words that read as a promise: what was changed

Date: 2026-11-10. Phase 5, step 4. The words searched (whole words, case-insensitive) in the README, CONTRIBUTING, getting started, FAQ, tips, the security page, the user manual, the guide chapters and the window's texts: accurate, correct, verified, validated, qualified, certified, proven, reliable, safe, guaranteed, defend, trust. A test (`tests/unit/test_disclaimer.py`) keeps `guarantee`, `defend`, `reliable`, `validated`, `proven`, `you can trust`, `can rely on` and `accurate` out of those pages and out of the window; the negative uses in the disclaimer ("not certified or qualified") and in the support statement ("no guaranteed support") are exempt.

| Where | Before | After | Why |
|---|---|---|---|
| README, "It runs on your own computer" | "every result says which input and which equation it came from, and the same input always gives the same report" | "every result can be traced to the inputs and the equation it was worked out from, and the same project, user name and generation time give the same report files" | The equation is named but 53 of 57 have no citation; reproducibility needs the same user name and time (claims C-04, C-11). |
| README, Reports | "reproducible byte for byte" | "reproducible byte for byte for the same project, user name and generation time" | C-04 |
| README, Plain-language problems | "every message names the file and field, says what is wrong and what to change" | "every problem has a message that names the file and field where it can and a hint on what to change" | A test checks that every code has an entry, not that every message is actionable (C-27). |
| README, Status | "a full pre-release audit" | "a pre-release audit … made with the same AI tooling that wrote the code and is not an independent review" | C-22 |
| User guide, introduction | "Principles you can rely on" | "Principles of the tool" | A promise heading. |
| FAQ | "Can I trust the equations?" | "How well are the equations backed?" | The answer already says "treat such results as engineering estimates". |
| FAQ | "Is project data safe to share?" | "Who can see my project data?" | "Safe" is a promise; the answer is about who can see it. |
| FAQ | "lists the guarantees" | "lists what the program is built to do and not to do, and how to check each statement" | |
| Security page | "What the tool promises" | "What the program is built to do" | |
| Glossary, Status of an input | "how far to trust a number" | "how well a number is backed" | |
| CONTRIBUTING | "so they are safe to paste" | "so you can paste them" | |
| Guide, troubleshooting | "accurate to the last edges found, not exact" | "only as precise as the last edges found, not exact" | |

Kept on purpose: the honest limits (the README "Known limits", the FAQ answer on `SOURCE_MISSING`, the examples' "invented data"), the spacecraft *safe mode* and *safe* power mode (a term of the domain), "reliably" in the Eb/N0 definition (a physical statement), and the program's own warning "results that use it are not trustworthy" (a warning about a placeholder).

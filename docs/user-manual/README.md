# User manual

This is the task-by-task manual for System Budget Studio: each page answers a few "How do I…" questions. If you have not run the tool yet, do [Getting started](../getting-started.md) first.

| Page | Questions it answers |
|---|---|
| [Create a project](create-a-project.md) | How do I start a new project, from a sample or a blank one? What is in a project folder? How do I keep revisions? |
| [Describe the spacecraft](describe-the-spacecraft.md) | How do I add or remove a unit, its power modes and a spacecraft mode? How do I type units? |
| [Unit data in a spreadsheet](unit-tables.md) | How do I export the unit power modes to a table, fill it in, and import it back safely? |
| [Placeholders and sources](placeholders-and-sources.md) | What does *n/a* or INCOMPLETE mean? How do I fill in a margin or an efficiency properly? |
| [Trace a number](trace-a-number.md) | How do I see how a number was worked out? Where did an input come from? What does the tool assume that I did not type? Which model is used, and can I choose another? |
| [Power budget](power-budget.md) | How do I get the power per mode? How do I check the solar array and battery over an orbit? |
| [Mass budget](mass-budget.md) | How do I get mass, centre of gravity and inertia, per phase, against a limit? How do I add propellant or an oxidizer? |
| [Thermal budget](thermal-budget.md) | How do I get heat dissipation and unit temperatures for a hot and a cold case? |
| [Link budget](link-budget.md) | How do I add a link in the window? How do I get link margin at a chosen range, and data volume over the passes? |
| [Scenarios](scenarios.md) | How do I add an orbit and a scenario (up to 180 days, circular or elliptical) in the window? How do I add ground stations and imaging targets, and which mode runs when? How do I use SpaceMissionStudio data? |
| [Reports and exports](reports-and-exports.md) | Which files do I get, and how do I regenerate a report exactly? |
| [Compare](compare.md) | How do I see what changed between two revisions or two scenarios? |
| [Read and fix problems](read-and-fix-problems.md) | What do the messages mean, and how do I jump to the cause? |
| [Use the window](use-the-window.md) | Where is everything in the GUI? What are the focused view and the Start here card? What are the shortcuts? |
| [Command-line reference](command-line.md) | What does each `budget` command and option do? What are the exit codes? |

The same material, organised by topic, is in the **user guide** that ships inside the tool (*Help → User guide*, or `budget guide --out guide` for HTML and PDF). The guide chapters live in [`src/budget_core/guide/chapters/`](../../src/budget_core/guide/chapters/); the manual pages here link to them for the details.

Words you do not know are in the [glossary](../glossary.md). Something broken? [Troubleshooting](../troubleshooting.md).

Next: [Create a project](create-a-project.md).

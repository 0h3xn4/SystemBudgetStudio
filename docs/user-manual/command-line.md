# Command-line reference

This page lists every `budget` command with its options, the exit codes, and the environment variables that matter. `budget <command> --help` prints the same options.

**Contents:** [Commands](#commands) · [Common options](#common-options) · [Exit codes](#exit-codes) · [Standard output and standard error](#standard-output-and-standard-error) · [Environment variables](#environment-variables) · [Use in scripts and CI](#how-do-i-use-it-in-a-script-or-in-ci)

## Commands

| Command | What it does |
|---|---|
| `budget new FOLDER --bus-voltage-v VOLTS [--name TEXT] [--bus-name TEXT] [--spacecraft-name TEXT]` | Create a blank project: one bus, placeholder configuration, no units ([create a project](create-a-project.md#how-do-i-start-a-blank-project)); the folder must not exist |
| `budget validate PROJECT [--format text\|json] [--strict]` | Check a project folder and list problems |
| `budget run PROJECT [--budget power\|mass\|thermal\|link\|all] [--report …] [--out DIR]` | Compute the static budgets and write reports (default: all budgets, all report kinds) |
| `budget scenario PROJECT [--scenario ID] [--out DIR]` | Compute a scenario's eclipses, passes and mode timeline |
| `budget power-timeline PROJECT [--scenario ID] [--case bol\|eol\|both] [--load-basis nominal\|margined] [--phase NAME] [--series-every N] [--no-plots] [--report …] [--out DIR]` | Time-domain power budget of a scenario |
| `budget link-passes PROJECT [--scenario ID] [--no-plots] [--report …] [--out DIR]` | Link margin, selected data rate and data volume over every pass |
| `budget compare PROJECT [OTHER] [--scenario ID] [--scenario-a ID] [--scenario-b ID] [--budget …] [--report …] [--max-rows N] [--out DIR]` | Compare two revisions or two scenarios |
| `budget units-export PROJECT [--out FILE.csv\|.xlsx]` | Write the unit power modes as a table to fill in outside the tool ([unit tables](unit-tables.md)) |
| `budget units-import PROJECT TABLE [--apply]` | Show the changes a filled-in table would make; with `--apply` write them into the unit files |
| `budget guide --out DIR [--format html\|pdf\|all] [--project PROJECT]` | Write the user guide (offline HTML and PDF) |
| `budget problems [CODE] [--markdown]` | Explain a problem code: the rule, why it matters, what to do (all codes are listed without `CODE`; `--markdown` writes the page [PROBLEMS.md](../PROBLEMS.md)) |
| `budget explain PROJECT [TABLE] [--row KEY ...] [--column HEADER] [--format text\|json] [--scenario ID] [--load-basis nominal\|margined] [--phase NAME]` | Show how one number of a budget table was obtained: the equation, the inputs with units and where they come from, every step (static power, mass, thermal and link tables the power timeline tables `timeline:...` and the link pass tables `linkpass:...`, for which `--scenario`, `--load-basis` and `--phase` choose what is solved; more to come). Without a table it lists the tables; with only the table, its columns and rows |
| `budget verify EXPORT PROJECT` | Say whether a project is the one an export was made from (input digest; exit 0 match, 1 different or not checkable, 2 export unreadable) |
| `budget self-test` | Check that this installation can compute and render a budget |
| `budget export-schemas DIR` | Write the JSON Schema of every file kind |
| `budget export-examples DIR [--force]` | Write the four example projects; an example folder that exists is never touched unless you add `--force` |
| `budget --version` | Print the version |

`--report` can be repeated and takes `xlsx`, `pdf`, `docx`, `json`, `csv` or `all`. `--scenario` is optional when the project has only one; with none or several the command says so and lists the ids. `--series-every N` takes 1 or more and `--max-rows N` 0 or more. Options cannot be abbreviated (`--str` is an error, not `--strict`). `budget` with no command prints the command list and exits with code 2.

## Common options

| Option | Meaning |
|---|---|
| `--out DIR` | Output folder (default: `<project>/results`) |
| `--user NAME` | User name for the provenance block (default: `BUDGET_USER`, then your login name). Accepted by `run`, `scenario`, `power-timeline`, `link-passes` and `compare` |
| `--date ISO8601` | Generation time, years 1950 to 2100 (default: `SOURCE_DATE_EPOCH`, then the clock); with `--user` it makes a report reproducible. Accepted by the same commands as `--user` |
| `--strict` | Treat warnings as failures (exit code 1). Accepted by `validate`, `run`, `power-timeline` and `link-passes` |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Finished; no error-level problem (and no warning with `--strict`) |
| 1 | An error-level problem or finding, a file that could not be written, or an unexpected error (one plain line, never a traceback) |
| 2 | The command was called wrongly (no command, unknown or abbreviated option, a value not allowed, several scenarios and no `--scenario`, `compare` without a second side, a `SOURCE_DATE_EPOCH` that is not a whole number of seconds) |
| 130 | Interrupted with Ctrl+C |

Note that finding a *result* problem (a limit exceeded) is exit code 1 even though every file was written.

## Standard output and standard error

| Stream | What goes there |
|---|---|
| Standard output | What the command produced: `Wrote ...` lines, summaries, warnings that need a person, the `INCOMPLETE` banner, the one-line summary (`N errors, M warnings.`), the table of a unit import, `validate`'s list of problems, `validate --format json` |
| Standard error | Why a command could not do its work: the error problems that make a run fail, `N errors; nothing was written.`, a project that cannot be loaded, a command called wrongly, a file that could not be written, `Internal error (...)`, failed self-test checks |

`budget validate` is the one exception: its list of problems is its result, so errors and warnings both go to standard output (`budget validate project > problems.txt` keeps them). The exit codes did not change. Both streams are in the same order on a terminal and with `2>&1`.

## Environment variables

| Variable | Used for |
|---|---|
| `BUDGET_USER` | The user name in the provenance block |
| `SOURCE_DATE_EPOCH` | The generation time (a whole number of seconds since 1970). A value that is set but not usable (empty, text, negative, out of range) is an error, not ignored |
| `QT_QPA_PLATFORM=offscreen` | Run the window without a screen (tests, `system-budget-studio --smoke`) |

## How do I use it in a script or in CI?

```bash
budget validate project --strict            # fail on any warning
budget run project --budget power --report csv --report json --out out
budget power-timeline project --out out || echo "violations found"   # exit code 1
```

`budget validate --format json` prints the problems as JSON for other tools. In a script, read the results from standard output and the reasons for a failure from standard error: `budget run project --out out > log.txt 2> errors.txt`. The tool needs no network and writes only into the output folder you name. The [offline test](../developer/README.md#the-offline-test) keeps that true.

Next: [Tips](../tips.md) · [Troubleshooting](../troubleshooting.md).

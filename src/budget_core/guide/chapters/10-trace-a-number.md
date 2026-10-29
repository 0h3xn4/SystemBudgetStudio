# Tracing a number

Every result can be followed back to the equation that made it, the inputs it used and the file each input came from. This chapter shows how, and how to see what the tool assumes besides what you typed.

## How a number was worked out

Select a value in a table (a power, a mass, a temperature, a link margin, a value of the power timeline or of the link passes) and press **Ctrl+Shift+I**, or right-click it and choose **Explain this value**. The **Explain** panel opens on the right with the equation, the inputs (value, unit, the file and field it was read from, its source and its status when it is not `sourced`) and the steps in between. The first time for the power timeline or the passes, the panel says it is preparing the explanation; the next values are immediate.

On the command line, `budget explain <project>` lists the tables that can be explained, and `budget explain <project> <table> --row <key> --column <header>` explains one number. An equation with no citation yet says `source: none yet (SOURCE_MISSING)`.

## Where an input came from

A number from a data sheet carries its `source` in its file. A plain input (a mass, a power, an orbit element) can say where it came from with a `provenance:` entry: a source, a note and a status (`sourced`, `estimate`, `illustrative` or `tbd`). In the window, select the number in **Model > Units** or **Power modes**: the Inspector (turn **View > Focused view** off to see it) has a *Source* field; a change is one undo step. On the command line, `budget source <project>` counts the inputs by status, and `budget source <project> <file> <path> --source "..."` records a source in place, keeping the comments of the file. The example projects are marked `illustrative`, and a report made from them says how many inputs are.

## Everything the tool assumes

The **Assumptions** page (**View > Show the assumptions**, Ctrl+Shift+A) lists, in one filterable list: your sourced numbers with their status and the file and field to edit; the settings, tolerances, limits and constants of the tool, with their value, why they are what they are and where they act; the model choices of each scenario; and the defaults the forms write. A double-click on a row that names a file opens it at the field. On the command line: `budget assumptions <project>` and `budget settings`. The settings are shown, not yet changeable.

## The models

`budget choices` lists every modelling choice of the tool and explains one. Three are made in the scenario file and have a drop-down in **Model > Scenario**, with the source of every value as its tooltip:

- **Shadow geometry**: cylindrical (a point is lit or dark) or conical (umbra and penumbra);
- **Earth constants**: WGS-84 (the default) or WGS-72, for an orbit given as elements and the Earth sphere of the shadow. A TLE is always propagated on WGS-72;
- **Irradiance on the array**: constant (the default) or seasonal, which reads the configured irradiance as the value at 1 AU and scales it by the inverse square of the Earth-Sun distance on the scenario date (about 3.4 % more in early January, 3.3 % less in early July).

A choice is one undo step. Choosing a model that older versions do not know also lists `model_choices` under `requires:` in `project.yaml`, so an older version refuses the project instead of ignoring the choice. The load basis (nominal or margined) is an option of a run. Every other model (SGP4 on mean elements, the low-precision Sun, the thermal model and others) is fixed and listed with the reason.

## Is this result from my project?

Every report names the tool and library versions, the project and revision, the scenario with its run parameters (including the Earth model and the irradiance model), and a digest of the inputs. `budget verify <export.json> <project>` compares that digest with the project and names the files that differ. After an upgrade to 2.0.0 the digest of every project is a new value, because the schema version of each file is part of it; `verify` of an older export then reports DIFFERENT although the inputs are the same.

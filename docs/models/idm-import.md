# Reading IDM-CIC models

Reads models from IDM-CIC (© CNES). IDM-CIC is software of the French space agency CNES for the early design of satellites. System Budget Studio is an independent tool: it uses no CNES software, library or data, it needs none installed, and CNES does not endorse or support it. This page describes in our own words what the tool reads from a model file and how.

**Status (decision D-237).** The reader is the first of five steps. It turns a model file into a typed model in memory and reports what it finds. It does not yet write anything into a project: the command `budget import idm`, the mapping onto units, modes and the mass budget, re-import, geometry and the window entry follow in later steps.

**Supported format.** The reader was written for version **3.4.0.19** of the published model description. Files saved by versions 3.4.x are read without a message; a file of a newer minor version (for example 3.5) is read with the warning `IDM_VERSION_NEWER`, and objects it does not know are left out and counted, never guessed.

## The file

A model file (`.idm`) is a ZIP archive. The tool reads **one entry only**, `model.xml` at the root of the archive, and never extracts anything: pictures, 3D files and the data of other programs in the archive are ignored. The XML is UTF-8; the program writes a byte order mark and line endings of CR LF, which the reader accepts. A document type declaration or entity definition is refused (`IDM_XML_UNSAFE`): a model has no use for one. The sizes are bounded ([settings](settings.md#reading-idm-cic-models)): the file, the unpacked model, the number of entries, the nesting and the number of elements, so that a wrong or hostile file cannot use all the memory.

The **revision** of a model is the SHA-256 of the bytes of `model.xml`: the same bytes always give the same revision.

## Value formats

A number uses a comma as the decimal separator and may have an exponent (`15,54`, `0,1554E3`, `1554E-2`); a dot, a thousands separator, `nan` and `inf` are refused. A date is `dd/mm/yyyy hh:mm:ss`. A yes/no value is `True` or `False`. A value in another format is the error `IDM_VALUE_INVALID` and the model is not used: the problem names the field and the object, never the value. Formulas that the program keeps for some properties are **never evaluated**: the stored value is read; a formula that the file marks as not valid is listed so that the stored value can be treated with care.

## Objects and identity

Every object has a `fullId`, a path-like identifier (`el.2_ss.PWR_eq.1` is equipment 1 of subsystem PWR in element 2). The tool identifies objects by `fullId` and uses names for display only, because a name can be changed. A reference to an object is a node with a `ref` attribute holding the other object's `fullId`; a reference that points nowhere leaves the object out with the warning `IDM_REF_UNRESOLVED`.

What is read, with the units the tool uses (lengths in metres, masses in kilograms, power in watts, temperatures in degrees Celsius as the file gives them, margins and fillings as fractions):

| Object | Read |
|---|---|
| System | project name, comment, version text, last change, propellant mass margin |
| Subsystem, element | id, name; the element's mass target, mass margin, power margin, forced propellant mass and margin |
| Related subsystem (an element's use of a subsystem) | forced mass and forced mass margin, if given |
| Equipment definition | name, optional flag and its default, enabled state per configuration, maturity level and mass margin, power margin, origin of the mass properties (from geometry or entered), entered mass, centre of mass and inertia, the four temperature limits, power modes (power and dissipation), shapes (mass definition and the numeric parameters of the 3D object) |
| Assembly | name (its content is read through its placed copies) |
| Physical occurrence | see below; its power mappings per element mode and per system mode, its thermal module, its tank contents and fillings |
| Element mode, system mode, thermal module, configuration | ids, names, links; a system mode's duty cycle |
| Additional properties | the definitions are listed; none is mapped |

Scenarios, trajectories, attitude files, materials, layers, roles, notes and external references are ignored.

## Which occurrences are physical

An equipment is a definition; what is in the satellite is its **occurrences**. An assembly is a group of equipment: its definition holds instances of other units, and every placed copy of the assembly holds a copy of those instances. Only the occurrences reachable from the instances **placed in an element**, walking down through placed assemblies, are physical. The instances inside an assembly definition are templates and are not counted (decision D-238). The same equipment placed twice is two occurrences, and each counts in the budgets.

## Problems

The codes of this step are `IDM_FILE_UNREADABLE`, `IDM_ARCHIVE_LIMIT`, `IDM_MODEL_MISSING`, `IDM_XML_INVALID`, `IDM_XML_UNSAFE`, `IDM_STRUCTURE_INVALID`, `IDM_VALUE_INVALID`, `IDM_VERSION_NEWER`, `IDM_REF_UNRESOLVED` and `IDM_UNIT_KIND_UNKNOWN`; see [the problem list](../PROBLEMS.md#idm-cic-models-import).

## What is not done

Nothing is estimated. A value the file does not give stays absent. Geometry is not evaluated in this step (the shape parameters are read for the later step). The tool never writes to the model file or to IDM-CIC.

Next: [Models](README.md) · [Docs index](../README.md).
